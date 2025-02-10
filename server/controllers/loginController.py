from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from server.models.garageModel import Garage
from server.models.remorqueurModel import Remorqueur
from server.settings import AsyncSession
from server.controllers.authController import (
    ACCESS_TOKEN_EXPIRE_HOURS,
    EASTERN_TZ,
    create_jwt_token,
    verify_password
)
from server.models.authModel import (
    LoginRequest,
    LoginResponse,
    PermissionResponse,
    RoleResponse,
    User,
    Role,
    UserDict
)

async def process_login(db: AsyncSession, login_data: LoginRequest) -> LoginResponse:
    """
    Process user login request and return appropriate response with user details.
    Handles three types of users: regular users, garage users, and remorqueur users.
    """
    # Initialize user and garage_name variables
    user = None
    garage_name = None

    # Try to find user in each possible table, with proper relationship loading
    queries = [
        # Try regular user first
        (select(User)
         .options(joinedload(User.role).joinedload(Role.permissions))
         .where(User.username == login_data.username)),
        
        # Try garage user
        (select(Garage)
         .options(joinedload(Garage.role).joinedload(Role.permissions))
         .where(Garage.username == login_data.username)),
        
        # Try remorqueur user
        (select(Remorqueur)
         .options(
             joinedload(Remorqueur.role).joinedload(Role.permissions),
             joinedload(Remorqueur.garage)
         )
         .where(Remorqueur.username == login_data.username))
    ]

    # Execute queries in sequence until we find the user
    for query in queries:
        result = await db.execute(query)
        user = result.unique().scalar_one_or_none()
        if user:
            break

    # If no user found in any table, raise authentication error
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Verify the provided password
    if not verify_password(user.password, login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Determine garage_name based on user type
    if isinstance(user, Garage):
        garage_name = user.name  # Garage users use their own name
    elif isinstance(user, Remorqueur):
        garage_name = user.garage.name  # Remorqueur users use their garage's name
    # Regular users don't have a garage_name

    # Create JWT token and set expiration
    access_token = create_jwt_token(user)
    expiration = datetime.now(EASTERN_TZ) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    # Create user dictionary with garage_name included
    user_dict = UserDict(
        id=user.id,
        username=user.username,
        is_active=user.is_active,
        garage_name=garage_name  # Include garage_name in user object
    )

    # Create role response with permissions
    role_response = RoleResponse(
        id=user.role.id,
        name=user.role.name,
        permissions=[
            PermissionResponse(id=perm.id, name=perm.name)
            for perm in user.role.permissions
        ]
    )

    # Construct and return the complete login response
    response = LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_dict,
        role=role_response,
        expires_at=expiration,
        garage_name=garage_name  # Also include at top level for compatibility
    )

    return response
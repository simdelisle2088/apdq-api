from fastapi import HTTPException, Request, status
from sqlalchemy import select
from server.settings import (
    AsyncSession,
)
from server.controllers.authController import  argon2_strong_hash, authenticate_user, verify_password
from server.models.authModel import  CreateUserRequest, LoginRequest, UpdateUserPassword, User, Role
from sqlalchemy.orm import joinedload

async def create_user(db: AsyncSession, user_data: CreateUserRequest) -> User:
    # Check if username already exists
    stmt = select(User).where(User.username == user_data.username)
    result = await db.execute(stmt)
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Get the role by name with permissions
    stmt = select(Role).options(
        joinedload(Role.permissions)
    ).where(Role.name == user_data.role_name)
    result = await db.execute(stmt)
    role = result.unique().scalar_one_or_none()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{user_data.role_name}' does not exist"
        )

    # Hash the password
    hashed_password = argon2_strong_hash(user_data.password)

    # Create the new user
    new_user = User(
        username=user_data.username,
        password=hashed_password,
        role_id=role.id,
        is_active=False  # Set default value explicitly
    )

    # Add and commit the new user to the database
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user

async def update_admin(
    request: Request,
    update_data: UpdateUserPassword,
    db: AsyncSession
):
    # Authenticate the requesting admin user
    token = request.headers.get("X-Deliver-Auth")
    current_user = await authenticate_user(token, db)
    
    # Verify the current user has appropriate privileges
    if not current_user.role or current_user.role.name not in ["superadmin", "apdq"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin and apdq users can perform this action."
        )

    # Find the user to update
    result = await db.execute(
        select(User).where(User.username == update_data.username)
    )
    user_to_update = result.scalar_one_or_none()
    
    if not user_to_update:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with username '{update_data.username}' not found."
        )

    # Add role-based access control
    if current_user.role.name == "apdq":
        # APDQ users can only update their own information
        if current_user.id != user_to_update.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="APDQ users can only update their own information."
            )
    # superadmin can update any user's information, so no additional checks needed

    # If updating username
    if update_data.new_username:
        # Check if the new username is already taken
        username_exists = await db.execute(
            select(User).where(User.username == update_data.new_username)
        )
        if username_exists.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already in use. Please choose another one."
            )
        user_to_update.username = update_data.new_username

    # If updating password
    if update_data.password:
        # Add more password validation rules as needed
        user_to_update.password = argon2_strong_hash(update_data.password)

    # Commit changes
    try:
        await db.commit()
        await db.refresh(user_to_update)
    except HTTPException as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user information."
        )

    # Return success response with user information
    return {
        "message": "User updated successfully",
        "username": user_to_update.username,
        "role": user_to_update.role.name
    }
import datetime
from typing import Union
from argon2 import PasswordHasher, Type, exceptions as argon2_exceptions 
from fastapi.security import OAuth2PasswordBearer
import jwt
from datetime import datetime, timedelta
import pytz
from sqlalchemy import select
from fastapi import HTTPException
from sqlalchemy.orm import joinedload
from server.models.authModel import Role, User
from server.models.garageModel import Garage
from server.models.remorqueurModel import Remorqueur
from server.settings import (
    AsyncSession,
    JWE_SECRET_KEY,
    ARGON2_SECRET_KEY
)
 
SECRET_KEY = JWE_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
EASTERN_TZ = pytz.timezone("America/New_York")



def argon2_strong_hash(password: str) -> str:
    # Create the peppered password
    peppered_password = f"{password}{ARGON2_SECRET_KEY}"

    # Create a PasswordHasher with custom parameters
    hasher = PasswordHasher(
        time_cost=1,
        memory_cost=65536,
        parallelism=1,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    )

    # Hash the password
    hash = hasher.hash(peppered_password)
    return hash

def create_jwt_token(user: Union[User, Garage, Remorqueur]) -> str:
    expiration = datetime.now(EASTERN_TZ) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    
    # Determine the role based on user type
    if isinstance(user, Garage):
        role = "garage"
    elif isinstance(user, Remorqueur):
        role = "remorqueur"
    else:
        role = user.role.name
        
    to_encode = {
        "sub": str(user.id),
        "exp": expiration,
        "role": role,
        "permissions": [perm.name for perm in user.role.permissions]
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def authenticate_user(token: str, db: AsyncSession) -> Union[User, Garage, Remorqueur]:
    """Authenticate user from token"""
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        
        if user_id is None or role is None:
            raise credentials_exception
            
    except jwt.PyJWTError:
        raise credentials_exception

    # Try to find the user based on role
    try:
        if role == "garage":
            result = await db.execute(
                select(Garage)
                .options(joinedload(Garage.role).joinedload(Role.permissions))
                .where(Garage.id == int(user_id))
            )
            user = result.unique().scalar_one_or_none()
        elif role == "remorqueur":
            result = await db.execute(
                select(Remorqueur)
                .options(joinedload(Remorqueur.role).joinedload(Role.permissions))
                .where(Remorqueur.id == int(user_id))
            )
            user = result.unique().scalar_one_or_none()
        else:
            result = await db.execute(
                select(User)
                .options(joinedload(User.role).joinedload(Role.permissions))
                .where(User.id == int(user_id))
            )
            user = result.unique().scalar_one_or_none()
        
        if user is None:
            raise credentials_exception
            
        return user
        
    except Exception:
        raise credentials_exception

async def has_permission(user: Union[User, Garage, Remorqueur], permission: str, db: AsyncSession):
    """Check if user has required permission"""
    user_permissions = [perm.name for perm in user.role.permissions]
    if permission not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )
    return True
    
def verify_password(stored_password: str, provided_password: str) -> bool:
    peppered_password = f"{provided_password}{ARGON2_SECRET_KEY}"
    try:
        hasher = PasswordHasher()
        hasher.verify(stored_password, peppered_password)
        return True
    except argon2_exceptions.VerifyMismatchError:
        return False

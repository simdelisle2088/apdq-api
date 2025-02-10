from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role_name: str

class UserCreate(BaseModel):
    username: str
    password: str
    role_name: str  
    
class PermissionResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)

# Role response model
class RoleResponse(BaseModel):
    id: int
    name: str
    permissions: Optional[List[PermissionResponse]] = [] 

    model_config = ConfigDict(from_attributes=True)
    
# User response model
class UserResponse(BaseModel):
    id: int
    username: str
    role: RoleResponse
    is_active: bool

class LoginRequest(BaseModel):
    username: str
    password: str

class UserDict(BaseModel):
    id: int
    username: str
    is_active: bool
    garage_name: Optional[str] = None  
    
    model_config = ConfigDict(from_attributes=True)

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserDict
    role: RoleResponse
    expires_at: datetime
    garage_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class AllUsers(BaseModel):
    id: int
    username: str

class UpdateUserRequest(BaseModel):
    username: str
    role_name: str

class UpdateUserPassword(BaseModel):
    username: str  
    new_username: Optional[str] = None
    password: Optional[str] = None

# Many-to-Many relationship between Role and Permission
role_permission = Table(
    'role_permission', Base.metadata,
    Column('role_id', ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', ForeignKey('permissions.id'), primary_key=True)
)

class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    users = relationship('User', back_populates='role') 
    permissions = relationship('Permission', secondary=role_permission, back_populates='roles')

class Permission(Base):
    __tablename__ = 'permissions'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    roles = relationship('Role', secondary=role_permission, back_populates='permissions')

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    role = relationship('Role', back_populates='users')
    is_active = Column(Boolean, default=False, nullable=False)

garage_message_recipients = Table(
    'garage_message_recipients',
    Base.metadata,
    Column('message_id', Integer, ForeignKey('garage_messages.id'), primary_key=True),
    Column('remorqueur_id', Integer, ForeignKey('remorqueurs.id'), primary_key=True)
)
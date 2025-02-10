from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from pydantic import BaseModel
from server.models.authModel import Base

class GarageBase(BaseModel):
    name: str
    username: str
    password: str
    role_id: int
    is_active: bool = True
    created_by_id: int
    stripe_customer_id: Optional[str] = None

class CreateGarageRequest(BaseModel):
    name: str
    email: str
    username: str
    password: str
    role_name: str

class UpdateGarageRequest(BaseModel):
    garage_name: str
    username: str | None = None
    password: str | None = None

class GarageRequest(BaseModel):
    username: Optional[str] = None
    stripe_customer_id: Optional[str] = None

class Garage(Base):
    __tablename__ = 'garages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False) 
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    payment_status = Column(String(50))
    payment_session_id = Column(String(255))
    stripe_customer_id = Column(String(255), nullable=True) 
  
    role = relationship('Role', backref='garages')
    created_by = relationship('User')
    remorqueurs = relationship('Remorqueur', back_populates='garage')

    admin_messages = relationship('AdminMessage', secondary='admin_message_recipients', back_populates='garages')
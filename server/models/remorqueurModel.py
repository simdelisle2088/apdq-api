# server/models/remorqueurModel.py
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from pydantic import BaseModel
from server.models.authModel import Base

class RemorqueurBase(BaseModel):
    name: str
    tel: str
    username: str
    password: str
    role_id: int
    garage_id: int
    is_active: bool = True

class CreateRemorqueurRequest(BaseModel):
    garage_name: str
    name: str
    tel: str
    username: str
    password: str
    role_name: str

class UpdateRemorqueurRequest(BaseModel):
    name: Optional[str] = None
    tel: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class Remorqueur(Base):
    __tablename__ = 'remorqueurs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    tel = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    garage_id = Column(Integer, ForeignKey('garages.id'), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    role = relationship('Role', backref='remorqueurs')
    garage = relationship('Garage', back_populates='remorqueurs')

    garage_messages = relationship('GarageMessage', secondary='garage_message_recipients', back_populates='remorqueurs')



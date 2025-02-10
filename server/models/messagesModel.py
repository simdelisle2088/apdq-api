from datetime import datetime
from typing import List, Optional
import pytz
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship
from pydantic import BaseModel
from server.models.authModel import Base

eastern = pytz.timezone('America/New_York')
def get_eastern_time():
    return datetime.now(eastern)

class AdminMessageRequest(BaseModel):
    garage_id: int

class GarageMessageRequest(BaseModel):
    remorqueur_id: int  

class DeleteMessageRequest(BaseModel):
    message_id: int
    
class CreateMessageRequest(BaseModel):
    receiver_id: int
    title: str
    content: str

class MessageBase(BaseModel):
    title: str
    content: str

class AdminMessageCreate(BaseModel):
    title: str
    content: str
    to_all: bool
    admin_id: int
    garage_ids: Optional[List[int]] = None

class GarageMessageCreate(BaseModel):
    title: str
    content: str
    to_all: bool
    garage_id: int  
    remorqueur_ids: Optional[List[int]] = None

class AdminMessageResponse(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime
    to_all: bool
    garage_ids: Optional[List[int]] = None
    is_read: bool = False


class GarageMessageResponse(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime
    to_all: bool
    remorqueur_ids: Optional[List[int]] = None
    is_read: bool = False

class DeleteMultipleMessagesRequest(BaseModel):
    message_ids: List[int]

class GarageMessage(Base):
    __tablename__ = 'garage_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=get_eastern_time)
    garage_id = Column(Integer, ForeignKey('garages.id'), nullable=False) 
    to_all = Column(Boolean, default=False, nullable=False)

    remorqueurs = relationship('Remorqueur', secondary='garage_message_recipients', back_populates='garage_messages')


class AdminMessage(Base):
    __tablename__ = 'admin_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=get_eastern_time)
    admin_id = Column(Integer, ForeignKey('users.id'), nullable=False)  
    to_all = Column(Boolean, default=False, nullable=False)  

    garages = relationship('Garage', secondary='admin_message_recipients', back_populates='admin_messages')
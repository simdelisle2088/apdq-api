# server/models/remorqueurModel.py
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String
from server.models.authModel import Base

class FAQCreate(BaseModel):
    question: str
    answer: str
    language: str

class FAQResponse(BaseModel):
    id: int
    question: str
    answer: str
    language: str
    
class DeleteResponse(BaseModel):
    message: str
    faq_id: int

class faq(Base):
    __tablename__ = 'faq'
    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False) 
    language = Column(String, nullable=False)
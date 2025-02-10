# server/models/response_models.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from server.models.authModel import RoleResponse

class PermissionResponse(BaseModel):
    id: int
    name: str
    
    model_config = ConfigDict(from_attributes=True)

class RoleResponse(BaseModel):
    id: int
    name: str
    permissions: List[PermissionResponse] = []
    
    model_config = ConfigDict(from_attributes=True)
    
class GarageBaseResponse(BaseModel):
    id: int
    name: str
    username: str
    role_id: int
    is_active: bool
    created_by_id: int
    
    model_config = ConfigDict(from_attributes=True)

class RemorqueurBaseResponse(BaseModel):
    id: int
    name: str
    username: str
    role_id: int
    garage_id: int
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)
    
class RemorqueurResponse(BaseModel):
    id: int
    name: str
    tel: str
    username: str
    role: RoleResponse
    garage_name: str
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)

class GarageResponse(BaseModel):
    id: int
    name: str
    email: str
    username: str
    role_id: int
    is_active: bool
    stripe_customer_id: Optional[str]
    payment_status: Optional[str]
    role: dict
    
    class Config:
        from_attributes = True

# Nested response models for relationship handling
class GarageWithRemorqueursResponse(GarageBaseResponse):
    remorqueurs: List[RemorqueurBaseResponse] = []

class RemorqueurWithGarageResponse(RemorqueurBaseResponse):
    garage: Optional[GarageBaseResponse] = None


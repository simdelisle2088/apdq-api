from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, Text, text
from sqlalchemy.orm import relationship
from server.models.authModel import Base



class VehicleBase(BaseModel):
    """Base Pydantic model for vehicle data validation"""
    brand: str
    model: str
    year_from: int
    year_to: Optional[int] = None
    delay_time_neutral: Optional[int] = None
    delay_time_deactivation: Optional[int] = None

class VehicleCreate(VehicleBase):
    """Model for creating new vehicles - inherits all fields from VehicleBase"""
    pass

class FileBase(BaseModel):
    """Base model for file metadata"""
    file_name: str
    file_path: str
    file_size: int
    upload_date: datetime

    class Config:
        from_attributes = True

class NeutralPDFResponse(FileBase):
    """Response model for neutral procedure PDF files"""
    id: int
    vehicle_id: int

class DeactivationPDFResponse(FileBase):
    """Response model for deactivation procedure PDF files"""
    id: int
    vehicle_id: int

class ImageResponse(FileBase):
    """Response model for image files"""
    id: int
    vehicle_id: int

class VehicleResponse(VehicleBase):
    """Complete vehicle response including related files"""
    id: int
    created_at: datetime
    updated_at: datetime
    neutral_pdfs: List[NeutralPDFResponse] = []
    deactivation_pdfs: List[DeactivationPDFResponse] = []
    images: List[ImageResponse] = []

    class Config:
        from_attributes = True
        populate_by_name = True

    @classmethod
    def from_orm(cls, obj):
        # Ensure relationships are empty lists if None
        if not hasattr(obj, 'neutral_pdfs'):
            obj.neutral_pdfs = []
        if not hasattr(obj, 'deactivation_pdfs'):
            obj.deactivation_pdfs = []
        if not hasattr(obj, 'images'):
            obj.images = []
        return super().from_orm(obj)

class ErrorResponse(BaseModel):
    """
    Standard error response model for all endpoints
    """
    detail: str = Field(..., description="Error message explaining what went wrong")

# Response models for the year endpoint
class YearsResponse(BaseModel):
    """
    Response model for the /years endpoint
    Contains a sorted list of all available years
    """
    years: List[int] = Field(
        ...,
        description="List of years where vehicles are available",
        example=[2018, 2019, 2020, 2021, 2022]
    )

# Response models for the brands endpoint
class BrandsResponse(BaseModel):
    """
    Response model for the /brands/{year} endpoint
    Contains list of brands available for a specific year
    """
    year: int = Field(..., description="The year that was queried")
    brands: List[str] = Field(
        ...,
        description="List of brands available for the specified year",
        example=["Toyota", "Honda", "Ford"]
    )

# Response models for the models endpoint
class ModelsResponse(BaseModel):
    """
    Response model for the /models/{year}/{brand} endpoint
    Contains list of models available for a specific year and brand
    """
    year: int = Field(..., description="The year that was queried")
    brand: str = Field(..., description="The brand that was queried")
    models: List[str] = Field(
        ...,
        description="List of models available for the specified year and brand",
        example=["Camry", "Corolla", "RAV4"]
    )

class VehicleFilterResponse(VehicleBase):
    """
    Complete vehicle response model for filtered queries
    Includes all vehicle data and associated files
    """
    id: int = Field(..., description="Unique identifier for the vehicle")
    created_at: datetime = Field(..., description="Timestamp when the vehicle was added")
    updated_at: datetime = Field(..., description="Timestamp of last update")
    neutral_pdfs: List[NeutralPDFResponse] = Field(
        default=[],
        description="List of associated neutral procedure PDFs"
    )
    deactivation_pdfs: List[DeactivationPDFResponse] = Field(
        default=[],
        description="List of associated deactivation procedure PDFs"
    )
    images: List[ImageResponse] = Field(
        default=[],
        description="List of associated vehicle images"
    )

    class Config:
        from_attributes = True
        populate_by_name = True
        
class VehicleFilterParams(BaseModel):
    """
    Query parameters for filtering vehicles
    Used for input validation in the /vehicles endpoint
    """
    year: int = Field(..., description="Year to filter by")
    brand: Optional[str] = Field(None, description="Brand to filter by")
    model: Optional[str] = Field(None, description="Model to filter by")

    class Config:
        from_attributes = True

# SQLAlchemy models for database
class Vehicle(Base):
    """SQLAlchemy model for vehicles table"""
    __tablename__ = "vehicles"
    
    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    year_from = Column(Integer, nullable=False)
    year_to = Column(Integer)
    delay_time_neutral = Column(Integer)
    delay_time_deactivation = Column(Integer)
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(
        DateTime, 
        server_default=text('CURRENT_TIMESTAMP'),
        onupdate=text('CURRENT_TIMESTAMP')
    )
    
    # Define relationships with cascade delete
    neutral_pdfs = relationship("NeutralPDF", back_populates="vehicle", cascade="all, delete-orphan", lazy='selectin')
    deactivation_pdfs = relationship("DeactivationPDF", back_populates="vehicle", cascade="all, delete-orphan", lazy='selectin')
    images = relationship("VehicleImage", back_populates="vehicle", cascade="all, delete-orphan", lazy='selectin')

class NeutralPDF(Base):
    """SQLAlchemy model for neutral procedure PDFs"""
    __tablename__ = "vehicle_neutral_pdfs"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"))
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    
    vehicle = relationship("Vehicle", back_populates="neutral_pdfs")

class DeactivationPDF(Base):
    """SQLAlchemy model for deactivation procedure PDFs"""
    __tablename__ = "vehicle_deactivation_pdfs"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"))
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    
    vehicle = relationship("Vehicle", back_populates="deactivation_pdfs")

class VehicleImage(Base):
    """SQLAlchemy model for vehicle images"""
    __tablename__ = "vehicle_images"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"))
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    
    vehicle = relationship("Vehicle", back_populates="images")
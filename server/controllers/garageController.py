from typing import List
from fastapi import HTTPException, Request,status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from server.models.garageModel import Garage, CreateGarageRequest, UpdateGarageRequest
from server.models.authModel import RoleResponse, User, Role, PermissionResponse
from server.controllers.authController import argon2_strong_hash, has_permission, authenticate_user
from server.models.remorqueurModel import Remorqueur
from server.models.reponseModel import GarageResponse, RemorqueurResponse
from server.settings import (
    AsyncSession,
)

async def create_garage(
    request: Request,
    db: AsyncSession,
    garage_data: CreateGarageRequest,
):
    # Get authenticated user with roles and permissions
    token = request.headers.get("X-Deliver-Auth")
    current_user = await authenticate_user(token, db)

    # Check if user has required role
    allowed_roles = ['superadmin', 'apdq']
    if current_user.role.name not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="Only superadmin or apdq roles can create garages"
        )
    
    # Check permission
    await has_permission(current_user, 'create_garage', db)
    
    # Check if garage name already exists
    result = await db.execute(
        select(Garage).where(Garage.name == garage_data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Garage with this name already exists"
        )
    
    # Check if username already exists
    result = await db.execute(
        select(Garage).where(Garage.username == garage_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Username already taken"
        )
    
    # Get role by name
    result = await db.execute(
        select(Role).where(Role.name == garage_data.role_name)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=400,
            detail=f"Role {garage_data.role_name} not found"
        )
    
    # Hash the password
    hashed_password = argon2_strong_hash(garage_data.password)
    
    # Create new garage
    new_garage = Garage(
        name=garage_data.name,
        email=garage_data.email,
        username=garage_data.username,
        password=hashed_password,
        role_id=role.id,
        created_by_id=current_user.id,
        is_active = False
    )
    
    db.add(new_garage)
    await db.commit()
    await db.refresh(new_garage)
    
    # Load relationships
    result = await db.execute(
        select(Garage)
        .options(joinedload(Garage.role).joinedload(Role.permissions))
        .where(Garage.id == new_garage.id)
    )
    garage_with_relations = result.unique().scalar_one()
    
    return GarageResponse(
        id=garage_with_relations.id,
        name=garage_with_relations.name,
        username=garage_with_relations.username,
        role=RoleResponse(
            id=garage_with_relations.role.id,
            name=garage_with_relations.role.name,
            permissions=[
                PermissionResponse(id=perm.id, name=perm.name)
                for perm in garage_with_relations.role.permissions
            ]
        ),
        is_active=garage_with_relations.is_active
    )

async def update_garage(
    request: Request,
    update_data: UpdateGarageRequest,
    db: AsyncSession
):
    # Authenticate the user
    token = request.headers.get("X-Deliver-Auth")
    current_user = await authenticate_user(token, db)

    # Check if the garage exists and if the current user is authorized
    result = await db.execute(select(Garage).where(Garage.name == update_data.garage_name))
    garage = result.scalar_one_or_none()
    if not garage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Garage with name '{update_data.garage_name}' not found."
        )
    if garage.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this garage."
        )

    # Update username and/or password
    if update_data.username:
        # Check if the new username is unique
        username_exists = await db.execute(
            select(Garage).where(Garage.username == update_data.username)
        )
        if username_exists.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already in use. Please choose another one."
            )
        garage.username = update_data.username

    if update_data.password:
        garage.password = argon2_strong_hash(update_data.password)

    # Commit changes
    try:
        await db.commit()
        await db.refresh(garage)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update garage: {str(e)}"
        )

    return {"message": "Garage updated successfully", "garage_name": garage.name, "username": garage.username}

async def get_garage_remorqueurs(
    db: AsyncSession,
    current_user: User
) -> List[RemorqueurResponse]:
    if not current_user.role.name.lower() == 'garage':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only garages can access their remorqueurs"
        )

    try:
        # Get garage details
        garage_result = await db.execute(
            select(Garage)
            .where(Garage.username == current_user.username)
        )
        garage = garage_result.scalar_one_or_none()
        
        if not garage:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Garage not found"
            )

        # Fetch remorqueurs with roles and permissions
        stmt = select(Remorqueur).options(
            joinedload(Remorqueur.role).joinedload(Role.permissions)
        ).where(Remorqueur.garage_id == garage.id)
        
        result = await db.execute(stmt)
        remorqueurs = result.scalars().unique().all()
        
        # Transform the data into the response model
        return [
            RemorqueurResponse(
                id=remorqueur.id,
                name=remorqueur.name,
                tel=remorqueur.tel,
                username=remorqueur.username,
                role=RoleResponse(
                    id=remorqueur.role.id,
                    name=remorqueur.role.name,
                    permissions=[
                        PermissionResponse(
                            id=permission.id,
                            name=permission.name
                        )
                        for permission in (remorqueur.role.permissions or [])
                    ]
                ),
                garage_name=garage.name,
                is_active=remorqueur.is_active
            )
            for remorqueur in remorqueurs
        ]

    except HTTPException as e:
        raise e
    except Exception as e:
        # Log the actual error for debugging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching remorqueurs: {str(e)}"
        )
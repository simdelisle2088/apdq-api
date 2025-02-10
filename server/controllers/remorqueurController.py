from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from server.models.remorqueurModel import Remorqueur, CreateRemorqueurRequest, UpdateRemorqueurRequest
from server.models.authModel import PermissionResponse, Role, RoleResponse
from server.models.garageModel import Garage
from server.controllers.authController import argon2_strong_hash, has_permission, authenticate_user
from server.models.reponseModel import RemorqueurResponse
from server.settings import AsyncSession

async def create_remorqueur(
    request: Request,
    db: AsyncSession,
    remorqueur_data: CreateRemorqueurRequest,
):
    # Get authenticated user
    token = request.headers.get("X-Deliver-Auth")
    current_user = await authenticate_user(token, db)

    # Check if user has required role and permission
    allowed_roles = ['garage']
    if current_user.role.name not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to create remorqueurs"
        )

    # Check permission
    await has_permission(current_user, 'create_remorqueur', db)

    # Get the garage
    result = await db.execute(
        select(Garage).where(Garage.name == remorqueur_data.garage_name)
    )
    garage = result.scalar_one_or_none()
    
    if not garage:
        raise HTTPException(
            status_code=404,
            detail=f"Garage {remorqueur_data.garage_name} not found"
        )

    # If user is a garage, verify they belong to this garage
    if current_user.role.name == 'garage' and current_user.id != garage.id:
        raise HTTPException(
            status_code=403,
            detail="You can only create remorqueurs for your own garage"
        )

    # Check if username already exists
    result = await db.execute(
        select(Remorqueur).where(Remorqueur.username == remorqueur_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Username already taken"
        )
    
    # Get role by name
    result = await db.execute(
        select(Role).where(Role.name == remorqueur_data.role_name)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=400,
            detail=f"Role {remorqueur_data.role_name} not found"
        )

    # Verify role is allowed for remorqueurs
    allowed_remorqueur_roles = ['remorqueur']
    if role.name not in allowed_remorqueur_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Role {role.name} is not allowed for remorqueurs"
        )
    
    # Hash the password
    hashed_password = argon2_strong_hash(remorqueur_data.password)
    
    # Create new remorqueur
    new_remorqueur = Remorqueur(
        name=remorqueur_data.name,
        tel=remorqueur_data.tel,
        username=remorqueur_data.username,
        password=hashed_password,
        role_id=role.id,
        garage_id=garage.id,
    )
    
    db.add(new_remorqueur)
    await db.commit()
    await db.refresh(new_remorqueur)
    
    # Load relationships
    result = await db.execute(
        select(Remorqueur)
        .options(
            joinedload(Remorqueur.role).joinedload(Role.permissions),
            joinedload(Remorqueur.garage)
        )
        .where(Remorqueur.id == new_remorqueur.id)
    )
    remorqueur_with_relations = result.unique().scalar_one()
    
    return RemorqueurResponse(
        id=remorqueur_with_relations.id,
        name=remorqueur_with_relations.name, 
        tel=remorqueur_with_relations.tel,
        username=remorqueur_with_relations.username,
        role=RoleResponse(
            id=remorqueur_with_relations.role.id,
            name=remorqueur_with_relations.role.name,
            permissions=[
                PermissionResponse(id=perm.id, name=perm.name)
                for perm in remorqueur_with_relations.role.permissions
            ]
        ),
        garage_name=remorqueur_with_relations.garage.name,
        is_active=remorqueur_with_relations.is_active
    )

async def update_remorqueur(
    request: Request,
    db: AsyncSession,
    remorqueur_id: int,
    update_data: UpdateRemorqueurRequest,
):
    token = request.headers.get("X-Deliver-Auth")
    current_user = await authenticate_user(token, db)

    allowed_roles = ['garage']
    if current_user.role.name not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update remorqueurs"
        )

    await has_permission(current_user, 'update_remorqueur', db)

    result = await db.execute(
        select(Remorqueur)
        .options(joinedload(Remorqueur.garage))
        .where(Remorqueur.id == remorqueur_id)
    )
    remorqueur = result.unique().scalar_one_or_none()

    if not remorqueur:
        raise HTTPException(
            status_code=404,
            detail="Remorqueur not found"
        )

    # For garage role, check if remorqueur belongs to their garage
    if current_user.role.name == 'garage':
        result = await db.execute(
            select(Garage).where(Garage.id == current_user.id)
        )
        user_garage = result.scalar_one_or_none()
        
        if not user_garage or user_garage.id != remorqueur.garage_id:
            raise HTTPException(
                status_code=403,
                detail="You can only update remorqueurs from your own garage"
            )

    if update_data.username:
        result = await db.execute(
            select(Remorqueur)
            .where(Remorqueur.username == update_data.username)
            .where(Remorqueur.id != remorqueur_id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Username already taken"
            )

    if update_data.name:
        remorqueur.name = update_data.name
    if update_data.tel:
        remorqueur.tel = update_data.tel
    if update_data.username:
        remorqueur.username = update_data.username
    if update_data.password:
        remorqueur.password = argon2_strong_hash(update_data.password)
    if update_data.is_active is not None: 
        remorqueur.is_active = update_data.is_active

    await db.commit()
    await db.refresh(remorqueur)

    result = await db.execute(
        select(Remorqueur)
        .options(
            joinedload(Remorqueur.role).joinedload(Role.permissions),
            joinedload(Remorqueur.garage)
        )
        .where(Remorqueur.id == remorqueur.id)
    )
    remorqueur_with_relations = result.unique().scalar_one()

    return RemorqueurResponse(
        id=remorqueur_with_relations.id,
        name=remorqueur_with_relations.name,
        username=remorqueur_with_relations.username,
        tel=remorqueur_with_relations.tel,
        role=RoleResponse(
            id=remorqueur_with_relations.role.id,
            name=remorqueur_with_relations.role.name,
            permissions=[
                PermissionResponse(id=perm.id, name=perm.name)
                for perm in remorqueur_with_relations.role.permissions
            ]
        ),
        garage_name=remorqueur_with_relations.garage.name,
        is_active=remorqueur_with_relations.is_active
    )

async def delete_remorqueur(
    request: Request,
    db: AsyncSession,
    remorqueur_id: int,
):

    # Verify user authentication and authorization
    token = request.headers.get("X-Deliver-Auth")
    current_user = await authenticate_user(token, db)

    # Check if user has appropriate role
    allowed_roles = ['garage']
    if current_user.role.name not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete remorqueurs"
        )

    # Verify specific permission for deleting remorqueurs
    await has_permission(current_user, 'delete_remorqueur', db)

    # Fetch the remorqueur with its relationships
    result = await db.execute(
        select(Remorqueur)
        .options(joinedload(Remorqueur.garage))
        .where(Remorqueur.id == remorqueur_id)
    )
    remorqueur = result.unique().scalar_one_or_none()

    if not remorqueur:
        raise HTTPException(
            status_code=404,
            detail="Remorqueur not found"
        )

    # For garage role, verify they can only delete remorqueurs from their garage
    if current_user.role.name == 'garage':
        result = await db.execute(
            select(Garage).where(Garage.id == current_user.id)
        )
        user_garage = result.scalar_one_or_none()
        
        if not user_garage or user_garage.id != remorqueur.garage_id:
            raise HTTPException(
                status_code=403,
                detail="You can only delete remorqueurs from your own garage"
            )

    # Perform the hard deletion
    await db.delete(remorqueur)
    
    # Commit the changes to the database
    await db.commit()

    return {
        "message": "Remorqueur successfully deleted",
        "remorqueur_id": remorqueur_id
    }
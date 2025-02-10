from typing import List, Optional
from sqlalchemy import distinct, and_, or_, select
from server.models.vehiculeModel import Vehicle
from server.settings import (
    AsyncSession,
)

async def get_available_years(db: AsyncSession) -> List[int]:
    # Get distinct year_from values
    years_from_stmt = select(distinct(Vehicle.year_from))
    years_from_result = await db.execute(years_from_stmt)
    years_from = years_from_result.scalars().all()
    
    # Get distinct year_to values
    years_to_stmt = select(distinct(Vehicle.year_to)).where(Vehicle.year_to.isnot(None))
    years_to_result = await db.execute(years_to_stmt)
    years_to = years_to_result.scalars().all()
    
    # Combine and process years
    all_years = set(years_from) | set(years_to)
    
    # Get all vehicles to process intermediate years
    vehicles_stmt = select(Vehicle)
    vehicles_result = await db.execute(vehicles_stmt)
    vehicles = vehicles_result.scalars().all()
    
    # Add intermediate years
    final_years = set()
    for vehicle in vehicles:
        start_year = vehicle.year_from
        end_year = vehicle.year_to or start_year
        final_years.update(range(start_year, end_year + 1))
            
    return sorted(list(final_years))

async def get_brands_by_year(db: AsyncSession, year: int) -> List[str]:
    stmt = select(distinct(Vehicle.brand)).where(
        and_(
            Vehicle.year_from <= year,
            or_(
                Vehicle.year_to.is_(None),
                Vehicle.year_to >= year
            )
        )
    )
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_models_by_year_and_brand(db: AsyncSession, year: int, brand: str) -> List[str]:
    stmt = select(distinct(Vehicle.model)).where(
        and_(
            Vehicle.brand == brand,
            Vehicle.year_from <= year,
            or_(
                Vehicle.year_to.is_(None),
                Vehicle.year_to >= year
            )
        )
    )
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_vehicle_by_filters(
    db: AsyncSession,
    year: int,
    brand: Optional[str] = None,
    model: Optional[str] = None
) -> List[Vehicle]:
    stmt = select(Vehicle).where(
        and_(
            Vehicle.year_from <= year,
            or_(
                Vehicle.year_to.is_(None),
                Vehicle.year_to >= year
            )
        )
    )
    
    if brand:
        stmt = stmt.where(Vehicle.brand == brand)
    if model:
        stmt = stmt.where(Vehicle.model == model)
    
    result = await db.execute(stmt)
    return result.scalars().all()

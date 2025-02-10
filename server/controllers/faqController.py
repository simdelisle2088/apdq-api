from sqlalchemy import delete, select
from server.models.faqModel import FAQCreate, faq
from server.settings import (
    AsyncSession,
)

async def create_faq_db(db: AsyncSession, faq_data: FAQCreate) -> faq:
    try:
        new_faq = faq(
            question=faq_data.question,
            answer=faq_data.answer,
            language=faq_data.language  
        )
        
        db.add(new_faq)
        await db.commit()  
        await db.refresh(new_faq)
        
        return new_faq
        
    except Exception as e:
        await db.rollback() 
        raise Exception(f"Database error: {str(e)}")
    
async def delete_faq_db(db: AsyncSession, faq_id: int) -> bool:
    
    try:
        # First check if the FAQ exists
        result = await db.execute(select(faq).where(faq.id == faq_id))
        faq_item = result.scalar_one_or_none()
        
        if not faq_item:
            return False
            
        # Delete the FAQ
        await db.execute(delete(faq).where(faq.id == faq_id))
        await db.commit()
        
        return True
        
    except Exception as e:
        await db.rollback()
        raise Exception(f"Database error: {str(e)}")
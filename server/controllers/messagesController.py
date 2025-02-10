from typing import List
from sqlalchemy import Boolean, and_, delete, select, insert, Table, Column, Integer, ForeignKey, update
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from datetime import datetime
from server.models.authModel import Base, User
from server.models.garageModel import Garage
from server.models.messagesModel import AdminMessage, AdminMessageCreate, AdminMessageResponse, GarageMessage, GarageMessageCreate, GarageMessageResponse, get_eastern_time
from server.models.remorqueurModel import Remorqueur
from server.settings import (
    AsyncSession,
)

# Define association tables
admin_message_recipients = Table(
    "admin_message_recipients",
    Base.metadata,
    Column("message_id", Integer, ForeignKey("admin_messages.id"), primary_key=True),
    Column("garage_id", Integer, ForeignKey("garages.id"), primary_key=True),
    Column("is_read", Boolean, default=False, nullable=False),
    extend_existing=True
)

garage_message_recipients = Table(
    "garage_message_recipients",
    Base.metadata,
    Column("message_id", Integer, ForeignKey("garage_messages.id"), primary_key=True),
    Column("remorqueur_id", Integer, ForeignKey("remorqueurs.id"), primary_key=True),
    Column("is_read", Boolean, default=False, nullable=False),
    extend_existing=True
)

async def get_all_admin_messages_logic(db: AsyncSession):
    try:
        # Get all admin messages
        messages_query = select(AdminMessage)
        result = await db.execute(messages_query)
        messages = result.scalars().all()

        message_responses = []
        for message in messages:
            # Get all recipients for this message
            recipients_query = (
                select(admin_message_recipients.c.garage_id)
                .where(admin_message_recipients.c.message_id == message.id)
            )
            recipients_result = await db.execute(recipients_query)
            recipient_ids = [row[0] for row in recipients_result]
            
            message_responses.append(AdminMessageResponse(
                id=message.id,
                title=message.title,
                content=message.content,
                created_at=message.created_at,
                to_all=message.to_all,
                garage_ids=recipient_ids,
                is_read=False
            ))

        return message_responses
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve all admin messages: {str(e)}")

async def get_all_garage_messages_logic(garage_id: int, db: AsyncSession):
    try:
        # Get all messages from a specific garage
        messages_query = select(GarageMessage).where(GarageMessage.garage_id == garage_id)
        result = await db.execute(messages_query)
        messages = result.scalars().all()

        message_responses = []
        for message in messages:
            # Get all recipients for this message
            recipients_query = (
                select(garage_message_recipients.c.remorqueur_id)
                .where(garage_message_recipients.c.message_id == message.id)
            )
            recipients_result = await db.execute(recipients_query)
            recipient_ids = [row[0] for row in recipients_result]
            
            message_responses.append(GarageMessageResponse(
                id=message.id,
                title=message.title,
                content=message.content,
                created_at=message.created_at,
                to_all=message.to_all,
                remorqueur_ids=recipient_ids,
                is_read=False
            ))

        return message_responses
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve all garage messages: {str(e)}")
    
async def get_admin_messages_logic(garage_id: int, db: AsyncSession):

    try:
        # Get all messages for this garage, including their read status
        messages_query = (
            select(
                AdminMessage,
                admin_message_recipients.c.is_read
            )
            .join(
                admin_message_recipients,
                AdminMessage.id == admin_message_recipients.c.message_id
            )
            .where(admin_message_recipients.c.garage_id == garage_id)
            .order_by(AdminMessage.created_at.desc())  # Show newest messages first
        )
        
        result = await db.execute(messages_query)
        messages = result.fetchall()

        message_responses = []
        for message, is_read in messages:
            # Get all recipients for this message to maintain the complete recipient list
            recipients_query = (
                select(admin_message_recipients.c.garage_id)
                .where(admin_message_recipients.c.message_id == message.id)
            )
            recipients_result = await db.execute(recipients_query)
            recipient_ids = [row[0] for row in recipients_result]
            
            message_responses.append(AdminMessageResponse(
                id=message.id,
                title=message.title,
                content=message.content,
                created_at=message.created_at,
                to_all=message.to_all,
                garage_ids=recipient_ids,
                is_read=is_read  # Individual read status for this garage
            ))

        return message_responses
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve admin messages: {str(e)}")
    
async def get_garage_messages_logic(remorqueur_id: int, db: AsyncSession):
   
    try:
        # First get the remorqueur's garage information
        remorqueur_query = (
            select(Remorqueur)
            .options(selectinload(Remorqueur.garage))
            .where(Remorqueur.id == remorqueur_id)
        )
        remorqueur_result = await db.execute(remorqueur_query)
        remorqueur = remorqueur_result.scalar_one_or_none()
        
        if not remorqueur:
            raise HTTPException(status_code=404, detail="Remorqueur not found")

        # Get all messages for this remorqueur, including their read status
        messages_query = (
            select(
                GarageMessage,
                garage_message_recipients.c.is_read
            )
            .join(
                garage_message_recipients,
                GarageMessage.id == garage_message_recipients.c.message_id
            )
            .where(
                and_(
                    GarageMessage.garage_id == remorqueur.garage_id,
                    garage_message_recipients.c.remorqueur_id == remorqueur_id
                )
            )
            .order_by(GarageMessage.created_at.desc())  # Show newest messages first
        )
        
        result = await db.execute(messages_query)
        messages = result.fetchall()
        
        message_responses = []
        for message, is_read in messages:
            # Get all recipients for this message to maintain the complete recipient list
            recipients_query = (
                select(garage_message_recipients.c.remorqueur_id)
                .where(garage_message_recipients.c.message_id == message.id)
            )
            recipients_result = await db.execute(recipients_query)
            recipient_ids = [row[0] for row in recipients_result]
            
            message_responses.append(GarageMessageResponse(
                id=message.id,
                title=message.title,
                content=message.content,
                created_at=message.created_at,
                to_all=message.to_all,
                remorqueur_ids=recipient_ids,
                is_read=is_read  # Individual read status for this remorqueur
            ))

        return message_responses
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve garage messages: {str(e)}"
        )
    
async def create_admin_message_logic(admin_id: int, message_data: AdminMessageCreate, db: AsyncSession):
    try:
        # First verify that the admin exists
        admin_query = select(User).where(
            and_(User.id == admin_id, User.role_id == 1)
        )
        admin = await db.execute(admin_query)
        admin_result = admin.scalar()
        
        if not admin_result:
            raise HTTPException(status_code=403, detail="Not authorized - Invalid admin ID")

        new_message = AdminMessage(
            admin_id=admin_id,
            title=message_data.title,
            content=message_data.content,
            to_all=message_data.to_all,
            created_at=get_eastern_time(),
        )
        db.add(new_message)
        await db.flush()

        # Handle recipient logic
        recipient_garage_ids = []
        if message_data.to_all:
            # If to_all is true, get all garage IDs created by this admin
            query = select(Garage.id).where(Garage.created_by_id == admin_id)
            result = await db.execute(query)
            recipient_garage_ids = [row[0] for row in result]
        elif message_data.garage_ids:
            # Verify that all garages were created by this admin
            query = select(Garage.id).where(
                and_(
                    Garage.id.in_(message_data.garage_ids),
                    Garage.is_active == True,
                    Garage.created_by_id == admin_id
                )
            )
            result = await db.execute(query)
            valid_ids = [row[0] for row in result]
            
            # Check if any invalid IDs were provided
            invalid_ids = set(message_data.garage_ids) - set(valid_ids)
            if invalid_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Garages with IDs {list(invalid_ids)} were not created by this admin"
                )
            recipient_garage_ids = valid_ids

        # Insert recipients if we have any
        if recipient_garage_ids:
            query = insert(admin_message_recipients).values([
                {"message_id": new_message.id, "garage_id": garage_id, "is_read": False}
                for garage_id in recipient_garage_ids
            ])
            await db.execute(query)

        await db.commit()
        return AdminMessageResponse(
            id=new_message.id,
            title=new_message.title,
            content=new_message.content,
            created_at=new_message.created_at,
            to_all=new_message.to_all,
            garage_ids=recipient_garage_ids,
            is_read=False
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create admin message: {str(e)}")
    
async def create_garage_message_logic(message_data: GarageMessageCreate, db: AsyncSession):
    try:
        new_message = GarageMessage(
            title=message_data.title,
            content=message_data.content,
            to_all=message_data.to_all,
            garage_id=message_data.garage_id,
            created_at=get_eastern_time(),
        )
        db.add(new_message)
        await db.flush()

        # Handle recipient logic
        recipient_ids = []
        if message_data.to_all:
            # If to_all is true, get all remorqueur IDs from the same garage
            query = select(Remorqueur.id).where(Remorqueur.garage_id == message_data.garage_id)
            result = await db.execute(query)
            recipient_ids = [row[0] for row in result]
        elif message_data.remorqueur_ids:
            # Verify that all remorqueurs belong to this garage
            query = select(Remorqueur.id).where(
                and_(
                    Remorqueur.id.in_(message_data.remorqueur_ids),
                    Remorqueur.garage_id == message_data.garage_id
                )
            )
            result = await db.execute(query)
            valid_ids = [row[0] for row in result]
            
            # Check if any invalid IDs were provided
            invalid_ids = set(message_data.remorqueur_ids) - set(valid_ids)
            if invalid_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Remorqueurs with IDs {list(invalid_ids)} do not belong to this garage"
                )
            recipient_ids = valid_ids

        # Insert recipients if we have any
        if recipient_ids:
            query = insert(garage_message_recipients).values([
                {"message_id": new_message.id, "remorqueur_id": remorqueur_id, "is_read": False}
                for remorqueur_id in recipient_ids
            ])
            await db.execute(query)

        await db.commit()
        return GarageMessageResponse(
            id=new_message.id,
            title=new_message.title,
            content=new_message.content,
            created_at=new_message.created_at,
            to_all=new_message.to_all,
            remorqueur_ids=recipient_ids,
            is_read=False
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create garage message: {str(e)}")

async def delete_admin_message_logic(message_id: int, db: AsyncSession):
    try:
        # First delete from recipients table
        delete_recipients = delete(admin_message_recipients).where(
            admin_message_recipients.c.message_id == message_id
        )
        await db.execute(delete_recipients)

        # Then delete the message
        delete_message = delete(AdminMessage).where(
            AdminMessage.id == message_id
        )
        result = await db.execute(delete_message)
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Message not found")

        await db.commit()
        return {"message": f"Admin message {message_id} deleted successfully"}

    except Exception as e:
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to delete admin message: {str(e)}")

async def delete_garage_message_logic(message_id: int, db: AsyncSession):
    try:
        # First delete from recipients table
        delete_recipients = delete(garage_message_recipients).where(
            garage_message_recipients.c.message_id == message_id
        )
        await db.execute(delete_recipients)

        # Then delete the message
        delete_message = delete(GarageMessage).where(
            GarageMessage.id == message_id
        )
        result = await db.execute(delete_message)

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Message not found")

        await db.commit()
        return {"message": f"Garage message {message_id} deleted successfully"}

    except Exception as e:
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to delete garage message: {str(e)}")

async def delete_multiple_admin_messages_logic(message_ids: List[int], db: AsyncSession):
    try:
        # First delete from recipients table
        delete_recipients = delete(admin_message_recipients).where(
            admin_message_recipients.c.message_id.in_(message_ids)
        )
        await db.execute(delete_recipients)

        # Then delete the messages
        delete_messages = delete(AdminMessage).where(
            AdminMessage.id.in_(message_ids)
        )
        result = await db.execute(delete_messages)

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="No messages found")

        await db.commit()
        return {"message": f"Successfully deleted {result.rowcount} messages"}

    except Exception as e:
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to delete messages: {str(e)}")
    
async def mark_admin_message_as_read_logic(message_id: int, garage_id: int, db: AsyncSession):
   
    try:
        # First verify that the message exists and the garage is a recipient
        verify_query = (
            select(admin_message_recipients)
            .where(
                and_(
                    admin_message_recipients.c.message_id == message_id,
                    admin_message_recipients.c.garage_id == garage_id
                )
            )
        )
        verify_result = await db.execute(verify_query)
        if not verify_result.first():
            raise HTTPException(
                status_code=404,
                detail="Message not found or garage is not a recipient"
            )

        # Update the read status for this specific garage
        update_stmt = (
            update(admin_message_recipients)
            .where(
                and_(
                    admin_message_recipients.c.message_id == message_id,
                    admin_message_recipients.c.garage_id == garage_id
                )
            )
            .values(is_read=True)
        )
        await db.execute(update_stmt)
        await db.commit()

        return {
            "message": "Message marked as read successfully",
            "message_id": message_id,
            "garage_id": garage_id
        }

    except Exception as e:
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        print(f"Error marking admin message as read: {str(e)}")  # Log the error
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark admin message as read: {str(e)}"
        )

async def mark_garage_message_as_read_logic(message_id: int, remorqueur_id: int, db: AsyncSession):
   
    try:
        # First verify that the message exists and the remorqueur is a recipient
        verify_query = (
            select(garage_message_recipients)
            .where(
                and_(
                    garage_message_recipients.c.message_id == message_id,
                    garage_message_recipients.c.remorqueur_id == remorqueur_id
                )
            )
        )
        verify_result = await db.execute(verify_query)
        if not verify_result.first():
            raise HTTPException(
                status_code=404,
                detail="Message not found or remorqueur is not a recipient"
            )

        # Update the read status for this specific remorqueur
        update_stmt = (
            update(garage_message_recipients)
            .where(
                and_(
                    garage_message_recipients.c.message_id == message_id,
                    garage_message_recipients.c.remorqueur_id == remorqueur_id
                )
            )
            .values(is_read=True)
        )
        await db.execute(update_stmt)
        await db.commit()

        return {
            "message": "Message marked as read successfully",
            "message_id": message_id,
            "remorqueur_id": remorqueur_id
        }

    except Exception as e:
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        print(f"Error marking garage message as read: {str(e)}")  # Log the error
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark garage message as read: {str(e)}"
        )
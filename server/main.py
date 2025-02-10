from ftplib import FTP
import hmac
import io
import os
from typing import Dict, List, Union
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
    status
)
from fastapi.responses import StreamingResponse
import pytz
from sqlalchemy import and_, func, insert, select, update
import stripe
from server import settings
from server.controllers.authController import ACCESS_TOKEN_EXPIRE_HOURS, ALGORITHM, SECRET_KEY, authenticate_user
from server.controllers.faqController import create_faq_db, delete_faq_db
from server.controllers.ftpController import FTPManager
from server.controllers.garageController import create_garage, get_garage_remorqueurs, update_garage
from server.controllers.loginController import process_login
from server.controllers.messagesController import create_admin_message_logic, create_garage_message_logic, delete_admin_message_logic, delete_garage_message_logic, delete_multiple_admin_messages_logic, get_admin_messages_logic, get_all_admin_messages_logic, get_all_garage_messages_logic, get_garage_messages_logic, mark_admin_message_as_read_logic, mark_garage_message_as_read_logic
from server.controllers.remorqueurController import create_remorqueur, delete_remorqueur, update_remorqueur
from server.controllers.userAdminController import create_user, update_admin
from server.controllers.vehicleController import get_available_years, get_brands_by_year, get_models_by_year_and_brand, get_vehicle_by_filters
from server.models.authModel import CreateUserRequest, LoginRequest, LoginResponse, PermissionResponse, Role, RoleResponse, UpdateUserPassword, User, UserResponse
from sqlalchemy.orm import joinedload, selectinload
from fastapi.middleware.cors import CORSMiddleware
from server.models.faqModel import DeleteResponse, FAQCreate, FAQResponse, faq
from server.models.garageModel import CreateGarageRequest, Garage, GarageRequest, UpdateGarageRequest
from server.models.messagesModel import AdminMessage, AdminMessageCreate, AdminMessageRequest, AdminMessageResponse, DeleteMessageRequest, DeleteMultipleMessagesRequest, GarageMessage, GarageMessageCreate, GarageMessageRequest, GarageMessageResponse, get_eastern_time
from server.models.remorqueurModel import CreateRemorqueurRequest, Remorqueur, UpdateRemorqueurRequest
from server.models.reponseModel import GarageResponse, GarageWithRemorqueursResponse, RemorqueurResponse, RemorqueurWithGarageResponse
from server.models.vehiculeModel import BrandsResponse, DeactivationPDF, NeutralPDF, Vehicle, VehicleCreate, VehicleFilterParams, VehicleFilterResponse, VehicleImage, VehicleResponse, YearsResponse
from server.settings import (
    get_primary_db,
    AsyncSession,
    DISPATCH_ADMIN_KEY,
)

app = FastAPI(
    debug=False,
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn

    # Make sure `settings.host`, `settings.port`, etc. are what you expect
    print(f"Starting server on {settings.host}:{settings.port}")

    uvicorn.run(
        "server.main:app",   # "server.main" = your module, "app" = FastAPI instance
        host=settings.host,   # e.g. "0.0.0.0"
        port=settings.port,   # e.g. 8000
        reload=settings.debug,
        log_level=settings.log_level  # e.g. "info"
    )

ftp_manager = FTPManager(
    host="148.113.140.18",
    user="ftp@apps.remorqueurbranche.com",
    password="U63DWAYZ7P9nnxx"
)

EASTERN_TZ = pytz.timezone("America/New_York")

stripe.api_key = "sk_test_51QkWvrCYKd15COmIkCuDzhjNSAccrHeDHqZgsZr2ydXCisiR0HaWFfFT3GN5EJKM2mGOlDo7nbH21v5oubGOnNZh007jmQfmwU"

# =============== Middlewares ===============#

async def authenticate(request: Request, db: AsyncSession = Depends(get_primary_db)):
    token = request.headers.get("X-Deliver-Auth")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Non autorisé"
        )
    
    user = await authenticate_user(token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Non autorisé"
        )
    return user
    
def is_dispatch(request: Request):
    if not hmac.compare_digest(
        request.headers.get("X-Dispatch-Key"), DISPATCH_ADMIN_KEY
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Non autorisé"
        )

# ============= End Middlewares =============#
# ================ Routers ==================#

auth_router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)
dispatch_router = APIRouter(
    prefix="/misc_dispatch",
    dependencies=[Depends(is_dispatch)],
)
garage_router = APIRouter(
    prefix="/garages",
    tags=["garages"],
    dependencies=[Depends(authenticate)]
)
remorqueur_router = APIRouter(
    prefix="/remorqueurs",
    tags=["remorqueurs"],
    dependencies=[Depends(authenticate)]
)
admin_router = APIRouter(
    prefix="/admin",
    tags=["admins"],
    dependencies=[Depends(authenticate)]
)

# =============== end routers ===============#
# =============== FTP ===============#
FTP_HOST = "148.113.140.18"
FTP_USER = "ftp@apps.remorqueurbranche.com"
FTP_PASS = "U63DWAYZ7P9nnxx"
@app.get("/ftp/images/{full_path:path}")
async def get_ftp_image(full_path: str):

    try:
        # Connect to FTP server
        ftp = FTP(FTP_HOST)
        ftp.login(FTP_USER, FTP_PASS)

        # Open a binary stream to fetch the image
        image_stream = io.BytesIO()
        ftp.retrbinary(f"RETR /{full_path}", image_stream.write)
        image_stream.seek(0)  # Reset pointer to the start

        # Quit FTP connection
        ftp.quit()

        # Determine correct MIME type based on file extension
        if full_path.lower().endswith(".png"):
            media_type = "image/png"
        elif full_path.lower().endswith(".jpg") or full_path.lower().endswith(".jpeg"):
            media_type = "image/jpeg"
        elif full_path.lower().endswith(".gif"):
            media_type = "image/gif"
        else:
            media_type = "application/octet-stream"  # Default binary file type

        # Serve the image as a StreamingResponse
        return StreamingResponse(image_stream, media_type=media_type)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching image: {str(e)}")
# =================== stripe_webhook =================#

endpoint_secret = "whsec_d4e2cec25d932fbfa0ca917d9ff17abf87e5fd7c7b8d4f28024fada28aaaa04d"

@app.post("/webhook", response_model=Dict[str, Union[str, int]])
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_primary_db)
):
    try:
        # Get and verify the webhook payload
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')
        print("Received webhook event")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
            print(f"Event type: {event['type']}")
        except ValueError as e:
            print(f"Error: Invalid payload - {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            print(f"Error: Invalid signature - {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Handle checkout.session.completed event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            print(f"Processing completed checkout for session: {session.id}")

            # Get customer details
            customer_email = session.customer_details.email
            print(f"Customer email: {customer_email}")
            customer_id = session.customer  
            print(f"Customer ID: {customer_id}")

            if not customer_email:
                print("No customer email found in session")
                return {"status": "error", "message": "No customer email found"}

            try:
                # Find the garage with a more specific query
                query = (
                    select(Garage)
                    .options(joinedload(Garage.role))
                    .where(
                        Garage.email == customer_email,
                        Garage.is_active == False 
                    )
                    .limit(1)  
                )
                
                result = await db.execute(query)
                garage = result.scalar_one_or_none()

                if not garage:
                    print(f"No inactive garage found with email: {customer_email}")
                    return {"status": "error", "message": "Garage not found"}

                # Update the garage status
                print(f"Updating garage: {garage.id}")
                update_query = (
                    update(Garage)
                    .where(Garage.id == garage.id)
                    .values(
                        is_active=True,
                        payment_status="completed",
                        payment_session_id=session.id,
                        stripe_customer_id=customer_id
                    )
                )
                await db.execute(update_query)
                await db.commit()
                
                print(f"Successfully activated garage {str(garage.id)}")
                return {"status": "success", "garage_id": str(garage.id)}

            except Exception as e:
                print(f"Database error: {str(e)}")
                await db.rollback()
                raise HTTPException(status_code=500, detail="Database error")

        # Handle subscription events
        elif event['type'] == 'customer.subscription.deleted':
            # Subscription was canceled and has ended
            subscription = event['data']['object']
            customer_id = subscription.customer
            print(f"Processing subscription deletion for customer: {customer_id}")

            try:
                # Update the garage's active status
                update_query = (
                    update(Garage)
                    .where(Garage.stripe_customer_id == customer_id)
                    .values(
                        is_active=False,
                        payment_status="subscription_ended"
                    )
                )
                await db.execute(update_query)
                await db.commit()
                print(f"Successfully deactivated garage for customer ID: {customer_id}")
                return {"status": "success", "message": "Subscription ended"}

            except Exception as e:
                print(f"Database error while processing subscription deletion: {str(e)}")
                await db.rollback()
                raise HTTPException(status_code=500, detail="Database error")

        elif event['type'] == 'customer.subscription.updated':
            # Subscription was updated (e.g., status changed)
            subscription = event['data']['object']
            customer_id = subscription.customer
            is_active = subscription.status in ["active", "trialing"]
            print(f"Processing subscription update for customer: {customer_id}")

            try:
                # Update the garage's active status based on subscription status
                update_query = (
                    update(Garage)
                    .where(Garage.stripe_customer_id == customer_id)
                    .values(
                        is_active=is_active,
                        payment_status=subscription.status
                    )
                )
                await db.execute(update_query)
                await db.commit()
                print(f"Successfully updated garage status to {is_active} for customer ID: {customer_id}")
                return {"status": "success", "message": "Subscription updated"}

            except Exception as e:
                print(f"Database error while processing subscription update: {str(e)}")
                await db.rollback()
                raise HTTPException(status_code=500, detail="Database error")

        return {"status": "received"}

    except Exception as e:
        print(f"Unexpected error in webhook handler: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")
    
@app.post("/billing/create-portal-session")
async def create_portal_session(
    request: GarageRequest,
    fastapi_request: Request,
    lang: str = Query(default='fr'),  # This automatically captures the 'lang' query parameter
    db: AsyncSession = Depends(get_primary_db)
):
    try:
        # Your existing garage validation code remains the same
        query = (
            select(Garage)
            .options(joinedload(Garage.role))
            .where(
                and_(
                    Garage.username == request.username,
                    Garage.is_active == True,
                    Garage.stripe_customer_id == request.stripe_customer_id
                )
            )
        )
        
        result = await db.execute(query)
        garage = result.scalar_one_or_none()
        
        if not garage:
            raise HTTPException(
                status_code=404,
                detail=f"Active garage with payment information not found for username: {request.username}"
            )
        
        if garage.role.name != 'garage':
            raise HTTPException(
                status_code=403,
                detail="Only garage accounts can access billing"
            )

        if not garage.stripe_customer_id:
            raise HTTPException(
                status_code=400,
                detail="No billing information found. Please complete the subscription process."
            )

        # Get the frontend URL from the request origin
        frontend_url = fastapi_request.headers.get("Origin", "http://localhost:5173")
        
        # Use the injected 'lang' parameter instead of trying to get it from query_params
        return_url = f"{frontend_url}/dashboard/{lang}/settings"
        print(f"Constructed return URL: {return_url}")
        
        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=garage.stripe_customer_id,
                return_url=return_url
            )
            print(f"Successfully created portal session: {portal_session.url}")
        except stripe.error.StripeError as se:
            print(f"Stripe error when creating portal session: {str(se)}")
            raise

        return {"url": portal_session.url}

    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create billing portal session: {str(e)}"
        )
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    
@garage_router.post("/api/v1/current_garage", response_model=GarageResponse)
async def get_current_garage(
    request: GarageRequest,
    db: AsyncSession = Depends(get_primary_db)
):
    try:
        # Query garage data directly using the username
        query = (
            select(Garage)
            .options(joinedload(Garage.role))
            .where(Garage.username == request.username)
        )
        
        result = await db.execute(query)
        garage = result.scalar_one_or_none()
        
        if not garage:
            raise HTTPException(
                status_code=404,
                detail=f"Garage not found for username: {request.username}"
            )
        
        role_data = {
            "id": garage.role.id,
            "name": garage.role.name,
            "permissions": [
                {"id": p.id, "name": p.name} 
                for p in garage.role.permissions
            ] if garage.role.permissions else []
        }
        
        return {
            "id": garage.id,
            "name": garage.name,
            "email": garage.email,
            "username": garage.username,
            "role_id": garage.role_id,
            "is_active": garage.is_active,
            "stripe_customer_id": garage.stripe_customer_id,
            "payment_status": garage.payment_status,
            "role": role_data
        }
        
    except Exception as e:
        print(f"Error fetching garage data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching garage data"
        )
# =================== stripe_webhook =================#
# =================== ADMIN =================#

@admin_router.get("/api/v1/all_faqs", response_model=List[FAQResponse], status_code=status.HTTP_200_OK)
async def get_all_faqs(db: AsyncSession = Depends(get_primary_db)):
    try:
        result = await db.execute(select(faq))
        faqs = result.scalars().all()

        return [
            FAQResponse(
                id=item.id,  # Include the ID in the response
                question=item.question,
                answer=item.answer,
                language=item.language  # Including language in the response
            ) 
            for item in faqs
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve FAQs: {str(e)}"
        )
    
@admin_router.get("/api/v1/faqs")
async def get_faqs(
    language: str = Query(None, regex="^(en|fr)$"),
    db: AsyncSession = Depends(get_primary_db),
):
    try:
        query = select(faq)
        if language:
            query = query.where(faq.language == language)
        
        result = await db.execute(query)
        faqs = result.scalars().all()
        return faqs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch FAQs: {str(e)}"
        )
    
@admin_router.post("/api/v1/faq", response_model=FAQResponse, status_code=status.HTTP_201_CREATED)
async def create_faq(
    faq_data: FAQCreate,
    db: AsyncSession = Depends(get_primary_db),
):
    # Validate language input
    if faq_data.language not in ['fr', 'en']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Language must be either 'fr' or 'en'"
        )
    
    try:
        new_faq = await create_faq_db(db=db, faq_data=faq_data)
        return FAQResponse(
            id=new_faq.id,
            question=new_faq.question,
            answer=new_faq.answer,
            language=new_faq.language  # Including language in the response
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create FAQ: {str(e)}"
        )
    
@admin_router.delete("/api/v1/faq/{faq_id}", response_model=DeleteResponse, 
                     status_code=status.HTTP_200_OK)
async def delete_faq(
    faq_id: int = Path(..., title="The ID of the FAQ to delete", ge=1),
    db: AsyncSession = Depends(get_primary_db)
):
    try:
        # Call the database function to delete the FAQ
        deleted = await delete_faq_db(db=db, faq_id=faq_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"FAQ with ID {faq_id} not found"
            )
            
        return DeleteResponse(
            message=f"FAQ with ID {faq_id} successfully deleted",
            faq_id=faq_id
        )
        
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete FAQ: {str(e)}"
        )
    
@garage_router.get("/api/v1/count", response_model=dict)
async def get_garage_count(db: AsyncSession = Depends(get_primary_db)):
    try:
        result = await db.execute(select(func.count(Garage.id)).where(Garage.is_active == True))
        count = result.scalar()  # Extracts the count from the result
        return {"total_garages": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch garage count: {str(e)}")

@dispatch_router.post("/api/v1/create-user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(request: CreateUserRequest, db: AsyncSession = Depends(get_primary_db)):
    # Call the create_user function to handle user creation
    user = await create_user(db, user_data=request)
    
    # Explicitly load user with relationships
    stmt = select(User).options(
        joinedload(User.role).joinedload(Role.permissions)
    ).where(User.id == user.id)
    result = await db.execute(stmt)
    user_with_relations = result.unique().scalar_one()

    # Format the response using Pydantic models
    return UserResponse(
        id=user_with_relations.id,
        username=user_with_relations.username,
        role=RoleResponse(
            id=user_with_relations.role.id,
            name=user_with_relations.role.name,
            permissions=[
                PermissionResponse(id=perm.id, name=perm.name) 
                for perm in user_with_relations.role.permissions
            ]
        ),
        is_active=user_with_relations.is_active
    )

@garage_router.post("/api/v1/create_garages", response_model=GarageResponse, status_code=status.HTTP_201_CREATED)
async def create_garage_endpoint(
    request: Request,
    garage_data: CreateGarageRequest,
    db: AsyncSession = Depends(get_primary_db)
):
    return await create_garage(request, db, garage_data)

@app.get("/api/v1/get_all_garages_with_remorqueurs/", 
         response_model=List[GarageWithRemorqueursResponse])
async def get_all_garages_with_remorqueurs(db: AsyncSession = Depends(get_primary_db)):
    try:
        result = await db.execute(
            select(Garage).options(
                joinedload(Garage.remorqueurs),
                joinedload(Garage.role)
            )
        )
        garages = result.scalars().unique().all()
        if not garages:
            return []
        return garages
    except HTTPException as e:
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while fetching garages"
        )

@app.get("/api/v1/get_all_remorqueurs_with_garages/", 
         response_model=List[RemorqueurWithGarageResponse])
async def get_all_remorqueurs_with_garages(db: AsyncSession = Depends(get_primary_db)):
    try:
        result = await db.execute(
            select(Remorqueur).options(
                joinedload(Remorqueur.garage),
                joinedload(Remorqueur.role)
            )
        )
        remorqueurs = result.scalars().unique().all()
        if not remorqueurs:
            return []
        return remorqueurs
    except HTTPException as e:
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while fetching remorqueurs"
        )

@admin_router.put("/api/v1/update_admin", status_code=status.HTTP_200_OK)
async def update_admin_endpoint(
    request: Request,
    update_data: UpdateUserPassword,
    db: AsyncSession = Depends(get_primary_db),
):
    return await update_admin(request, update_data, db)
# =================== END ADMIN =================#
# =================== MESSAGES =================#

@admin_router.get("/api/v1/get_all_admin_messages", response_model=List[AdminMessageResponse])
async def get_all_admin_messages(
    db: AsyncSession = Depends(get_primary_db)
):
    return await get_all_admin_messages_logic(db)

@garage_router.get("/api/v1/get_all_garage_messages", response_model=List[GarageMessageResponse])
async def get_all_garage_messages(
    garage_id: int,
    db: AsyncSession = Depends(get_primary_db)
):
    return await get_all_garage_messages_logic(garage_id, db)

@admin_router.post("/api/v1/get_garages_fromAdmin_messages", response_model=List[AdminMessageResponse])
async def get_garages_fromAdmin_messages(
    request: AdminMessageRequest,
    db: AsyncSession = Depends(get_primary_db)
):
    return await get_admin_messages_logic(request.garage_id, db)

@garage_router.post("/api/v1/get_remoqueurs_fromGarage_messages", response_model=List[GarageMessageResponse])
async def get_remoqueurs_fromGarage_messages(
    request: GarageMessageRequest,
    db: AsyncSession = Depends(get_primary_db)
):

    try:
        messages = await get_garage_messages_logic(request.remorqueur_id, db)
        print(f"Successfully retrieved {len(messages)} messages")
        return messages
    except Exception as e:
        print(f"Error in route handler: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve messages: {str(e)}"
        )

@admin_router.post("/api/v1/create_admin_messages", response_model=AdminMessageResponse)
async def create_admin_messages(
    message_data: AdminMessageCreate, 
    db: AsyncSession = Depends(get_primary_db)
):
    return await create_admin_message_logic(message_data.admin_id, message_data, db)

@garage_router.post("/api/v1/create_garage_messages", response_model=GarageMessageResponse)
async def create_garage_messages(message_data: GarageMessageCreate, db: AsyncSession = Depends(get_primary_db)):
    return await create_garage_message_logic(message_data, db)

@admin_router.delete("/api/v1/delete_admin_message", response_model=dict)
async def delete_admin_message(
    request: DeleteMessageRequest,
    db: AsyncSession = Depends(get_primary_db)
):
    return await delete_admin_message_logic(request.message_id, db)

@garage_router.delete("/api/v1/delete_garage_message", response_model=dict)
async def delete_garage_message(
    request: DeleteMessageRequest,
    db: AsyncSession = Depends(get_primary_db)
):
    return await delete_garage_message_logic(request.message_id, db)

@admin_router.delete("/api/v1/delete_admin_messages", response_model=dict)
async def delete_admin_messages(
    request: DeleteMultipleMessagesRequest,
    db: AsyncSession = Depends(get_primary_db)
):
    return await delete_multiple_admin_messages_logic(request.message_ids, db)

@admin_router.put("/admin-messages/{message_id}/read")
async def mark_admin_message_as_read(
    message_id: int,
    request: AdminMessageRequest,
    db: AsyncSession = Depends(get_primary_db)
):
    return await mark_admin_message_as_read_logic(
        message_id=message_id,
        garage_id=request.garage_id,
        db=db
    )

@garage_router.put("/garage-messages/{message_id}/read")
async def mark_garage_message_as_read(
    message_id: int,
    request: GarageMessageRequest,
    db: AsyncSession = Depends(get_primary_db)
):
    return await mark_garage_message_as_read_logic(
        message_id=message_id,
        remorqueur_id=request.remorqueur_id,
        db=db
    )
# =================== END MESSAGES =================#
# =================== Garages =================#
@remorqueur_router.post("/api/v1/create_remorqueur", 
                        response_model=RemorqueurResponse, status_code=status.HTTP_201_CREATED)
async def create_remorqueur_endpoint(
    request: Request,
    remorqueur_data: CreateRemorqueurRequest,
    db: AsyncSession = Depends(get_primary_db)
):
    return await create_remorqueur(request, db, remorqueur_data)

@remorqueur_router.get("/api/v1/get_garage_remorqueurs/", 
                       response_model=List[RemorqueurResponse])
async def get_garage_remorqueurs_endpoint(
    request: Request,
    current_user: User = Depends(authenticate),
    db: AsyncSession = Depends(get_primary_db)
):
    return await get_garage_remorqueurs(db, current_user)

@remorqueur_router.put("/api/v1/update_remorqueur/{remorqueur_id}", 
                       response_model=RemorqueurResponse)
async def update_remorqueur_endpoint(
    request: Request,
    remorqueur_id: int,
    update_data: UpdateRemorqueurRequest,
    db: AsyncSession = Depends(get_primary_db)
):
    return await update_remorqueur(request, db, remorqueur_id, update_data)

@remorqueur_router.delete("/api/v1/delete_remorqueur/{remorqueur_id}", 
                         response_model=dict)
async def delete_remorqueur_endpoint(
    request: Request,
    remorqueur_id: int,
    db: AsyncSession = Depends(get_primary_db)
):
    return await delete_remorqueur(request, db, remorqueur_id)

@garage_router.put("/api/v1/update_garage", status_code=status.HTTP_200_OK)
async def update_garage_endpoint(
    request: Request,
    update_data: UpdateGarageRequest,
    db: AsyncSession = Depends(get_primary_db),
):
    return await update_garage(request, update_data, db)


# =================== END Garages =================#
# =================== FTP =================#
@app.post("/vehicles/", response_model=VehicleResponse)
async def create_vehicle(vehicle: VehicleCreate, db: AsyncSession = Depends(get_primary_db)):
    """Create a new vehicle entry"""
    async with db.begin():
        # Create vehicle instance with all fields from the request
        db_vehicle = Vehicle(
            brand=vehicle.brand,
            model=vehicle.model,
            year_from=vehicle.year_from,
            year_to=vehicle.year_to,
            delay_time_neutral=vehicle.delay_time_neutral,
            delay_time_deactivation=vehicle.delay_time_deactivation,
            # Adding the procedure fields that were missing
        )
        db.add(db_vehicle)
        await db.flush()

        # Load the vehicle with its relationships using the new relationship names
        stmt = select(Vehicle).options(
            selectinload(Vehicle.neutral_pdfs),      # Changed from pdfs to neutral_pdfs
            selectinload(Vehicle.deactivation_pdfs), # Added deactivation_pdfs
            selectinload(Vehicle.images)
        ).where(Vehicle.id == db_vehicle.id)
        
        result = await db.execute(stmt)
        loaded_vehicle = result.scalar_one()
        
        # Convert SQLAlchemy model to dict with the new structure
        vehicle_dict = {
            "id": loaded_vehicle.id,
            "brand": loaded_vehicle.brand,
            "model": loaded_vehicle.model,
            "year_from": loaded_vehicle.year_from,
            "year_to": loaded_vehicle.year_to,
            "delay_time_neutral": loaded_vehicle.delay_time_neutral,
            "delay_time_deactivation": loaded_vehicle.delay_time_deactivation,
            "created_at": loaded_vehicle.created_at,
            "updated_at": loaded_vehicle.updated_at,
            # Split PDFs into two separate lists
            "neutral_pdfs": [
                {
                    "id": pdf.id,
                    "vehicle_id": pdf.vehicle_id,
                    "file_name": pdf.file_name,
                    "file_path": pdf.file_path,
                    "file_size": pdf.file_size,
                    "upload_date": pdf.upload_date
                } for pdf in loaded_vehicle.neutral_pdfs
            ],
            "deactivation_pdfs": [
                {
                    "id": pdf.id,
                    "vehicle_id": pdf.vehicle_id,
                    "file_name": pdf.file_name,
                    "file_path": pdf.file_path,
                    "file_size": pdf.file_size,
                    "upload_date": pdf.upload_date
                } for pdf in loaded_vehicle.deactivation_pdfs
            ],
            "images": [
                {
                    "id": img.id,
                    "vehicle_id": img.vehicle_id,
                    "file_name": img.file_name,
                    "file_path": img.file_path,
                    "file_size": img.file_size,
                    "upload_date": img.upload_date
                } for img in loaded_vehicle.images
            ]
        }
        
        # Create the response using our updated VehicleResponse model
        return VehicleResponse(**vehicle_dict)

@app.get("/vehicles/", response_model=List[VehicleResponse])
async def get_vehicles(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_primary_db)):
    """Get list of vehicles"""
    async with db.begin():
        result = await db.execute(select(Vehicle).offset(skip).limit(limit))
        vehicles = result.scalars().all()
        return [VehicleResponse.from_orm(vehicle) for vehicle in vehicles]


@app.get("/vehicles/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(vehicle_id: int, db: AsyncSession = Depends(get_primary_db)):
    """Get specific vehicle by ID"""
    async with db.begin():
        result = await db.execute(select(Vehicle).filter(Vehicle.id == vehicle_id))
        vehicle = result.scalar_one_or_none()
        if vehicle is None:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        return VehicleResponse.from_orm(vehicle)
    
@app.put("/vehicles/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: int,
    vehicle: VehicleCreate,
    db: AsyncSession = Depends(get_primary_db)
):
    """Update an existing vehicle entry"""
    async with db.begin():
        # Get existing vehicle
        result = await db.execute(select(Vehicle).filter(Vehicle.id == vehicle_id))
        db_vehicle = result.scalar_one_or_none()
        
        if not db_vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        
        # Update vehicle fields
        for field, value in vehicle.dict(exclude_unset=True).items():
            setattr(db_vehicle, field, value)
        
        await db.flush()
        
        # Reload vehicle with relationships
        stmt = select(Vehicle).options(
            selectinload(Vehicle.neutral_pdfs),
            selectinload(Vehicle.deactivation_pdfs),
            selectinload(Vehicle.images)
        ).where(Vehicle.id == vehicle_id)
        
        result = await db.execute(stmt)
        loaded_vehicle = result.scalar_one()
        
        return VehicleResponse.from_orm(loaded_vehicle)

@app.post("/vehicles/{vehicle_id}/upload-image")
async def upload_image(
    vehicle_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_primary_db),
):
    """Upload image file for a vehicle"""
    async with db.begin():
        result = await db.execute(select(Vehicle).filter(Vehicle.id == vehicle_id))
        vehicle = result.scalar_one_or_none()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif"}
        file_ext = os.path.splitext(file.filename.lower())[1]
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail="Invalid image format")

        try:
            server_path, file_size = await ftp_manager.upload_file(file.file, file.filename, "image")
            db_image = VehicleImage(
                vehicle_id=vehicle_id,
                file_name=file.filename,
                file_path=server_path,
                file_size=file_size,
            )
            db.add(db_image)
            await db.flush()
            await db.refresh(db_image)

            return {"message": "Image uploaded successfully", "file_path": server_path}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/vehicles/{vehicle_id}/upload-neutral-pdf")
async def upload_neutral_pdf(
    vehicle_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_primary_db),
):
    """Upload neutral procedure PDF file for a vehicle"""
    async with db.begin():
        result = await db.execute(select(Vehicle).filter(Vehicle.id == vehicle_id))
        vehicle = result.scalar_one_or_none()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="File must be a PDF")

        try:
            server_path, file_size = await ftp_manager.upload_file(file.file, file.filename, "pdf")
            db_pdf = NeutralPDF(
                vehicle_id=vehicle_id,
                file_name=file.filename,
                file_path=server_path,
                file_size=file_size,
            )
            db.add(db_pdf)
            await db.flush()
            await db.refresh(db_pdf)

            return {"message": "Neutral PDF uploaded successfully", "file_path": server_path}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/vehicles/{vehicle_id}/upload-deactivation-pdf")
async def upload_deactivation_pdf(
    vehicle_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_primary_db),
):
    """Upload deactivation procedure PDF file for a vehicle"""
    async with db.begin():
        result = await db.execute(select(Vehicle).filter(Vehicle.id == vehicle_id))
        vehicle = result.scalar_one_or_none()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="File must be a PDF")

        try:
            server_path, file_size = await ftp_manager.upload_file(file.file, file.filename, "pdf")
            db_pdf = DeactivationPDF(
                vehicle_id=vehicle_id,
                file_name=file.filename,
                file_path=server_path,
                file_size=file_size,
            )
            db.add(db_pdf)
            await db.flush()
            await db.refresh(db_pdf)

            return {"message": "Deactivation PDF uploaded successfully", "file_path": server_path}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.delete("/vehicles/{vehicle_id}/neutral-pdfs/{pdf_id}")
async def delete_neutral_pdf(
    vehicle_id: int,
    pdf_id: int,
    db: AsyncSession = Depends(get_primary_db),
):
    """Delete a neutral procedure PDF file"""
    async with db.begin():
        result = await db.execute(
            select(NeutralPDF).filter(
                NeutralPDF.id == pdf_id,
                NeutralPDF.vehicle_id == vehicle_id,
            )
        )
        pdf = result.scalar_one_or_none()
        if not pdf:
            raise HTTPException(status_code=404, detail="PDF not found")

        try:
            await ftp_manager.delete_file(pdf.file_path)
            await db.delete(pdf)
            return {"message": "Neutral PDF deleted successfully"}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.delete("/vehicles/{vehicle_id}/deactivation-pdfs/{pdf_id}")
async def delete_deactivation_pdf(
    vehicle_id: int,
    pdf_id: int,
    db: AsyncSession = Depends(get_primary_db),
):
    """Delete a deactivation procedure PDF file"""
    async with db.begin():
        result = await db.execute(
            select(DeactivationPDF).filter(
                DeactivationPDF.id == pdf_id,
                DeactivationPDF.vehicle_id == vehicle_id,
            )
        )
        pdf = result.scalar_one_or_none()
        if not pdf:
            raise HTTPException(status_code=404, detail="PDF not found")

        try:
            await ftp_manager.delete_file(pdf.file_path)
            await db.delete(pdf)
            return {"message": "Deactivation PDF deleted successfully"}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
@app.post("/vehicles/{vehicle_id}/update-neutral-pdf")
async def update_neutral_pdf(
    vehicle_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_primary_db),
):
    """Update neutral procedure PDF file for a vehicle, replacing any existing one"""
    async with db.begin():
        # Check if vehicle exists
        result = await db.execute(select(Vehicle).filter(Vehicle.id == vehicle_id))
        vehicle = result.scalar_one_or_none()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="File must be a PDF")

        try:
            # Delete existing PDFs if any
            result = await db.execute(
                select(NeutralPDF).filter(NeutralPDF.vehicle_id == vehicle_id)
            )
            existing_pdfs = result.scalars().all()
            
            for pdf in existing_pdfs:
                await ftp_manager.delete_file(pdf.file_path)
                await db.delete(pdf)
            
            # Upload new PDF
            server_path, file_size = await ftp_manager.upload_file(file.file, file.filename, "pdf")
            db_pdf = NeutralPDF(
                vehicle_id=vehicle_id,
                file_name=file.filename,
                file_path=server_path,
                file_size=file_size,
            )
            db.add(db_pdf)
            await db.flush()
            await db.refresh(db_pdf)

            return {"message": "Neutral PDF updated successfully", "file_path": server_path}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/vehicles/{vehicle_id}/update-deactivation-pdf")
async def update_deactivation_pdf(
    vehicle_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_primary_db),
):
    """Update deactivation procedure PDF file for a vehicle, replacing any existing one"""
    async with db.begin():
        # Check if vehicle exists
        result = await db.execute(select(Vehicle).filter(Vehicle.id == vehicle_id))
        vehicle = result.scalar_one_or_none()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="File must be a PDF")

        try:
            # Delete existing PDFs if any
            result = await db.execute(
                select(DeactivationPDF).filter(DeactivationPDF.vehicle_id == vehicle_id)
            )
            existing_pdfs = result.scalars().all()
            
            for pdf in existing_pdfs:
                await ftp_manager.delete_file(pdf.file_path)
                await db.delete(pdf)
            
            # Upload new PDF
            server_path, file_size = await ftp_manager.upload_file(file.file, file.filename, "pdf")
            db_pdf = DeactivationPDF(
                vehicle_id=vehicle_id,
                file_name=file.filename,
                file_path=server_path,
                file_size=file_size,
            )
            db.add(db_pdf)
            await db.flush()
            await db.refresh(db_pdf)

            return {"message": "Deactivation PDF updated successfully", "file_path": server_path}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/vehicles/{vehicle_id}/update-image")
async def update_image(
    vehicle_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_primary_db),
):
    """Update image file for a vehicle, replacing any existing one"""
    async with db.begin():
        # Check if vehicle exists
        result = await db.execute(select(Vehicle).filter(Vehicle.id == vehicle_id))
        vehicle = result.scalar_one_or_none()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif"}
        file_ext = os.path.splitext(file.filename.lower())[1]
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail="Invalid image format")

        try:
            # Delete existing images if any
            result = await db.execute(
                select(VehicleImage).filter(VehicleImage.vehicle_id == vehicle_id)
            )
            existing_images = result.scalars().all()
            
            for image in existing_images:
                await ftp_manager.delete_file(image.file_path)
                await db.delete(image)
            
            # Upload new image
            server_path, file_size = await ftp_manager.upload_file(file.file, file.filename, "image")
            db_image = VehicleImage(
                vehicle_id=vehicle_id,
                file_name=file.filename,
                file_path=server_path,
                file_size=file_size,
            )
            db.add(db_image)
            await db.flush()
            await db.refresh(db_image)

            return {"message": "Image updated successfully", "file_path": server_path}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/test-ftp")
async def test_ftp_connection_endpoint():
    try:
        # Create an FTP connection
        ftp = FTP("148.113.140.18")
        # Use positional arguments instead of keyword arguments
        ftp.login("ftp@apps.remorqueurbranche.com", "U63DWAYZ7P9nnxx")
        
        current_dir = ftp.pwd()
        dir_list = ftp.nlst()
        
        results = {
            "status": "Connected successfully",
            "current_directory": current_dir,
            "directory_contents": dir_list
        }
        
        ftp.quit()
        return results
        
    except Exception as e:
        return {
            "status": "FTP Test failed",
            "error": str(e)
        }
# =================== END FTP =================#
@auth_router.post("/api/v1/login", response_model=LoginResponse)
async def login_endpoint(
    request: LoginRequest, 
    db: AsyncSession = Depends(get_primary_db)
):
    return await process_login(db, request)


@app.get("/api/v1/years", response_model=YearsResponse)
async def get_years(db: AsyncSession = Depends(get_primary_db)):
    years = await get_available_years(db)
    return YearsResponse(years=years)

@app.get("/api/v1/brands/{year}", response_model=BrandsResponse)
async def get_brands(year: int, db: AsyncSession = Depends(get_primary_db)):
    brands = await get_brands_by_year(db, year)
    if not brands:
        raise HTTPException(status_code=404, detail="No brands found for this year")
    return BrandsResponse(year=year, brands=brands)

@app.get("/api/v1/models/{year}/{brand}", response_model=List[str])
async def get_models(
    year: int,
    brand: str,
    db: AsyncSession = Depends(get_primary_db)
):
    models = await get_models_by_year_and_brand(db, year, brand)
    if not models:
        raise HTTPException(status_code=404, detail="No models found for this year and brand")
    return models

@app.get("/api/v1/vehicles", response_model=List[VehicleFilterResponse])
async def get_vehicles(
    params: VehicleFilterParams = Depends(),
    db: AsyncSession = Depends(get_primary_db)
):
    vehicles = await get_vehicle_by_filters(db, params.year, params.brand, params.model)
    if not vehicles:
        raise HTTPException(status_code=404, detail="No vehicles found matching the criteria")
    return vehicles

# Include routers
app.include_router(auth_router)
app.include_router(dispatch_router)
app.include_router(garage_router)
app.include_router(remorqueur_router)
app.include_router(admin_router)
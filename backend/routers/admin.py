from sqlalchemy import func, update, delete
from pydantic import BaseModel, HttpUrl

from core.models import User, APIToken, Base, Meeting
from core.schemas import (
    UserCreate, UserResponse, TokenResponse, UserDetailResponse, 
    UserBase, UserUpdate, MeetingResponse, WebhookUpdate, 
    PaginatedMeetingUserStatResponse, MeetingUserStat
)
from core.database import get_db, init_db
from core.auth import get_current_user

# Logging configuration
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import secrets
import string
import os
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Security, Response
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, attributes
from typing import List, Optional
from datetime import datetime

# App initialization
app = FastAPI(title="Vexa Admin API")

# Security - Reuse logic from bot-manager/auth.py for admin token verification
API_KEY_HEADER = APIKeyHeader(name="X-Admin-API-Key", auto_error=False) # Use a distinct header
USER_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False) # For user-facing endpoints
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN") # Read from environment

async def verify_admin_token(admin_api_key: str = Security(API_KEY_HEADER)):
    """Dependency to verify the admin API token."""
    if not ADMIN_API_TOKEN:
        logger.error("CRITICAL: ADMIN_API_TOKEN environment variable not set!")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin authentication is not configured on the server."
        )
    
    if not admin_api_key or admin_api_key != ADMIN_API_TOKEN:
        logger.warning(f"Invalid admin token provided.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin token."
        )
    logger.info("Admin token verified successfully.")
    # No need to return anything, just raises exception on failure 

# Router setup (all routes require admin token verification)
admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(verify_admin_token)]
)

# New router for user-facing actions
user_router = APIRouter(
    prefix="/user",
    tags=["User"],
    dependencies=[Depends(get_current_user)]
)

# --- Helper Functions --- 
def generate_secure_token(length=40):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))

# --- User Endpoints ---
@user_router.put("/webhook",
             response_model=UserResponse,
             summary="Set user webhook URL",
             description="Set a webhook URL for the authenticated user to receive notifications.")
async def set_user_webhook(
    webhook_update: WebhookUpdate, 
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    """
    Updates the webhook_url for the currently authenticated user.
    The URL is stored in the user's 'data' JSONB field.
    """
    if user.data is None:
        user.data = {}
    
    user.data['webhook_url'] = str(webhook_update.webhook_url)

    # Flag the 'data' field as modified for SQLAlchemy to detect the change
    attributes.flag_modified(user, "data")

    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info(f"Updated webhook URL for user {user.email}")
    
    return UserResponse.from_orm(user)

# --- Admin Endpoints (Copied and adapted from bot-manager/admin.py) --- 
@admin_router.post("/users",
             response_model=UserResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Find or create a user by email",
             responses={
                 status.HTTP_200_OK: {
                     "description": "User found and returned",
                     "model": UserResponse,
                 },
                 status.HTTP_201_CREATED: {
                     "description": "User created successfully",
                     "model": UserResponse,
                 }
             })
async def create_user(user_in: UserCreate, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_in.email))
    existing_user = result.scalars().first()

    if existing_user:
        logger.info(f"Found existing user: {existing_user.email} (ID: {existing_user.id})")
        response.status_code = status.HTTP_200_OK
        return UserResponse.from_orm(existing_user)

    user_data = user_in.dict()
    db_user = User(
        email=user_data['email'],
        name=user_data.get('name'),
        image_url=user_data.get('image_url'),
        max_concurrent_bots=user_data.get('max_concurrent_bots', 1)
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    logger.info(f"Admin created user: {db_user.email} (ID: {db_user.id})")
    return UserResponse.from_orm(db_user)

@admin_router.get("/users", 
            response_model=List[UserResponse], # Use List import
            summary="List all users")
async def list_users(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()
    return [UserResponse.from_orm(u) for u in users]

@admin_router.get("/users/email/{user_email}",
            response_model=UserResponse, # Changed from UserDetailResponse
            summary="Get a specific user by email") # Removed ', including their API tokens'
async def get_user_by_email(user_email: str, db: AsyncSession = Depends(get_db)):
    """Gets a user by their email.""" # Removed ', eagerly loading their API tokens.'
    # Removed .options(selectinload(User.api_tokens))
    result = await db.execute(
        select(User)
        .where(User.email == user_email)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Return the user object. Pydantic will handle serialization using UserDetailResponse.
    return user

@admin_router.get("/users/{user_id}", 
            response_model=UserDetailResponse, # Use the detailed response schema
            summary="Get a specific user by ID, including their API tokens")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Gets a user by their ID, eagerly loading their API tokens."""
    # Eagerly load the api_tokens relationship
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.api_tokens))
    )
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )
        
    # Return the user object. Pydantic will handle serialization using UserDetailResponse.
    return user

@admin_router.patch("/users/{user_id}",
             response_model=UserResponse,
             summary="Update user details",
             description="Update user's name, image URL, or max concurrent bots.")
async def update_user(user_id: int, user_update: UserUpdate, db: AsyncSession = Depends(get_db)):
    """
    Updates a user's details. Only provided fields will be updated.
    """
    # Use update() for an efficient update operation
    update_data = user_update.dict(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update data provided."
        )

    stmt = update(User).where(User.id == user_id).values(**update_data)
    result = await db.execute(stmt)

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    await db.commit()

    # Fetch and return the updated user
    updated_user = await db.get(User, user_id)
    return updated_user

@admin_router.post("/users/{user_id}/tokens", 
             response_model=TokenResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Generate a new API token for a user")
async def create_token_for_user(user_id: int, db: AsyncSession = Depends(get_db)):
    # Use the APIToken model from core.models
    new_token = APIToken(
        token=generate_secure_token(),
        user_id=user_id
    )
    db.add(new_token)
    await db.commit()
    await db.refresh(new_token)
    logger.info(f"Admin created token for user ID: {user_id}")
    return new_token

@admin_router.delete("/tokens/{token_id}", 
                status_code=status.HTTP_204_NO_CONTENT,
                summary="Revoke/Delete an API token by its ID")
async def delete_token(token_id: int, db: AsyncSession = Depends(get_db)):
    """
    Deletes a token by its primary key.
    """
    stmt = delete(APIToken).where(APIToken.id == token_id)
    result = await db.execute(stmt)

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found"
        )
    
    await db.commit()
    logger.info(f"Admin deleted token ID: {token_id}")
    # Return a 204 response, so no response body is needed
    return

# --- Usage Stats Endpoints ---
@admin_router.get("/stats/meetings-users",
            response_model=PaginatedMeetingUserStatResponse,
            summary="Get paginated list of meetings joined with users")
async def list_meetings_with_users(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves a paginated list of all meetings, joined with the user who created them.
    """
    # Query for the total count of meetings
    total_count_result = await db.execute(select(func.count(Meeting.id)))
    total = total_count_result.scalar_one()

    # Query for the paginated items
    query = (
        select(Meeting)
        .join(Meeting.user_links)
        .join(User)
        .options(selectinload(Meeting.user_links).selectinload(UserMeeting.user))
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(query)
    meetings = result.scalars().unique().all()

    # Manually construct the response items
    items = []
    for meeting in meetings:
        # This assumes one user per meeting for this stat, or takes the first one
        if meeting.user_links:
            user_response = UserResponse.from_orm(meeting.user_links[0].user)
            meeting_stat = MeetingUserStat(
                **MeetingResponse.from_orm(meeting).dict(),
                user=user_response
            )
            items.append(meeting_stat)

    return PaginatedMeetingUserStatResponse(total=total, items=items)

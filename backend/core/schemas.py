from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime

class Platform(str, Enum):
    google_meet = "google_meet"
    zoom = "zoom"

    @staticmethod
    def construct_meeting_url(platform: str, native_meeting_id: str) -> Optional[str]:
        if platform == "google_meet":
            return f"https://meet.google.com/{native_meeting_id}"
        # Add other platform URL constructions here
        return None

class MeetingBase(BaseModel):
    platform: Platform
    native_meeting_id: str

class MeetingCreate(MeetingBase):
    bot_name: Optional[str] = None
    language: Optional[str] = None
    task: Optional[str] = None

class MeetingResponse(MeetingBase):
    id: int
    status: str
    bot_container_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    data: Dict[str, Any] = {}
    created_at: datetime
    updated_at: Optional[datetime] = None
    constructed_meeting_url: Optional[str] = None

    class Config:
        orm_mode = True

class BotStatusResponse(BaseModel):
    running_bots: List[Dict[str, Any]]

class TranscriptionSegment(BaseModel):
    start_time: float
    end_time: float
    text: str
    speaker: Optional[str] = None
    language: Optional[str] = None

    class Config:
        orm_mode = True

class TranscriptionResponse(BaseModel):
    segments: List[TranscriptionSegment]

class WebhookPayload(BaseModel):
    platform: Platform
    native_meeting_id: str

# User management schemas
class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    image_url: Optional[str] = None
    max_concurrent_bots: int = 1

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: Optional[str] = None
    image_url: Optional[str] = None
    max_concurrent_bots: Optional[int] = None

class UserResponse(UserBase):
    id: int
    data: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        orm_mode = True

class UserDetailResponse(UserResponse):
    api_tokens: List['TokenResponse'] = []

    class Config:
        orm_mode = True

class TokenResponse(BaseModel):
    id: int
    token: str
    user_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class WebhookUpdate(BaseModel):
    webhook_url: HttpUrl

# Pagination and stats schemas
class MeetingUserStat(BaseModel):
    user_id: int
    meeting_count: int
    total_duration: Optional[float] = None

class PaginatedMeetingUserStatResponse(BaseModel):
    items: List[MeetingUserStat]
    total: int
    page: int
    per_page: int

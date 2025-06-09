from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from core.database import get_db
from core.models import Meeting, User, Transcription as TranscriptionModel, UserMeeting
from core.schemas import MeetingResponse, TranscriptionResponse, Platform, TranscriptionSegment
from core.auth import get_current_user
from vexa_client.client import VexaClient

router = APIRouter()

@router.get("/meetings", response_model=List[MeetingResponse], tags=["Transcripts & Meetings"])
async def get_meetings(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Meeting).join(UserMeeting).filter(UserMeeting.user_id == current_user.id)
    )
    meetings = result.scalars().all()
    return meetings

@router.get("/transcripts/{platform}/{native_meeting_id}", response_model=TranscriptionResponse, tags=["Transcripts & Meetings"])
async def get_transcript(
    request: Request,
    platform: Platform,
    native_meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Meeting)
        .join(UserMeeting)
        .filter(
            Meeting.platform == platform.value,
            Meeting.platform_specific_id == native_meeting_id,
            UserMeeting.user_id == current_user.id
        )
    )
    meeting = result.scalars().first()

    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found or you do not have access")

    if meeting.data.get("is_live", False):
        try:
            infra_client: VexaClient = request.app.state.infra_client
            infra_response = infra_client.get_transcript(
                platform=platform.value,
                native_meeting_id=native_meeting_id
            )
            return infra_response
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Infra API error: {e}")

    # Serve from local cache
    result = await db.execute(
        select(TranscriptionModel)
        .filter(TranscriptionModel.meeting_id == meeting.id)
        .order_by(TranscriptionModel.start_time)
    )
    transcripts = result.scalars().all()
    
    return TranscriptionResponse(
        id=meeting.id,
        platform=meeting.platform,
        native_meeting_id=meeting.native_meeting_id,
        status=meeting.status,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        segments=[TranscriptionSegment.from_orm(t) for t in transcripts]
    ) 
from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from vexa_client.client import VexaClient, VexaClientError
from core.database import get_db
from core.models import Meeting, User, UserMeeting
from core.schemas import MeetingCreate, MeetingResponse, Platform, BotStatusResponse
from core.auth import get_current_user

router = APIRouter(
    prefix="/bots",
    tags=["Bot Management"],
)

@router.post("",
         summary="Request a new bot",
         response_model=MeetingResponse,
         status_code=status.HTTP_201_CREATED)
async def request_bot(
    request: Request,
    meeting_data: MeetingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Meeting).filter(
            Meeting.platform == meeting_data.platform.value,
            Meeting.platform_specific_id == meeting_data.native_meeting_id
        )
    )
    existing_meeting = result.scalars().first()

    if existing_meeting:
        result = await db.execute(
            select(UserMeeting).filter(
                UserMeeting.user_id == current_user.id,
                UserMeeting.meeting_id == existing_meeting.id
            )
        )
        link = result.scalars().first()
        if not link:
            user_meeting_link = UserMeeting(user_id=current_user.id, meeting_id=existing_meeting.id)
            db.add(user_meeting_link)
            await db.commit()
        return existing_meeting

    try:
        infra_client: VexaClient = request.app.state.infra_client
        infra_response = infra_client.request_bot(
            platform=meeting_data.platform.value,
            native_meeting_id=meeting_data.native_meeting_id,
        )
    except VexaClientError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Infra API error: {e}")

    new_meeting = Meeting(
        platform=meeting_data.platform.value,
        platform_specific_id=meeting_data.native_meeting_id,
        status="active",
        data={"is_live": True, "infra_meeting_id": infra_response.get("id")}
    )
    db.add(new_meeting)
    await db.commit()
    await db.refresh(new_meeting)

    user_meeting_link = UserMeeting(user_id=current_user.id, meeting_id=new_meeting.id)
    db.add(user_meeting_link)
    await db.commit()

    return new_meeting

@router.delete("/{platform}/{native_meeting_id}",
            summary="Stop a bot",
            status_code=status.HTTP_202_ACCEPTED)
async def stop_bot(
    request: Request,
    platform: Platform,
    native_meeting_id: str,
    current_user: User = Depends(get_current_user)
):
    try:
        infra_client: VexaClient = request.app.state.infra_client
        response = infra_client.stop_bot(
            platform=platform.value,
            native_meeting_id=native_meeting_id
        )
        return response
    except VexaClientError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Infra API error: {e}")

@router.get("/status",
         summary="Get status of running bots",
         response_model=BotStatusResponse)
async def get_bots_status(request: Request, current_user: User = Depends(get_current_user)):
    try:
        infra_client: VexaClient = request.app.state.infra_client
        status_list = infra_client.get_running_bots_status()
        return {"running_bots": status_list}
    except VexaClientError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Infra API error: {e}") 
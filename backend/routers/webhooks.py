from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import attributes
from pydantic import BaseModel
from core.database import get_db
from core.models import Meeting, Transcription as TranscriptionModel
from core.schemas import Platform, WebhookPayload
from vexa_client.client import VexaClient, VexaClientError

router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
)

@router.post("/meeting-finished", include_in_schema=False)
async def handle_webhook(request: Request, payload: WebhookPayload, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Meeting).filter(
            Meeting.platform == payload.platform.value,
            Meeting.platform_specific_id == payload.native_meeting_id
        )
    )
    meeting = result.scalars().first()

    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    try:
        infra_client: VexaClient = request.app.state.infra_client
        final_transcript = infra_client.get_transcript(
            platform=payload.platform.value,
            native_meeting_id=payload.native_meeting_id
        )

        for segment in final_transcript.get("segments", []):
            db_segment = TranscriptionModel(
                meeting_id=meeting.id,
                start_time=segment.get("start_time"),
                end_time=segment.get("end_time"),
                text=segment.get("text"),
                speaker=segment.get("speaker"),
                language=segment.get("language"),
            )
            db.add(db_segment)

        if meeting.data is None:
            meeting.data = {}
        
        meeting.data['is_live'] = False
        meeting.data['transcript_cached'] = True
        attributes.flag_modified(meeting, "data")
        
        await db.commit()

        infra_client.delete_meeting(
            platform=payload.platform.value,
            native_meeting_id=payload.native_meeting_id
        )

    except VexaClientError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Infra API Error: {e}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing webhook: {e}")

    return {"message": "Webhook processed successfully"} 
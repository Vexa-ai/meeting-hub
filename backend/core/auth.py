from fastapi import Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.models import User, APIToken

api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_current_user(
    api_key: str = Security(api_key_scheme), 
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to verify user API key and return user object."""
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API Key")

    result = await db.execute(
        select(APIToken).where(APIToken.token == api_key).options(selectinload(APIToken.user))
    )
    db_token = result.scalars().first()

    if not db_token or not db_token.user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key")
    
    return db_token.user

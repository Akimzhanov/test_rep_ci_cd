from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from apps.users.models import Users, Session
from apps.users.auth_jwt import decode_token,create_token
from datetime import timedelta
from apps.database import get_db_session
from fastapi import APIRouter

router = APIRouter()

@router.websocket("/secure")
async def websocket_secure(websocket: WebSocket, db: AsyncSession = Depends(get_db_session)):
    await websocket.accept()

    # 1. Получаем оба токена
    access_token = websocket.query_params.get("access_token")
    refresh_token = websocket.query_params.get("refresh_token")

    if not access_token or not refresh_token:
        await websocket.close(code=1008, reason="Missing tokens")
        return

    # 2. Пробуем расшифровать access_token
    payload = await decode_token(access_token)
    
    # 3. Если access_token истёк, пробуем обновить через refresh_token
    if not payload or "sub" not in payload:
        refresh_payload = await decode_token(refresh_token)
        if not refresh_payload or "sub" not in refresh_payload:
            await websocket.close(code=1008, reason="Invalid refresh token")
            return

        # Проверяем сессию
        stmt = select(Session).where(Session.refresh_token == refresh_token, Session.is_active == True)
        result = await db.execute(stmt)
        session = result.scalars().first()

        if not session:
            await websocket.close(code=1008, reason="Session not found or expired")
            return

        # Выдаём новый access_token
        new_access_token = await create_token({"sub": refresh_payload["sub"]}, expires_delta=timedelta(minutes=5))
        payload = refresh_payload

        await websocket.send_json({
            "type": "new_token",
            "access_token": new_access_token
        })

    # 4. Получаем пользователя из access_token или обновлённого payload
    stmt = select(Users).where(Users.username == payload["sub"])
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        await websocket.close(code=1008, reason="User not found")
        return

    await websocket.send_text(f"✅ Authenticated as {user.username}")

    try:
        while True:
            msg = await websocket.receive_text()
            await websocket.send_text(f"Echo: {msg}")
    except WebSocketDisconnect:
        print(f"🔌 Disconnected: {user.username}")
    except Exception as e:
        print(f"⚠️ Error: {e}")

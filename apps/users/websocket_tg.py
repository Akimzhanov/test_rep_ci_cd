from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,update
from apps.users.models import *
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



connections: dict[int, list[WebSocket]] = {}

@router.websocket("/chats/{chat_id}")
async def websocket_chat(chat_id: int, websocket: WebSocket, db: AsyncSession = Depends(get_db_session)):
    await websocket.accept()

    # 🔐 Получение токенов
    access_token = websocket.query_params.get("access_token")
    refresh_token = websocket.query_params.get("refresh_token")

    if not access_token or not refresh_token:
        await websocket.close(code=1008, reason="Missing tokens")
        return

    payload = await decode_token(access_token)
    if not payload or "sub" not in payload:
        refresh_payload = await decode_token(refresh_token)
        if not refresh_payload or "sub" not in refresh_payload:
            await websocket.close(code=1008, reason="Invalid refresh token")
            return

        session_q = select(Session).where(Session.refresh_token == refresh_token, Session.is_active == True)
        session_result = await db.execute(session_q)
        session = session_result.scalars().first()
        if not session:
            await websocket.close(code=1008, reason="Session not found or expired")
            return

        new_access_token = await create_token({"sub": refresh_payload["sub"]}, expires_delta=timedelta(minutes=5))
        payload = refresh_payload
        await websocket.send_json({"type": "new_token", "access_token": new_access_token})

    # 🔍 Получаем пользователя
    user_q = select(Users).where(Users.username == payload["sub"])
    result = await db.execute(user_q)
    user = result.scalars().first()
    if not user:
        await websocket.close(code=1008, reason="User not found")
        return

    # 👥 Проверка, что пользователь участник чата
    is_participant_q = select(ChatUser).where(ChatUser.chat_id == chat_id, ChatUser.user_id == user.id)
    participant_result = await db.execute(is_participant_q)
    if not participant_result.scalars().first():
        await websocket.close(code=1008, reason="You are not in this chat")
        return

    # ✅ Авторизован
    connections.setdefault(chat_id, []).append(websocket)
    await websocket.send_text(f"✅ Connected to chat #{chat_id} as {user.username}")

    # 📜 Отправляем историю сообщений
    history_q = select(Messages).where(Messages.chat_id == chat_id).order_by(Messages.timestamp)
    result = await db.execute(history_q)
    history = result.scalars().all()
    await websocket.send_json([
        {
            "type": "history",
            "id": m.id,
            "chat_id": m.chat_id,
            "sender_id": m.sender_id,
            "text": m.text,
            "timestamp": m.timestamp.isoformat(),
            "is_read": m.is_read
        }
        for m in history
    ])

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "send":
                text = data.get("text")
                message = Messages(chat_id=chat_id, sender_id=user.id, text=text)
                db.add(message)
                await db.commit()
                await db.refresh(message)

                history_q = select(Messages).where(Messages.chat_id == chat_id).order_by(Messages.timestamp)
                result = await db.execute(history_q)
                history = result.scalars().all()
                await websocket.send_json([
                {
                    "type": "history",
                    "id": m.id,
                    "chat_id": m.chat_id,
                    "sender_id": m.sender_id,
                    "text": m.text,
                    "timestamp": m.timestamp.isoformat(),
                    "is_read": m.is_read
                }
                for m in history])
                # 🔁 Рассылаем обоим участникам
                # payload = {
                #     "type": "message",
                #     "id": message.id,
                #     "chat_id": message.chat_id,
                #     "sender_id": message.sender_id,
                #     "text": message.text,
                #     "timestamp": message.timestamp.isoformat(),
                #     "is_read": message.is_read
                # }

                # for ws in connections.get(chat_id, []):
                #     await ws.send_json(payload)

            elif data.get("type") == "read":
                await db.execute(
                    update(Messages)
                    .where(Messages.chat_id == chat_id, Messages.sender_id != user.id)
                    .values(is_read=True)
                )
                await db.commit()

    except WebSocketDisconnect:
        connections[chat_id].remove(websocket)
        print(f"🔌 Disconnected: {user.username}")
    except Exception as e:
        print(f"⚠️ Error: {e}")

from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,update
from apps.users.models import *
from apps.users.auth_jwt import decode_token,create_token
from datetime import timedelta
from apps.database import get_db_session
from fastapi import APIRouter

router = APIRouter()

connections: dict[int, list[WebSocket]] = {}
user_last_message: dict[int, str] = {}

@router.websocket("/chats/{chat_id}")
async def websocket_chat(chat_id: int, websocket: WebSocket, db: AsyncSession = Depends(get_db_session)):
    await websocket.accept()

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

    user_q = select(Users).where(Users.username == payload["sub"])
    result = await db.execute(user_q)
    user = result.scalars().first()
    if not user:
        await websocket.close(code=1008, reason="User not found")
        return

    is_participant_q = select(ChatUser).where(ChatUser.chat_id == chat_id, ChatUser.user_id == user.id)
    participant_result = await db.execute(is_participant_q)
    if not participant_result.scalars().first():
        await websocket.close(code=1008, reason="You are not in this chat")
        return

    connections.setdefault(chat_id, []).append(websocket)
    await websocket.send_text(f"Connected to chat #{chat_id} as {user.username}")

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
                text = data.get("text", "").strip()

                if not text:
                    await websocket.send_json({"type": "error", "message": "Message is too short"})
                    continue

                if user_last_message.get(user.id) == text:
                    await websocket.send_json({"type": "error", "message": "Duplicate message detected"})
                    continue

                user_last_message[user.id] = text

                message = Messages(chat_id=chat_id, sender_id=user.id, text=text)
                db.add(message)
                await db.commit()
                await db.refresh(message)

                payload = {
                    "type": "message",
                    "id": message.id,
                    "chat_id": message.chat_id,
                    "sender_id": message.sender_id,
                    "text": message.text,
                    "timestamp": message.timestamp.isoformat(),
                    "is_read": message.is_read
                }

                for ws in connections.get(chat_id, []):
                    await ws.send_json(payload)

            elif data.get("type") == "read":
                await db.execute(
                    update(Messages)
                    .where(Messages.chat_id == chat_id, Messages.sender_id != user.id)
                    .values(is_read=True)
                )
                await db.commit()

    except WebSocketDisconnect:
        if websocket in connections.get(chat_id, []):
            connections[chat_id].remove(websocket)
            if not connections[chat_id]:  
                del connections[chat_id]

        # Очищаем последнее сообщение пользователя
        user_last_message.pop(user.id, None)

        print(f"Disconnected: {user.username}")

    except Exception as e:
        print(f"Error: {e}")





group_connections: dict[int, list[WebSocket]] = {}
group_last_message: dict[int, dict[int, str]] = {}  

@router.websocket("/groups/{group_id}")
async def websocket_group_chat(group_id: int, websocket: WebSocket, db: AsyncSession = Depends(get_db_session)):
    await websocket.accept()

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

    user_q = select(Users).where(Users.username == payload["sub"])
    result = await db.execute(user_q)
    user = result.scalars().first()
    if not user:
        await websocket.close(code=1008, reason="User not found")
        return

    is_member_q = select(GroupUser).where(GroupUser.group_id == group_id, GroupUser.user_id == user.id)
    member_result = await db.execute(is_member_q)
    if not member_result.scalars().first():
        await websocket.close(code=1008, reason="You are not in this group")
        return

    group_connections.setdefault(group_id, []).append(websocket)
    group_last_message.setdefault(group_id, {}) 

    await websocket.send_json({
        "type": "connect",
        "message": f"Connected to group #{group_id} as {user.username}"
    })

    group = select(Groups).where(Groups.id == group_id)
    result = await db.execute(group)
    group_ = result.scalars().first()
    chat = select(Chats).where(Chats.title == group_.title, Chats.chats_type == ChatType.GROUP)
    result = await db.execute(chat)
    group_chat = result.scalars().first()
    history_q = select(Messages).where(Messages.chat_id == group_chat.id).order_by(Messages.timestamp)
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
                text = data.get("text", "").strip()

                if not text:
                    await websocket.send_json({"type": "error", "message": "Message is too short"})
                    continue

                last_message = group_last_message[group_id].get(user.id)
                if last_message == text:
                    await websocket.send_json({"type": "error", "message": "Duplicate message detected"})
                    continue

                group_last_message[group_id][user.id] = text

                message = Messages(chat_id=group_chat.id, sender_id=user.id, text=text)
                db.add(message)
                await db.commit()
                await db.refresh(message)

                payload = {
                    "type": "message",
                    "id": message.id,
                    "chat_id": message.chat_id,
                    "sender_id": message.sender_id,
                    "text": message.text,
                    "timestamp": message.timestamp.isoformat(),
                    "is_read": message.is_read
                }

                for ws in group_connections.get(group_id, []):
                    await ws.send_json(payload)

            elif data.get("type") == "read":
                await db.execute(
                    update(Messages)
                    .where(Messages.chat_id == group_id, Messages.sender_id != user.id)
                    .values(is_read=True)
                )
                await db.commit()

    except WebSocketDisconnect as e:
        if websocket in group_connections.get(group_id, []):
            group_connections[group_id].remove(websocket)
        print(f"Disconnected from group {group_id}: {user.username} (code={e.code})")

        if not group_connections[group_id]:
            del group_connections[group_id]
            del group_last_message[group_id]

    except Exception as e:
        print(f"Error in group chat: {e}")


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from apps.database import get_db_session
from apps.users.models import Chats, Users, ChatUser, ChatType, Messages
from apps.chats.schema import *
from apps.users.user_router import get_current_user

router = APIRouter()

@router.post("/chats/create", response_model=ChatResponse)
async def create_chat(
    chat_data: ChatCreate,
    current_user: Users = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    chat = Chats(title=chat_data.title, chats_type=chat_data.chats_type)
    db.add(chat)
    await db.flush()  # Получаем chat.id

    # Добавляем создателя в чат
    chat_user = ChatUser(chat_id=chat.id, user_id=current_user.id)
    db.add(chat_user)

    # Добавляем остальных участников
    for uid in chat_data.user_ids:
        db.add(ChatUser(chat_id=chat.id, user_id=uid))

    await db.commit()
    await db.refresh(chat)
    return chat

@router.get("/chats", response_model=list[ChatResponse])
async def list_user_chats(
    current_user: Users = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    query = select(Chats).join(ChatUser).where(ChatUser.user_id == current_user.id)
    result = await db.execute(query)
    return result.scalars().all()




@router.post("/messages/send", response_model=MessageResponse)
async def send_message(
    payload: MessageCreate,
    current_user: Users = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    # Проверка, что чат существует и пользователь является участником
    chat_q = await db.execute(select(ChatUser).where(
        ChatUser.chat_id == payload.chat_id,
        ChatUser.user_id == current_user.id
    ))
    if not chat_q.scalars().first():
        raise HTTPException(status_code=403, detail="You are not in this chat")

    msg = Messages(
        chat_id=payload.chat_id,
        sender_id=current_user.id,
        text=payload.text
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg

@router.get("/messages/{chat_id}", response_model=list[MessageResponse])
async def get_messages(chat_id: int, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(
        select(Messages).where(Messages.chat_id == chat_id).order_by(Messages.timestamp)
    )
    return result.scalars().all()

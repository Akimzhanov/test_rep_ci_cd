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



@router.post("/create_private_chat")
async def create_private_chat(user1_id: int, user2_id: int, db: AsyncSession = Depends(get_db_session)):
    if user1_id == user2_id:
        raise HTTPException(status_code=400, detail="Cannot create chat with self")

    # Убедимся, что оба пользователя существуют
    users_stmt = select(Users).where(Users.id.in_([user1_id, user2_id]))
    result = await db.execute(users_stmt)
    users_found = result.scalars().all()
    if len(users_found) != 2:
        raise HTTPException(status_code=404, detail="One or both users not found")

    # Проверим, есть ли уже приватный чат между этими двумя пользователями
    chat_stmt = select(Chats).where(Chats.chats_type == ChatType.PRIVATE)
    chat_result = await db.execute(chat_stmt)
    private_chats = chat_result.scalars().all()

    for chat in private_chats:
        participant_stmt = select(ChatUser).where(ChatUser.chat_id == chat.id)
        result = await db.execute(participant_stmt)
        participants = [cu.user_id for cu in result.scalars().all()]
        if set(participants) == set([user1_id, user2_id]):
            return {"detail": "Chat already exists", "chat_id": chat.id}

    # Создаем новый чат
    new_chat = Chats(
        title=f"Private Chat {user1_id}-{user2_id}",
        chats_type=ChatType.PRIVATE
    )
    db.add(new_chat)
    await db.commit()
    await db.refresh(new_chat)

    # Добавим пользователей в таблицу chat_user
    user_links = [
        ChatUser(chat_id=new_chat.id, user_id=user1_id),
        ChatUser(chat_id=new_chat.id, user_id=user2_id)
    ]
    db.add_all(user_links)
    await db.commit()

    return {"detail": "Private chat created", "chat_id": new_chat.id}


@router.get("/history/{chat_id}", response_model=list[MessageResponse])
async def get_chat_history(
    chat_id: int,
    current_user: Users = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    # Проверяем, что чат существует
    chat_stmt = select(Chats).where(Chats.id == chat_id)
    result = await db.execute(chat_stmt)
    chat = result.scalars()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Проверка участия
    user_stmt = select(ChatUser).where(ChatUser.chat_id == chat_id, ChatUser.user_id == current_user.id)
    result = await db.execute(user_stmt)
    user_chat = result.scalars()
    if not user_chat:
        raise HTTPException(status_code=403, detail="You are not a participant of this chat")

    # Возвращаем историю сообщений
    messages_stmt = select(Messages).where(Messages.chat_id == chat_id).order_by(Messages.timestamp.desc())
    result = await db.execute(messages_stmt)
    messages = result.scalars().all()

    return messages

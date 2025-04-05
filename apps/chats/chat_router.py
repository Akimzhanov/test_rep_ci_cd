from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from apps.database import get_db_session
from apps.users.models import *
from apps.chats.schema import *
from apps.users.user_router import get_current_user
from sqlalchemy.orm import joinedload

router = APIRouter()

@router.post("/chats/create", response_model=ChatResponse)
async def create_chat(
    chat_data: ChatCreate,
    current_user: Users = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    chat = Chats(title=chat_data.title, chats_type=chat_data.chats_type)
    db.add(chat)
    await db.flush()  

    chat_user = ChatUser(chat_id=chat.id, user_id=current_user.id)
    db.add(chat_user)

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
    query = select(Chats).join(ChatUser).where(ChatUser.user_id == current_user.id).distinct()
    result = await db.execute(query)
    return result.scalars().all()



@router.post("/create_private_chat")
async def create_private_chat(user1_id: int, user2_id: int,current_user: Users = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    if user1_id == user2_id:
        raise HTTPException(status_code=400, detail="Cannot create chat with self")

    users_stmt = select(Users).where(Users.id.in_([user1_id, user2_id]))
    result = await db.execute(users_stmt)
    users_found = result.scalars().all()
    if len(users_found) != 2:
        raise HTTPException(status_code=404, detail="One or both users not found")

    chat_stmt = select(Chats).where(Chats.chats_type == ChatType.PRIVATE)
    chat_result = await db.execute(chat_stmt)
    private_chats = chat_result.scalars().all()

    for chat in private_chats:
        participant_stmt = select(ChatUser).where(ChatUser.chat_id == chat.id)
        result = await db.execute(participant_stmt)
        participants = [cu.user_id for cu in result.scalars().all()]
        if set(participants) == set([user1_id, user2_id]):
            return {"detail": "Chat already exists", "chat_id": chat.id}

    new_chat = Chats(
        title=f"Private Chat {user1_id}-{user2_id}",
        chats_type=ChatType.PRIVATE
    )
    db.add(new_chat)
    await db.commit()
    await db.refresh(new_chat)

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
    limit: int = Query(20, ge=1, le=100),      
    offset: int = Query(0, ge=0),               
    current_user: Users = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    chat_stmt = select(Chats).where(Chats.id == chat_id)
    result = await db.execute(chat_stmt)
    chat = result.scalars().first() 
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    user_stmt = select(ChatUser).where(ChatUser.chat_id == chat_id, ChatUser.user_id == current_user.id)
    result = await db.execute(user_stmt)
    user_chat = result.scalars().first()
    if not user_chat:
        raise HTTPException(status_code=403, detail="You are not a participant of this chat")

    messages_stmt = (
        select(Messages)
        .where(Messages.chat_id == chat_id)
        .order_by(Messages.timestamp.asc())  
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(messages_stmt)
    messages = result.scalars().all()

    return messages



@router.post("/groups")
async def create_group(payload: GroupCreateSchema, current_user: Users = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    new_group = Groups(
        title=payload.title,
        creator_id=payload.creator_id,
    )
    db.add(new_group)
    await db.commit()
    await db.refresh(new_group)
    users_ids = [payload.creator_id] + payload.user_ids

    creator = GroupUser(group_id=new_group.id, user_id=payload.creator_id)
    db.add(creator)
    for user_id in payload.user_ids:
        group_user = GroupUser(group_id=new_group.id, user_id=user_id)
        db.add(group_user)

    new_chat = Chats(
        title=payload.title,   
        chats_type=ChatType.GROUP
    )
    db.add(new_chat)

    await db.commit()
    await db.refresh(new_chat)

    for user_id in users_ids:
        db.add(ChatUser(chat_id=new_chat.id, user_id=user_id))

    await db.commit()
    return {"detail": "Group and chat created", "group_id": new_group.id}

@router.get("/groups", response_model=List[GroupResponseSchema])
async def list_groups(current_user: Users = Depends(get_current_user),db: AsyncSession = Depends(get_db_session)):
    query = select(Groups).options(joinedload(Groups.users)).where(Groups.users.any(id=current_user.id))
    result = await db.execute(query)
    return result.unique().scalars().all()


@router.get("/groups/{group_id}/", response_model=GroupResponseSchema)
async def get_group(group_id: int, db: AsyncSession = Depends(get_db_session)):
    query = (
        select(Groups)
        .options(joinedload(Groups.users)) 
        .where(Groups.id == group_id)
    )
    result = await db.execute(query)
    group = result.scalars().first()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group

@router.post("/groups/{group_id}/add_user")
async def add_user_to_group(group_id: int, payload: AddUserToGroupSchema, current_user: Users = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(Groups).where(Groups.id == group_id))
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    existing = await db.execute(
        select(GroupUser).where(GroupUser.group_id == group_id, GroupUser.user_id == payload.user_id)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="User already in group")

    db.add(GroupUser(group_id=group_id, user_id=payload.user_id))
    await db.commit()

    return {"detail": "User added to group"}



@router.delete("/groups/{group_id}/remove_user/{user_id}")
async def remove_user_from_group(group_id: int, user_id: int, current_user: Users = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    stmt = select(GroupUser).where(GroupUser.group_id == group_id, GroupUser.user_id == user_id)
    result = await db.execute(stmt)
    group_user = result.scalars().first()

    if not group_user:
        raise HTTPException(status_code=404, detail="User not in group")

    await db.delete(group_user)
    await db.commit()
    return {"detail": "User removed from group"}

from pydantic import BaseModel
from typing import List
from datetime import datetime
from apps.users.models import ChatType

class ChatCreate(BaseModel):
    title: str
    chats_type: ChatType
    user_ids: List[int]

class ChatResponse(BaseModel):
    id: int
    title: str
    chats_type: ChatType

    class Config:
        orm_mode = True

class MessageCreate(BaseModel):
    chat_id: int
    text: str

class MessageResponse(BaseModel):
    id: int
    chat_id: int
    sender_id: int
    text: str
    timestamp: datetime
    is_read: bool

    class Config:
        orm_mode = True

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        orm_mode = True


class GroupCreateSchema(BaseModel):
    title: str
    creator_id: int
    user_ids: List[int]

class GroupResponseSchema(BaseModel):
    id: int
    title: str
    creator_id: int
    users: List[UserResponse] = []  

    class Config:
        orm_mode = True


class AddUserToGroupSchema(BaseModel):
    user_id: int

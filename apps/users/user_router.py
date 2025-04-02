from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from apps.database import get_db_session
from apps.users.models import Users, Session
from datetime import timedelta
from apps.users.schema import *
from apps.users.auth_jwt import hash_password, verify_password, create_token, decode_token
from fastapi import Request

router = APIRouter()


async def extract_client_info(request: Request):
    user_agent = request.headers.get("user-agent")
    ip = request.client.host
    return user_agent, ip


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db_session)) -> Users:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = auth.split(" ")[1]
    payload = await decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = select(Users).where(Users.username == payload["sub"])
    result = await db.execute(user)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.post("/register", response_model=UserSchema)
async def register(payload: UserSchema, db: AsyncSession = Depends(get_db_session)):
    try:
        user = select(Users).where(Users.username == payload.username)
        result = await db.execute(user)
        existing_user = result.scalars().first()

        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")

        new_user = Users(
            username=payload.username,
            email=payload.email,
            password= await hash_password(payload.password)
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return new_user
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
async def login(payload: UserLoginSchema, request: Request, db: AsyncSession = Depends(get_db_session)):
    user = select(Users).where(Users.username == payload.username)
    result = await db.execute(user)
    user = result.scalars().first()

    if not user or not await verify_password(payload.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = await create_token({"sub": user.username}, expires_delta=timedelta(minutes=5))
    refresh_token = await create_token({"sub": user.username}, expires_delta=timedelta(days=30))

    user_agent, ip = await extract_client_info(request)

    new_session = Session(
        user_id=user.id,
        refresh_token=refresh_token,
        user_agent=user_agent,
        ip_address=ip
    )
    db.add(new_session)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }


# @router.post("/refresh")
# async def refresh_token(request: Request, db: AsyncSession = Depends(get_db_session)):
#     try:
#         body = await request.json()
#         token = body.get("refresh_token")
#         if not token:
#             raise HTTPException(status_code=400, detail="Missing refresh_token")
#     except Exception:
#         raise HTTPException(status_code=400, detail="Invalid JSON")

#     payload = await decode_token(token)
#     if not payload:
#         raise HTTPException(status_code=401, detail="Invalid refresh token")

#     sessions_user = select(Session).where(Session.refresh_token == token, Session.is_active == True)
#     result = await db.execute(sessions_user)
#     session = result.scalars().first()

#     if not session:
#         raise HTTPException(status_code=403, detail="Session not found or expired")

#     access_token = await create_token({"sub": payload["sub"]}, expires_delta=timedelta(days=1))

#     return {"access_token": access_token}


@router.get("/devices")
async def list_devices(current_user: Users = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    sessions_user = select(Session).where(Session.user_id == current_user.id, Session.is_active == True)
    result = await db.execute(sessions_user)
    sessions = result.scalars().all()

    return [
        {
            "id": s.id,
            "ip": s.ip_address,
            "user_agent": s.user_agent,
            "created_at": s.created_at
        } for s in sessions
    ]

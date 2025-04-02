
from fastapi import FastAPI
from apps.users import user_router,websocket_tg
from apps.chats import chat_router
app = FastAPI()

app.include_router(user_router.router, prefix="/api", tags=['users'])
app.include_router(chat_router.router, prefix="/api", tags=['chats'])
app.include_router(websocket_tg.router, prefix="/ws", tags=['users_socket'])


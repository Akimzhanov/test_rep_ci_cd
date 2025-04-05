
from fastapi import FastAPI
from apps.users import user_router,websocket_tg
from apps.chats import chat_router
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)



app.include_router(user_router.router, prefix="/api", tags=['users'])
app.include_router(chat_router.router, prefix="/api", tags=['chats'])
app.include_router(websocket_tg.router, prefix="/ws", tags=['users_socket'])
app.mount("/static", StaticFiles(directory="static", html=True), name="static")
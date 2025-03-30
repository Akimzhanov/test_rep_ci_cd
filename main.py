
from fastapi import FastAPI
from apps.users import user_router
app = FastAPI()

app.include_router(user_router.router, prefix="/api", tags=['users'])



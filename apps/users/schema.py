from pydantic import BaseModel


class UserSchema(BaseModel):
    id: int = None
    username: str
    email: str
    password: str

    
    class Config:
        orm_mode = True


class UserLoginSchema(BaseModel):
    username: str
    password: str
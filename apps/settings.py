from pydantic_settings import SettingsConfigDict, BaseSettings

from apps.users.auth_jwt import SECRET_KEY  



class Settings(BaseSettings):
    DB_NAME: str
    DB_USER: str
    DB_PORT: int
    DB_HOST: str
    DB_PASS: str

    SECRET_KEY: str
    HASH: str

    @property
    def DATABASE_URL_asyncpg(self):
        return f'postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'
    

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

print(1)
print(2)

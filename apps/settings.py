from pydantic_settings import SettingsConfigDict, BaseSettings  



class Settings(BaseSettings):
    DB_NAME: str
    DB_USER: str
    DB_PORT: int
    DB_HOST: str
    DB_PASS: str

    @property
    def DATABASE_URL_asyncpg(self):
        return f'postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'
    

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

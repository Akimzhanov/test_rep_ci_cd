Проект: Личный и групповой чат на FastAPI с авторизацией через JWT, WebSocket сообщениями и хранением в PostgreSQL.

Технологии

FastAPI — backend сервер
WebSockets — для обмена сообщениями в реальном времени
PostgreSQL — база данных
Alembic — миграции БД
Docker + Docker Compose — контейнеризация
SQLAlchemy — ORM
asyncpg — асинхронный драйвер для PostgreSQL
passlib — хеширование паролей
JWT — авторизация


Пример .env

DB_NAME=tg_chat
DB_USER=asyl
DB_PORT=5432
DB_HOST=db
DB_PASS=1

SECRET_KEY=your_secret_key
HASH=HS256


Структура проекта:

apps/
  ├── chats/             
  ├── users/             
  ├── migrations/        
static/                  
main.py                  
Dockerfile               
docker-compose.yml       
requirements.txt         
alembic.ini              
.env                     



Старт проекта:
Запустить команду в корневой директории

alembic revision --autogenerate
alembic upgrade head

docker-compose up --build



Сервер FastAPI будет доступен на: http://localhost:8000

Swagger документация API: http://localhost:8000/docs



Все API работают через авторизацию JWT, кроме регистрации и авторизации.

Есть 3 страницы:
Где localhost нужно использовать IP ПК.


http://localhost:8000/static/login.html  - страница авторизации для личных и групповых чатов

http://10.1.5.107:8000/static/group.html  - страница группового чата с списком групп авторизованного пользователя, 
работает вебсокет для обмена сообщения в настоящем времени

http://10.1.5.107:8000/static/index.html  -  страница личных чатов пользователя, работает вебсокет 
для обмена сообщения в настоящем времени
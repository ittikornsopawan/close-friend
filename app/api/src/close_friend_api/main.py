from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from close_friend_api.config import settings
from close_friend_api.routers import conversations, health, personas

app = FastAPI(title="Close Friend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(conversations.router)
app.include_router(personas.router)

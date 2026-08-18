import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get(
    "CF_WORKER_DATABASE_URL",
    "postgresql+psycopg://close_friend:close_friend@localhost:5432/close_friend",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

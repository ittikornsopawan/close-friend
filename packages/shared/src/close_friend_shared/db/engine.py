import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Alembic and the seed script both run as one-shot tooling against the same
# Postgres instance app/api and app/worker use — CF_API_DATABASE_URL is
# reused here rather than inventing a third env var name for the same value.
DATABASE_URL = os.environ.get(
    "CF_API_DATABASE_URL",
    "postgresql+psycopg://close_friend:close_friend@localhost:5432/close_friend",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

from celery import Celery

from close_friend_api.config import settings

# Producer-only: sends tasks by name onto the shared Redis broker without
# importing app/worker's Celery app or task functions, keeping the two
# services deployable independently. No result backend — the API doesn't
# read task results; it reads message status from Redis itself.
celery_client = Celery("close_friend_api_producer", broker=settings.redis_url)

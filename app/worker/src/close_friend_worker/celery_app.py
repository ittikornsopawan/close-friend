from celery import Celery

from close_friend_worker.config import REDIS_URL

celery_app = Celery("close_friend_worker", broker=REDIS_URL, backend=REDIS_URL)
celery_app.autodiscover_tasks(["close_friend_worker"])

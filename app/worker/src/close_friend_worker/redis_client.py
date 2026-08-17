import redis

from close_friend_worker.config import REDIS_URL

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

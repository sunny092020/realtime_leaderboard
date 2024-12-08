from typing import Dict, List, Tuple, Union

from redis import Redis


class RedisOperations:
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client

    def update_leaderboard_score(self, quiz_id: str, user_id: str, score: int) -> None:
        """Update a user's score in the Redis leaderboard"""
        redis_key = f"quiz:{quiz_id}:leaderboard"
        self.redis_client.zadd(redis_key, {user_id: score})

    def get_leaderboard(self, quiz_id: str) -> List[Dict[str, Union[str, float]]]:
        """Get top 10 scores from the leaderboard"""
        redis_key = f"quiz:{quiz_id}:leaderboard"
        # Get top 10 scores
        leaderboard_data: List[Tuple[str, float]] = self.redis_client.zrevrange(
            redis_key, 0, 9, withscores=True
        )
        return [
            {"user_id": user_id, "score": score} for user_id, score in leaderboard_data
        ]

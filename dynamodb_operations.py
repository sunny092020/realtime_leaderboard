from datetime import datetime
from typing import Dict, Optional

from boto3.client import BaseClient
from loguru import logger


class DynamoDBOperations:
    def __init__(self, dynamodb_client: BaseClient):
        self.dynamodb = dynamodb_client
        self.table_name = "quiz_scores"

    def save_score(self, user_id: str, quiz_id: str, score: int) -> None:
        """Save a user's quiz score to DynamoDB"""
        try:
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    "user_id": {"S": user_id},
                    "quiz_id": {"S": quiz_id},
                    "score": {"N": str(score)},
                    "timestamp": {"S": datetime.utcnow().isoformat()},
                },
            )
        except Exception as e:
            logger.error(f"Error saving score to DynamoDB: {e}")
            raise

    def get_user_score(self, user_id: str, quiz_id: str) -> Optional[int]:
        """Retrieve a user's score for a specific quiz"""
        try:
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={"user_id": {"S": user_id}, "quiz_id": {"S": quiz_id}},
            )
            if "Item" in response:
                return int(response["Item"]["score"]["N"])
            return 0
        except Exception as e:
            logger.error(f"Error retrieving score from DynamoDB: {e}")
            return 0

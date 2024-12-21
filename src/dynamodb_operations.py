from datetime import datetime
from typing import Dict, Optional
import boto3
from loguru import logger


class DynamoDBOperations:
    def __init__(self, dynamodb_client: 'boto3.client.BaseClient'):
        self.dynamodb = dynamodb_client
        self.table_name = "quiz_scores"
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Ensure the DynamoDB table exists, create it if it doesn't"""
        try:
            self.dynamodb.describe_table(TableName=self.table_name)
            logger.info(f"Table {self.table_name} exists")
        except self.dynamodb.exceptions.ResourceNotFoundException:
            logger.info(f"Creating table {self.table_name}")
            self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'quiz_id', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                    {'AttributeName': 'quiz_id', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            # Wait for table to be created
            waiter = self.dynamodb.get_waiter('table_exists')
            waiter.wait(TableName=self.table_name)
            logger.info(f"Table {self.table_name} created successfully")

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

import os
import boto3
import redis
from kafka.admin import KafkaAdminClient
from kafka import KafkaConsumer

# Redis configuration
def get_redis_client():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True,
    )

# DynamoDB configuration
def get_dynamodb_client():
    return boto3.client(
        "dynamodb",
        endpoint_url=os.getenv("DYNAMODB_ENDPOINT", "http://dynamodb-local:8000"),
        region_name=os.getenv("AWS_REGION", "local"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "local"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "local"),
        aws_session_token=None,
        verify=False,
    )

# Kafka configuration
def get_kafka_admin_client():
    return KafkaAdminClient(
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    )

def get_kafka_consumer(max_retries: int = 5, retry_delay: int = 5) -> KafkaConsumer:
    return KafkaConsumer(
        bootstrap_servers=[os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")],
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="quiz_group",
    ) 
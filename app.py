import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

import boto3
import redis
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, join_room
from kafka import KafkaConsumer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import NoBrokersAvailable, TopicAlreadyExistsError
from loguru import logger

from const import VALID_QUIZZES, VALID_USER_IDS  # Import constants

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Redis and DynamoDB clients using environment variables
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)

dynamodb = boto3.client(
    "dynamodb",
    endpoint_url=os.getenv("DYNAMODB_ENDPOINT", "http://dynamodb-local:8000"),
    region_name=os.getenv("AWS_REGION", "local"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "local"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "local"),
    aws_session_token=None,
    verify=False,
)


def ensure_topic_exists(topic_name: str) -> None:
    try:
        admin_client = KafkaAdminClient(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        )
        new_topic = NewTopic(name=topic_name, num_partitions=1, replication_factor=1)
        admin_client.create_topics([new_topic])
        logger.info(f"Created new topic: {topic_name}")
    except TopicAlreadyExistsError:
        logger.info(f"Topic already exists: {topic_name}")
    except NoBrokersAvailable:
        logger.error("Failed to connect to Kafka. Exiting...")
        sys.exit(1)


# Add new function to create consumer
def get_kafka_consumer(max_retries: int = 5, retry_delay: int = 5) -> KafkaConsumer:
    for attempt in range(max_retries):
        try:
            consumer = KafkaConsumer(
                bootstrap_servers=[os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")],
                auto_offset_reset="latest",
                enable_auto_commit=True,
                group_id="quiz_group",
            )
            logger.info("Successfully created Kafka consumer")
            return consumer
        except NoBrokersAvailable:
            if attempt == max_retries - 1:
                logger.error(
                    f"Failed to create Kafka consumer after {max_retries} attempts. Exiting..."
                )
                sys.exit(1)
            logger.warning(
                f"Kafka not available, retrying consumer creation in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(retry_delay)


@app.route("/")
def hello():
    return "Hello, World!"


@socketio.on("connect")
def handle_connect():
    logger.info("Client connected")


@socketio.on("join_quiz")
def handle_join_quiz(data: Dict[str, str]) -> Dict[str, str]:
    user_id = str(data.get("user_id"))
    quiz_id = str(data.get("quiz_id"))

    # Validate user_id and quiz_id
    if user_id not in VALID_USER_IDS:
        return {"status": "error", "message": "Invalid user ID"}
    if quiz_id not in VALID_QUIZZES:
        return {"status": "error", "message": "Invalid quiz ID"}

    # Create Kafka topic name for this quiz's leaderboard
    topic_name = f"leaderboard_scoring_{quiz_id}"

    # Ensure the Kafka topic exists
    ensure_topic_exists(topic_name)

    # Get consumer and subscribe to the topic
    consumer = get_kafka_consumer()
    consumer.subscribe([topic_name])

    # Subscribe user to the Socket.IO room
    join_room(topic_name)

    logger.info(
        f"User {user_id} joined quiz {quiz_id} and subscribed to Kafka topic {topic_name}"
    )
    return {"status": "success", "message": f"Joined quiz {quiz_id}"}


@socketio.on("submit_answer")
def handle_answer_submission(data: Dict[str, str]) -> Dict[str, str]:
    user_id = str(data.get("user_id"))
    quiz_id = str(data.get("quiz_id"))
    answer = str(data.get("answer"))

    # Validate inputs
    if user_id not in VALID_USER_IDS or quiz_id not in VALID_QUIZZES:
        return {"status": "error", "message": "Invalid user ID or quiz ID"}

    # Calculate score (implement your scoring logic here)
    score = calculate_score(answer, quiz_id, user_id)

    # Update DynamoDB
    dynamodb.put_item(
        TableName="quiz_scores",
        Item={
            "user_id": {"S": user_id},
            "quiz_id": {"S": quiz_id},
            "score": {"N": str(score)},
            "timestamp": {"S": datetime.utcnow().isoformat()},
        },
    )

    # Update Redis cache
    redis_key = f"quiz:{quiz_id}:leaderboard"
    redis_client.zadd(redis_key, {user_id: score})

    # Get updated leaderboard
    leaderboard = get_leaderboard(quiz_id)

    # Emit update to all users in the quiz room
    topic_name = f"leaderboard_scoring_{quiz_id}"
    socketio.emit(
        "leaderboard_update",
        {"leaderboard": leaderboard, "quiz_id": quiz_id},
        room=topic_name,
    )

    return {"status": "success", "message": "Answer submitted successfully"}


def calculate_score(answer: str, quiz_id: str, user_id: str) -> int:
    # Retrieve the user's past score from DynamoDB
    response = dynamodb.get_item(
        TableName="quiz_scores",
        Key={"user_id": {"S": user_id}, "quiz_id": {"S": quiz_id}},
    )

    past_score = int(response["Item"]["score"]["N"]) if "Item" in response else 0

    # Calculate new score (implement your scoring logic here)
    new_score = len(answer)

    # Accumulate past score with new score
    total_score = past_score + new_score
    return total_score


def get_leaderboard(quiz_id: str) -> List[Dict[str, Union[str, float]]]:
    redis_key = f"quiz:{quiz_id}:leaderboard"
    # Get top 10 scores
    leaderboard_data: List[Tuple[str, float]] = redis_client.zrevrange(
        redis_key, 0, 9, withscores=True
    )
    return [{"user_id": user_id, "score": score} for user_id, score in leaderboard_data]


@socketio.on("get_leaderboard")
def handle_get_leaderboard(data: Dict[str, str]) -> Optional[Dict[str, str]]:
    quiz_id = str(data.get("quiz_id"))
    if quiz_id not in VALID_QUIZZES:
        return {"status": "error", "message": "Invalid quiz ID"}

    leaderboard = get_leaderboard(quiz_id)
    socketio.emit(
        "leaderboard_update",
        {"leaderboard": leaderboard, "quiz_id": quiz_id},
        room=request.sid,
    )
    return {"status": "success", "message": "Leaderboard sent"}


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)

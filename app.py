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
from config import get_redis_client, get_dynamodb_client, get_kafka_admin_client, get_kafka_consumer
from redis_operations import RedisOperations
from dynamodb_operations import DynamoDBOperations

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize clients
redis_client = get_redis_client()
redis_ops = RedisOperations(redis_client)
dynamodb_client = get_dynamodb_client()
dynamodb_ops = DynamoDBOperations(dynamodb_client)

def ensure_topic_exists(topic_name: str) -> None:
    try:
        admin_client = get_kafka_admin_client()
        new_topic = NewTopic(name=topic_name, num_partitions=1, replication_factor=1)
        admin_client.create_topics([new_topic])
        logger.info(f"Created new topic: {topic_name}")
    except TopicAlreadyExistsError:
        logger.info(f"Topic already exists: {topic_name}")
    except NoBrokersAvailable:
        logger.error("Failed to connect to Kafka. Exiting...")
        sys.exit(1)

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

    # Calculate score
    score = calculate_score(answer, quiz_id, user_id)

    # Update DynamoDB
    dynamodb_ops.save_score(user_id, quiz_id, score)

    # Update Redis cache
    redis_ops.update_leaderboard_score(quiz_id, user_id, score)

    # Get updated leaderboard
    leaderboard = redis_ops.get_leaderboard(quiz_id)

    # Emit update to all users in the quiz room
    topic_name = f"leaderboard_scoring_{quiz_id}"
    socketio.emit(
        "leaderboard_update",
        {"leaderboard": leaderboard, "quiz_id": quiz_id},
        room=topic_name,
    )

    return {"status": "success", "message": "Answer submitted successfully"}

def calculate_score(answer: str, quiz_id: str, user_id: str) -> int:
    # Get the user's past score from DynamoDB
    past_score = dynamodb_ops.get_user_score(user_id, quiz_id)

    # Calculate new score (implement your scoring logic here)
    new_score = len(answer)

    # Accumulate past score with new score
    total_score = past_score + new_score
    return total_score

def get_leaderboard(quiz_id: str) -> List[Dict[str, Union[str, float]]]:
    return redis_ops.get_leaderboard(quiz_id)

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

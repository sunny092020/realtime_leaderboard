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

from config import (get_dynamodb_client, get_kafka_admin_client, get_redis_client)
from const import VALID_QUIZZES, VALID_USER_IDS  
from kafka_operations import KafkaOperations
from dynamodb_operations import DynamoDBOperations
from redis_operations import RedisOperations
from scoring import calculate_score
from validation import validate_quiz_id, validate_user_and_quiz

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize clients
redis_client = get_redis_client()
redis_ops = RedisOperations(redis_client)
dynamodb_client = get_dynamodb_client()
dynamodb_ops = DynamoDBOperations(dynamodb_client)
kafka_ops = KafkaOperations()

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
    is_valid, error_message = validate_user_and_quiz(user_id, quiz_id)
    if not is_valid:
        return {"status": "error", "message": error_message}

    # Create Kafka topic name for this quiz's leaderboard
    topic_name = f"leaderboard_scoring_{quiz_id}"

    # Ensure the Kafka topic exists
    kafka_ops.ensure_topic_exists(topic_name)

    # Get consumer and subscribe to the topic
    kafka_ops.consumer.subscribe([topic_name])

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
    is_valid, error_message = validate_user_and_quiz(user_id, quiz_id)
    if not is_valid:
        return {"status": "error", "message": error_message}

    # Calculate score
    score = calculate_score(answer, quiz_id, user_id, dynamodb_ops)

    # Update DynamoDB
    dynamodb_ops.save_score(user_id, quiz_id, score)

    # Update Redis cache
    redis_ops.update_leaderboard_score(quiz_id, user_id, score)

    # Get updated leaderboard
    leaderboard = redis_ops.get_leaderboard(quiz_id)

    # Publish leaderboard update to Kafka topic
    topic_name = f"leaderboard_scoring_{quiz_id}"
    kafka_ops.publish_leaderboard_update(topic_name, leaderboard, quiz_id)

    return {"status": "success", "message": "Answer submitted successfully"}


def get_leaderboard(quiz_id: str) -> List[Dict[str, Union[str, float]]]:
    return redis_ops.get_leaderboard(quiz_id)


@socketio.on("get_leaderboard")
def handle_get_leaderboard(data: Dict[str, str]) -> Optional[Dict[str, str]]:
    quiz_id = str(data.get("quiz_id"))
    is_valid, error_message = validate_quiz_id(quiz_id)
    if not is_valid:
        return {"status": "error", "message": error_message}

    leaderboard = get_leaderboard(quiz_id)
    topic_name = f"leaderboard_scoring_{quiz_id}"
    kafka_ops.publish_leaderboard_update(topic_name, leaderboard, quiz_id)
    return {"status": "success", "message": "Leaderboard sent"}


if __name__ == "__main__":
    # Start Kafka consumer in a background thread
    import threading
    consumer_thread = threading.Thread(
        target=kafka_ops.run_consumer_task,
        args=(socketio,),
        daemon=True
    )
    consumer_thread.start()
    
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)

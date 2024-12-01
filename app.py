from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room
from flask_cors import CORS
from loguru import logger
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from kafka import KafkaConsumer
from const import VALID_USER_IDS, VALID_QUIZZES  # Import constants
import json
import redis
import boto3
from datetime import datetime

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Redis and DynamoDB clients
redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
dynamodb = boto3.client('dynamodb',
    endpoint_url='http://dynamodb-local:8000',
    region_name='local',
    aws_access_key_id='local',
    aws_secret_access_key='local',
    aws_session_token=None,
    verify=False
)

def ensure_topic_exists(topic_name):
    try:
        admin_client = KafkaAdminClient(bootstrap_servers='kafka:9092')
        new_topic = NewTopic(name=topic_name, num_partitions=1, replication_factor=1)
        admin_client.create_topics([new_topic])
        logger.info(f"Created new topic: {topic_name}")
    except TopicAlreadyExistsError:
        logger.info(f"Topic already exists: {topic_name}")

def create_quiz_scores_table():
    try:
        dynamodb.describe_table(TableName='quiz_scores')
        logger.info("Table 'quiz_scores' already exists.")
    except dynamodb.exceptions.ResourceNotFoundException:
        dynamodb.create_table(
            TableName='quiz_scores',
            KeySchema=[
                {
                    'AttributeName': 'user_id',
                    'KeyType': 'HASH'  # Partition key
                },
                {
                    'AttributeName': 'quiz_id',
                    'KeyType': 'RANGE'  # Sort key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'  # String
                },
                {
                    'AttributeName': 'quiz_id',
                    'AttributeType': 'S'  # String
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        logger.info("Created table 'quiz_scores'.")

# Call this function at the start of your application
create_quiz_scores_table()

@app.route('/')
def hello():
    return 'Hello, World!'

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')

@socketio.on('join_quiz')
def handle_join_quiz(data):
    user_id = str(data.get('user_id'))
    quiz_id = str(data.get('quiz_id'))
    
    # Validate user_id and quiz_id
    if user_id not in VALID_USER_IDS:
        return {'status': 'error', 'message': 'Invalid user ID'}
    if quiz_id not in VALID_QUIZZES:
        return {'status': 'error', 'message': 'Invalid quiz ID'}
    
    # Create Kafka topic name for this quiz's leaderboard
    topic_name = f'leaderboard_scoring_{quiz_id}'
    
    # Ensure the Kafka topic exists
    ensure_topic_exists(topic_name)
    
    # Create Kafka consumer and subscribe to the topic
    consumer = KafkaConsumer(
        bootstrap_servers=['kafka:9092'],
        auto_offset_reset='latest',
        enable_auto_commit=True,
        group_id=f'quiz_group_{quiz_id}'
    )
    consumer.subscribe([topic_name])
    
    # Subscribe user to the Socket.IO room
    join_room(topic_name)
    
    logger.info(f'User {user_id} joined quiz {quiz_id} and subscribed to Kafka topic {topic_name}')
    return {'status': 'success', 'message': f'Joined quiz {quiz_id}'}

@socketio.on('submit_answer')
def handle_answer_submission(data):
    user_id = str(data.get('user_id'))
    quiz_id = str(data.get('quiz_id'))
    answer = data.get('answer')
    
    # Validate inputs
    if user_id not in VALID_USER_IDS or quiz_id not in VALID_QUIZZES:
        return {'status': 'error', 'message': 'Invalid user ID or quiz ID'}
    
    # Calculate score (implement your scoring logic here)
    score = calculate_score(answer, quiz_id, user_id)
    
    # Update DynamoDB
    dynamodb.put_item(
        TableName='quiz_scores',
        Item={
            'user_id': {'S': user_id},
            'quiz_id': {'S': quiz_id},
            'score': {'N': str(score)},
            'timestamp': {'S': datetime.utcnow().isoformat()}
        }
    )
    
    # Update Redis cache
    redis_key = f'quiz:{quiz_id}:leaderboard'
    redis_client.zadd(redis_key, {user_id: score})
    
    # Get updated leaderboard
    leaderboard = get_leaderboard(quiz_id)
    
    # Emit update to all users in the quiz room
    topic_name = f'leaderboard_scoring_{quiz_id}'
    socketio.emit('leaderboard_update', {
        'leaderboard': leaderboard,
        'quiz_id': quiz_id
    }, room=topic_name)
    
    return {'status': 'success', 'message': 'Answer submitted successfully'}

def calculate_score(answer, quiz_id, user_id):
    # Retrieve the user's past score from DynamoDB
    response = dynamodb.get_item(
        TableName='quiz_scores',
        Key={
            'user_id': {'S': user_id},
            'quiz_id': {'S': quiz_id}
        }
    )
    
    past_score = int(response['Item']['score']['N']) if 'Item' in response else 0
    
    # Calculate new score (implement your scoring logic here)
    new_score = len(answer)
    
    # Accumulate past score with new score
    total_score = past_score + new_score
    return total_score

def get_leaderboard(quiz_id):
    redis_key = f'quiz:{quiz_id}:leaderboard'
    # Get top 10 scores
    leaderboard_data = redis_client.zrevrange(redis_key, 0, 9, withscores=True)
    return [{'user_id': user_id, 'score': score} for user_id, score in leaderboard_data]

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
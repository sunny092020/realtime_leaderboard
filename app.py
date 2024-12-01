from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room
from flask_cors import CORS
from loguru import logger
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from kafka import KafkaConsumer
from const import VALID_USER_IDS, VALID_QUIZZES  # Import constants

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

def ensure_topic_exists(topic_name):
    try:
        admin_client = KafkaAdminClient(bootstrap_servers='kafka:9092')
        new_topic = NewTopic(name=topic_name, num_partitions=1, replication_factor=1)
        admin_client.create_topics([new_topic])
        logger.info(f"Created new topic: {topic_name}")
    except TopicAlreadyExistsError:
        logger.info(f"Topic already exists: {topic_name}")

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

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
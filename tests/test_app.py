import pytest
from unittest.mock import Mock, patch
from app import app, socketio
import json

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_redis():
    with patch('redis.Redis') as mock:
        # Mock zrevrange for leaderboard
        mock.return_value.zrevrange.return_value = [
            (b'user1', 100.0),
            (b'user2', 90.0)
        ]
        # Mock zadd for score updates
        mock.return_value.zadd.return_value = True
        yield mock

@pytest.fixture
def mock_dynamodb():
    with patch('boto3.client') as mock:
        # Mock put_item
        mock.return_value.put_item.return_value = {}
        # Mock get_item
        mock.return_value.get_item.return_value = {
            'Item': {
                'score': {'N': '10'}
            }
        }
        yield mock

@pytest.fixture
def mock_kafka():
    with patch('kafka.admin.KafkaAdminClient') as admin_mock, \
         patch('kafka.KafkaConsumer') as consumer_mock:
        admin_mock.return_value.create_topics.return_value = None
        consumer_mock.return_value.subscribe.return_value = None
        yield (admin_mock, consumer_mock)

def test_hello(client):
    response = client.get('/')
    assert response.data == b'Hello, World!'

def test_join_quiz_invalid_user(client):
    with patch('app.VALID_USER_IDS', {'valid_user'}):
        client = socketio.test_client(app)
        response = client.emit('join_quiz', {
            'user_id': 'invalid_user',
            'quiz_id': 'quiz1'
        }, callback=True)
        assert response['status'] == 'error'
        assert response['message'] == 'Invalid user ID'

def test_join_quiz_success(client, mock_kafka):
    with patch('app.VALID_USER_IDS', {'user1'}), \
         patch('app.VALID_QUIZZES', {'quiz1'}):
        client = socketio.test_client(app)
        response = client.emit('join_quiz', {
            'user_id': 'user1',
            'quiz_id': 'quiz1'
        }, callback=True)
        assert response['status'] == 'success'
        assert response['message'] == 'Joined quiz quiz1'

def test_submit_answer(client, mock_redis, mock_dynamodb):
    with patch('app.VALID_USER_IDS', {'user1'}), \
         patch('app.VALID_QUIZZES', {'quiz1'}):
        client = socketio.test_client(app)
        response = client.emit('submit_answer', {
            'user_id': 'user1',
            'quiz_id': 'quiz1',
            'answer': 'test answer'
        }, callback=True)
        assert response['status'] == 'success'
        assert response['message'] == 'Answer submitted successfully'

def test_get_leaderboard(client, mock_redis):
    with patch('app.VALID_QUIZZES', {'quiz1'}):
        client = socketio.test_client(app)
        response = client.emit('get_leaderboard', {
            'quiz_id': 'quiz1'
        }, callback=True)
        
        # Verify that leaderboard data was emitted
        received = client.get_received()
        assert len(received) > 0
        assert received[0]['name'] == 'leaderboard_update'
        assert 'leaderboard' in received[0]['args'][0]
        assert 'quiz_id' in received[0]['args'][0]

def test_calculate_score():
    from app import calculate_score
    with patch('boto3.client') as mock_dynamodb:
        # Mock get_item to return a previous score
        mock_dynamodb.return_value.get_item.return_value = {
            'Item': {
                'score': {'N': '10'}
            }
        }
        
        score = calculate_score('test answer', 'quiz1', 'user1')
        # Score should be previous score (10) + length of answer (11)
        assert score == 21 
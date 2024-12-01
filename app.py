from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room
from loguru import logger

app = Flask(__name__)
socketio = SocketIO(app)

# Store valid user IDs and quizzes (in practice, this should be in a database)
VALID_USER_IDS = {'11111', '22222', '33333', '44444', '55555', 
                  '66666', '77777', '88888', '99999', '101010'}
VALID_QUIZZES = {'quiz1', 'quiz2', 'quiz3', 'quiz4', 'quiz5',
                 'quiz6', 'quiz7', 'quiz8', 'quiz9', 'quiz10'}

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
    
    # Subscribe user to the quiz's leaderboard room
    room = f'leaderboard_scoring_{quiz_id}'
    join_room(room)
    
    logger.info(f'User {user_id} joined quiz {quiz_id}')
    return {'status': 'success', 'message': f'Joined quiz {quiz_id}'}

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True) 
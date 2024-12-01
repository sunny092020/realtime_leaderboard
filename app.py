from flask import Flask
from flask_socketio import SocketIO
from loguru import logger

app = Flask(__name__)
socketio = SocketIO(app)

@app.route('/')
def hello():
    return 'Hello, World!'

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True) 
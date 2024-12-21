import json
import sys
import os
import time
from kafka.admin import NewTopic
from kafka.errors import NoBrokersAvailable, TopicAlreadyExistsError
from loguru import logger
from kafka import KafkaConsumer, KafkaProducer
import threading

from config import get_kafka_admin_client

class KafkaOperations:
    def __init__(self, max_retries=5, retry_delay=5):
        self.admin_client = None
        self._consumer = None
        self._producer = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._connect_with_retry()
        self.subscribed_topics = set()  # Track subscribed topics

    @property
    def consumer(self):
        if self._consumer is None:
            self._consumer = self._get_kafka_consumer()
        return self._consumer

    @property
    def producer(self):
        if self._producer is None:
            self._producer = self._get_kafka_producer()
        return self._producer
    
    def _get_kafka_consumer(self, max_retries: int = 5, retry_delay: int = 5) -> KafkaConsumer:
        consumer = KafkaConsumer(
            bootstrap_servers=[os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")],
            auto_offset_reset="latest",
            enable_auto_commit=True,
            group_id="quiz_group",
        )
        # Subscribe to any existing topics
        if self.subscribed_topics:
            consumer.subscribe(list(self.subscribed_topics))
        return consumer

    def _get_kafka_producer(self) -> KafkaProducer:
        return KafkaProducer(
            bootstrap_servers=[os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    
    def _connect_with_retry(self):
        for attempt in range(self.max_retries):
            try:
                self.admin_client = get_kafka_admin_client()
                logger.info("Successfully connected to Kafka")
                return
            except NoBrokersAvailable:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Failed to connect to Kafka. Retrying in {self.retry_delay} seconds... (Attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(self.retry_delay)
                else:
                    logger.error("Failed to connect to Kafka after maximum retries. Exiting...")
                    sys.exit(1)

    def ensure_topic_exists(self, topic_name: str) -> None:
        try:
            new_topic = NewTopic(name=topic_name, num_partitions=1, replication_factor=1)
            self.admin_client.create_topics([new_topic])
            logger.info(f"Created new topic: {topic_name}")
        except TopicAlreadyExistsError:
            logger.info(f"Topic already exists: {topic_name}")
        except NoBrokersAvailable:
            logger.error("Lost connection to Kafka. Attempting to reconnect...")
            self._connect_with_retry()
            self.ensure_topic_exists(topic_name)  # Retry the operation 

    def start_consumer_with_monitoring(self, socketio) -> None:
        """
        Start the consumer thread with monitoring
        """
        self._consumer_thread = self._start_consumer_thread(socketio)
        self._monitor_thread = threading.Thread(
            target=self._monitor_consumer_thread,
            args=(socketio,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("Started Kafka consumer with monitoring")

    def _start_consumer_thread(self, socketio) -> threading.Thread:
        """
        Create and start a new consumer thread
        """
        consumer_thread = threading.Thread(
            target=self.run_consumer_task,
            args=(socketio,),
            daemon=True
        )
        consumer_thread.start()
        return consumer_thread

    def _monitor_consumer_thread(self, socketio) -> None:
        """
        Monitor the consumer thread and restart if it dies
        """
        while True:
            if not self._consumer_thread.is_alive():
                logger.warning("Kafka consumer thread died. Restarting...")
                self._consumer_thread = self._start_consumer_thread(socketio)
            time.sleep(5)  # Check every 5 seconds

    def run_consumer_task(self, socketio) -> None:
        """
        Continuously consume messages from Kafka and emit them via Socket.IO
        """
        while True:
            try:
                for message in self.consumer:
                    data = json.loads(message.value.decode('utf-8'))
                    topic_name = message.topic
                    socketio.emit(
                        "leaderboard_update",
                        data,
                        room=topic_name
                    )
            except Exception as e:
                logger.error(f"Error in Kafka consumer: {e}")
                time.sleep(1)  # Wait before retrying

    def publish_leaderboard_update(self, topic_name: str, leaderboard: list, quiz_id: str) -> None:
        """
        Publish leaderboard update to Kafka topic
        """
        try:
            self.producer.send(
                topic_name,
                value={
                    "leaderboard": leaderboard,
                    "quiz_id": quiz_id
                }
            )
        except Exception as e:
            logger.error(f"Error publishing to Kafka: {e}")

    def subscribe_to_topic(self, topic_name: str) -> None:
        """Subscribe to a new topic while maintaining existing subscriptions"""
        self.subscribed_topics.add(topic_name)
        if self._consumer:
            self._consumer.subscribe(list(self.subscribed_topics))
            logger.info(f"Subscribed to topics: {self.subscribed_topics}")
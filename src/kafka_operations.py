import json
import sys
import os
import time
from kafka.admin import NewTopic
from kafka.errors import NoBrokersAvailable, TopicAlreadyExistsError
from loguru import logger
from kafka import KafkaConsumer, KafkaProducer
from typing import Optional

from config import get_kafka_admin_client

class KafkaOperations:
    def __init__(self, max_retries=5, retry_delay=5):
        self.admin_client = None
        self._consumer = None
        self._producer = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._connect_with_retry()

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
        return KafkaConsumer(
            bootstrap_servers=[os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")],
            auto_offset_reset="latest",
            enable_auto_commit=True,
            group_id="quiz_group",
        )

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
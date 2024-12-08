import sys
import os
import time
from kafka.admin import NewTopic
from kafka.errors import NoBrokersAvailable, TopicAlreadyExistsError
from loguru import logger
from kafka import KafkaConsumer

from config import get_kafka_admin_client

class KafkaOperations:
    def __init__(self, max_retries=5, retry_delay=5):
        self.admin_client = None
        self._consumer = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._connect_with_retry()

    @property
    def consumer(self):
        if self._consumer is None:
            self._consumer = self._get_kafka_consumer()
        return self._consumer
    
    def _get_kafka_consumer(self, max_retries: int = 5, retry_delay: int = 5) -> KafkaConsumer:
        return KafkaConsumer(
            bootstrap_servers=[os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")],
            auto_offset_reset="latest",
            enable_auto_commit=True,
            group_id="quiz_group",
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
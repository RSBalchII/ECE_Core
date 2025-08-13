import redis
import json
import uuid
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Blackboard:
    def __init__(self):
        try:
            self.redis_client = redis.StrictRedis(host='redis', port=6379, db=0)
            # Test connection
            self.redis_client.ping()
            logging.info("Successfully connected to Redis Blackboard.")
        except redis.exceptions.ConnectionError as e:
            logging.error(f"Could not connect to Redis Blackboard: {e}")
            self.redis_client = None

    def post_message(self, source_agent: str, content: str):
        if not self.redis_client:
            logging.error("Cannot post message: Redis client not initialized.")
            return

        try:
            message_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()

            message = {
                "message_id": message_id,
                "timestamp": timestamp,
                "source_agent": source_agent,
                "content": content
            }

            json_message = json.dumps(message)
            self.redis_client.rpush('blackboard_stream', json_message)
            logging.info(f"Message posted by {source_agent} with ID {message_id}.")
        except Exception as e:
            logging.error(f"Error posting message to Blackboard: {e}")

    def read_latest_messages(self, n: int) -> list:
        if not self.redis_client:
            logging.error("Cannot read messages: Redis client not initialized.")
            return []

        try:
            # Retrieve the last n messages from the blackboard_stream
            # lrange(key, start, end) where -1 is the last element, -n is the nth from last
            messages_raw = self.redis_client.lrange('blackboard_stream', -n, -1)
            
            messages = []
            for msg_raw in messages_raw:
                try:
                    # Redis returns bytes, so decode to utf-8 string before JSON deserialization
                    message_dict = json.loads(msg_raw.decode('utf-8'))
                    messages.append(message_dict)
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding message from Redis: {e} - Raw: {msg_raw}")
                except Exception as e:
                    logging.error(f"Unexpected error processing message from Redis: {e} - Raw: {msg_raw}")
            return messages
        except Exception as e:
            logging.error(f"Error reading messages from Blackboard: {e}")
            return []

    def clear(self) -> bool:
        if not self.redis_client:
            logging.error("Cannot clear blackboard: Redis client not initialized.")
            return False

        try:
            # The delete command returns the number of keys that were removed.
            # If 'blackboard_stream' existed and was removed, it returns 1.
            # If it didn't exist, it returns 0.
            result = self.redis_client.delete('blackboard_stream')
            if result == 1:
                logging.info("Blackboard 'blackboard_stream' cleared successfully.")
                return True
            else:
                logging.info("Blackboard 'blackboard_stream' was already empty or did not exist.")
                return True # Still consider it a success if it was already clear
        except Exception as e:
            logging.error(f"Error clearing blackboard: {e}")
            return False
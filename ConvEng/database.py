import os
from app import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

# load dot env
load_dotenv()


def initialize_mongo_connection():
    try:
        # initialize MongoDB Python client
        mongo_client = MongoClient(os.environ["MONGODB_URI"], server_api=ServerApi("1"))
        # get the MongoDB database
        mongo_db = mongo_client[os.environ["MONGODB_NAME"]]
        return mongo_client, mongo_db
    except Exception as e:
        # Handle the connection error
        logging.critical(f"Error initializing MongoDB connection: {e}")
        return None, None


# Initialize the MongoDB connection
mongo_client, mongo_db = initialize_mongo_connection()


def rebuild_mongo_connection():
    global mongo_client
    global mongo_db
    try:
        # Rebuild MongoDB connection
        mongo_client = MongoClient(os.environ["MONGODB_URI"], server_api=ServerApi("1"))
        mongo_db = mongo_client[os.environ["MONGODB_NAME"]]
        return True
    except Exception as e:
        # Handle the connection error
        logging.critical(f"Error rebuilding MongoDB connection: {e}")
        return False


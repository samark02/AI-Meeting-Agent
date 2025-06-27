import os
import jwt
import json
import warnings
from dotenv import load_dotenv
from datetime import datetime, timedelta, UTC
from database import mongo_db
import bson.json_util as jutil
from models import ChatConversationMemory
from langchain_core.messages import AIMessage, HumanMessage
import re
import logging 
# load environment variables
load_dotenv()
import base64
from cryptography.fernet import Fernet
cipher_suite = Fernet(os.getenv("FERNET_KEY"))


# create token for JWT Auth
def create_jwt_token(data: dict, expires_delta: timedelta = None):
    # things to encode
    to_encode = data.copy()
    # set token expiry
    expire = datetime.now(UTC) + timedelta(days=3650)
    # update token expiry
    to_encode.update({"exp": expire})
    # encode JWT
    encoded_jwt = jwt.encode(
        to_encode, os.environ["JWT_SECRET_KEY"], algorithm=os.environ["JWT_ALGORITHM"]
    )
    # return encoded JWT
    return encoded_jwt


# fetch config from db
def fetch_client_config(client_id: str, config_version: str = "v1"):
    # get data from config
    config_data_encrypted = mongo_db["client_configurations"].find_one(
        {"client_id": client_id, "config_version": config_version}
    )
    config_data = json.loads(jutil.dumps(config_data_encrypted))
    # decrypt data
    encrypted_data = base64.b64decode(config_data.get("config", "").encode("utf-8"))
    decrypted_data = cipher_suite.decrypt(encrypted_data)
    # Convert string back to JSON
    config_data = jutil.loads(str(decrypted_data.decode()))
    # return response
    if not config_data:
        warnings.warn(">> Config is not set in DB. You should look into it.")
        return None
    # Parse db config and return
    return config_data


# fetch conversation memory from db
def fetch_conversation_memory(client_id: str, conversation_id: str):
    # get memory from db
    memory_data = mongo_db["conversation_memory"].find_one(
        {"client_id": client_id, "conversation_id": conversation_id}
    )
    if not memory_data:
        warnings.warn(">> Memory was not found, you should probably create a new one.")
        return [],0,0,0,0
    # Parse db config and return
    memory_data = jutil.loads(jutil.dumps(memory_data))
    # create a conversation
    chat_history = []
  
    for memory_item in memory_data["conversation_history"]:
        if memory_item["role"] == "user":
            chat_history.append(HumanMessage(content=memory_item["content"]))
        elif memory_item["role"] == "agent":
            chat_history.append(AIMessage(content=memory_item["content"]))
        else:
            raise RuntimeError(
                "Message role can not be any value apart from user / agent."
            )
    # return response
    try:
        return chat_history,memory_data['total_tokens'],memory_data['prompt_tokens'],memory_data['completion_tokens'],memory_data['total_cost']
    except:
        return chat_history,0,0,0,0

# store conversation memory in db
def store_conversation_memory(
    client_id: str, conversation_id: str, conversation_history: list, total_tokens: int, prompt_tokens: int,completion_tokens: int,total_cost: int
):
    # parse the conversation history
    history_parsed = []
    for conversation_message in conversation_history:
        if conversation_message.type == "human":
            history_parsed.append({"role": "user", "content": conversation_message.content})
        elif conversation_message.type == "ai":
            history_parsed.append({"role": "agent", "content": conversation_message.content})
    # get memory from db
    memory_data = mongo_db["conversation_memory"].update_one(
        {"client_id": client_id, "conversation_id": conversation_id},
        {
            "$set": {
                "client_id": client_id,
                "conversation_id": conversation_id,
                "conversation_history": history_parsed,
                "actions_history": [],
                "conversation_metadata": {},
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
                "total_tokens": total_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_cost": total_cost   
            }
        },
        upsert=True,
    )
    # return response
    return memory_data

def parse_json(input_string, default="{}"):
    try:
        start_index = input_string.find('{')
        end_index = input_string.rfind('}') + 1
        json_str = input_string[start_index:end_index]
        # try to directly parse the JSON string
        return json.loads(json_str)
        # if it was parsed successfully return the JSON string
    except json.JSONDecodeError:
        start_index = input_string.find('{')
        end_index = input_string.rfind('}') + 1
        json_str = input_string[start_index:end_index]
        json_str = re.sub(r'^```.*\n', '', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'\n```$', '', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'<[^>]+>', '', json_str, flags=re.MULTILINE)
        json_str = json_str.strip()
        # check for boolean false endings
        false_ends = [":f", ":fa", ":fal", ":fals"]
        for end in false_ends:
            if json_str.rstrip().endswith(end):
                json_str = json_str.rstrip(end)
                json_str += ":false"
        # check for boolean true endings
        false_ends = [":t", ":tr", ":tru"]
        for end in false_ends:
            if json_str.rstrip().endswith(end):
                json_str = json_str.rstrip(end)
                json_str += ":true"
        # check for null endings
        false_ends = [":n", ":nu", ":nul"]
        for end in false_ends:
            if json_str.endswith(end):
                json_str = json_str.rstrip(end)
                json_str += ":null"
        # remove . from end
        if json_str.rstrip().endswith('.'):
            json_str = json_str.rstrip('.')
        # check if the string ends with a colon, if so simply add null to it
        if json_str.rstrip().endswith(':'):
            json_str += 'null'
        # replace trailing comma if present
        elif json_str.rstrip().endswith(','):
            json_str = json_str.rstrip(',')
        # check if the json ends with comma and quotes if so remove it
        elif json_str.rstrip().endswith(', "'):
            json_str = json_str.rstrip(', "')
        
        # if the JSON string has mismatched quotes, add a quote to the end
        json_quotes_count = json_str.count('"')
        text_quotes_count = json_str.count('\\\"')
        quotes_count = json_quotes_count - text_quotes_count
        # add quotes if needed
        if quotes_count % 2 != 0:
            json_str += '"'
        # if the resulting json_str ends with quote, we need to determine if it is a key or value
        if json_str.endswith('"'):
            # find the last quote
            last_quote_index = json_str.rstrip().rfind('"')
            # if last quote was found
            if last_quote_index != -1:
                # find the seocnd last quote
                second_last_quote_index = json_str[:last_quote_index].rfind("\"")
                # if the second last quote is not preceeded by a colon, it could be a key
                # check if part of array
                if json_str.rfind("[") > json_str.rfind("]") and json_str.rfind("[") > json_str.rfind(":") and json_str.rfind("[") > json_str.rfind("{"):
                    pass
                # so add a null as value
                elif json_str[:second_last_quote_index].strip()[-1] != ":":
                    json_str += ": null"
        # check whether in string
        in_string = False
        # find unmatching brackets
        bracket_stack = []
        bracker_matcher = {"}": "{", "]": "[", "{": "}", "[": "]"}
        for idx, char in enumerate(json_str.replace("\\\"", "")):
            if char == "\"" and json_str[max(0, idx-2):] != "\\\"":
                in_string = not in_string
            # check char for brackets
            if char in ['{', '['] and not in_string:
                bracket_stack.append(char)
            elif char in ['}', ']'] and not in_string:
                if bracker_matcher[char] == bracket_stack[-1]:
                    bracket_stack.pop()
        # add brackets
        while bracket_stack:
            json_str += bracker_matcher[bracket_stack.pop()]
        # final try to load the json str
        try:
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError as e:
            # logging.exception(f"X> Failed to repair JSON: {e}")
            # logging.info(f"X> Failed to parse: {json_str}\n")
            return 

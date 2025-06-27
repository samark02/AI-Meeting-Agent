import os
import json
from datetime import datetime, UTC
from enum import Enum as PyEnum
from typing import Annotated, List, Dict, Optional
from pydantic import BaseModel, Field, AnyUrl, BeforeValidator, ConfigDict, Json


# Represents an ObjectId field in the database.
PyObjectId = Annotated[str, BeforeValidator(str)]


class JsonListStr(BaseModel):
    json_obj: Json[List[str]]


class User(BaseModel):
    client_id: str = Field(description="client id for authentication", example="8400")
    username: str = Field(description="username for authentication", example="kapture")
    password: str = Field(
        description="password for authentication", example="Kapture123"
    )


class LoginResponse(BaseModel):
    access_token: str = Field(
        description="access token to be used to access protected APIs"
    )
    token_type: str = Field(
        description="type of the access token to be used", example="Bearer"
    )


class TokenValidationResponse(BaseModel):
    username: str = Field(description="username of the token holder", example="kapture")
    detail: str = Field(description="Token state detail", example="Token Valid")


class GetConversationConfig(BaseModel):
    client_id: str = Field(description="Client ID")
    config_version: Optional[str] = Field(description="Config Version", default="v1")


class AddConversationConfig(BaseModel):
    client_id: str = Field(description="Client ID")
    engine_name: str = Field(description="Conversation Engine to use")
    engine_model: str = Field(description="Model to use in the conversation engine")
    engine_auth: str = Field(description="API Key to be used for the model")
    config_version: str = Field(description="Version of the config", default="v1")
    prompt_template: str = Field(description="The system prompt template")
    created_at: Optional[datetime] = Field(default=datetime.now(UTC))
    updated_at: Optional[datetime] = Field(default=datetime.now(UTC))


class ChatConversationRequest(BaseModel):
    input: str = Field(description="input message from the user")
    client_id: str = Field(description="Client ID")
    config_version: str = Field(description="Client Configuration Version")
    conversation_id: Optional[str] = Field(description="Conversation ID", default=None)
    

class ChatHistoryRequest(BaseModel):
    client_id: str = Field(description="Client ID")
    conversation_id: str = Field(description="Conversation ID")


class ChatConversationResponse(BaseModel):
    message: str = Field(description="Message from the agent")
    conversation_id: str = Field(description="Identifier for the conversation")


class ChatToolConfig(BaseModel):
    """
    A config object for Chat Tools.
    """

    tool_id: str = Field(description="Tool ID / Name")
    tool_variables: Dict = Field(description="Environment variables as a JSON object")
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "tool_id": "create_democrm_support_ticket",
                "tool_variables": {
                    "ASSIGN_EMP": "Ankit Tiwari",
                    "API_COOKIE": "JSESSIONID=0987654323456789098765432345678987654323456789",
                },
            }
        },
    )


class ChatConversationConfig(BaseModel):
    """
    A config object for Chat Conversations.
    """

    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    client_id: str = Field(description="Client ID")
    engine_name: str = Field(description="Name of the Engine")
    engine_model: str = Field(description="Model to be used by the Engine")
    engine_auth: str = Field(
        description="Auth Key for the model and the engine (eg. OpenAI API Key)"
    )
    config_version: str = Field(default="v1")
    prompt_template: str = Field(description="Template for the system prompt.")
    tool_config: Optional[List[Optional[ChatToolConfig]]] = Field(
        description="Configuration for the tools to be used."
    )
    created_at: Optional[datetime] = Field(default=datetime.now(UTC))
    updated_at: Optional[datetime] = Field(default=datetime.now(UTC))
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "client_id": "8400",
                "engine_name": "langchain_tool_agent",
                "engine_model": "gpt-4o",
                "engine_auth": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "config_version": "v1",
                "prompt_template": "You are a helpful agent!",
                "tool_config": [
                    {
                        "tool_id": "create_democrm_support_ticket",
                        "tool_variables": {
                            "ASSIGN_EMP": "Ankit Tiwari",
                            "API_COOKIE": "JSESSIONID=0987654323456789098765432345678987654323456789",
                        },
                    }
                ],
                "created_at": datetime(2024, 1, 27, 0, 0, 0, 0),
                "updated_at": datetime(2024, 1, 27, 0, 0, 0, 0),
            }
        },
    )


class ChatConversationMemory(BaseModel):
    """
    An object to maintain conversation history.
    """

    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    client_id: str = Field(...)
    conversation_id: str = Field(...)
    conversation_history: List[Dict] = Field(default=[])
    actions_history: List[Dict] = Field(default=[])
    conversation_metadata: Optional[Dict] = Field(default={})
    created_at: Optional[datetime] = Field(default=datetime.now(UTC))
    updated_at: Optional[datetime] = Field(default=datetime.now(UTC))
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "client_id": "8400",
                "conversation_id": "909864567",
                "conversation_history": [
                    {
                        "role": "user",
                        "content": "Hi",
                        "timestamp": datetime(2024, 1, 27, 0, 0, 0, 0),
                    },
                    {
                        "role": "agent",
                        "content": "Hello!",
                        "timestamp": datetime(2024, 1, 27, 1, 0, 0, 0),
                    },
                ],
                "actions_history": [
                    {
                        "name": "send_email_to_customer",
                        "input": {
                            "email": "swastik@example.com",
                            "subject": "hello",
                            "body": "Hello Swastik,\nThanks,\nBot",
                        },
                    }
                ],
                "conversation_metadata": {},
                "created_at": datetime(2024, 1, 27, 0, 0, 0, 0),
                "updated_at": datetime(2024, 1, 27, 0, 0, 0, 0),
            }
        },
    )

class ChatConversationInitialization(BaseModel):
    text: str = Field(description="Summary Text")
    client_id: str = Field(description="Client ID")
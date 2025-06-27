import os
import time
import json
import uuid
import typing
from datetime import datetime, UTC
from app import (
    app,
    OpenAPI,
    Request,
    JSONResponse,
    logging,
    HTTPException,
    Depends,
    get_current_user,
)
from database import mongo_db
from utils import (
    fetch_client_config,
    fetch_conversation_memory,
    store_conversation_memory,
    create_jwt_token,
    parse_json,
)

from fastapi.openapi.docs import get_swagger_ui_html
from models import (
    User,
    LoginResponse,
    TokenValidationResponse,
    ChatConversationRequest,
    ChatConversationResponse,
    ChatConversationConfig,
    ChatConversationInitialization,
    GetConversationConfig,
    AddConversationConfig,
    ChatHistoryRequest,
)

from rag import RAGSystem
import bson.json_util as jutil
from invoke_agent import agent_run
import base64
from cryptography.fernet import Fernet

cipher_suite = Fernet(os.getenv("FERNET_KEY"))

# API for generating OpenAPI Specs, important to add API Prefix
@app.get(f"/kapnotes/openapi.json", response_model=OpenAPI, include_in_schema=False)
async def openapi(request: Request):
    return JSONResponse(app.openapi())


# API for accessing OpenAPI Docs
@app.get(f"/kapnotes/docs", include_in_schema=False)
def swagger(request: Request):
    client_host = request.client.host
    logging.info(f"[{client_host}] - OpenAPI Specs was hit")
    return get_swagger_ui_html(
        openapi_url=f"/kapnotes/openapi.json",
        title="Chat Conversation Engine API",
    )


# An API Endpoint to loging in
@app.post(f"/kapnotes/auth/login", tags=["Authentication"])
async def login(user: User) -> LoginResponse:
    # Fake user password auth
    if (
        user.username == os.environ["JWT_FAKE_USER"]
        and user.password == os.environ["JWT_FAKE_PASS"]
    ):
        # Generate a JWT token for the user.
        token = create_jwt_token({"sub": user.client_id})
        # return for API Call
        return JSONResponse({"access_token": token, "token_type": "bearer"})
    else:
        # raise exception if user or pass not valid
        raise HTTPException(status_code=401, detail="Invalid credentials")


# An API endpoint to validate User
@app.post(f"/kapnotes/auth/validate", tags=["Authentication"])
async def validate_token(
    current_user: str = Depends(get_current_user),
) -> TokenValidationResponse:
    return JSONResponse({"detail": "Token Valid", "username": current_user})


# An API endpoint to get the config for a client
@app.post(f"/kapnotes/config/get", tags=["Configuration"])
async def get_conversation_config(
    request_body: GetConversationConfig, current_user: str = Depends(get_current_user)
) -> ChatConversationConfig:
    """
    DANGER: Never do this if you are unsure. Can lead to data leakage.
    """
    # time for logging purposes
    start_time = time.time()
    if(request_body.client_id!=current_user):
        return JSONResponse(
        {
            "status": "success",
            "message": "Conversation config fetching failed. Please check your Auth Key.",
            "configuration": {},
            "eval_time": time.time() - start_time,
        }
    )

    # Get the config from DB
    conversation_config = mongo_db["client_configurations"].find_one(
        {"client_id": current_user, "config_version": request_body.config_version}
    )
    config_data = json.loads(jutil.dumps(conversation_config))
    # decrypt data
    encrypted_data = base64.b64decode(config_data.get("config", "").encode("utf-8"))
    decrypted_data = cipher_suite.decrypt(encrypted_data)
    # Convert string back to JSON
    config_data = jutil.loads(str(decrypted_data.decode()))
    # return response

    # return response
    return JSONResponse(
        {
            "status": "success",
            "message": "Conversation config fetched",
            "configuration": config_data,
            "eval_time": time.time() - start_time,
        }
    )


# An API endpoint to add a config
@app.post(f"/kapnotes/config/add", tags=["Configuration"])
async def add_conversation_config(
    request_body: ChatConversationConfig, current_user: str = Depends(get_current_user)
) -> ChatConversationConfig:
    """
    DANGER: Never do this if you are unsure.
    """
    # time for logging purposes
    start_time = time.time()

    encrypted_data = cipher_suite.encrypt(request_body.model_dump_json().encode())
    #     # Encode the encrypted bytes to a Base64 string
    encoded_data = base64.b64encode(encrypted_data).decode("utf-8")
    # # Insert or update the configuration in MongoDB


    conversation_configed = mongo_db["client_configurations"].update_one(
        {
            "config_version": request_body.config_version,
            "client_id": request_body.client_id,
        },
        {"$set": {"config": encoded_data}},
        upsert=True,
    )

    # return response
    return JSONResponse(
        {
            "status": "success",
            "message": "Conversation config updated",
            "configuration": json.loads(jutil.dumps(conversation_configed.raw_result)),
            "eval_time": time.time() - start_time,
        }
    )


# An API endpoint to delete conversation config
@app.post(f"/kapnotes/config/delete", tags=["Configuration"])
async def delete_conversation_config(
    request_body: GetConversationConfig, current_user: str = Depends(get_current_user)
) -> ChatConversationConfig:
    """
    DANGER: Never do this if you are unsure. Leads to production breakage.
    """
    # time for logging purposes
    start_time = time.time()

    # Update the config in DB
    deleted_config = mongo_db["client_configurations"].delete_one(
        {"client_id": current_user, "config_version": request_body.config_version}
    )

    # return response
    return JSONResponse(
        {
            "status": "success",
            "message": "Conversation config has been deleted",
            "configuration": json.loads(jutil.dumps(deleted_config.raw_result)),
            "eval_time": time.time() - start_time,
        }
    )


# An API endpoint to have a conversation
@app.post(f"/kapnotes/chat/completions", tags=["Completions"])
async def chat_completions(
    request_body: ChatConversationRequest, current_user: str = Depends(get_current_user)
) -> ChatConversationResponse:
    # time for logging purposes
    try:
        start_time = time.time()
        # validate client id is same as the token
        if current_user != request_body.client_id:
            return JSONResponse(
                {
                    "status": "forbidden",
                    "message": "Attempted to use another client's id with your client key. This will be reported.",
                },
                status_code=403,
            )

        # get conversation config
        conversation_config = fetch_client_config(
            client_id=request_body.client_id, config_version=request_body.config_version
        )
    # return error if no config was found
        if not conversation_config:
            return JSONResponse(
                {
                    "status": "misconfigured",
                    "message": "Attempted to use completions API without appropriate configuration.",
                },
                status_code=400,
            )

        # Parse config from DB
        conversation_config = jutil.loads(jutil.dumps(conversation_config))
                        
        # make sure conversation id exists
        conversation_id = request_body.conversation_id
        if not request_body.conversation_id:
            conversation_id = str(uuid.uuid4())

        # try to get the conversation history
        conversation_history, total_tokens, prompt_tokens,completion_tokens,total_cost = fetch_conversation_memory(
            client_id=request_body.client_id, conversation_id=conversation_id
        )

        agent_response, conversation_history,cb = agent_run(conversation_config,request_body.input,conversation_history)

        store_conversation_memory(
            client_id=request_body.client_id,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
            total_tokens = total_tokens+ cb.total_tokens,
            prompt_tokens = prompt_tokens+ cb.prompt_tokens,
            completion_tokens = completion_tokens+cb.completion_tokens,
            total_cost = total_cost+cb.total_cost
        )
        
        output = parse_json(agent_response["output"])
        if not output:
        # return response
            return JSONResponse(
                {
                    "status": "success",
                    "message":agent_response["output"],
                    "conversation_id": conversation_id,
                    "eval_time": time.time() - start_time,
                    "details_name": None,
                    "details_value": None,
                }
            )
    
        output_response= {
            "status": "success",
            "conversation_id": conversation_id,
            "eval_time": time.time() - start_time,
            "details_value": None,
            "details_name": None,
        }
        
        output_response["message"] = output['text']
        output.pop("text")
        for keys,value in output.items():
            output_response[keys] = value
        
        return JSONResponse(output_response)
    except Exception as e:
        # Handle the connection error
        logging.exception(f"Completions API failed: {e}")
        return


# An API endpoint to fetch conversation history
@app.post(f"/kapnotes/chat/history", tags=["Completions"])
async def fetch_chat_history(
    request_body: ChatHistoryRequest, current_user: str = Depends(get_current_user)
) -> typing.Dict:
    # time for logging purposes
    start_time = time.time()

    # validate client id is same as the token
    if current_user != request_body.client_id:
        return JSONResponse(
            {
                "status": "forbidden",
                "message": "Attempted to use another client's id with your client key. This will be reported.",
            },
            status_code=403,
        )

    # try to get the conversation history
    conversation_history = mongo_db["conversation_memory"].find_one(
        {"client_id": current_user, "conversation_id": request_body.conversation_id},
        {"_id": 0, "created_at": 0, "updated_at": 0}
    )

    # return response
    return JSONResponse(
        {
            "status": "success",
            "conversation_history": json.loads(jutil.dumps(conversation_history)),
            "eval_time": time.time() - start_time,
        }
    )

@app.post(f"/kapnotes/chat/initialize", tags=["Completions"])
async def chat_initialize(
    request_body: ChatConversationInitialization, current_user: str = Depends(get_current_user)
) -> typing.Dict:
    """
    DANGER: Never do this if you are unsure. Leads to production breakage.
    """
    start_time = time.time()
    
    try:
        rag = RAGSystem()
        rag.add_text(request_body.text, request_body.client_id, source_name="meeting_notes_2024")
        
        return JSONResponse(
            {
                "status": "success",
                "eval_time": time.time() - start_time,
            }
        )
    except Exception as e:
        return JSONResponse(
            {
                "status": "failed",
                "reason": e,
                "eval_time": time.time() - start_time,
            }
        )
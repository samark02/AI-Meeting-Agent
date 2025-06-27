import os
import jwt
import json
import time
import logging
from dotenv import load_dotenv
from pydantic import ValidationError

from fastapi import FastAPI
from fastapi import status
from fastapi import Depends
from fastapi import Response
from fastapi import exceptions
from fastapi import HTTPException
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.openapi.models import OpenAPI
from fastapi.exceptions import RequestValidationError

from fastapi.security import HTTPBearer
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# load dotenv
load_dotenv()

# generate the fastapi app
app = FastAPI(
    title="Chat Conversation Engine API",
    summary="Have a conversation with an agent with tool capabilities.",
    version="0.0.1",
    redoc_url=f"/kapnotes/redoc",
    docs_url=f"/kapnotes/docs",
    openapi_url=f"/kapnotes/openapi.json",
    swagger_ui_parameters={"displayRequestDuration": True, "displayOperationId": True},
)

# config the origins and handel CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] - [%(name)s] [%(process)s] - [%(module)s.%(funcName)s, line %(lineno)s] - %(message)s",
    handlers=[
        logging.handlers.TimedRotatingFileHandler(
            "ce-v001-dev.log",
            when="midnight",
            interval=1,
            backupCount=7,
        ),
        logging.StreamHandler(),
    ],
    datefmt="%Y-%m-%d %H:%M:%S %Z",
)

# Starlette logging middleware
middleware = [
    Middleware(TrustedHostMiddleware, allowed_hosts=["*"]),
]

# OAuth2 Password Bearer
oauth2_scheme = HTTPBearer()


# Function to decode and verify the JWT token
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        # get token credentials
        token_credentials = token.credentials
        # decode JWT payload
        payload = jwt.decode(
            token_credentials,
            os.environ["JWT_SECRET_KEY"],
            algorithms=[os.environ["JWT_ALGORITHM"]],
        )
        # get username from payload
        username: str = payload.get("sub")
        # if no username invalidate
        if username is None:
            raise HTTPException(status_code=400, detail="Token Invalid")
        return username
    except jwt.exceptions.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token Expired"
        )
    except Exception as e:
        logging.exception(str(e))
        raise HTTPException(status_code=401, detail="Unauthorized")


# a function to inject request body back in request stream
async def set_request_body(request: Request, body: bytes):
    async def receive():
        return {"type": "http.request", "body": body}

    request._receive = receive


# middleware for logging
@app.middleware("http")
async def request_response_logger(request: Request, call_next):
    # Log the request method and path
    client_host = request.client.host
    request_path = request.url
    request_method = request.method
    # make request dirty by reading body from stream
    request_body = await request.body()
    # inject body back in request stream
    await set_request_body(request, request_body)
    # block content if login or validate APIs
    if str(request_path).endswith("login"):
        request_body = "{}"
    # clean request body
    try:
        request_body = json.dumps(json.loads(request_body))
    except json.JSONDecodeError:
        pass
    # log request
    logging.info(
        f"[{str(client_host)}] - Request: [{str(request_method)} {str(request_path)}] - Payload: {request_body}"
    )
    # Proceed with the request
    response = await call_next(request)
    # read response body
    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk
    # re-create a new response to be sent with the same details
    response = Response(
        content=response_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )
    # clean response body
    try:
        response_body = json.dumps(json.loads(response_body))
    except json.JSONDecodeError:
        pass
    # reset response for openapi.json
    if str(request_path).endswith("openapi.json") or str(request_path).endswith(
        "/kapnotes/docs"
    ):
        response_body = "{}"
    # Log the response status code
    logging.info(
        f"[{str(client_host)}] - Response: [{str(request_method)} {str(request_path)}] - Status: {str(response.status_code)} - Payload: {response_body}"
    )
    # return response
    return response


# Handle Pydantic Validation Errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"status": "error", "detail": exc.errors()},
    )


# add validation handler
@app.exception_handler(exceptions.RequestValidationError)
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc):
    logging.info(f"ValidationError: {exc}")
    exc_json = exc.__dict__
    response = {"detail": exc_json.get("_errors"), "status": "error"}
    return JSONResponse(response, status_code=422)


# import routes to application
import routes

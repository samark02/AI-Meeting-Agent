####################################################
#            _  _ ____ ____ _  _                   #
#            |\/| |  | |    |_/                    #
#            |  | |__| |___ | \_                   #
#                                                  #
#            ____ ____ ____ _  _ ____ ____         #
#            [__  |___ |__/ |  | |___ |__/         #
#            ___] |___ |  \  \/  |___ |  \         #
####################################################


####################################################
#                    IMPORTS                       #
####################################################

import os
import json
import jwt
import logging
import time
import bson.json_util as jutil
from dotenv import load_dotenv
from pydantic import ValidationError
from typing import Any, Dict
from pymongo import MongoClient
from datetime import datetime, timedelta
from pymongo.server_api import ServerApi

from fastapi import FastAPI
from fastapi import status
from fastapi import Depends
from fastapi import Response
from fastapi import exceptions
from fastapi import HTTPException
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.openapi.models import OpenAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.exceptions import RequestValidationError

from fastapi.security import HTTPBearer
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware


####################################################
#                 INITIALIZATION                   #
####################################################

# load dotenv
load_dotenv()

# generate the fastapi app
app = FastAPI(
    title="xPertVoice Mock APIs",
    summary="Mock APIs for client Integrations with xPertVoice.",
    version="0.0.1",
    redoc_url=f"/mock/api/redoc",
    docs_url=f"/mock/api/docs",
    openapi_url=f"/mock/api/openapi.json",
    swagger_ui_parameters={"displayRequestDuration":True,"displayOperationId":True},
)

# logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] - [%(name)s] [%(process)s] - [%(module)s.%(funcName)s, line %(lineno)s] - %(message)s",
    handlers=[
        logging.handlers.TimedRotatingFileHandler(
            "mockapi.log",
            when="midnight",
            interval=1,
            backupCount=7,
        ),
        logging.StreamHandler(),
    ],
    datefmt="%Y-%m-%d %H:%M:%S %Z",
)


####################################################
#                  MIDDLEWARES                     #
####################################################

# config the origins and handel CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
            token_credentials, os.environ.get('JWT_SECRET_KEY'), algorithms=[os.environ.get('JWT_ALGORITHM')]
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
    logging.info(f"[{str(client_host)}] - Request: [{str(request_method)} {str(request_path)}] - Payload: {request_body}")
    # Proceed with the request
    response = await call_next(request)
    # read response body
    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk
    # re-create a new response to be sent with the same details
    response = Response(content=response_body, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
    # clean response body
    try:
        response_body = json.dumps(json.loads(response_body))
    except json.JSONDecodeError:
        pass
    # reset response for openapi.json
    if str(request_path).endswith("openapi.json") or str(request_path).endswith("/offenseval/api/docs") :
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


# create token for JWT Auth
def create_jwt_token(data: dict, expires_delta: timedelta = None):
    # things to encode
    to_encode = data.copy()
    # set token expiry
    expire = datetime.utcnow() + timedelta(days=3600)
    # update token expiry
    to_encode.update({"exp": expire})
    # encode JWT
    encoded_jwt = jwt.encode(to_encode, os.environ['JWT_SECRET_KEY'], algorithm=os.environ['JWT_ALGORITHM'])
    # return encoded JWT
    return encoded_jwt


####################################################
#                   DATABASE                       #
####################################################

def initialize_mongo_connection():
    try:
        # initialize MongoDB Python client
        mongo_client = MongoClient(os.environ['MONGODB_URI'], server_api=ServerApi('1'))
        # get the MongoDB database
        mongo_db = mongo_client[os.environ['MOCKDB_NAME']]
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
        mongo_client = MongoClient(os.environ['MONGODB_URI'], server_api=ServerApi('1'))
        mongo_db = mongo_client[os.environ['MONGODB_NAME']]
        return True
    except Exception as e:
        # Handle the connection error
        logging.critical(f"Error rebuilding MongoDB connection: {e}")
        return False

####################################################
#                ENTERGY ROUTES                    #
####################################################

# API for generating OpenAPI Specs, important to add API Prefix
@app.get(f"/mock/api/openapi.json", response_model=OpenAPI, include_in_schema=False)
async def openapi(request: Request):
    return JSONResponse(app.openapi())


# API for accessing OpenAPI Docs
@app.get(f"/mock/api/docs", include_in_schema=False)
def swagger(request: Request):
    client_host = request.client.host
    logging.info(f"[{client_host}] - OpenAPI Specs was hit")
    return get_swagger_ui_html(
        openapi_url=f"/mock/api/openapi.json",
        title="Mock APIs",
    )


# An API Endpoint to loging in
@app.post(f"/mock/api/auth/login", tags=["Authentication"])
async def login(user: Dict) -> Dict:
    # Fake user password auth
    if user['username'] == os.environ.get('JWT_FAKE_USER') and user['password'] == os.environ.get('JWT_FAKE_PASS'):
        # Generate a JWT token for the user.
        token = create_jwt_token({"sub": user['username']})
        # return for API Call
        return JSONResponse({"access_token": token, "token_type": "bearer"})
    else:
        # raise exception if user or pass not valid
        raise HTTPException(status_code=401, detail="Invalid credentials")


# An API endpoint to validate User
@app.post(f"/mock/api/auth/validate", tags=["Authentication"])
async def validate_token(current_user: str = Depends(get_current_user)) -> Dict:
    return JSONResponse({"detail": "Token Valid", "username": current_user})


# An API endpoint to add an invoice in DB
@app.post("/mock/api/entergy/invoice/add", tags=["Entergy Texas"])
async def add_entergy_invoice(request_body: Dict) -> Dict:
    # Soft validate the dict
    if "customer_phone" not in request_body or "customer_name" not in request_body or "customer_invoice" not in request_body:
        return {"status": "error", "message": "One or more of customer_name, customer_phone, customer_invoice missing."}
    # Add or update the invoice
    invoice_update = mongo_db["entergy_invoices"].update_one(
        {"customer_phone": request_body['customer_phone']},
        {"$set": request_body},
        upsert=True
    )
    # return response
    return {"status": "success", "message": "An invoice was added successfully."}


# An API endpoint to fetch an invoice from DB
@app.post(f"/mock/api/entergy/invoice/get", tags=["Entergy Texas"])
async def fetch_entergy_invoice(request_body: Dict) -> Dict:
    # validate the request body to fetch the invoice
    if "customer_phone" not in request_body:
        return {"status": "error", "message": "You must share a customer_phone to fetch the invoice"}
    # fetch the invoice from DB
    invoice_data = mongo_db['entergy_invoices'].find_one(
        {"customer_phone": request_body["customer_phone"]}
    )
    # invoice is found or not
    if not invoice_data:
        return {"status": "not found", "message": "No invoice was found with the shared contact number."}
    # cleanup of invoice data
    del invoice_data["_id"]
    # return the invoice when found
    return {"status": "success", "invoice": json.loads(jutil.dumps(invoice_data))}


####################################################
#                  BFSI ROUTES                     #
####################################################

# An API endpoint to add an insurance policy in DB
@app.post("/mock/api/bfsi/policy/add", tags=["BFSI"])
async def add_insurance_policy(request_body: Dict) -> Dict:
    # Soft validate the dict
    if "customer_phone" not in request_body or "customer_name" not in request_body or "customer_policy_id" not in request_body:
        return {"status": "error", "message": "One or more of customer_name, customer_phone, customer_policy_id missing."}
    # Add or update the policy
    policy_update = mongo_db["insurance_policies"].update_one(
        {"customer_phone": request_body['customer_phone']},
        {"$set": request_body},
        upsert=True
    )
    # return response
    return {"status": "success", "message": "An insurance policy was added successfully."}


# An API endpoint to fetch the user's insurance policy
@app.post(f"/mock/api/bfsi/policy/fetch", tags=["BFSI"])
async def fetch_insurance_policy(request_body: Dict) -> Dict:
    # validate the request body to fetch the policy
    if "customer_phone" not in request_body:
        return {"status": "error", "message": "You must share a customer_phone to fetch the insurance policy"}
    # fetch the policy from DB
    policy_data = mongo_db['insurance_policies'].find_one(
        {"customer_phone": request_body["customer_phone"]}
    )
    # invoice is found or not
    if not policy_data:
        return {"status": "not found", "message": "No insurance policy was found with the shared contact number."}
    # cleanup of invoice data
    del policy_data["_id"]
    # return the invoice when found
    return {"status": "success", "invoice": json.loads(jutil.dumps(policy_data))}


@app.post(f"/mock/api/bfsi/policy/list", tags=["BFSI"])
async def list_insurance_policies(request_body: Dict) -> Dict:
    # validate the request body to fetch the policy
    if "customer_phone" not in request_body:
        return {"status": "error", "message": "You must share a customer_phone to fetch the list of insurance policies"}
    # fetch the policy from DB
    policy_data = mongo_db['insurance_policies'].find_one(
        {"customer_phone": request_body["customer_phone"]}
    )
    # invoice is found or not
    if not policy_data:
        return {"status": "not found", "message": "No insurance policy was found with the shared contact number."}
    # cleanup of invoice data
    del policy_data["_id"]
    # return the invoice when found
    return {"status": "success", "invoice": json.loads(jutil.dumps(policy_data))}

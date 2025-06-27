from pydub import AudioSegment
from google.cloud import storage
from datetime import datetime
import io
import os
import requests
import tempfile
from KapNotes import call_all
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
import json
import concurrent.futures

app = FastAPI()

bucket_name = os.environ['GCP_BUCKET_NAME']
# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'gcp_details.json'
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name.lower())

# Configuration
API_CONFIG = {
    "base_url": os.getenv("BASE_URL", "http://0.0.0.0:8000"),
    "endpoint": os.getenv("ENDPOINT", "/kapnotes/chat/completions"),
    "auth_token": os.getenv("AUTH_TOKEN", ""),
    "client_id": os.getenv("CLIENT_ID", "kapnotes"),
    "config_version": os.getenv("CONFIG_VERSION", "v1"),
    "conversation_id": os.getenv("CONVERSATION_ID", "conv1"),
}

def get_meetings_for_date_count(folderPath):
    prefix = f"{folderPath}/"
    blobs = list(bucket.list_blobs(prefix=prefix))
    meetings = set()
    for blob in blobs:
        parts = blob.name.split("/")
        if len(parts) > 2 and parts[2]:
            meetings.add(parts[2])
    return len(meetings)

def upload_to_gcp(blob_name, file_data):
    try:
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Create a temporary file to store the audio data
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file_data)
            temp_file_path = temp_file.name
        
        # Upload the temporary file to GCP
        blob.upload_from_filename(temp_file_path)
        
        # Clean up the temporary file
        os.unlink(temp_file_path)
        
        return True, blob.public_url
    except Exception as e:
        return False, str(e)
    
import json
@app.get('/notter/get-clients')
def get_clients():
    try:
        blobs = list(bucket.list_blobs(prefix=""))
        client_names = set()
        for blob in blobs:
            client_name = blob.name.split("/")[0]
            if client_name:
                client_names.add(client_name)
        return {"clients": sorted(list(client_names))}
    except Exception as e:
        return {'error': str(e)}, 500

class ClientRequest(BaseModel):
    clientName: str

@app.post("/notter/add-client")
def add_client(request: ClientRequest):
    try:
        client_name = request.clientName.strip().lower()

        if not client_name:
            raise HTTPException(status_code=400, detail="Client name is required")
        
        # Create an empty file in the client's folder to ensure it exists
        blob = bucket.blob(f"{client_name}/.clientinfo")
        blob.upload_from_string('')

        return {"status": "success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class Metadata(BaseModel):
    clientName: str = "kapture"
    fileName: str = "audio.wav"
    filePath: str = "kapture/audio/file_one.wav"
    folderPath: str = "kapture/19-01-2025"
    totalChunks: int = 1

@app.post("/notter/upload-audio")
async def upload_audio(
    audio: UploadFile = File(...),
    metadata: str = Form("{}")
):
    try:
        metadata_dict = json.loads(metadata)
        meta = Metadata(**metadata_dict)

        # Convert audio file to WAV
        audio_data = await audio.read()
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
        wav_file = io.BytesIO()
        audio_segment.export(wav_file, format="wav")
        wav_file.seek(0)

        # Generate folder path and blob name
        no_of_meetings = get_meetings_for_date_count(meta.folderPath)
        meta.folderPath = f"{meta.folderPath}/meeting_{no_of_meetings + 1}"
        blob_name = f"{meta.folderPath}/audio.wav"

        # Upload to GCP
        success, result = upload_to_gcp(blob_name, wav_file.read())

        # Execute additional processing asynchronously
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            executor.submit(call_all, meta.clientName, meta.folderPath, meta.fileName)

        if success:
            return {
                "message": "Audio uploaded successfully",
                "url": result,
                "filename": blob_name
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to upload audio: {result}")

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChatRequest(BaseModel):
    message: str

@app.post('/notter/chat')
def chat(request: ChatRequest):
    try:
        user_message = request.message
        # conversation_id = str(uuid.uuid4())
        
        # Prepare the payload for the law API
        payload = {
            "input": user_message,
            "client_id": API_CONFIG["client_id"],
            "config_version": API_CONFIG["config_version"],
            "conversation_id": API_CONFIG["conversation_id"]
        }
        
        # Make the API call
        response = requests.post(
            f"{API_CONFIG['base_url']}{API_CONFIG['endpoint']}", 
            json=payload,
            headers={
                'Authorization': f"Bearer {API_CONFIG['auth_token']}",
                'Content-Type': 'application/json'
            }
        )
        response.raise_for_status()
        response = json.loads(response.text)
        # Raise an error for bad responses
        return response['message']

    except requests.RequestException as e:
        return {'error': str(e)}, 500
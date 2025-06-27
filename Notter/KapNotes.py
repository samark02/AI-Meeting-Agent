import requests
import openai
import os
import time
import json
from google.cloud import storage
from dotenv import load_dotenv

# load dot env
load_dotenv()

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/samar.k/Desktop/Kapture/Hackathon/gcp_details.json'
storage_client = storage.Client()
bucket = storage_client.bucket("kapnotes")

def call_transcriber(audio):
    print("Transcribing")
    base_url = 'https://obviously-full-reptile.ngrok-free.app/kapnotes/'
    url = base_url+"upload/"
    try:
        files = {"file": open(audio, "rb")}
        response = requests.post(url, files=files)
        job_id = response.json()["job_id"]

        status_url = f"{base_url}status/{job_id}"
        status = requests.get(status_url).json()

        download_url = f"{base_url}download/{job_id}"
        transcript = requests.get(download_url).json()
    except Exception as e:
        print(e)
    print(transcript)
    return transcript


def analyze_transcript(transcript):
    print("Analyzing")
    # Define the prompt
    prompt = (
        "You are an assistant that processes meeting transcripts. "
        "Given the transcript below, provide the following:\n\n"
        "1. **Summary**: A detailed summary overview of the conversation in 100-150 words\n"
        "2. **Key Points**: Bullet points highlighting critical discussions.\n"
        "3. **Action Items**: Bullet points detailing tasks assigned, including the responsible individuals and deadlines.\n\n"
        "Transcript:\n"
        f"{transcript}\n\n"
        "Please format your response with clear headings for each section. Dont use any astriks to highlight or make bold letters."
    )
    
    openai.api_key = os.getenv("OPENAI_API_KEY")
    try:
        # Call the OpenAI API
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.5,
        )

        print(response.choices[0].message.content)
        # Extract and return the response content
    except Exception as e:
        print(e)
    return response.choices[0].message.content

## GCP Cloud
def create_gcp_bucket(bucket):
    location = "ASIA"
    storage_class = "STANDARD"

    # bucket = storage_client.bucket(bucket_name.lower())
    bucket.storage_class = storage_class
    bucket = storage_client.create_bucket(bucket, location=location)

    print(f"Bucket {bucket.name} created in {bucket.location} with storage class {bucket.storage_class}.")

def store_notes_to_gcp(text_content, bucket_name, folderPath, transcription):
    print("Uploading Summary")
    
    try:
        # Create a new blob (object) in the bucket
        summary_blob = bucket.blob(f"{folderPath}/summary.txt")
        summary_blob.upload_from_string(text_content)
        
        transcription_string = json.dumps(transcription)
        json_blob = bucket.blob(f"{folderPath}/transcription.txt")
        json_blob.upload_from_string(transcription_string)
    except Exception as e:
        print(e)
    print(f"'{summary_blob}' uploaded to bucket '{bucket_name}'.")
    return None

def add_to_rag(text_content,client_name):
    print("Adding to RAG")
    API_CONFIG = {
        "base_url": "http://127.0.0.1:6069",
        "endpoint": "/kapnotes/chat/completions",
        "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDUyNjUxMzE3fQ.gYhKT-ZfwhJmXeErVJo1DnAD5MwDIKtocKgVSz3MxwQ",
    }
    try:
        payload = {
                "text": text_content,
                "client_id" : client_name
            }

        response = requests.post(
                f"{API_CONFIG['base_url']}/kapnotes/chat/initialize", 
                json=payload,
                headers={
                    'Authorization': f"Bearer {API_CONFIG['auth_token']}",
                    'Content-Type': 'application/json'
                }
            )
    except Exception as e:
        print(e)
    print("Added to RAG")
    return True

def download_from_bucket(blob_name, destination_file_path, bucket_name):
    print("Downloading Audio")
    try:
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(destination_file_path)
    except Exception as e:
        print(e)
    
    print(f"File {blob_name} downloaded to {destination_file_path}.")
    return destination_file_path

# if __name__ == "__main__":
def call_all(client_name,folderPath,FileName):
    start_time = time.time()
    
    bucket_name = "kapnotes"
    # blob_name = f"{folderPath}/summary.txt"
    audio_blob_name = f"{folderPath}/{FileName}"
    destination_file_path = "audio.mp3"
    
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/samar.k/Desktop/Kapture/Hackathon/gcp_details.json'
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name.lower())

    audio_content = download_from_bucket(audio_blob_name, destination_file_path, bucket_name)

    transcription = call_transcriber(audio_content)

    text_content = analyze_transcript(transcription)
    
    store_notes_to_gcp(text_content, bucket_name, folderPath,transcription)
    
    add_to_rag(text_content,client_name)
    
    print(text_content)
    print("Eval :", time.time() - start_time)
    
    return None

# import os
# from typing import Optional
# from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
# from fastapi.responses import JSONResponse, FileResponse
# from pydantic import BaseModel
# import uuid
# import shutil
# from pathlib import Path
# import uvicorn
# from datetime import datetime
# import json
# from typing import Dict, List

# # Import the transcriber code from previous implementation
# from faster_whisper import WhisperModel
# from pyannote.audio import Pipeline
# import torch
# import wave
# import contextlib
# from pydub import AudioSegment
# import numpy as np

# # Create necessary directories
# UPLOAD_DIR = Path("uploaded_files")
# RESULTS_DIR = Path("transcription_results")
# UPLOAD_DIR.mkdir(exist_ok=True)
# RESULTS_DIR.mkdir(exist_ok=True)

# # Initialize FastAPI app
# app = FastAPI(title="Audio Transcription API")

# # Store job status
# jobs: Dict[str, Dict] = {}

# class TranscriptionJob(BaseModel):
#     job_id: str
#     status: str
#     created_at: str
#     completed_at: Optional[str] = None
#     file_name: str
#     result_file: Optional[str] = None
#     error: Optional[str] = None

# class SpeakerAwareTranscriber:
#     def __init__(self, hf_token: str, model_size: str = "tiny"):
#         self.hf_token = hf_token
#         self.device = self._setup_device()
#         self.model_size = model_size
#         self._initialize_models()
    
#     def _setup_device(self) -> str:
#         if torch.cuda.is_available():
#             try:
#                 torch.cuda.empty_cache()
#                 torch.zeros((1,), device='cuda')
#                 print("Using CUDA for processing")
#                 return "cuda"
#             except RuntimeError:
#                 print("CUDA initialization error. Falling back to CPU...")
#                 return "cpu"
#         return "cpu"

#     def _initialize_models(self):
#         try:
#             self.diarization = Pipeline.from_pretrained(
#                 "pyannote/speaker-diarization-3.0",
#                 use_auth_token=self.hf_token
#             )
#             if self.device == "cuda":
#                 self.diarization = self.diarization.to(torch.device("cuda"))

#             compute_type = "float16" if self.device == "cuda" else "float32"
#             self.transcriber = WhisperModel(
#                 self.model_size,
#                 device=self.device,
#                 compute_type=compute_type
#             )
#             print(f"Models initialized successfully on {self.device}")
#         except Exception as e:
#             raise RuntimeError(f"Failed to initialize models: {str(e)}")

#     async def process_audio(self, audio_path: str, min_speakers: int = 1, max_speakers: int = 5):
#         try:
#             if not os.path.exists(audio_path):
#                 raise FileNotFoundError(f"Audio file not found: {audio_path}")

#             # Convert to WAV if needed
#             if not audio_path.lower().endswith('.wav'):
#                 audio = AudioSegment.from_file(audio_path)
#                 wav_path = str(Path(audio_path).with_suffix('.wav'))
#                 audio.export(wav_path, format='wav')
#                 audio_path = wav_path

#             # Transcribe
#             segments, _ = self.transcriber.transcribe(
#                 audio_path,
#                 beam_size=5,
#                 vad_filter=True,
#                 vad_parameters=dict(min_silence_duration_ms=500)
#             )
#             transcript_segments = list(segments)

#             # Diarize
#             diarization_result = self.diarization(
#                 audio_path,
#                 min_speakers=min_speakers,
#                 max_speakers=max_speakers
#             )

#             # Create speaker mapping
#             speaker_mapping = {}
#             for turn, _, speaker in diarization_result.itertracks(yield_label=True):
#                 speaker_mapping[(turn.start, turn.end)] = speaker

#             # Combine results
#             final_segments = []
#             for seg in transcript_segments:
#                 speaker = "UNKNOWN"
#                 for (start, end), spk in speaker_mapping.items():
#                     if (seg.start >= start and seg.end <= end) or \
#                        (seg.start <= start and seg.end >= end) or \
#                        (seg.start <= start and seg.end >= start) or \
#                        (seg.start <= end and seg.end >= end):
#                         speaker = spk
#                         break

#                 segment_dict = {
#                     "start": seg.start,
#                     "end": seg.end,
#                     "speaker": speaker,
#                     "text": seg.text,
#                     "words": [{"text": word.word, "start": word.start, "end": word.end} 
#                              for word in seg.words] if seg.words else []
#                 }
#                 final_segments.append(segment_dict)

#             return final_segments

#         except Exception as e:
#             raise RuntimeError(f"Processing error: {str(e)}")

# # Initialize transcriber

# HF_TOKEN = "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"  # Replace with your token
# transcriber = SpeakerAwareTranscriber(hf_token=HF_TOKEN, model_size="tiny")

# async def process_audio_file(job_id: str, file_path: str):
#     try:
#         # Process the audio
#         segments = await transcriber.process_audio(file_path)
        
#         # Save results
#         result_file = RESULTS_DIR / f"{job_id}_transcript.json"
#         with open(result_file, 'w', encoding='utf-8') as f:
#             json.dump(segments, f, ensure_ascii=False, indent=2)
        
#         # Update job status
#         jobs[job_id].update({
#             "status": "completed",
#             "completed_at": datetime.now().isoformat(),
#             "result_file": str(result_file)
#         })
        
#     except Exception as e:
#         jobs[job_id].update({
#             "status": "failed",
#             "completed_at": datetime.now().isoformat(),
#             "error": str(e)
#         })

# @app.post("/upload/", response_model=TranscriptionJob)
# async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
#     try:
#         # Generate job ID
#         job_id = str(uuid.uuid4())
        
#         # Save uploaded file
#         file_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
#         with file_path.open("wb") as buffer:
#             shutil.copyfileobj(file.file, buffer)
        
#         # Create job entry
#         job = TranscriptionJob(
#             job_id=job_id,
#             status="processing",
#             created_at=datetime.now().isoformat(),
#             file_name=file.filename
#         )
#         jobs[job_id] = job.dict()
        
#         # Process in background
#         background_tasks.add_task(process_audio_file, job_id, str(file_path))
        
#         return job
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/status/{job_id}", response_model=TranscriptionJob)
# async def get_job_status(job_id: str):
#     if job_id not in jobs:
#         raise HTTPException(status_code=404, detail="Job not found")
#     return jobs[job_id]

# @app.get("/download/{job_id}")
# async def download_transcript(job_id: str):
#     if job_id not in jobs:
#         raise HTTPException(status_code=404, detail="Job not found")
    
#     job = jobs[job_id]
#     if job["status"] != "completed":
#         raise HTTPException(status_code=400, detail="Transcription not completed")
    
#     result_file = Path(job["result_file"])
#     if not result_file.exists():
#         raise HTTPException(status_code=404, detail="Result file not found")
    
#     return FileResponse(
#         result_file,
#         filename=f"transcript_{job_id}.json",
#         media_type="application/json"
#     )

# @app.get("/")
# async def root():
#     return {"message": "Audio Transcription API is running"}

# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)



# import os
# from typing import Optional, Dict, List
# from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
# from fastapi.responses import JSONResponse, FileResponse
# from pydantic import BaseModel
# import uuid
# import shutil
# from pathlib import Path
# import uvicorn
# from datetime import datetime
# import json
# import asyncio
# from pydub import AudioSegment
# import torch
# import numpy as np
# from faster_whisper import WhisperModel
# from pyannote.audio import Pipeline

# # Constants
# UPLOAD_DIR = Path("uploaded_files")
# RESULTS_DIR = Path("transcription_results")
# CHUNK_DIR = Path("audio_chunks")
# MAX_CHUNK_DURATION = 10 * 60 * 1000  # 10 minutes in milliseconds
# PROCESSING_TIMEOUT = 3600  # 1 hour timeout for processing

# # Create necessary directories
# for dir_path in [UPLOAD_DIR, RESULTS_DIR, CHUNK_DIR]:
#     dir_path.mkdir(exist_ok=True)

# # Initialize FastAPI app
# app = FastAPI(title="Audio Transcription API")

# # Store job status
# jobs: Dict[str, Dict] = {}

# class TranscriptionJob(BaseModel):
#     job_id: str
#     status: str
#     created_at: str
#     completed_at: Optional[str] = None
#     file_name: str
#     result_file: Optional[str] = None
#     error: Optional[str] = None
#     progress: Optional[float] = 0.0
#     total_chunks: Optional[int] = None
#     processed_chunks: Optional[int] = 0

# class SpeakerAwareTranscriber:
#     def __init__(self, hf_token: str, model_size: str = "tiny"):
#         self.hf_token = hf_token
#         self.device = self._setup_device()
#         self.model_size = model_size
#         self._initialize_models()
    
#     def _setup_device(self) -> str:
#         if torch.cuda.is_available():
#             try:
#                 torch.cuda.empty_cache()
#                 torch.zeros((1,), device='cuda')
#                 print("Using CUDA for processing")
#                 return "cuda"
#             except RuntimeError:
#                 print("CUDA initialization error. Falling back to CPU...")
#                 return "cpu"
#         return "cpu"

#     def _initialize_models(self):
#         try:
#             self.diarization = Pipeline.from_pretrained(
#                 "pyannote/speaker-diarization-3.0",
#                 use_auth_token=self.hf_token
#             )
#             if self.device == "cuda":
#                 self.diarization = self.diarization.to(torch.device("cuda"))

#             compute_type = "float16" if self.device == "cuda" else "float32"
#             self.transcriber = WhisperModel(
#                 self.model_size,
#                 device=self.device,
#                 compute_type=compute_type
#             )
#             print(f"Models initialized successfully on {self.device}")
#         except Exception as e:
#             raise RuntimeError(f"Failed to initialize models: {str(e)}")

#     def _split_audio(self, audio_path: str) -> List[Path]:
#         """Split audio file into chunks."""
#         audio = AudioSegment.from_file(audio_path)
#         chunks = []
        
#         for i in range(0, len(audio), MAX_CHUNK_DURATION):
#             chunk = audio[i:i + MAX_CHUNK_DURATION]
#             chunk_path = CHUNK_DIR / f"chunk_{len(chunks)}_{Path(audio_path).stem}.wav"
#             chunk.export(chunk_path, format='wav')
#             chunks.append(chunk_path)
        
#         return chunks

#     async def process_chunk(self, chunk_path: str, min_speakers: int = 1, max_speakers: int = 5):
#         """Process a single audio chunk."""
#         try:
#             # Transcribe
#             segments, _ = self.transcriber.transcribe(
#                 str(chunk_path),
#                 beam_size=5,
#                 vad_filter=True,
#                 vad_parameters=dict(min_silence_duration_ms=500)
#             )
#             transcript_segments = list(segments)

#             # Diarize
#             diarization_result = self.diarization(
#                 str(chunk_path),
#                 min_speakers=min_speakers,
#                 max_speakers=max_speakers
#             )

#             # Create speaker mapping
#             speaker_mapping = {}
#             for turn, _, speaker in diarization_result.itertracks(yield_label=True):
#                 speaker_mapping[(turn.start, turn.end)] = speaker

#             # Combine results
#             final_segments = []
#             for seg in transcript_segments:
#                 speaker = "UNKNOWN"
#                 for (start, end), spk in speaker_mapping.items():
#                     if (seg.start >= start and seg.end <= end) or \
#                        (seg.start <= start and seg.end >= end) or \
#                        (seg.start <= start and seg.end >= start) or \
#                        (seg.start <= end and seg.end >= end):
#                         speaker = spk
#                         break

#                 segment_dict = {
#                     "start": seg.start,
#                     "end": seg.end,
#                     "speaker": speaker,
#                     "text": seg.text,
#                     "words": [{"text": word.word, "start": word.start, "end": word.end} 
#                              for word in seg.words] if seg.words else []
#                 }
#                 final_segments.append(segment_dict)

#             return final_segments

#         except Exception as e:
#             raise RuntimeError(f"Chunk processing error: {str(e)}")

#     async def process_audio(self, audio_path: str, job_id: str, min_speakers: int = 1, max_speakers: int = 5):
#         try:
#             # Split audio into chunks
#             chunks = self._split_audio(audio_path)
            
#             # Update job with total chunks
#             jobs[job_id].update({
#                 "total_chunks": len(chunks),
#                 "processed_chunks": 0
#             })

#             # Process chunks with timeout
#             all_segments = []
#             time_offset = 0
            
#             for i, chunk_path in enumerate(chunks):
#                 try:
#                     # Use asyncio.wait_for instead of asyncio.timeout
#                     segments = await asyncio.wait_for(
#                         self.process_chunk(chunk_path, min_speakers, max_speakers),
#                         timeout=PROCESSING_TIMEOUT
#                     )
                    
#                     # Adjust timestamps
#                     for seg in segments:
#                         seg["start"] += time_offset
#                         seg["end"] += time_offset
#                         for word in seg["words"]:
#                             word["start"] += time_offset
#                             word["end"] += time_offset
                    
#                     all_segments.extend(segments)
                    
#                     # Update progress
#                     jobs[job_id].update({
#                         "processed_chunks": i + 1,
#                         "progress": round((i + 1) / len(chunks) * 100, 2)
#                     })
                    
#                     # Clean up chunk file
#                     chunk_path.unlink()
                
#                 except asyncio.TimeoutError:
#                     raise RuntimeError(f"Processing timeout for chunk {i}")
                
#                 time_offset += MAX_CHUNK_DURATION / 1000  # Convert ms to seconds

#             return all_segments

#         except Exception as e:
#             # Clean up any remaining chunk files
#             for chunk in CHUNK_DIR.glob(f"*_{Path(audio_path).stem}.wav"):
#                 chunk.unlink(missing_ok=True)
#             raise RuntimeError(f"Processing error: {str(e)}")

# async def process_audio_file(job_id: str, file_path: str):
#     try:
#         # Process the audio
#         segments = await transcriber.process_audio(file_path, job_id)
        
#         # Save results
#         result_file = RESULTS_DIR / f"{job_id}_transcript.json"
#         with open(result_file, 'w', encoding='utf-8') as f:
#             json.dump(segments, f, ensure_ascii=False, indent=2)
        
#         # Update job status
#         jobs[job_id].update({
#             "status": "completed",
#             "completed_at": datetime.now().isoformat(),
#             "result_file": str(result_file),
#             "progress": 100
#         })
        
#     except Exception as e:
#         jobs[job_id].update({
#             "status": "failed",
#             "completed_at": datetime.now().isoformat(),
#             "error": str(e)
#         })
#     finally:
#         # Clean up original file
#         Path(file_path).unlink(missing_ok=True)

# # Initialize transcriber
# HF_TOKEN = "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"  # Replace with your token
# transcriber = SpeakerAwareTranscriber(hf_token=HF_TOKEN, model_size="tiny")

# @app.post("/upload/", response_model=TranscriptionJob)
# async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
#     try:
#         # Generate job ID
#         job_id = str(uuid.uuid4())
        
#         # Save uploaded file
#         file_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
#         with file_path.open("wb") as buffer:
#             shutil.copyfileobj(file.file, buffer)
        
#         # Create job entry
#         job = TranscriptionJob(
#             job_id=job_id,
#             status="processing",
#             created_at=datetime.now().isoformat(),
#             file_name=file.filename,
#             progress=0
#         )
#         jobs[job_id] = job.dict()
        
#         # Process in background
#         background_tasks.add_task(process_audio_file, job_id, str(file_path))
        
#         return job
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/status/{job_id}", response_model=TranscriptionJob)
# async def get_job_status(job_id: str):
#     if job_id not in jobs:
#         raise HTTPException(status_code=404, detail="Job not found")
#     return jobs[job_id]

# @app.get("/download/{job_id}")
# async def download_transcript(job_id: str):
#     if job_id not in jobs:
#         raise HTTPException(status_code=404, detail="Job not found")
    
#     job = jobs[job_id]
#     if job["status"] != "completed":
#         raise HTTPException(status_code=400, detail="Transcription not completed")
    
#     result_file = Path(job["result_file"])
#     if not result_file.exists():
#         raise HTTPException(status_code=404, detail="Result file not found")
    
#     return FileResponse(
#         result_file,
#         filename=f"transcript_{job_id}.json",
#         media_type="application/json"
#     )

# @app.get("/")
# async def root():
#     return {"message": "Audio Transcription API is running"}

# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)



import os
from typing import Optional, Dict, List
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import uuid
import shutil
from pathlib import Path
import uvicorn
from datetime import datetime
import json
import asyncio
from pydub import AudioSegment
import torch
import numpy as np
from faster_whisper import WhisperModel
from pyannote.audio import Pipeline

# Constants
UPLOAD_DIR = Path("uploaded_files")
RESULTS_DIR = Path("transcription_results")
CHUNK_DIR = Path("audio_chunks")
MAX_CHUNK_DURATION = 10 * 60 * 1000  # 10 minutes in milliseconds
PROCESSING_TIMEOUT = 3600  # 1 hour timeout for processing

# Create necessary directories
for dir_path in [UPLOAD_DIR, RESULTS_DIR, CHUNK_DIR]:
    dir_path.mkdir(exist_ok=True)

# Initialize FastAPI app
app = FastAPI(title="Audio Transcription API")

# Store job status
jobs: Dict[str, Dict] = {}

class TranscriptionJob(BaseModel):
    job_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    file_name: str
    result_file: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[float] = 0.0
    total_chunks: Optional[int] = None
    processed_chunks: Optional[int] = 0

class SpeakerAwareTranscriber:
    def __init__(self, hf_token: str, model_size: str = "tiny"):
        self.hf_token = hf_token
        self.model_size = model_size
        self._initialize_models()
    
    def _setup_device(self) -> str:
        # Force CPU usage
        return "cpu"

    def _initialize_models(self):
        try:
            # Force CPU initialization for diarization
            self.diarization = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.0",
                use_auth_token=self.hf_token
            ).to(torch.device("cpu"))

            # Force CPU initialization for whisper
            self.transcriber = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="float32"  # Use float32 for CPU
            )
            print("Models initialized successfully on CPU")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize models: {str(e)}")

    def _split_audio(self, audio_path: str) -> List[Path]:
        """Split audio file into chunks."""
        audio = AudioSegment.from_file(audio_path)
        chunks = []
        
        for i in range(0, len(audio), MAX_CHUNK_DURATION):
            chunk = audio[i:i + MAX_CHUNK_DURATION]
            chunk_path = CHUNK_DIR / f"chunk_{len(chunks)}_{Path(audio_path).stem}.wav"
            chunk.export(chunk_path, format='wav')
            chunks.append(chunk_path)
        
        return chunks

    async def process_chunk(self, chunk_path: str, min_speakers: int = 1, max_speakers: int = 5):
        """Process a single audio chunk."""
        try:
            # Transcribe
            segments, _ = self.transcriber.transcribe(
                str(chunk_path),
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            transcript_segments = list(segments)

            # Diarize
            diarization_result = self.diarization(
                str(chunk_path),
                min_speakers=min_speakers,
                max_speakers=max_speakers
            )

            # Create speaker mapping
            speaker_mapping = {}
            for turn, _, speaker in diarization_result.itertracks(yield_label=True):
                speaker_mapping[(turn.start, turn.end)] = speaker

            # Combine results
            final_segments = []
            for seg in transcript_segments:
                speaker = "UNKNOWN"
                for (start, end), spk in speaker_mapping.items():
                    if (seg.start >= start and seg.end <= end) or \
                       (seg.start <= start and seg.end >= end) or \
                       (seg.start <= start and seg.end >= start) or \
                       (seg.start <= end and seg.end >= end):
                        speaker = spk
                        break

                segment_dict = {
                    "start": seg.start,
                    "end": seg.end,
                    "speaker": speaker,
                    "text": seg.text,
                    "words": [{"text": word.word, "start": word.start, "end": word.end} 
                             for word in seg.words] if seg.words else []
                }
                final_segments.append(segment_dict)

            return final_segments

        except Exception as e:
            raise RuntimeError(f"Chunk processing error: {str(e)}")

    async def process_audio(self, audio_path: str, job_id: str, min_speakers: int = 1, max_speakers: int = 5):
        try:
            # Split audio into chunks
            chunks = self._split_audio(audio_path)
            
            # Update job with total chunks
            jobs[job_id].update({
                "total_chunks": len(chunks),
                "processed_chunks": 0
            })

            # Process chunks with timeout
            all_segments = []
            time_offset = 0
            
            for i, chunk_path in enumerate(chunks):
                try:
                    segments = await asyncio.wait_for(
                        self.process_chunk(chunk_path, min_speakers, max_speakers),
                        timeout=PROCESSING_TIMEOUT
                    )
                    
                    # Adjust timestamps
                    for seg in segments:
                        seg["start"] += time_offset
                        seg["end"] += time_offset
                        for word in seg["words"]:
                            word["start"] += time_offset
                            word["end"] += time_offset
                    
                    all_segments.extend(segments)
                    
                    # Update progress
                    jobs[job_id].update({
                        "processed_chunks": i + 1,
                        "progress": round((i + 1) / len(chunks) * 100, 2)
                    })
                    
                    # Clean up chunk file
                    chunk_path.unlink()
                
                except asyncio.TimeoutError:
                    raise RuntimeError(f"Processing timeout for chunk {i}")
                
                time_offset += MAX_CHUNK_DURATION / 1000  # Convert ms to seconds

            return all_segments

        except Exception as e:
            # Clean up any remaining chunk files
            for chunk in CHUNK_DIR.glob(f"*_{Path(audio_path).stem}.wav"):
                chunk.unlink(missing_ok=True)
            raise RuntimeError(f"Processing error: {str(e)}")

async def process_audio_file(job_id: str, file_path: str):
    try:
        # Process the audio
        segments = await transcriber.process_audio(file_path, job_id)
        
        # Save results
        result_file = RESULTS_DIR / f"{job_id}_transcript.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
        
        # Update job status
        jobs[job_id].update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "result_file": str(result_file),
            "progress": 100
        })
        
    except Exception as e:
        jobs[job_id].update({
            "status": "failed",
            "completed_at": datetime.now().isoformat(),
            "error": str(e)
        })
    finally:
        # Clean up original file
        Path(file_path).unlink(missing_ok=True)

# Initialize transcriber with CPU
HF_TOKEN = ""  # Replace with your token
transcriber = SpeakerAwareTranscriber(hf_token=HF_TOKEN, model_size="tiny")

@app.post("/upload/", response_model=TranscriptionJob)
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Save uploaded file
        file_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Create job entry
        job = TranscriptionJob(
            job_id=job_id,
            status="processing",
            created_at=datetime.now().isoformat(),
            file_name=file.filename,
            progress=0
        )
        jobs[job_id] = job.dict()
        
        # Process in background
        background_tasks.add_task(process_audio_file, job_id, str(file_path))
        
        return job
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{job_id}", response_model=TranscriptionJob)
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/download/{job_id}")
async def download_transcript(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Transcription not completed")
    
    result_file = Path(job["result_file"])
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="Result file not found")
    
    return FileResponse(
        result_file,
        filename=f"transcript_{job_id}.json",
        media_type="application/json"
    )

@app.get("/")
async def root():
    return {"message": "Audio Transcription API is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

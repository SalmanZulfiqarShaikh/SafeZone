import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Load variables from .env
load_dotenv()

app = FastAPI()

# CRITICAL: Allow your Vite frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # Default Vite port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"status": "Backend is running!"}

@app.get("/api/hello")
def hello():
    return {"message": "Backend Setup done! Waiting for the task"}
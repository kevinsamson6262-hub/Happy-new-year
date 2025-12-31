from fastapi import FastAPI, APIRouter, HTTPException
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from typing import List
import uuid
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging

# ================== FIREBASE INITIALIZATION (RENDER SAFE) ==================

firebase_config = {
    "type": "service_account",
    "project_id": os.environ["FIREBASE_PROJECT_ID"],
    "private_key": os.environ["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
    "client_email": os.environ["FIREBASE_CLIENT_EMAIL"],
    "token_uri": "https://oauth2.googleapis.com/token",
}

cred = credentials.Certificate(firebase_config)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Firestore client
db = firestore.client()

# ================== FASTAPI APP ==================

app = FastAPI(title="FastAPI + Firebase API", version="1.0")
api_router = APIRouter(prefix="/api")

# ================== MODELS ==================

class Story(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    author: str
    title: str
    story: str
    year: str = Field(default_factory=lambda: str(datetime.now().year))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StoryCreate(BaseModel):
    author: str
    title: str
    story: str


class ContactMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContactMessageCreate(BaseModel):
    name: str
    email: str
    message: str


# ================== ROUTES ==================

@api_router.get("/")
async def root():
    return {"status": "Backend running 🚀"}


# ===== STORIES =====

@api_router.post("/stories", response_model=Story)
async def create_story(input: StoryCreate):
    try:
        story_obj = Story(**input.model_dump())
        data = story_obj.model_dump()
        data["timestamp"] = story_obj.timestamp.isoformat()

        db.collection("stories").document(story_obj.id).set(data)
        return story_obj

    except Exception as e:
        logging.error(f"Error adding story: {e}")
        raise HTTPException(status_code=500, detail="Failed to add story")


@api_router.get("/stories", response_model=List[Story])
async def get_stories():
    try:
        docs = db.collection("stories").stream()
        result = []

        for doc in docs:
            data = doc.to_dict()
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            result.append(Story(**data))

        return sorted(result, key=lambda x: x.timestamp, reverse=True)

    except Exception as e:
        logging.error(f"Error fetching stories: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch stories")


# ===== CONTACT =====

@api_router.post("/contact", response_model=ContactMessage)
async def save_contact_message(input: ContactMessageCreate):
    try:
        msg = ContactMessage(**input.model_dump())
        data = msg.model_dump()
        data["timestamp"] = msg.timestamp.isoformat()

        db.collection("contact_messages").document(msg.id).set(data)
        return msg

    except Exception as e:
        logging.error(f"Error saving contact message: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")


# ================== CORS ==================

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================== LOGGING ==================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# ================== ROUTER ==================

app.include_router(api_router)

# ================== SHUTDOWN ==================

@app.on_event("shutdown")
async def shutdown_event():
    logging.info("Shutting down FastAPI app gracefully.")

from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from typing import List
import uuid
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging
from pathlib import Path

# ================== SETUP ==================
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Initialize Firebase only once
if not firebase_admin._apps:
    cred = credentials.Certificate(ROOT_DIR / os.environ["FIREBASE_CREDENTIALS"])
    firebase_admin.initialize_app(cred)

# Firestore client
db = firestore.client()

# ================== FASTAPI APP ==================
app = FastAPI(title="FastAPI + Firebase API", version="1.0")
api_router = APIRouter(prefix="/api")

# ================== MODELS ==================

# ----- STORY MODELS -----
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


# ----- CONTACT MODELS (NEW) -----
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
    return {"message": "Hello from Firebase-backed FastAPI!"}


# ===== STORIES APIs =====

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


# ===== CONTACT FORM API (NEW) =====

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


# ================== MIDDLEWARE ==================

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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ================== INCLUDE ROUTER ==================
app.include_router(api_router)

# ================== SHUTDOWN ==================
@app.on_event("shutdown")
async def shutdown_event():
    logging.info("Shutting down FastAPI app gracefully.")

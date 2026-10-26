"""FastAPI server: serves the HTML interface and the JSON API.

Run with:  uvicorn server:app --reload
Then open: http://127.0.0.1:8000
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from anthropic import APIError
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from fridge_chef import core

load_dotenv()

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

MAX_PHOTOS = 4
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB per photo

app = FastAPI(title="Fridge Chef")


@lru_cache(maxsize=1)
def get_client():
    return core.make_client()


class RecipeRequest(BaseModel):
    ingredients: str = Field(max_length=2000)
    diet: str = "No restriction"
    cuisine: str = "Any"
    max_minutes: int = Field(30, ge=10, le=180)
    servings: int = Field(2, ge=1, le=12)
    count: int = Field(3, ge=1, le=5)

    @field_validator("ingredients")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Please add at least one ingredient.")
        return v

    @field_validator("diet")
    @classmethod
    def valid_diet(cls, v: str) -> str:
        if v not in core.DIETS:
            raise ValueError("Unknown diet option.")
        return v

    @field_validator("cuisine")
    @classmethod
    def valid_cuisine(cls, v: str) -> str:
        if v not in core.CUISINES:
            raise ValueError("Unknown cuisine option.")
        return v


def _client_or_500():
    try:
        return get_client()
    except core.MissingKeyError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


@app.get("/api/health")
def health():
    return {"status": "ok", "model": core.MODEL}


@app.get("/api/options")
def options():
    """Lets the browser build its dropdowns from the server's lists."""
    return {"diets": core.DIETS, "cuisines": core.CUISINES}


@app.post("/api/detect")
def detect(files: list[UploadFile] = File(...)):
    if not files or len(files) > MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"Send between 1 and {MAX_PHOTOS} photos.")

    images: list[tuple[bytes, str]] = []
    for f in files:
        if f.content_type not in core.ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP or GIF photos are supported.")
        data = f.file.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="Each photo must be 5 MB or smaller.")
        if not data:
            raise HTTPException(status_code=400, detail="One of the photos was empty.")
        images.append((data, f.content_type))

    client = _client_or_500()
    try:
        return {"ingredients": core.detect_ingredients(client, images)}
    except core.ModelOutputError as err:
        raise HTTPException(status_code=502, detail="Couldn't read that photo reliably. Try again.") from err
    except APIError as err:
        raise HTTPException(status_code=502, detail=f"AI service error: {err}") from err


@app.post("/api/recipes")
def recipes(req: RecipeRequest):
    client = _client_or_500()
    try:
        result = core.suggest_recipes(
            client,
            ingredients=req.ingredients,
            diet=req.diet,
            cuisine=req.cuisine,
            max_minutes=req.max_minutes,
            servings=req.servings,
            count=req.count,
        )
        return {"recipes": result}
    except core.ModelOutputError as err:
        raise HTTPException(status_code=502, detail="The AI returned something unexpected. Please try again.") from err
    except APIError as err:
        raise HTTPException(status_code=502, detail=f"AI service error: {err}") from err


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

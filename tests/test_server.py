from fastapi.testclient import TestClient

import server
from fridge_chef import core

client = TestClient(server.app)

SAMPLE_RECIPE = {
    "title": "Tomato Rice",
    "time_minutes": 25,
    "difficulty": "Easy",
    "uses": ["rice", "tomato"],
    "missing": ["cumin"],
    "substitutions": [{"missing": "cumin", "substitute": "coriander powder", "note": "milder"}],
    "steps": ["Cook rice", "Add tomato"],
}


def fake_client(monkeypatch):
    monkeypatch.setattr(server, "get_client", lambda: object())


def test_health_and_index():
    assert client.get("/api/health").json()["status"] == "ok"
    page = client.get("/")
    assert page.status_code == 200
    assert "Fridge Chef" in page.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


def test_options_lists_match_core():
    data = client.get("/api/options").json()
    assert data["diets"] == core.DIETS
    assert data["cuisines"] == core.CUISINES


def test_recipes_success(monkeypatch):
    fake_client(monkeypatch)
    monkeypatch.setattr(core, "suggest_recipes", lambda *a, **k: [SAMPLE_RECIPE])
    res = client.post("/api/recipes", json={"ingredients": "rice, tomato"})
    assert res.status_code == 200
    assert res.json()["recipes"][0]["title"] == "Tomato Rice"


def test_recipes_rejects_empty_ingredients():
    res = client.post("/api/recipes", json={"ingredients": "   "})
    assert res.status_code == 422


def test_recipes_rejects_unknown_diet():
    res = client.post("/api/recipes", json={"ingredients": "rice", "diet": "carnivore"})
    assert res.status_code == 422


def test_recipes_missing_key_gives_clear_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    server.get_client.cache_clear()
    res = client.post("/api/recipes", json={"ingredients": "rice"})
    assert res.status_code == 500
    assert "ANTHROPIC_API_KEY" in res.json()["detail"]


def test_recipes_bad_model_output_maps_to_502(monkeypatch):
    fake_client(monkeypatch)

    def boom(*a, **k):
        raise core.ModelOutputError("nope")

    monkeypatch.setattr(core, "suggest_recipes", boom)
    res = client.post("/api/recipes", json={"ingredients": "rice"})
    assert res.status_code == 502


def test_detect_success(monkeypatch):
    fake_client(monkeypatch)
    monkeypatch.setattr(core, "detect_ingredients", lambda c, imgs: ["tomato", "paneer"])
    res = client.post("/api/detect", files=[("files", ("a.png", b"\x89PNG-data", "image/png"))])
    assert res.status_code == 200
    assert res.json()["ingredients"] == ["tomato", "paneer"]


def test_detect_rejects_non_image():
    res = client.post("/api/detect", files=[("files", ("a.pdf", b"%PDF", "application/pdf"))])
    assert res.status_code == 400


def test_detect_rejects_too_many_photos():
    files = [("files", (f"{i}.png", b"x", "image/png")) for i in range(server.MAX_PHOTOS + 1)]
    assert client.post("/api/detect", files=files).status_code == 400


def test_detect_rejects_oversized_photo(monkeypatch):
    monkeypatch.setattr(server, "MAX_PHOTO_BYTES", 10)
    res = client.post("/api/detect", files=[("files", ("a.png", b"x" * 50, "image/png"))])
    assert res.status_code == 413

import pytest

from fridge_chef import core


def test_extract_json_plain_array():
    assert core.extract_json('["a", "b"]') == ["a", "b"]


def test_extract_json_with_code_fence_and_chatter():
    reply = 'Sure! Here you go:\n```json\n[{"title": "Omelette"}]\n```\nEnjoy.'
    assert core.extract_json(reply) == [{"title": "Omelette"}]


def test_extract_json_object():
    assert core.extract_json('{"ingredients": ["egg"]}') == {"ingredients": ["egg"]}


def test_extract_json_rejects_text_without_json():
    with pytest.raises(core.ModelOutputError):
        core.extract_json("I could not find anything.")


def test_extract_json_rejects_broken_json():
    with pytest.raises(core.ModelOutputError):
        core.extract_json('[{"title": "Oops"')


def test_normalize_recipes_fills_defaults_and_cleans_lists():
    raw = [
        {
            "title": "Tomato Egg Curry",
            "time_minutes": 20,
            "uses": ["egg", "Egg", " tomato "],
            "missing": [],
            "substitutions": [{"missing": "cream", "substitute": "yogurt", "note": "tangier"}],
            "steps": ["Boil eggs", "", "Simmer"],
        },
        {"no_title": True},  # dropped
    ]
    out = core.normalize_recipes(raw)
    assert len(out) == 1
    assert out[0]["uses"] == ["egg", "tomato"]
    assert out[0]["steps"] == ["Boil eggs", "Simmer"]
    assert out[0]["substitutions"][0]["substitute"] == "yogurt"
    assert out[0]["difficulty"] == ""


def test_normalize_recipes_accepts_wrapped_object():
    out = core.normalize_recipes({"recipes": [{"title": "Toast"}]})
    assert out[0]["title"] == "Toast"


def test_normalize_recipes_empty_raises():
    with pytest.raises(core.ModelOutputError):
        core.normalize_recipes([])


def test_detect_ingredients_rejects_bad_type():
    with pytest.raises(ValueError):
        core.detect_ingredients(object(), [(b"x", "application/pdf")])


def test_make_client_without_key_raises(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    with pytest.raises(core.MissingKeyError):
        core.make_client()

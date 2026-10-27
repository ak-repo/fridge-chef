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
    out = core.normalize_recipes({"recipes": [{"title": "Toast", "uses": ["bread"], "missing": [], "steps": ["Toast bread"]}]})
    assert out[0]["title"] == "Toast"
    assert out[0]["time_minutes"] is None


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


VALID_RECIPE = {"title": " Toast ", "uses": ["bread"], "missing": [], "steps": ["Toast bread"]}


@pytest.mark.parametrize("suffix", [' Extra [uncertain]', ' ["another"]', ' {"another": true}'])
def test_extract_json_ignores_trailing_content(suffix):
    assert core.extract_json('["tomato"]' + suffix) == ["tomato"]


def test_clean_strings_filters_types_and_deduplicates():
    assert core._clean_strings([None, 42, {}, " Egg ", "egg", ""]) == ["Egg"]


@pytest.mark.parametrize("changes", [
    {"title": "  "}, {"title": 42}, {"steps": []}, {"steps": [None, 42]}, {"steps": "Cook"},
    {"uses": None}, {"missing": "none"}, {"time_minutes": True},
    {"time_minutes": None}, {"time_minutes": 0}, {"time_minutes": -1},
    {"time_minutes": 2.5}, {"time_minutes": {}}, {"time_minutes": "20"},
])
def test_normalize_rejects_invalid_recipe(changes):
    with pytest.raises(core.ModelOutputError):
        core.normalize_recipes([{**VALID_RECIPE, **changes}])


@pytest.mark.parametrize("field", ["uses", "missing", "steps", "title"])
def test_normalize_rejects_missing_required_field(field):
    raw = dict(VALID_RECIPE)
    raw.pop(field)
    with pytest.raises(core.ModelOutputError):
        core.normalize_recipes([raw])


def test_normalize_preserves_steps_and_drops_invalid_recipes():
    raw = {**VALID_RECIPE, "steps": [" Stir ", "", None, "Stir", "Serve"], "time_minutes": 10}
    out = core.normalize_recipes([{"title": "Invalid"}, raw])
    assert len(out) == 1
    assert out[0]["title"] == "Toast"
    assert out[0]["steps"] == ["Stir", "Stir", "Serve"]
    assert out[0]["time_minutes"] == 10


def model_client(reply):
    from types import SimpleNamespace
    from unittest.mock import Mock
    create = Mock(return_value=SimpleNamespace(content=[SimpleNamespace(type="text", text=reply)]))
    return SimpleNamespace(messages=SimpleNamespace(create=create))


@pytest.mark.parametrize("reply, expected", [
    ('[]', []), ('{"ingredients": []}', []),
    ('{"ingredients": [" egg ", "Egg", null, 42, {}]}', ["egg"]),
])
def test_detect_sdk_response(reply, expected):
    client = model_client(reply)
    assert core.detect_ingredients(client, [(b"photo", "image/png")]) == expected
    request = client.messages.create.call_args.kwargs
    assert request["messages"][0]["content"][0]["source"]["data"] == "cGhvdG8="


@pytest.mark.parametrize("reply", ['{}', '{"ingredients": null}', '{"ingredients": "egg"}', '["egg"', 'no JSON'])
def test_detect_rejects_invalid_model_response(reply):
    with pytest.raises(core.ModelOutputError):
        core.detect_ingredients(model_client(reply), [(b"photo", "image/png")])


def test_suggest_sdk_response():
    import json
    client = model_client(json.dumps([VALID_RECIPE]))
    assert core.suggest_recipes(client, "bread")[0]["title"] == "Toast"
    assert "bread" in client.messages.create.call_args.kwargs["messages"][0]["content"]

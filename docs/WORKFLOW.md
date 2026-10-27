# Fridge Chef project workflow

This document describes the end-to-end workflow from setup through ingredient detection and recipe generation.

## 1. Configure and start the app

1. Install the packages in `requirements.txt` (and `requirements-dev.txt` to run tests).
2. Copy `.env.example` to `.env` and set `OLLAMA_API_KEY` using a key from [Ollama](https://ollama.com/settings/keys). Optionally set `OLLAMA_MODEL` or `OLLAMA_BASE_URL`; defaults are `gemma4:31b` and `https://ollama.com`.
3. Start the FastAPI app with `uvicorn server:app --reload` and open `http://127.0.0.1:8000`.
4. The optional Streamlit interface can be started with `streamlit run streamlit_app.py` after installing Streamlit.

`fridge_chef/core.py` loads the environment and creates an Anthropic SDK client configured for Ollama's compatible endpoint. Both interfaces use this shared core. The API key remains server-side; do not place it in browser code or commit `.env`.

## 2. Main user workflow

1. The browser loads the page and requests `/api/options` to populate diet and cuisine choices. Recipe submission stays disabled until options load; a failed load offers a retry button. `/api/health` reports server status and the selected model.
2. The user either types ingredients or selects up to four fridge or pantry photos. The browser serializes photo additions and resizes photos where supported, shows previews, and sends them to `/api/detect` as multipart form data. Detection stays disabled while photos are processing or a detection request is active.
3. The API checks photo count, content type, and 5 MB per-photo limit. The core converts each accepted image to base64, asks the configured vision model to identify clearly visible ingredients, parses the JSON response, removes blanks and case-insensitive duplicates, and returns the ingredient list.
4. The browser merges detected ingredients with any typed list. The user can review and edit the comma-separated ingredients before requesting recipes.
5. The browser sends ingredients and preferences (`diet`, `cuisine`, `max_minutes`, `servings`, and `count`) to `/api/recipes`. The API validates the request, then the core asks the model for recipes in the expected JSON shape.
6. The core decodes the first JSON object or array without consuming trailing commentary. Detection requires an array or an object containing an `ingredients` array; an empty array is valid. List cleaning retains only nonblank strings and deduplicates ingredients case-insensitively. Recipes require a nonblank string title, explicit `uses` and `missing` arrays, and at least one valid step. Repeated steps retain their order. Supplied cooking times must be positive integers; omitted times remain optional. Invalid recipes are dropped, and a response containing no usable recipes returns HTTP 502. The browser renders recipe cards with ingredients on hand, missing ingredients, substitutions, timing, difficulty, and steps.

## 3. Request and error handling

- Invalid or empty recipe requests return HTTP 422. Unsupported photos or invalid photo counts return HTTP 400; oversized photos return HTTP 413.
- If `OLLAMA_API_KEY` is missing, the API returns a configuration error. Add the key to `.env`, then restart the application.
- If Ollama is unavailable or returns an API error, the API responds with HTTP 502 and an AI service error detail. If the reply cannot be parsed or contains no usable recipes, the API returns HTTP 502 with a user-facing message.
- The browser displays API error details as text. It does not insert model output as HTML.

## 4. Development workflow

1. Change shared prompts, API client behavior, JSON parsing, or normalization in `fridge_chef/core.py`.
2. Change routes, input constraints, and HTTP error mapping in `server.py`.
3. Change browser interactions and presentation in `static/`; the plain HTML/CSS/JavaScript app has no build step.
4. Keep the optional Streamlit UI aligned with shared core behavior when changing configuration or recipe functionality.
5. Run `pytest` (install `requirements-dev.txt` first). Tests mock model calls and should work without an Ollama key or network access.

## Workflow map

```text
Browser
        |
        v
FastAPI routes (server.py) ---- validates input, applies limits, maps errors
        |
        v
Shared core (fridge_chef/core.py) <---- Streamlit (direct calls)
        |                             prompts, client, parsing/normalization
        |
        v
Ollama-compatible cloud endpoint ---- model response
        |
        v
Shared core -> API/UI -> user sees editable ingredients and recipe cards
```

## Browser regression tests

The browser tests use mocked HTTP/model responses and delayed image processing; no API key or running server is needed. Install the optional tooling and Chromium once:

```bash
pip install -r requirements-browser.txt
python -m playwright install chromium
pytest
```

Without Playwright installed, pytest skips the browser module and runs the core/API suite. With Playwright installed, Chromium must also be installed. The browser cases cover overlapping photo additions, detection locking during preview changes, options failure/retry, and recipe-request locking.

## Browser presentation

The browser uses a cream and sage light palette and follows the device's dark-mode setting with a matching dark palette. On desktop, the ingredient workspace sits beside preferences; mobile stacks these in reading order. Photos are optional, and the upload button supports keyboard selection as well as drag and drop. Review detected ingredients in the comma-separated editor before choosing **Find recipes**. Numeric preferences are checked before submission. Loading and retry states retain entered values, and successful generation focuses the results heading. Reduced-motion preferences disable decorative animation and smooth scrolling. There is no frontend build step or external asset dependency.

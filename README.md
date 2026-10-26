# Fridge Chef

Take a photo of your fridge, or type what you have, and get recipes with
substitutions for anything you're missing.

Built with Python (FastAPI), the [Ollama](https://ollama.com) cloud API, and a plain
HTML/CSS/JavaScript browser interface. No build step, no frontend framework.

## How it works

1. **Photo (optional):** the browser shrinks your photos and sends them to the server.
   The model's vision reads them and lists the ingredients.
2. **Edit:** the detected list appears in a text box so you can correct mistakes.
3. **Recipes:** the model suggests recipes that fit your diet, cuisine, time and servings,
   and gives a substitute for every missing ingredient.

Your API key stays on the server and is never sent to the browser.

## Project layout

```
fridge-chef/
├── server.py              FastAPI app: JSON API + serves the web page
├── fridge_chef/
│   └── core.py            Prompts, model calls, JSON parsing (no web code)
├── static/
│   ├── index.html         The browser interface
│   ├── style.css          Styles (light and dark mode)
│   └── app.js             Upload, editing, rendering, API calls
├── streamlit_app.py       Optional alternative interface
├── tests/                 pytest tests (no API key needed)
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

## Quick start

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # Windows: copy .env.example .env
# open .env and paste your Ollama API key

uvicorn server:app --reload
```

Open http://127.0.0.1:8000 in your browser.

Get a free API key at https://ollama.com/settings/keys.

## API

| Method | Path           | Purpose                                                        |
| ------ | -------------- | -------------------------------------------------------------- |
| GET    | `/api/health`  | Server status and model name                                   |
| GET    | `/api/options` | Diet and cuisine choices                                       |
| POST   | `/api/detect`  | Multipart upload (`files`, up to 4 photos, 5 MB each) → ingredients |
| POST   | `/api/recipes` | JSON `{ingredients, diet, cuisine, max_minutes, servings, count}` → recipes |

Interactive docs are available at http://127.0.0.1:8000/docs while the server runs.

## Project workflow

See [docs/WORKFLOW.md](docs/WORKFLOW.md) for the end-to-end application flow, error handling, and development workflow.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests mock the model calls, so they run offline and cost nothing.

## Optional: Streamlit interface

```bash
pip install streamlit
streamlit run streamlit_app.py
```

## Configuration

| Variable           | Default        | Meaning                                  |
| ------------------ | -------------- | ---------------------------------------- |
| `OLLAMA_API_KEY`   | (required)     | Your Ollama cloud API key                |
| `OLLAMA_MODEL`     | `gemma4:31b`   | Model for photos and recipes             |
| `OLLAMA_BASE_URL`  | `https://ollama.com` | API base URL (change to use a local Ollama server) |

## Known limitations

- Ingredient detection from photos can miss items or confuse similar ones. That is why the
  list is editable before recipes are generated.
- Recipes are AI-generated. Check allergens, cooking times and food safety yourself.
- There is no login or rate limiting, so don't expose the server publicly with your key
  without adding them.

## Ideas for next steps

- Save favourite recipes (SQLite) and a "what I cooked this week" history
- "Use up expiring items first" with expiry dates
- Nutrition estimates and calorie targets
- Malayalam / Hindi input and output
- Shopping list for missing ingredients
- Dockerfile and deployment (Render, Railway, Fly.io)

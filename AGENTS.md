# Repository Guidelines

## Project Structure & Module Organization

- `server.py` defines the FastAPI routes and serves the browser app.
- `fridge_chef/core.py` contains shared model calls, prompts, parsing, and normalization.
- `static/` holds the plain HTML, CSS, and JavaScript client; there is no frontend build step.
- `streamlit_app.py` is an optional alternate interface.
- `tests/` contains pytest coverage for the core and HTTP API. `docs/WORKFLOW.md` describes the end-to-end flow.

## Build, Test, and Development Commands

- `python -m venv venv && source venv/bin/activate` creates and activates a local environment (on Windows use `venv\\Scripts\\activate`).
- `pip install -r requirements.txt` installs runtime dependencies; `pip install -r requirements-dev.txt` adds test dependencies.
- `uvicorn server:app --reload` starts the FastAPI app at `http://127.0.0.1:8000`.
- `pytest` runs the automated suite. Tests mock model calls and should not require an API key.
- `streamlit run streamlit_app.py` starts the optional Streamlit interface when Streamlit is installed.

## Coding Style & Naming Conventions

Use four spaces for Python indentation, `snake_case` for functions and variables, and `CapWords` for classes. Keep shared behavior in `fridge_chef/core.py` so both interfaces remain consistent; keep routes and HTTP validation in `server.py`. Browser changes belong in `static/` and should use the existing plain JavaScript/CSS structure. No formatter or linter is configured, so keep changes consistent with nearby code.

## Testing Guidelines

Use pytest. Name test modules `test_*.py` and test functions `test_*`. Add or update tests alongside changes to parsing, normalization, validation, or route behavior. Mock external model calls so tests remain offline and do not incur API usage. Run `pytest` from the repository root.

## Agentic Change History

For each task where an agent makes or proposes code changes, append an entry to `docs/AGENTIC_PROMPT_HISTORY.md`. Record the date, the user's prompt, a short summary of files and decisions, and verification performed (or why none was run). Preserve the user's wording when practical, but omit secrets, credentials, and other sensitive data. Keep entries chronological; do not rewrite earlier entries.

## Commit & Pull Request Guidelines

Do not create commits or run `git push` or `git pull`. Leave changes in the working tree for the repository owner to review and manage. Recent history uses Conventional Commit-style prefixes, for example `feat: ...`; follow this convention when describing proposed changes. Pull request descriptions should explain the user-visible change, note configuration or API impact, and include test results. For browser-facing changes, include a screenshot when it helps reviewers assess the result; link related issues when available.

## Security & Configuration

Copy `.env.example` to `.env` and set `OLLAMA_API_KEY` locally. Never commit `.env` or expose credentials in browser code. Keep model/API configuration server-side and avoid logging secrets.

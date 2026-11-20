# Hali Backend

FastAPI authentication API for the Hali frontend.

## Run locally

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Set `AUTH_SECRET_KEY` in `.env` to a private random value (for example, generate one with `openssl rand -hex 32`). Set `AUTH_COUNSELLOR_INVITE_CODE` if counsellor sign-up is needed. Keep `.env` private; it is ignored by Git.

Start the API from this directory:

```sh
DATABASE_URL=sqlite:///./hali.db uvicorn app.main:app --env-file .env --reload --port 8001
```

The Hali frontend's Vite development server proxies `/api` requests to port 8001. For a hosted API, configure `VITE_API_BASE_URL` in the frontend with the API's `/api` URL and configure the backend's `ALLOWED_ORIGINS`.

Run backend tests with:

```sh
python -m pytest tests
```

Production deployments require a private `AUTH_SECRET_KEY`, a persistent non-SQLite database, `ENVIRONMENT=production`, HTTPS, and the correct `ALLOWED_ORIGINS`.

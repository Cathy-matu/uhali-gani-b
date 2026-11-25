# Hali Backend

FastAPI authentication API for the Hali frontend.

## Run locally

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Set `AUTH_SECRET_KEY` in `.env` to a private random value (for example, generate one with `openssl rand -hex 32`). This is the session-signing key; it is **not** the counsellor invitation code. To enable counsellor sign-up, set `AUTH_COUNSELLOR_INVITE_CODE` to the code counsellors will enter in the registration form. Keep `.env` private; it is ignored by Git.

The invitation code is case-sensitive; surrounding spaces are ignored. If registration returns `403`, check that the running backend loaded the same `AUTH_COUNSELLOR_INVITE_CODE` from this `.env`, then stop and restart the API. If that variable was previously exported in the shell, run `unset AUTH_COUNSELLOR_INVITE_CODE` before restarting to use the `.env` value instead. Never put real secrets in `.env.example`.

Start the API from this directory:

```sh
DATABASE_URL=sqlite:///./hali.db uvicorn app.main:app --env-file .env --reload --port 8001
```

The Hali frontend's Vite development server proxies `/api` requests to port 8001. For separate production hosts, set the frontend build variable `VITE_API_BASE_URL` to the backend's full `/api` URL, and set `ALLOWED_ORIGINS` to the exact frontend origin (scheme and host, no path). The API allows credentialed CORS requests for those origins.

The session is stored in an HTTP-only cookie. Keep the frontend and API on the same site where possible (for example, `hali.example.com` and `api.example.com`) so browsers can send the cookie reliably. For genuinely cross-site hosts, set `AUTH_COOKIE_SAMESITE=none`; this requires `ENVIRONMENT=production` and HTTPS. Some browsers restrict third-party cookies, so a same-site custom domain or same-origin `/api` reverse proxy is more reliable. Do not use wildcard origins with credentials.

Run backend tests with:

```sh
python -m pytest tests
```

Production deployments require a private `AUTH_SECRET_KEY`, a persistent non-SQLite database, `ENVIRONMENT=production`, HTTPS, and the correct `ALLOWED_ORIGINS`.

import os
import secrets
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, DATABASE_URL, engine, get_db
from .models import User
from .schemas import ConsentUpdateRequest, LoginRequest, RegisterRequest, UserResponse
from .security import (
    SESSION_COOKIE,
    SESSION_TTL,
    create_session_token,
    get_auth_secret,
    hash_password,
    read_session_user_id,
    verify_password,
)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").casefold()
COOKIE_SECURE = ENVIRONMENT == "production"
COOKIE_SAMESITE = "lax"
COOKIE_PATH = "/api"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_auth_secret()
    if ENVIRONMENT == "production" and DATABASE_URL.startswith("sqlite"):
        raise RuntimeError("Production deployments must use a managed database, not SQLite.")
    Base.metadata.create_all(bind=engine)
    ensure_username_schema()
    yield


def ensure_username_schema() -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    if "username" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(32)"))
    with engine.begin() as connection:
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username ON users (username)")
        )


app = FastAPI(title="Hali API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type"],
)

auth_router = APIRouter(prefix="/api")
Database = Annotated[Session, Depends(get_db)]


def set_session_cookie(response: Response, user_id: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(user_id),
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path=COOKIE_PATH,
    )


def get_current_user(request: Request, db: Database) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = read_session_user_id(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in to continue.",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@auth_router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Database) -> User:
    if payload.role == "counsellor":
        invitation = os.getenv("AUTH_COUNSELLOR_INVITE_CODE", "")
        supplied = payload.counsellor_invite_code or ""
        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Counsellor registration is not configured. Contact your university.",
            )
        if not secrets.compare_digest(supplied.encode("utf-8"), invitation.encode("utf-8")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="That counsellor invitation code is not valid.",
            )

    user = User(
        full_name=payload.full_name,
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        pseudonym=f"Hali-{secrets.token_urlsafe(12)}" if payload.role == "student" else None,
        research_consent=payload.research_consent,
        recontact_consent=payload.recontact_consent,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email or username already exists. Try signing in instead.",
        ) from error
    db.refresh(user)
    set_session_cookie(response, user.id)
    return user


@auth_router.post("/auth/login", response_model=UserResponse)
def login(payload: LoginRequest, response: Response, db: Database) -> User:
    user_column = User.email if "@" in payload.identifier else User.username
    user = db.scalar(select(User).where(user_column == payload.identifier))
    if user is None or not verify_password(user.password_hash, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The username/email or password you entered is incorrect.",
        )
    set_session_cookie(response, user.id)
    return user


@auth_router.get("/auth/me", response_model=UserResponse)
def me(user: CurrentUser) -> User:
    return user


@auth_router.patch("/auth/consent", response_model=UserResponse)
def update_consent(payload: ConsentUpdateRequest, user: CurrentUser, db: Database) -> User:
    user.research_consent = payload.research
    user.recontact_consent = payload.recontact
    db.commit()
    db.refresh(user)
    return user


@auth_router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path=COOKIE_PATH,
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


app.include_router(auth_router)

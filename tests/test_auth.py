import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.database import Base, engine
from app.main import app, ensure_username_schema


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def register_student(client):
    return client.post(
        "/api/auth/register",
        json={
            "full_name": "Amina Wekesa",
            "username": "amina.w",
            "email": "AMINA@UNIVERSITY.EDU",
            "password": "a-very-long-test-password",
            "role": "student",
            "research_consent": True,
        },
    )


def test_student_can_register_and_restore_session(client):
    response = register_student(client)

    assert response.status_code == 201
    assert response.json()["username"] == "amina.w"
    assert response.json()["email"] == "amina@university.edu"
    assert response.json()["role"] == "student"
    assert response.json()["pseudonym"].startswith("Hali-")
    assert response.json()["research_consent"] is True
    assert response.json()["recontact_consent"] is False
    assert "password_hash" not in response.json()
    assert "httponly" in response.headers["set-cookie"].lower()

    session = client.get("/api/auth/me")
    assert session.status_code == 200
    assert session.json()["id"] == response.json()["id"]


def test_duplicate_email_is_rejected(client):
    assert register_student(client).status_code == 201

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Another Student",
            "username": "another.student",
            "email": "amina@university.edu",
            "password": "another-long-password",
            "role": "student",
        },
    )

    assert response.status_code == 409


def test_duplicate_username_is_rejected_case_insensitively(client):
    assert register_student(client).status_code == 201

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Another Student",
            "username": "AMINA.W",
            "email": "another@university.edu",
            "password": "another-long-password",
            "role": "student",
        },
    )

    assert response.status_code == 409


def test_counsellor_registration_requires_invitation(client):
    payload = {
        "full_name": "Counsellor Account",
        "username": "counsellor.account",
        "email": "counsellor@university.edu",
        "password": "a-very-long-test-password",
        "role": "counsellor",
    }
    assert client.post("/api/auth/register", json=payload).status_code == 403

    response = client.post(
        "/api/auth/register",
        json={**payload, "counsellor_invite_code": "test-counsellor-invite"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "counsellor"


def test_login_uses_password_and_account_role(client):
    register_student(client)

    response = client.post(
        "/api/auth/login",
        json={"identifier": "amina.w", "password": "wrong-password"},
    )
    assert response.status_code == 401

    response = client.post(
        "/api/auth/login",
        json={"identifier": "AMINA.W", "password": "a-very-long-test-password"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "student"

    email_login = client.post(
        "/api/auth/login",
        json={"identifier": "AMINA@UNIVERSITY.EDU", "password": "a-very-long-test-password"},
    )
    assert email_login.status_code == 200


def test_logout_clears_session(client):
    register_student(client)
    assert client.get("/api/auth/me").status_code == 200

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_consent_choices_are_persisted_for_the_authenticated_user(client):
    register_student(client)

    response = client.patch(
        "/api/auth/consent",
        json={"research": False, "recontact": True},
    )

    assert response.status_code == 200
    assert response.json()["research_consent"] is False
    assert response.json()["recontact_consent"] is True
    assert client.get("/api/auth/me").json()["recontact_consent"] is True


def test_registration_rejects_unsupported_roles_and_short_passwords(client):
    payload = {
        "full_name": "Test Account",
        "username": "test.user",
        "email": "test@university.edu",
        "password": "short",
        "role": "admin",
    }

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 422


def test_registration_rejects_invalid_username(client):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test Account",
            "username": "invalid username",
            "email": "test@university.edu",
            "password": "a-very-long-test-password",
            "role": "student",
        },
    )

    assert response.status_code == 422


def test_existing_users_table_gets_optional_username_column():
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY)"))

    ensure_username_schema()

    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    assert "username" in columns
    Base.metadata.drop_all(bind=engine)

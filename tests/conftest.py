import os

os.environ["AUTH_SECRET_KEY"] = "test-only-secret-key-that-is-at-least-thirty-two-characters"
os.environ["AUTH_COUNSELLOR_INVITE_CODE"] = "test-counsellor-invite"
os.environ["DATABASE_URL"] = "sqlite://"

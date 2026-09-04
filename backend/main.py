"""`uvicorn main:app --reload` 지원용 재노출."""
from app.main import app  # noqa: F401

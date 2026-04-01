# pyright: reportMissingImports=false

from fastapi import HTTPException, Request, status

from ollama_router.admin.auth import validate_session
from ollama_router.config import Config


def get_current_user(request: Request) -> str:
    config: Config = request.app.state.config
    session_token = request.cookies.get("admin_session")
    username = validate_session(session_token, config.admin_session_secret)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return username

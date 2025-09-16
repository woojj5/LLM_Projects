import jwt
from fastapi import Header, HTTPException
from .config import settings
from fastapi.middleware.cors import CORSMiddleware

def auth_guard(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing token")
    token = authorization.split(" ", 1)[1]
    try:
        jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid token")

def apply_cors(app, origins: list[str] | None = None):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

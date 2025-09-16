from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import jwt, time
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginReq(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(req: LoginReq):
    if not (req.username and req.password):
        raise HTTPException(401, "invalid credentials")
    payload = {"sub": req.username, "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}

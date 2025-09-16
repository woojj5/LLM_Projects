from datetime import datetime, timedelta
import jwt
from ..config import settings


SECRET = settings.jwt_secret
ALG = settings.jwt_algorithm




def create_token(user_id: str, exp_minutes=60):
    payload = {"sub": user_id, "exp": datetime.utcnow() + timedelta(minutes=exp_minutes)}
    return jwt.encode(payload, SECRET, algorithm=ALG)




def verify_token(token: str):
    try:
        return jwt.decode(token, SECRET, algorithms=[ALG])
    except jwt.PyJWTError:
        return None
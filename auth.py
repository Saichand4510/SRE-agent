from jose import jwt, JWTError,ExpiredSignatureError
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi import Request
import os


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd_context = CryptContext(schemes=["bcrypt"])

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_token(username: str):
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
def get_current_user(request:Request,token: str = Depends(oauth2_scheme)):
    username= decode_token(token)
    request.state.user = username

    return username
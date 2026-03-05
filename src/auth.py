from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .config import settings

# using bcrypt for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# the endpoint where we get the token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    # helper to generate a jwt token with an expiry time
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # default to 15 mins if not specified
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    # signing the token with our secret key
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    # this function checks if the token provided in the request is valid
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Couldn't validate those credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # decode the token and get the username
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

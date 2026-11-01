import hashlib, hmac, os
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User

RANK = {"viewer": 1, "engineer": 2, "admin": 3}
_bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(16).hex()
    return f"{salt}${hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), 120_000).hex()}"


def verify_password(pw: str, stored: str) -> bool:
    salt, _ = stored.split("$")
    return hmac.compare_digest(hash_password(pw, salt), stored)


def create_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.TOKEN_TTL_MIN)
    return jwt.encode({"sub": user.username, "exp": exp}, settings.SECRET_KEY, algorithm="HS256")


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(401, "authentication required")
    try:
        sub = jwt.decode(creds.credentials, settings.SECRET_KEY, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid or expired token")
    user = db.query(User).filter_by(username=sub, active=True).first()  # role always read from DB
    if not user:
        raise HTTPException(401, "unknown or disabled user")
    return user


def require_role(minimum: str):
    def dep(user: User = Depends(current_user)) -> User:
        if RANK[user.role] < RANK[minimum]:
            raise HTTPException(403, f"requires role '{minimum}' or higher")
        return user
    return dep

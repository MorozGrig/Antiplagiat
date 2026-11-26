"""Basic user registration and JWT login endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from jose import jwt
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_db
from app.models.enums import UserRole, UserStatus
from app.models.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])
_passwords = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    username_or_email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    role: str


class AuthResponse(TokenResponse):
    user: UserResponse


def _issue_token(user: User) -> tuple[str, int]:
    settings = get_settings()
    expires = int(settings.access_token_expire_minutes * 60)
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user.id), "iat": now, "exp": now + timedelta(seconds=expires)},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_db)):
    existing = await session.scalar(
        select(User.id).where(
            or_(User.username == payload.username, User.email == str(payload.email).lower())
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Имя пользователя или email уже заняты")

    user = User(
        username=payload.username,
        email=str(payload.email).lower(),
        password_hash=_passwords.hash(payload.password),
        role=UserRole.user,
        status=UserStatus.active,
    )
    session.add(user)
    try:
        await session.flush()
        await session.refresh(user)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Имя пользователя или email уже заняты") from exc

    token, expires = _issue_token(user)
    return AuthResponse(
        access_token=token,
        expires_in=expires,
        user=UserResponse(id=str(user.id), username=user.username, email=user.email, role=user.role.value),
    )


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)):
    user = await session.scalar(
        select(User).where(
            or_(User.username == payload.username_or_email, User.email == payload.username_or_email.lower())
        )
    )
    if (
        user is None
        or user.status != UserStatus.active
        or not _passwords.verify(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, expires = _issue_token(user)
    return AuthResponse(
        access_token=token,
        expires_in=expires,
        user=UserResponse(id=str(user.id), username=user.username, email=user.email, role=user.role.value),
    )

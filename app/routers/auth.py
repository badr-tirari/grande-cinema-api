"""US01 - Inscription et connexion."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.db import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["Authentification"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    """Crée un compte spectateur (rôle USER)."""
    email = payload.email.lower()
    if db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cet email")
    user = User(email=email, full_name=payload.full_name, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    """Connexion (formulaire OAuth2 : `username` = email). Renvoie un jeton JWT."""
    user = db.scalars(select(User).where(User.email == form.username.lower())).first()
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email ou mot de passe incorrect")
    return Token(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    """Profil de l'utilisateur connecté."""
    return user

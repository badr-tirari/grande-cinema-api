"""Fixtures de test : base SQLite en mémoire isolée pour chaque test."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret-key-with-at-least-32-bytes!")

from datetime import UTC, datetime, timedelta  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Movie, Role, Showtime, User  # noqa: E402
from app.services.booking import create_room_with_seats, ends_at_for  # noqa: E402

PASSWORD = "Motdepasse-123"


def paris_day(dt: datetime) -> str:
    """Jour (AAAA-MM-JJ) d'une date dans le fuseau du cinéma."""
    from zoneinfo import ZoneInfo

    aware = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return aware.astimezone(ZoneInfo("Europe/Paris")).date().isoformat()


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def data(db_session):
    """Une salle de 2 x 3 places, un film, une séance demain et une séance passée."""
    room = create_room_with_seats(db_session, "Salle Test", 2, 3)
    movie = Movie(title="Blue Note Nights", description="Jazz", genre="Documentaire", duration_min=90)
    db_session.add(movie)
    db_session.flush()
    tomorrow = datetime.now(UTC) + timedelta(days=1)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    future = Showtime(
        movie_id=movie.id,
        room_id=room.id,
        starts_at=tomorrow,
        ends_at=ends_at_for(tomorrow, 90),
        price_cents=1000,
    )
    past = Showtime(
        movie_id=movie.id,
        room_id=room.id,
        starts_at=yesterday,
        ends_at=ends_at_for(yesterday, 90),
        price_cents=1000,
    )
    db_session.add_all([future, past])
    db_session.add_all(
        [
            User(email="user@test.fr", full_name="User Test", hashed_password=hash_password(PASSWORD)),
            User(email="other@test.fr", full_name="Other Test", hashed_password=hash_password(PASSWORD)),
            User(
                email="admin@test.fr",
                full_name="Admin Test",
                hashed_password=hash_password(PASSWORD),
                role=Role.ADMIN,
            ),
        ]
    )
    db_session.commit()
    return {"room": room, "movie": movie, "future": future, "past": past, "seats": [s.id for s in room.seats]}


def login(client, email: str) -> dict[str, str]:
    r = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def user_headers(client, data):
    return login(client, "user@test.fr")


@pytest.fixture
def other_headers(client, data):
    return login(client, "other@test.fr")


@pytest.fixture
def admin_headers(client, data):
    return login(client, "admin@test.fr")

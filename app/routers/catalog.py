"""US02 - Films et horaires ; US03 - Places disponibles en temps réel (accès public)."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Movie, Showtime
from app.schemas import MovieOut, MovieWithShowtimes, ShowtimeOut
from app.services.booking import count_booked, local_day_bounds

router = APIRouter(prefix="/api", tags=["Catalogue"])


def _showtime_out(db: Session, showtime: Showtime) -> ShowtimeOut:
    out = ShowtimeOut.model_validate(showtime)
    out.available_seats = showtime.room.capacity - count_booked(db, showtime.id)
    return out


@router.get("/movies", response_model=list[MovieOut])
def list_movies(
    search: str | None = Query(default=None, description="Filtre sur le titre"),
    db: Session = Depends(get_db),
) -> list[Movie]:
    """Films à l'affiche, triés par titre."""
    stmt = select(Movie).order_by(Movie.title)
    if search:
        stmt = stmt.where(Movie.title.ilike(f"%{search}%"))
    return list(db.scalars(stmt))


@router.get("/movies/{movie_id}", response_model=MovieWithShowtimes)
def get_movie(movie_id: int, db: Session = Depends(get_db)) -> MovieWithShowtimes:
    """Détail d'un film avec ses séances à venir."""
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(404, "Film introuvable")
    now = datetime.now(UTC)
    stmt = (
        select(Showtime)
        .where(Showtime.movie_id == movie_id, Showtime.starts_at > now)
        .options(selectinload(Showtime.room))
        .order_by(Showtime.starts_at)
    )
    result = MovieWithShowtimes.model_validate(movie)
    result.showtimes = [_showtime_out(db, s) for s in db.scalars(stmt)]
    return result


@router.get("/showtimes", response_model=list[ShowtimeOut])
def list_showtimes(
    day: date | None = Query(default=None, description="Jour (AAAA-MM-JJ). Par défaut : à venir"),
    movie_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[ShowtimeOut]:
    """Séances à venir, filtrables par jour et par film."""
    stmt = select(Showtime).options(selectinload(Showtime.room)).order_by(Showtime.starts_at)
    if day:
        start, end = local_day_bounds(day)
        stmt = stmt.where(Showtime.starts_at >= start, Showtime.starts_at < end)
    else:
        stmt = stmt.where(Showtime.starts_at > datetime.now(UTC))
    if movie_id:
        stmt = stmt.where(Showtime.movie_id == movie_id)
    return [_showtime_out(db, s) for s in db.scalars(stmt)]

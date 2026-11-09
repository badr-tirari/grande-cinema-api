"""US07 - Programmation ; US08 - Suivi des réservations ; US09 - Taux de remplissage.

Toutes les routes exigent le rôle ADMIN (dépendance `require_admin` au niveau du routeur).
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db import get_db
from app.models import Booking, Movie, Room, Showtime
from app.schemas import (
    MovieCreate,
    MovieOut,
    MovieUpdate,
    RoomOut,
    ShowtimeCreate,
    ShowtimeOut,
    ShowtimeUpdate,
)
from app.services.booking import (
    BookingError,
    check_room_free,
    count_booked,
    ends_at_for,
)

router = APIRouter(prefix="/api/admin", tags=["Administration"], dependencies=[Depends(require_admin)])


def _http(exc: BookingError) -> HTTPException:
    return HTTPException(exc.status_code, exc.message)


# --- Salles -------------------------------------------------------------------
@router.get("/rooms", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db)) -> list[Room]:
    return list(db.scalars(select(Room).order_by(Room.id)))


# --- Films (US07) ---------------------------------------------------------------
@router.post("/movies", response_model=MovieOut, status_code=status.HTTP_201_CREATED)
def create_movie(payload: MovieCreate, db: Session = Depends(get_db)) -> Movie:
    movie = Movie(**payload.model_dump())
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie


@router.patch("/movies/{movie_id}", response_model=MovieOut)
def update_movie(movie_id: int, payload: MovieUpdate, db: Session = Depends(get_db)) -> Movie:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(404, "Film introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(movie, field, value)
    db.commit()
    db.refresh(movie)
    return movie


@router.delete("/movies/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_movie(movie_id: int, db: Session = Depends(get_db)) -> Response:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(404, "Film introuvable")
    has_bookings = db.scalar(
        select(func.count(Booking.id)).join(Showtime).where(Showtime.movie_id == movie_id)
    )
    if has_bookings:
        raise HTTPException(409, "Film avec réservations : supprimez d'abord ses séances futures")
    db.delete(movie)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Séances (US07) -------------------------------------------------------------
def _showtime_out(db: Session, showtime: Showtime) -> ShowtimeOut:
    out = ShowtimeOut.model_validate(showtime)
    out.available_seats = showtime.room.capacity - count_booked(db, showtime.id)
    return out


@router.post("/showtimes", response_model=ShowtimeOut, status_code=status.HTTP_201_CREATED)
def create_showtime(payload: ShowtimeCreate, db: Session = Depends(get_db)) -> ShowtimeOut:
    movie = db.get(Movie, payload.movie_id)
    room = db.get(Room, payload.room_id)
    if movie is None or room is None:
        raise HTTPException(404, "Film ou salle introuvable")
    ends_at = ends_at_for(payload.starts_at, movie.duration_min)
    try:
        check_room_free(db, room.id, payload.starts_at, ends_at)
    except BookingError as exc:
        raise _http(exc) from None
    showtime = Showtime(
        movie_id=movie.id,
        room_id=room.id,
        starts_at=payload.starts_at,
        ends_at=ends_at,
        price_cents=payload.price_cents,
    )
    db.add(showtime)
    db.commit()
    db.refresh(showtime)
    return _showtime_out(db, showtime)


@router.patch("/showtimes/{showtime_id}", response_model=ShowtimeOut)
def update_showtime(showtime_id: int, payload: ShowtimeUpdate, db: Session = Depends(get_db)) -> ShowtimeOut:
    showtime = db.get(Showtime, showtime_id)
    if showtime is None:
        raise HTTPException(404, "Séance introuvable")
    data = payload.model_dump(exclude_unset=True)
    if ("room_id" in data or "starts_at" in data) and count_booked(db, showtime_id):
        raise HTTPException(409, "Séance avec réservations : salle et horaire ne sont plus modifiables")
    if "room_id" in data and db.get(Room, data["room_id"]) is None:
        raise HTTPException(404, "Salle introuvable")
    for field, value in data.items():
        setattr(showtime, field, value)
    showtime.ends_at = ends_at_for(showtime.starts_at, showtime.movie.duration_min)
    try:
        check_room_free(db, showtime.room_id, showtime.starts_at, showtime.ends_at, exclude_id=showtime.id)
    except BookingError as exc:
        db.rollback()
        raise _http(exc) from None
    db.commit()
    db.refresh(showtime)
    return _showtime_out(db, showtime)


@router.delete("/showtimes/{showtime_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_showtime(showtime_id: int, db: Session = Depends(get_db)) -> Response:
    showtime = db.get(Showtime, showtime_id)
    if showtime is None:
        raise HTTPException(404, "Séance introuvable")
    if count_booked(db, showtime_id):
        raise HTTPException(409, "Séance avec réservations confirmées : suppression impossible")
    for booking in list(showtime.bookings):  # réservations annulées uniquement
        db.delete(booking)
    db.delete(showtime)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Suivi des réservations (US08) ---------------------------------------------------
# --- Taux de remplissage (US09) ---------------------------------------------------------

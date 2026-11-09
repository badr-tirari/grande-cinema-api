"""US07 - Programmation ; US08 - Suivi des réservations ; US09 - Taux de remplissage.

Toutes les routes exigent le rôle ADMIN (dépendance `require_admin` au niveau du routeur).
"""

from collections import defaultdict
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.security import require_admin
from app.db import get_db
from app.models import BookedSeat, Booking, BookingStatus, Movie, Room, Showtime
from app.routers.bookings import to_out
from app.schemas import (
    BookingOut,
    MovieCreate,
    MovieOut,
    MovieUpdate,
    OccupancyItem,
    OccupancyReport,
    RoomOut,
    ShowtimeCreate,
    ShowtimeOut,
    ShowtimeUpdate,
    SlotOccupancy,
)
from app.services.booking import (
    BookingError,
    as_utc,
    check_room_free,
    count_booked,
    ends_at_for,
    load_booking,
    local_day_bounds,
)

router = APIRouter(prefix="/api/admin", tags=["Administration"], dependencies=[Depends(require_admin)])

PEAK_THRESHOLD = 0.8


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
@router.get("/bookings", response_model=list[BookingOut])
def list_bookings(
    showtime_id: int | None = None,
    day: date | None = Query(default=None, description="Jour de la séance (AAAA-MM-JJ)"),
    booking_status: BookingStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[BookingOut]:
    stmt = select(Booking.id).join(Showtime).order_by(Booking.created_at.desc())
    if showtime_id:
        stmt = stmt.where(Booking.showtime_id == showtime_id)
    if day:
        start, end = local_day_bounds(day)
        stmt = stmt.where(Showtime.starts_at >= start, Showtime.starts_at < end)
    if booking_status:
        stmt = stmt.where(Booking.status == booking_status)
    return [to_out(load_booking(db, i), with_email=True) for i in db.scalars(stmt)]


# --- Taux de remplissage (US09) ---------------------------------------------------------
def slot_of(starts_at: datetime) -> str:
    """Regroupe les séances par créneau (heure locale du cinéma) pour repérer les pics."""
    hour = as_utc(starts_at).astimezone(get_settings().tz).hour
    if hour < 14:
        return "Matin (< 14h)"
    if hour < 18:
        return "Après-midi (14h-18h)"
    if hour < 21:
        return "Soirée (18h-21h)"
    return "Nuit (>= 21h)"


def rate(booked: int, capacity: int) -> float:
    return round(booked / capacity, 4) if capacity else 0.0


@router.get("/stats/occupancy", response_model=OccupancyReport)
def occupancy(
    date_from: date | None = Query(default=None, description="Début (inclus)"),
    date_to: date | None = Query(default=None, description="Fin (incluse)"),
    db: Session = Depends(get_db),
) -> OccupancyReport:
    booked_sub = (
        select(BookedSeat.showtime_id, func.count(BookedSeat.id).label("booked"))
        .group_by(BookedSeat.showtime_id)
        .subquery()
    )
    stmt = (
        select(Showtime, func.coalesce(booked_sub.c.booked, 0))
        .outerjoin(booked_sub, booked_sub.c.showtime_id == Showtime.id)
        .options(selectinload(Showtime.movie), selectinload(Showtime.room))
        .order_by(Showtime.starts_at)
    )
    if date_from:
        stmt = stmt.where(Showtime.starts_at >= local_day_bounds(date_from)[0])
    if date_to:
        stmt = stmt.where(Showtime.starts_at < local_day_bounds(date_to)[1])

    items: list[OccupancyItem] = []
    slots: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # séances, réservées, capacité
    for showtime, booked in db.execute(stmt).all():
        capacity = showtime.room.capacity
        r = rate(booked, capacity)
        items.append(
            OccupancyItem(
                showtime_id=showtime.id,
                movie_title=showtime.movie.title,
                room=showtime.room.name,
                starts_at=showtime.starts_at,
                booked=booked,
                capacity=capacity,
                occupancy_rate=r,
                peak=r >= PEAK_THRESHOLD,
            )
        )
        agg = slots[slot_of(showtime.starts_at)]
        agg[0] += 1
        agg[1] += booked
        agg[2] += capacity

    total_booked = sum(i.booked for i in items)
    total_capacity = sum(i.capacity for i in items)
    return OccupancyReport(
        global_rate=rate(total_booked, total_capacity),
        peak_threshold=PEAK_THRESHOLD,
        by_showtime=items,
        by_slot=[
            SlotOccupancy(slot=k, showtimes=v[0], booked=v[1], capacity=v[2], occupancy_rate=rate(v[1], v[2]))
            for k, v in sorted(slots.items())
        ],
    )

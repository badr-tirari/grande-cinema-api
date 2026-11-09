"""Règles métier de la réservation (indépendantes du framework HTTP)."""

import secrets
import string
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models import BookedSeat, Booking, BookingStatus, Room, Seat, Showtime, User


class BookingError(Exception):
    """Erreur métier, traduite en réponse HTTP par la couche API."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def as_utc(value: datetime) -> datetime:
    """SQLite renvoie des dates sans fuseau : on les considère en UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    """Début et fin (exclue) d'une journée dans le fuseau du cinéma (Europe/Paris)."""
    start = datetime.combine(day, time.min, tzinfo=get_settings().tz)
    return start, start + timedelta(days=1)


def generate_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "GC-" + "".join(secrets.choice(alphabet) for _ in range(length))


def booked_seat_ids(db: Session, showtime_id: int) -> set[int]:
    rows = db.scalars(select(BookedSeat.seat_id).where(BookedSeat.showtime_id == showtime_id))
    return set(rows)


def count_booked(db: Session, showtime_id: int) -> int:
    stmt = select(func.count(BookedSeat.id)).where(BookedSeat.showtime_id == showtime_id)
    return db.scalar(stmt) or 0


def get_showtime_or_404(db: Session, showtime_id: int) -> Showtime:
    showtime = db.get(Showtime, showtime_id)
    if showtime is None:
        raise BookingError("Séance introuvable", 404)
    return showtime


def check_room_free(
    db: Session, room_id: int, starts_at: datetime, ends_at: datetime, exclude_id: int | None = None
) -> None:
    """Refuse deux séances qui se chevauchent dans la même salle (US07)."""
    stmt = select(Showtime).where(
        Showtime.room_id == room_id,
        Showtime.starts_at < ends_at,
        Showtime.ends_at > starts_at,
    )
    if exclude_id is not None:
        stmt = stmt.where(Showtime.id != exclude_id)
    if db.scalars(stmt).first() is not None:
        raise BookingError("La salle est déjà occupée sur ce créneau", 409)


def ends_at_for(starts_at: datetime, duration_min: int, cleaning_min: int = 15) -> datetime:
    return starts_at + timedelta(minutes=duration_min + cleaning_min)


def create_booking(db: Session, user: User, showtime_id: int, seat_ids: list[int]) -> Booking:
    """Réserve des places pour une séance (US04).

    Ordre des contrôles : séance existante, séance non commencée, nombre de places,
    places appartenant bien à la salle, places libres.
    """
    settings = get_settings()
    showtime = get_showtime_or_404(db, showtime_id)

    if as_utc(showtime.starts_at) <= datetime.now(UTC):
        raise BookingError("Cette séance a déjà commencé", 400)
    if len(seat_ids) > settings.max_seats_per_booking:
        raise BookingError(f"Maximum {settings.max_seats_per_booking} places par réservation", 400)

    seats = db.scalars(select(Seat).where(Seat.id.in_(seat_ids), Seat.room_id == showtime.room_id)).all()
    if len(seats) != len(seat_ids):
        raise BookingError("Une ou plusieurs places n'existent pas dans cette salle", 400)

    already_taken = booked_seat_ids(db, showtime_id) & set(seat_ids)
    if already_taken:
        raise BookingError("Une ou plusieurs places viennent d'être réservées", 409)

    booking = Booking(
        code=generate_code(),
        user_id=user.id,
        showtime_id=showtime.id,
        status=BookingStatus.CONFIRMED,
        total_cents=showtime.price_cents * len(seats),
    )
    booking.seats = [BookedSeat(showtime_id=showtime.id, seat_id=seat.id) for seat in seats]
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def cancel_booking(db: Session, booking: Booking) -> Booking:
    """Annule une réservation et libère immédiatement les places (US06)."""
    if booking.status == BookingStatus.CANCELLED:
        raise BookingError("Réservation déjà annulée", 400)
    if as_utc(booking.showtime.starts_at) <= datetime.now(UTC):
        raise BookingError("Impossible d'annuler une séance commencée", 400)
    booking.status = BookingStatus.CANCELLED
    booking.seats.clear()
    db.commit()
    db.refresh(booking)
    return booking


def load_booking(db: Session, booking_id: int) -> Booking | None:
    stmt = (
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.seats).selectinload(BookedSeat.seat),
            selectinload(Booking.showtime).selectinload(Showtime.movie),
            selectinload(Booking.showtime).selectinload(Showtime.room),
            selectinload(Booking.user),
        )
    )
    return db.scalars(stmt).first()


def create_room_with_seats(db: Session, name: str, rows: int, seats_per_row: int) -> Room:
    room = Room(name=name, capacity=rows * seats_per_row)
    room.seats = [
        Seat(row_label=string.ascii_uppercase[r], number=n)
        for r in range(rows)
        for n in range(1, seats_per_row + 1)
    ]
    db.add(room)
    db.flush()
    return room

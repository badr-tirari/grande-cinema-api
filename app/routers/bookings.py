"""US04 - Réserver ; US05 - Billet dématérialisé ; US06 - Mes réservations / annulation."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.models import Booking, User
from app.schemas import BookedSeatOut, BookingCreate, BookingOut
from app.services.booking import BookingError, create_booking, load_booking

router = APIRouter(prefix="/api/bookings", tags=["Réservations"])


def to_out(booking: Booking, with_email: bool = False) -> BookingOut:
    return BookingOut(
        id=booking.id,
        code=booking.code,
        status=booking.status,
        total_cents=booking.total_cents,
        created_at=booking.created_at,
        showtime_id=booking.showtime_id,
        movie_title=booking.showtime.movie.title,
        room=booking.showtime.room.name,
        starts_at=booking.showtime.starts_at,
        seats=[
            BookedSeatOut(seat_id=bs.seat.id, row_label=bs.seat.row_label, number=bs.seat.number)
            for bs in booking.seats
        ],
        customer_email=booking.user.email if with_email else None,
    )


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def book(payload: BookingCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Réserve une ou plusieurs places. 409 si une place est déjà prise."""
    try:
        booking = create_booking(db, user, payload.showtime_id, payload.seat_ids)
    except BookingError as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    return to_out(load_booking(db, booking.id))

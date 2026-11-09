"""Modèle de données : utilisateurs, salles, places, films, séances, réservations."""

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Date-heure stockée en UTC et toujours relue avec son fuseau.

    PostgreSQL (timestamptz) conserve le fuseau, mais SQLite l'ignore : sans
    normalisation, une séance à 20h45 (Paris) était relue comme 20h45 UTC.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


class Role(enum.StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class BookingStatus(enum.StrEnum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), default=Role.USER)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    capacity: Mapped[int] = mapped_column(Integer)

    seats: Mapped[list["Seat"]] = relationship(
        back_populates="room", cascade="all, delete-orphan", order_by="Seat.id"
    )

    __table_args__ = (CheckConstraint("capacity > 0", name="ck_room_capacity_positive"),)


class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    row_label: Mapped[str] = mapped_column(String(2))
    number: Mapped[int] = mapped_column(Integer)

    room: Mapped[Room] = relationship(back_populates="seats")

    __table_args__ = (UniqueConstraint("room_id", "row_label", "number", name="uq_seat_position"),)


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    genre: Mapped[str] = mapped_column(String(50), default="")
    duration_min: Mapped[int] = mapped_column(Integer)
    poster_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    showtimes: Mapped[list["Showtime"]] = relationship(back_populates="movie", cascade="all, delete-orphan")

    __table_args__ = (CheckConstraint("duration_min > 0", name="ck_movie_duration_positive"),)


class Showtime(Base):
    __tablename__ = "showtimes"

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime())
    price_cents: Mapped[int] = mapped_column(Integer)

    movie: Mapped[Movie] = relationship(back_populates="showtimes")
    room: Mapped[Room] = relationship()
    bookings: Mapped[list["Booking"]] = relationship(back_populates="showtime")

    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="ck_showtime_price_positive"),
        CheckConstraint("ends_at > starts_at", name="ck_showtime_period"),
    )


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    showtime_id: Mapped[int] = mapped_column(ForeignKey("showtimes.id"), index=True)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"), default=BookingStatus.CONFIRMED
    )
    total_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    user: Mapped[User] = relationship(back_populates="bookings")
    showtime: Mapped[Showtime] = relationship(back_populates="bookings")
    seats: Mapped[list["BookedSeat"]] = relationship(back_populates="booking", cascade="all, delete-orphan")


class BookedSeat(Base):
    """Place occupée pour une séance donnée.

    La contrainte d'unicité (showtime_id, seat_id) garantit, au niveau de la base,
    qu'une même place ne peut pas être vendue deux fois pour une séance,
    même si deux requêtes arrivent en même temps.
    """

    __tablename__ = "booked_seats"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    showtime_id: Mapped[int] = mapped_column(ForeignKey("showtimes.id"), index=True)
    seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id"))

    booking: Mapped[Booking] = relationship(back_populates="seats")
    seat: Mapped[Seat] = relationship()

    __table_args__ = (UniqueConstraint("showtime_id", "seat_id", name="uq_seat_per_showtime"),)

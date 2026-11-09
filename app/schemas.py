"""Schémas Pydantic : validation des entrées et format des réponses de l'API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import BookingStatus, Role


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Authentification -------------------------------------------------------
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class UserOut(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    role: Role


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - type de jeton OAuth2, pas un secret
    user: UserOut


# --- Films et séances --------------------------------------------------------
class MovieBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    genre: str = Field(default="", max_length=50)
    duration_min: int = Field(gt=0, le=600)
    poster_url: str | None = None


class MovieCreate(MovieBase):
    pass


class MovieUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    genre: str | None = Field(default=None, max_length=50)
    duration_min: int | None = Field(default=None, gt=0, le=600)
    poster_url: str | None = None


class MovieOut(ORMModel, MovieBase):
    id: int


class RoomOut(ORMModel):
    id: int
    name: str
    capacity: int


class ShowtimeCreate(BaseModel):
    movie_id: int
    room_id: int
    starts_at: datetime
    price_cents: int = Field(ge=0, le=100_00)


class ShowtimeUpdate(BaseModel):
    starts_at: datetime | None = None
    room_id: int | None = None
    price_cents: int | None = Field(default=None, ge=0, le=100_00)


class ShowtimeOut(ORMModel):
    id: int
    movie_id: int
    room: RoomOut
    starts_at: datetime
    ends_at: datetime
    price_cents: int
    available_seats: int | None = None


class MovieWithShowtimes(MovieOut):
    showtimes: list[ShowtimeOut] = []


# --- Places -----------------------------------------------------------------
class SeatStatus(BaseModel):
    seat_id: int
    row_label: str
    number: int
    available: bool


class SeatMap(BaseModel):
    showtime_id: int
    room: str
    capacity: int
    available_count: int
    seats: list[SeatStatus]


# --- Réservations -----------------------------------------------------------
class BookingCreate(BaseModel):
    showtime_id: int
    seat_ids: list[int] = Field(min_length=1)

    @field_validator("seat_ids")
    @classmethod
    def no_duplicates(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("Une même place ne peut pas être demandée deux fois")
        return value


class BookedSeatOut(BaseModel):
    seat_id: int
    row_label: str
    number: int


class BookingOut(BaseModel):
    id: int
    code: str
    status: BookingStatus
    total_cents: int
    created_at: datetime
    showtime_id: int
    movie_title: str
    room: str
    starts_at: datetime
    seats: list[BookedSeatOut]
    customer_email: EmailStr | None = None


# --- Statistiques -----------------------------------------------------------
class OccupancyItem(BaseModel):
    showtime_id: int
    movie_title: str
    room: str
    starts_at: datetime
    booked: int
    capacity: int
    occupancy_rate: float
    peak: bool


class SlotOccupancy(BaseModel):
    slot: str
    showtimes: int
    booked: int
    capacity: int
    occupancy_rate: float


class OccupancyReport(BaseModel):
    global_rate: float
    peak_threshold: float
    by_showtime: list[OccupancyItem]
    by_slot: list[SlotOccupancy]

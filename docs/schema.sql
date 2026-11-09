-- Schéma PostgreSQL de La Grande Cinéma (généré depuis app/models.py)
-- Usage : psql "$DATABASE_URL" -f docs/schema.sql

CREATE TYPE user_role AS ENUM ('USER', 'ADMIN');
CREATE TYPE booking_status AS ENUM ('CONFIRMED', 'CANCELLED');

CREATE TABLE movies (
	id SERIAL NOT NULL,
	title VARCHAR(200) NOT NULL,
	description TEXT NOT NULL,
	genre VARCHAR(50) NOT NULL,
	duration_min INTEGER NOT NULL,
	poster_url VARCHAR(500),
	PRIMARY KEY (id),
	CONSTRAINT ck_movie_duration_positive CHECK (duration_min > 0)
);

CREATE INDEX ix_movies_title ON movies (title);

CREATE TABLE rooms (
	id SERIAL NOT NULL,
	name VARCHAR(50) NOT NULL,
	capacity INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_room_capacity_positive CHECK (capacity > 0),
	UNIQUE (name)
);


CREATE TABLE users (
	id SERIAL NOT NULL,
	email VARCHAR(255) NOT NULL,
	full_name VARCHAR(120) NOT NULL,
	hashed_password VARCHAR(255) NOT NULL,
	role user_role NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE seats (
	id SERIAL NOT NULL,
	room_id INTEGER NOT NULL,
	row_label VARCHAR(2) NOT NULL,
	number INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_seat_position UNIQUE (room_id, row_label, number),
	FOREIGN KEY(room_id) REFERENCES rooms (id) ON DELETE CASCADE
);

CREATE INDEX ix_seats_room_id ON seats (room_id);

CREATE TABLE showtimes (
	id SERIAL NOT NULL,
	movie_id INTEGER NOT NULL,
	room_id INTEGER NOT NULL,
	starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
	ends_at TIMESTAMP WITH TIME ZONE NOT NULL,
	price_cents INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_showtime_price_positive CHECK (price_cents >= 0),
	CONSTRAINT ck_showtime_period CHECK (ends_at > starts_at),
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE,
	FOREIGN KEY(room_id) REFERENCES rooms (id)
);

CREATE INDEX ix_showtimes_room_id ON showtimes (room_id);
CREATE INDEX ix_showtimes_starts_at ON showtimes (starts_at);
CREATE INDEX ix_showtimes_movie_id ON showtimes (movie_id);

CREATE TABLE bookings (
	id SERIAL NOT NULL,
	code VARCHAR(12) NOT NULL,
	user_id INTEGER NOT NULL,
	showtime_id INTEGER NOT NULL,
	status booking_status NOT NULL,
	total_cents INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(showtime_id) REFERENCES showtimes (id)
);

CREATE INDEX ix_bookings_user_id ON bookings (user_id);
CREATE UNIQUE INDEX ix_bookings_code ON bookings (code);
CREATE INDEX ix_bookings_showtime_id ON bookings (showtime_id);

CREATE TABLE booked_seats (
	id SERIAL NOT NULL,
	booking_id INTEGER NOT NULL,
	showtime_id INTEGER NOT NULL,
	seat_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_seat_per_showtime UNIQUE (showtime_id, seat_id),
	FOREIGN KEY(booking_id) REFERENCES bookings (id) ON DELETE CASCADE,
	FOREIGN KEY(showtime_id) REFERENCES showtimes (id),
	FOREIGN KEY(seat_id) REFERENCES seats (id)
);

CREATE INDEX ix_booked_seats_showtime_id ON booked_seats (showtime_id);


"""US04 - Réserver ; US05 - Billet ; US06 - Mes réservations / annulation."""


def book(client, headers, showtime_id, seat_ids):
    return client.post(
        "/api/bookings", json={"showtime_id": showtime_id, "seat_ids": seat_ids}, headers=headers
    )


def test_booking_requires_authentication(client, data):
    r = client.post("/api/bookings", json={"showtime_id": data["future"].id, "seat_ids": [data["seats"][0]]})
    assert r.status_code == 401


def test_book_seats_success(client, data, user_headers):
    r = book(client, user_headers, data["future"].id, data["seats"][:3])
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "CONFIRMED"
    assert body["total_cents"] == 3000
    assert body["code"].startswith("GC-")
    assert len(body["seats"]) == 3


def test_cannot_book_taken_seat(client, data, user_headers, other_headers):
    assert book(client, user_headers, data["future"].id, [data["seats"][0]]).status_code == 201
    r = book(client, other_headers, data["future"].id, [data["seats"][0], data["seats"][1]])
    assert r.status_code == 409


def test_cannot_book_past_showtime(client, data, user_headers):
    assert book(client, user_headers, data["past"].id, [data["seats"][0]]).status_code == 400


def test_cannot_book_unknown_showtime(client, data, user_headers):
    assert book(client, user_headers, 999, [data["seats"][0]]).status_code == 404


def test_cannot_book_seat_of_another_room(client, data, user_headers):
    assert book(client, user_headers, data["future"].id, [99999]).status_code == 400


def test_duplicate_seat_in_request_rejected(client, data, user_headers):
    s = data["seats"][0]
    assert book(client, user_headers, data["future"].id, [s, s]).status_code == 422


def test_max_seats_per_booking(client, data, user_headers, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.get_settings(), "max_seats_per_booking", 2)
    assert book(client, user_headers, data["future"].id, data["seats"][:3]).status_code == 400

"""US04 - Réserver ; US05 - Billet ; US06 - Mes réservations / annulation."""

from datetime import UTC


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


def test_my_bookings_and_ticket(client, data, user_headers, other_headers):
    created = book(client, user_headers, data["future"].id, [data["seats"][0]]).json()
    mine = client.get("/api/bookings/me", headers=user_headers).json()
    assert [b["code"] for b in mine] == [created["code"]]
    assert client.get("/api/bookings/me", headers=other_headers).json() == []

    ticket = client.get(f"/api/bookings/{created['id']}", headers=user_headers)
    assert ticket.status_code == 200
    assert ticket.json()["movie_title"] == "Blue Note Nights"
    # Un autre spectateur ne peut pas voir ce billet.
    assert client.get(f"/api/bookings/{created['id']}", headers=other_headers).status_code == 404


def test_cancel_frees_seats(client, data, user_headers, other_headers):
    created = book(client, user_headers, data["future"].id, [data["seats"][0]]).json()
    r = client.post(f"/api/bookings/{created['id']}/cancel", headers=user_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"
    assert r.json()["seats"] == []
    # La place est de nouveau réservable.
    assert book(client, other_headers, data["future"].id, [data["seats"][0]]).status_code == 201
    # Une 2e annulation est refusée.
    assert client.post(f"/api/bookings/{created['id']}/cancel", headers=user_headers).status_code == 400


def test_cannot_cancel_someone_else_booking(client, data, user_headers, other_headers):
    created = book(client, user_headers, data["future"].id, [data["seats"][0]]).json()
    assert client.post(f"/api/bookings/{created['id']}/cancel", headers=other_headers).status_code == 404


def test_cannot_cancel_started_showtime(client, db_session, data, user_headers):
    from datetime import datetime, timedelta

    created = book(client, user_headers, data["future"].id, [data["seats"][0]]).json()
    data["future"].starts_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.commit()
    assert client.post(f"/api/bookings/{created['id']}/cancel", headers=user_headers).status_code == 400

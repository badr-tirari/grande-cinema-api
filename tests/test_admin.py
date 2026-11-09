"""US07 - Programmation ; US08 - Suivi ; US09 - Taux de remplissage."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


def iso(dt):
    return dt.isoformat()


def test_admin_routes_forbidden_for_user(client, data, user_headers):
    assert client.get("/api/admin/rooms", headers=user_headers).status_code == 403
    assert client.get("/api/admin/rooms").status_code == 401


def test_movie_crud(client, data, admin_headers):
    r = client.post(
        "/api/admin/movies",
        headers=admin_headers,
        json={"title": "Orbite", "genre": "SF", "duration_min": 120},
    )
    assert r.status_code == 201
    movie_id = r.json()["id"]
    r = client.patch(f"/api/admin/movies/{movie_id}", headers=admin_headers, json={"duration_min": 125})
    assert r.json()["duration_min"] == 125
    assert client.delete(f"/api/admin/movies/{movie_id}", headers=admin_headers).status_code == 204
    assert client.patch("/api/admin/movies/999", headers=admin_headers, json={}).status_code == 404
    assert client.delete("/api/admin/movies/999", headers=admin_headers).status_code == 404


def test_cannot_delete_movie_with_bookings(client, data, admin_headers, user_headers):
    client.post(
        "/api/bookings",
        headers=user_headers,
        json={"showtime_id": data["future"].id, "seat_ids": [data["seats"][0]]},
    )
    assert client.delete(f"/api/admin/movies/{data['movie'].id}", headers=admin_headers).status_code == 409


def test_showtime_create_and_overlap(client, data, admin_headers):
    rooms = client.get("/api/admin/rooms", headers=admin_headers).json()
    assert rooms[0]["capacity"] == 6
    start = datetime.now(UTC) + timedelta(days=3)
    payload = {
        "movie_id": data["movie"].id,
        "room_id": data["room"].id,
        "starts_at": iso(start),
        "price_cents": 990,
    }
    r = client.post("/api/admin/showtimes", headers=admin_headers, json=payload)
    assert r.status_code == 201
    assert r.json()["available_seats"] == 6
    # Même salle, 30 min plus tard : chevauchement refusé.
    payload["starts_at"] = iso(start + timedelta(minutes=30))
    assert client.post("/api/admin/showtimes", headers=admin_headers, json=payload).status_code == 409
    payload["movie_id"] = 999
    assert client.post("/api/admin/showtimes", headers=admin_headers, json=payload).status_code == 404


def test_showtime_update_and_delete(client, data, admin_headers, user_headers):
    sid = data["future"].id
    r = client.patch(f"/api/admin/showtimes/{sid}", headers=admin_headers, json={"price_cents": 1200})
    assert r.status_code == 200 and r.json()["price_cents"] == 1200
    new_start = data["future"].starts_at + timedelta(hours=5)
    r = client.patch(f"/api/admin/showtimes/{sid}", headers=admin_headers, json={"starts_at": iso(new_start)})
    assert r.status_code == 200
    assert (
        client.patch(f"/api/admin/showtimes/{sid}", headers=admin_headers, json={"room_id": 999}).status_code
        == 404
    )
    assert client.patch("/api/admin/showtimes/999", headers=admin_headers, json={}).status_code == 404

    client.post(
        "/api/bookings", headers=user_headers, json={"showtime_id": sid, "seat_ids": [data["seats"][0]]}
    )
    # Une séance réservée ne change plus d'horaire et ne se supprime pas.
    assert (
        client.patch(
            f"/api/admin/showtimes/{sid}",
            headers=admin_headers,
            json={"starts_at": iso(new_start + timedelta(hours=1))},
        ).status_code
        == 409
    )
    assert client.delete(f"/api/admin/showtimes/{sid}", headers=admin_headers).status_code == 409
    assert client.delete(f"/api/admin/showtimes/{data['past'].id}", headers=admin_headers).status_code == 204
    assert client.delete("/api/admin/showtimes/999", headers=admin_headers).status_code == 404


def test_update_showtime_into_overlap_is_refused(client, data, admin_headers):
    other_start = data["future"].starts_at + timedelta(days=1)
    r = client.post(
        "/api/admin/showtimes",
        headers=admin_headers,
        json={
            "movie_id": data["movie"].id,
            "room_id": data["room"].id,
            "starts_at": iso(other_start),
            "price_cents": 990,
        },
    )
    new_id = r.json()["id"]
    r = client.patch(
        f"/api/admin/showtimes/{new_id}",
        headers=admin_headers,
        json={"starts_at": iso(data["future"].starts_at)},
    )
    assert r.status_code == 409

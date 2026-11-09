"""US07 - Programmation ; US08 - Suivi ; US09 - Taux de remplissage."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from tests.conftest import paris_day

PARIS = ZoneInfo("Europe/Paris")


def iso(dt):
    return dt.isoformat()


def test_admin_routes_forbidden_for_user(client, data, user_headers):
    assert client.get("/api/admin/bookings", headers=user_headers).status_code == 403
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


def test_admin_bookings_list_and_filters(client, data, admin_headers, user_headers):
    client.post(
        "/api/bookings",
        headers=user_headers,
        json={"showtime_id": data["future"].id, "seat_ids": [data["seats"][0]]},
    )
    all_bookings = client.get("/api/admin/bookings", headers=admin_headers).json()
    assert len(all_bookings) == 1 and all_bookings[0]["customer_email"] == "user@test.fr"
    day = paris_day(data["future"].starts_at)
    params = {"showtime_id": data["future"].id, "day": day, "status": "CONFIRMED"}
    assert len(client.get("/api/admin/bookings", headers=admin_headers, params=params).json()) == 1
    params["status"] = "CANCELLED"
    assert client.get("/api/admin/bookings", headers=admin_headers, params=params).json() == []


def test_occupancy_report(client, data, admin_headers, user_headers):
    client.post(
        "/api/bookings",
        headers=user_headers,
        json={"showtime_id": data["future"].id, "seat_ids": data["seats"][:5]},
    )
    report = client.get("/api/admin/stats/occupancy", headers=admin_headers).json()
    item = next(i for i in report["by_showtime"] if i["showtime_id"] == data["future"].id)
    assert item["booked"] == 5 and item["capacity"] == 6
    assert item["occupancy_rate"] == round(5 / 6, 4)
    assert item["peak"] is True
    assert report["global_rate"] == round(5 / 12, 4)
    assert sum(s["showtimes"] for s in report["by_slot"]) == 2

    day = paris_day(data["future"].starts_at)
    filtered = client.get(
        "/api/admin/stats/occupancy",
        headers=admin_headers,
        params={"date_from": day, "date_to": day},
    ).json()
    assert [i["showtime_id"] for i in filtered["by_showtime"]] == [data["future"].id]


def test_slot_and_rate_helpers():
    from app.routers.admin import rate, slot_of

    assert slot_of(datetime(2026, 7, 1, 10, tzinfo=PARIS)) == "Matin (< 14h)"
    assert slot_of(datetime(2026, 7, 1, 15, tzinfo=PARIS)) == "Après-midi (14h-18h)"
    assert slot_of(datetime(2026, 7, 1, 19, tzinfo=PARIS)) == "Soirée (18h-21h)"
    assert slot_of(datetime(2026, 7, 1, 22, tzinfo=PARIS)) == "Nuit (>= 21h)"
    assert rate(0, 0) == 0.0

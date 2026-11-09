"""US02 - Films et horaires ; US03 - Places disponibles."""

from tests.conftest import paris_day


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_list_movies_and_search(client, data):
    assert [m["title"] for m in client.get("/api/movies").json()] == ["Blue Note Nights"]
    assert client.get("/api/movies", params={"search": "blue"}).json()[0]["genre"] == "Documentaire"
    assert client.get("/api/movies", params={"search": "inconnu"}).json() == []


def test_movie_detail_lists_only_future_showtimes(client, data):
    r = client.get(f"/api/movies/{data['movie'].id}")
    assert r.status_code == 200
    showtimes = r.json()["showtimes"]
    assert [s["id"] for s in showtimes] == [data["future"].id]
    assert showtimes[0]["available_seats"] == 6


def test_movie_not_found(client):
    assert client.get("/api/movies/999").status_code == 404


def test_list_showtimes_filters(client, data):
    ids = [s["id"] for s in client.get("/api/showtimes").json()]
    assert ids == [data["future"].id]
    day = paris_day(data["past"].starts_at)
    by_day = client.get("/api/showtimes", params={"day": day}).json()
    assert [s["id"] for s in by_day] == [data["past"].id]
    assert client.get("/api/showtimes", params={"movie_id": 999}).json() == []

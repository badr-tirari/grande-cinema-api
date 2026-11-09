"""US01 - Inscription et connexion."""

from app.core.security import hash_password, verify_password


def test_hash_and_verify_password():
    hashed = hash_password("secret-123")
    assert hashed != "secret-123"
    assert verify_password("secret-123", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("x", "not-a-bcrypt-hash")


def test_register_then_login(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "Nouveau@Test.fr", "full_name": "Nouveau", "password": "Motdepasse-1"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "nouveau@test.fr"
    assert r.json()["role"] == "USER"
    assert "hashed_password" not in r.json()

    r = client.post("/api/auth/login", data={"username": "nouveau@test.fr", "password": "Motdepasse-1"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["full_name"] == "Nouveau"


def test_register_duplicate_email_conflict(client, data):
    r = client.post(
        "/api/auth/register",
        json={"email": "user@test.fr", "full_name": "Doublon", "password": "Motdepasse-1"},
    )
    assert r.status_code == 409


def test_register_rejects_weak_password(client):
    r = client.post("/api/auth/register", json={"email": "a@test.fr", "full_name": "AB", "password": "court"})
    assert r.status_code == 422


def test_login_wrong_password(client, data):
    r = client.post("/api/auth/login", data={"username": "user@test.fr", "password": "mauvais"})
    assert r.status_code == 401


def test_me_requires_valid_token(client):
    assert client.get("/api/auth/me").status_code == 401
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer jeton-invalide"})
    assert r.status_code == 401

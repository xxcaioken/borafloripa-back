"""
Auth tests — cover the flows that guard the whole application.

Useful because: if register/login break, nothing works. These tests catch
regressions in password hashing (sha256_crypt), JWT generation, and the
dependency that all protected routes share (get_current_user).
"""
import uuid


def unique_email():
    return f"user_{uuid.uuid4().hex[:8]}@test.com"


class TestRegister:
    def test_returns_token_on_success(self, client):
        r = client.post("/api/auth/register", json={
            "name": "Maria Silva", "email": unique_email(), "password": "senha123",
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["name"] == "Maria Silva"

    def test_duplicate_email_is_rejected(self, client):
        email = unique_email()
        client.post("/api/auth/register", json={"name": "A", "email": email, "password": "p"})
        r = client.post("/api/auth/register", json={"name": "B", "email": email, "password": "p"})
        assert r.status_code == 400


class TestLogin:
    def test_valid_credentials_return_token(self, client):
        email = unique_email()
        client.post("/api/auth/register", json={"name": "João", "email": email, "password": "abc123"})
        r = client.post("/api/auth/login", json={"email": email, "password": "abc123"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_wrong_password_returns_401(self, client):
        email = unique_email()
        client.post("/api/auth/register", json={"name": "Ana", "email": email, "password": "correct"})
        r = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
        assert r.status_code == 401

    def test_unknown_email_returns_401(self, client):
        r = client.post("/api/auth/login", json={"email": "ghost@test.com", "password": "pass"})
        assert r.status_code == 401


class TestProtectedRoutes:
    def test_partner_events_requires_auth(self, client):
        r = client.get("/api/partners/events")
        assert r.status_code == 401

    def test_partner_stats_requires_auth(self, client):
        r = client.get("/api/partners/stats")
        assert r.status_code == 401

    def test_authenticated_user_can_access_partner_stats(self, client, auth_headers):
        r = client.get("/api/partners/stats", headers=auth_headers)
        assert r.status_code == 200

"""
Partner dashboard tests.

Cover the ownership guards — the security rules that prevent one partner
from editing another's venue or events. These are the most critical
authorization checks in the application.
"""
import uuid


def unique_email():
    return f"partner_{uuid.uuid4().hex[:8]}@test.com"


class TestPartnerStats:
    def test_new_user_has_no_venues_or_events(self, client, auth_headers):
        r = client.get("/api/partners/stats", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total_events"] == 0
        assert data["featured_events"] == 0
        assert data["venues"] == []

    def test_new_user_has_empty_event_list(self, client, auth_headers):
        r = client.get("/api/partners/events", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == []


class TestEventOwnership:
    def test_create_event_for_unowned_venue_returns_403(self, client, auth_headers):
        """User cannot create events for venues they don't own."""
        r = client.post("/api/partners/events", headers=auth_headers, json={
            "venue_id": 99999,
            "title": "Evento Invasor",
            "date": "2026-08-01T20:00:00",
            "category": "bar",
        })
        # 403 if venue exists but not owned, 403 also covers non-existent
        assert r.status_code == 403

    def test_create_event_without_auth_returns_401(self, client):
        r = client.post("/api/partners/events", json={
            "venue_id": 1, "title": "Teste", "date": "2026-08-01T20:00:00", "category": "bar",
        })
        assert r.status_code == 401

    def test_update_event_without_auth_returns_401(self, client):
        r = client.put("/api/partners/events/1", json={
            "venue_id": 1, "title": "Teste", "date": "2026-08-01T20:00:00", "category": "bar",
        })
        assert r.status_code == 401

    def test_delete_event_without_auth_returns_401(self, client):
        r = client.delete("/api/partners/events/1")
        assert r.status_code == 401

    def test_delete_nonexistent_event_returns_404(self, client, auth_headers):
        r = client.delete("/api/partners/events/999999", headers=auth_headers)
        assert r.status_code == 404


class TestVenueOwnership:
    def test_update_unowned_venue_returns_403(self, client, auth_headers):
        """User cannot update a venue they don't own."""
        r = client.put("/api/partners/venues/99999", headers=auth_headers, json={
            "name": "Hacked Venue", "city": "Florianópolis",
            "lat": -27.0, "lng": -48.0,
        })
        assert r.status_code == 403

    def test_update_venue_without_auth_returns_401(self, client):
        r = client.put("/api/partners/venues/1", json={
            "name": "Hacked", "city": "Florianópolis", "lat": -27.0, "lng": -48.0,
        })
        assert r.status_code == 401


class TestAnalytics:
    def test_analytics_returns_empty_for_new_user(self, client, auth_headers):
        r = client.get("/api/partners/analytics", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_analytics_invalid_days_returns_400(self, client, auth_headers):
        r = client.get("/api/partners/analytics", headers=auth_headers, params={"days": 999})
        assert r.status_code == 400

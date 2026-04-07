"""
Events endpoint tests.

Cover the public feed — the most-used endpoint in the whole app.
Useful because: the feed is the entry point for every user. Regressions
here mean the app shows nothing to anyone.
"""


class TestFeed:
    def test_returns_list(self, client):
        r = client.get("/api/events/feed", params={"city": "Florianópolis"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_today_filter_returns_list(self, client):
        r = client.get("/api/events/feed", params={"city": "Florianópolis", "today": "true"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_free_filter_returns_list(self, client):
        r = client.get("/api/events/feed", params={"city": "Florianópolis", "free": "true"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestVenuesList:
    def test_returns_list(self, client):
        r = client.get("/api/events/venues", params={"city": "Florianópolis"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_search_query_returns_list(self, client):
        r = client.get("/api/events/venues", params={"city": "Florianópolis", "q": "bar"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_category_filter_returns_list(self, client):
        r = client.get("/api/events/venues", params={"city": "Florianópolis", "category": "bar"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestVenueDetail:
    def test_nonexistent_venue_returns_404(self, client):
        r = client.get("/api/events/venues/999999")
        assert r.status_code == 404

    def test_tags_endpoint_returns_list(self, client):
        r = client.get("/api/events/tags-full")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

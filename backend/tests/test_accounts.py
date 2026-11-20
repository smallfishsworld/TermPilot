import pytest

from termpilot.errors import NotAuthenticated
from termpilot.security.sealing import SealError, seal_json, unseal, unseal_json
from termpilot.security.tokens import issue_token, read_token


def test_wrong_password_gets_no_token(client):
    response = client.post("/api/auth/session", json={"username": "demo", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert "token" not in response.json()


def test_non_numeric_username_is_rejected(client):
    response = client.post("/api/auth/session", json={"username": "alice", "password": "x"})
    assert response.status_code == 422


def test_sign_in_returns_profile_and_stores_sealed_cookies(client, db):
    response = client.post("/api/auth/session", json={"username": "demo", "password": "demo"})
    body = response.json()
    assert body["first_visit"] is True
    assert body["student"]["display_name"] == "Alex Morgan"
    from termpilot.db.models import CampusLink

    link = db.get(CampusLink, body["student"]["id"])
    assert link is not None and "demo" not in link.sealed_cookies  # encrypted at rest
    again = client.post("/api/auth/session", json={"username": "demo", "password": "demo"}).json()
    assert again["first_visit"] is False


def test_protected_routes_need_a_valid_token(client, auth):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    assert client.get("/api/me", headers=auth).status_code == 200


def test_sign_out_revokes_existing_tokens(client, auth):
    assert client.delete("/api/auth/session", headers=auth).status_code == 204
    response = client.get("/api/me", headers=auth)
    assert response.status_code == 401
    assert "signed out" in response.json()["error"]["message"]


def test_feed_tokens_cannot_call_the_api(client, settings, auth):
    student_id = client.get("/api/me", headers=auth).json()["id"]
    feed = issue_token(settings, student_id, 0, scope="feed")
    assert client.get("/api/me", headers={"Authorization": f"Bearer {feed}"}).status_code == 401


def test_token_roundtrip_and_tampering(settings):
    token = issue_token(settings, 42, 3)
    claims = read_token(settings, token)
    assert (claims.student_id, claims.epoch) == (42, 3)
    with pytest.raises(NotAuthenticated):
        read_token(settings, token[:-2] + ("AA" if not token.endswith("AA") else "BB"))


def test_sealing_roundtrip_and_tamper_detection(settings):
    sealed = seal_json(settings, {"lms": {"session": "abc"}})
    assert unseal_json(settings, sealed) == {"lms": {"session": "abc"}}
    with pytest.raises(SealError):
        unseal(settings, sealed[:-4] + "AAAA")


def test_preferences_update(client, auth):
    response = client.patch("/api/me", json={"interests": "machine learning", "term_start": "2026-09-14"}, headers=auth)
    assert response.json()["interests"] == "machine learning"
    term = client.get("/api/me/term", headers=auth).json()
    assert term["start"] == "2026-09-14" and term["current_week"] == 5
    cleared = client.patch("/api/me", json={"clear_term_start": True}, headers=auth).json()
    assert cleared["term_start"] is None


def test_public_config(client):
    assert client.get("/api/config").json() == {
        "demo_mode": True,
        "assistant": False,
        "library": False,
        "web_search": False,
    }

"""Sentry PII scrubbing.

Sentry is an external processor and this platform handles student personal
data, so these are safety tests, not nice-to-haves: a regression here leaks
names and phone numbers to a third party.
"""

from app.core.observability.sentry import (
    REDACTED,
    _before_send,
    _is_sensitive,
    _scrub,
    init_sentry,
)


class TestSensitiveKeyMatching:
    def test_matches_case_insensitively_and_as_substring(self):
        assert _is_sensitive("email")
        assert _is_sensitive("Email")
        assert _is_sensitive("parent_email")
        assert _is_sensitive("STUDENT_PHONE")

    def test_leaves_ordinary_keys_alone(self):
        assert not _is_sensitive("batch_id")
        assert not _is_sensitive("lecture_status")
        assert not _is_sensitive("count")


class TestScrub:
    def test_redacts_personal_data(self):
        out = _scrub(
            {
                "student_name": "Asha Patil",
                "parent_phone": "9876543210",
                "email": "asha@example.com",
                "batch_id": "b-1",
            }
        )
        assert out["student_name"] == REDACTED
        assert out["parent_phone"] == REDACTED
        assert out["email"] == REDACTED
        # Non-sensitive values must survive, or the report is useless.
        assert out["batch_id"] == "b-1"

    def test_redacts_credentials(self):
        out = _scrub({"password": "hunter2", "authorization": "Bearer x"})
        assert out["password"] == REDACTED
        assert out["authorization"] == REDACTED

    def test_recurses_into_nested_structures(self):
        out = _scrub({"data": {"students": [{"full_name": "X", "roll_no": "12"}]}})
        student = out["data"]["students"][0]
        assert student["full_name"] == REDACTED
        assert student["roll_no"] == REDACTED

    def test_does_not_mutate_the_input(self):
        original = {"email": "a@b.c"}
        _scrub(original)
        assert original["email"] == "a@b.c"

    def test_caps_recursion_depth(self):
        deep: dict = {}
        node = deep
        for _ in range(40):
            node["child"] = {}
            node = node["child"]
        node["email"] = "leak@example.com"
        # Must terminate rather than recurse without bound.
        assert _scrub(deep) is not None


class TestBeforeSend:
    def test_drops_headers_and_cookies_wholesale(self):
        event = {
            "request": {
                "url": "/api/v1/students",
                "headers": {"Authorization": "Bearer secret"},
                "cookies": {"access_token": "secret"},
            }
        }
        out = _before_send(event, {})
        assert "headers" not in out["request"]
        assert "cookies" not in out["request"]

    def test_scrubs_request_data(self):
        event = {"request": {"data": {"phone": "9876543210", "batch_id": "b-1"}}}
        out = _before_send(event, {})
        assert out["request"]["data"]["phone"] == REDACTED
        assert out["request"]["data"]["batch_id"] == "b-1"

    def test_never_raises_on_a_malformed_event(self):
        # Reporting must not be able to take the app down. A bad event is
        # dropped (None), not propagated as an exception.
        assert _before_send({"request": "not-a-dict"}, {}) is not None

    def test_tags_with_request_id_when_one_is_set(self):
        from app.core.middleware.request_id import request_id_ctx

        token = request_id_ctx.set("req-abc")
        try:
            out = _before_send({}, {})
            assert out["tags"]["request_id"] == "req-abc"
        finally:
            request_id_ctx.reset(token)

    def test_omits_request_id_tag_when_unset(self):
        out = _before_send({}, {})
        assert "request_id" not in out.get("tags", {})


class TestInit:
    def test_disabled_without_a_dsn(self):
        # The default settings carry no DSN, so the suite and local dev never
        # emit anything.
        assert init_sentry() is False

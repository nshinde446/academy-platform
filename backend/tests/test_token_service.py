import uuid

import pytest
from jose import JWTError

from app.modules.auth.services.token_service import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
)


class TestAccessToken:
    def test_create_and_verify(self):
        user_id = uuid.uuid4()
        roles = ["teacher"]
        branch_id = uuid.uuid4()

        token = create_access_token(user_id, roles, branch_id)
        payload = verify_access_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["roles"] == ["teacher"]
        assert payload["branch_id"] == str(branch_id)
        assert payload["type"] == "access"

    def test_no_branch_id(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id, ["admin"], None)
        payload = verify_access_token(token)
        assert payload["branch_id"] is None

    def test_reject_refresh_token_as_access(self):
        user_id = uuid.uuid4()
        refresh_token, _ = create_refresh_token(user_id)
        with pytest.raises(JWTError):
            verify_access_token(refresh_token)

    def test_invalid_token_raises(self):
        with pytest.raises(JWTError):
            verify_access_token("invalid.token.here")


class TestRefreshToken:
    def test_create_and_verify(self):
        user_id = uuid.uuid4()
        token, jti = create_refresh_token(user_id)

        assert jti is not None
        payload = verify_refresh_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["jti"] == jti
        assert payload["type"] == "refresh"

    def test_reject_access_token_as_refresh(self):
        user_id = uuid.uuid4()
        access_token = create_access_token(user_id, ["admin"])
        with pytest.raises(JWTError):
            verify_refresh_token(access_token)

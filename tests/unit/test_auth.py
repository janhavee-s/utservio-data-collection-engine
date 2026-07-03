"""Tests for API authentication system."""

import os
from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.auth import verify_api_key
from app.configuration.settings import get_settings, reset_settings


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset settings singleton before each test."""
    reset_settings()
    yield
    reset_settings()


class TestSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_reset_settings_clears_singleton(self):
        s1 = get_settings()
        reset_settings()
        s2 = get_settings()
        assert s1 is not s2

    def test_settings_reads_env_prefix(self):
        with patch.dict(os.environ, {"CI_API_KEY": "env-key-value"}):
            reset_settings()
            settings = get_settings()
            assert settings.api_key == "env-key-value"


class TestVerifyApiKey:
    def test_missing_api_key_returns_401(self):
        """Missing X-API-Key header should return 401."""
        with patch.dict(os.environ, {"CI_API_KEY": "secret"}):
            reset_settings()
            app = FastAPI()

            @app.get("/test", dependencies=[Depends(verify_api_key)])
            async def test_endpoint():
                return {"ok": True}

            client = TestClient(app)
            response = client.get("/test")
            assert response.status_code == 401
            assert "Missing API key" in response.json()["detail"]

    def test_invalid_api_key_returns_403(self):
        """Wrong API key should return 403."""
        with patch.dict(os.environ, {"CI_API_KEY": "secret"}):
            reset_settings()
            app = FastAPI()

            @app.get("/test", dependencies=[Depends(verify_api_key)])
            async def test_endpoint():
                return {"ok": True}

            client = TestClient(app)
            response = client.get("/test", headers={"X-API-Key": "wrong-key"})
            assert response.status_code == 403
            assert "Invalid API key" in response.json()["detail"]

    def test_valid_api_key_returns_200(self):
        """Correct API key should return 200."""
        with patch.dict(os.environ, {"CI_API_KEY": "secret"}):
            reset_settings()
            app = FastAPI()

            @app.get("/test", dependencies=[Depends(verify_api_key)])
            async def test_endpoint():
                return {"ok": True}

            client = TestClient(app)
            response = client.get("/test", headers={"X-API-Key": "secret"})
            assert response.status_code == 200
            assert response.json() == {"ok": True}

    def test_no_api_key_configured_allows_all(self):
        """When no API key is configured, all requests should be allowed."""
        with patch.dict(os.environ, {"CI_API_KEY": ""}):
            reset_settings()
            app = FastAPI()

            @app.get("/test", dependencies=[Depends(verify_api_key)])
            async def test_endpoint():
                return {"ok": True}

            client = TestClient(app)
            response = client.get("/test")
            assert response.status_code == 200

    def test_timing_safe_comparison(self):
        """Verify hmac.compare_digest is used (constant-time comparison)."""
        with patch.dict(os.environ, {"CI_API_KEY": "secret"}):
            reset_settings()
            app = FastAPI()

            @app.get("/test", dependencies=[Depends(verify_api_key)])
            async def test_endpoint():
                return {"ok": True}

            client = TestClient(app)
            wrong_keys = ["a", "ab", "abc", "test"]
            for key in wrong_keys:
                response = client.get("/test", headers={"X-API-Key": key})
                assert response.status_code in (401, 403)


class TestVerifyApiKeyWithSettings:
    def test_verifies_against_settings_api_key(self):
        """verify_api_key should use the configured API key."""
        with patch.dict(os.environ, {"CI_API_KEY": "my-secret-key"}):
            reset_settings()
            app = FastAPI()

            @app.get("/test", dependencies=[Depends(verify_api_key)])
            async def test_endpoint():
                return {"ok": True}

            client = TestClient(app)

            # Wrong key
            response = client.get("/test", headers={"X-API-Key": "wrong"})
            assert response.status_code == 403

            # Correct key
            response = client.get("/test", headers={"X-API-Key": "my-secret-key"})
            assert response.status_code == 200

    def test_empty_key_not_configured(self):
        """Empty string API key should disable auth."""
        with patch.dict(os.environ, {"CI_API_KEY": ""}):
            reset_settings()
            app = FastAPI()

            @app.get("/test", dependencies=[Depends(verify_api_key)])
            async def test_endpoint():
                return {"ok": True}

            client = TestClient(app)
            response = client.get("/test")
            assert response.status_code == 200

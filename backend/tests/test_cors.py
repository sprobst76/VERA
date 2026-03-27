import pytest


@pytest.mark.asyncio
async def test_cors_allows_x_api_key_header(client):
    """CORS preflight must allow X-API-Key header (SEC-04)."""
    r = await client.options(
        "/api/v1/shifts",
        headers={
            "Origin": "http://localhost:31368",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    allowed = r.headers.get("access-control-allow-headers", "")
    assert "x-api-key" in allowed.lower(), f"X-API-Key not in allowed headers: {allowed}"


@pytest.mark.asyncio
async def test_cors_allows_authorization_header(client):
    """CORS preflight must still allow Authorization header."""
    r = await client.options(
        "/api/v1/shifts",
        headers={
            "Origin": "http://localhost:31368",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    allowed = r.headers.get("access-control-allow-headers", "")
    assert "authorization" in allowed.lower(), f"Authorization not in allowed headers: {allowed}"

import logging

import httpx
import pytest

from comradbot.services.external_monitor import ExternalMonitorService


@pytest.mark.asyncio
async def test_external_monitor_pings_configured_url_without_following_redirects() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        service = ExternalMonitorService(
            "https://monitor.example/check-id",
            interval_seconds=60,
            timeout_seconds=5,
            client=client,
        )
        await service.start()
        await service.start()
        await service.close()

    assert [request.url for request in requests] == [httpx.URL("https://monitor.example/check-id")]


@pytest.mark.asyncio
async def test_external_monitor_failure_is_safe_and_does_not_log_secret_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_url = "https://monitor.example/secret-check-id"

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        service = ExternalMonitorService(
            secret_url,
            interval_seconds=60,
            timeout_seconds=5,
            client=client,
        )
        with caplog.at_level(logging.WARNING):
            await service.start()
        await service.close()

    assert "External monitor heartbeat failed" in caplog.text
    assert secret_url not in caplog.text


@pytest.mark.asyncio
async def test_external_monitor_is_inert_without_a_url() -> None:
    async with httpx.AsyncClient() as client:
        service = ExternalMonitorService(
            None,
            interval_seconds=60,
            timeout_seconds=5,
            client=client,
        )
        await service.start()
        assert service.enabled is False
        await service.close()

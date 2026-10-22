"""Bounded local single-user HTTP boundary; deliberately not public authentication."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

LIMIT = 2 * 1024 * 1024


class LocalBoundary:
    def __init__(self, app: ASGIApp, origins: tuple[str, ...]) -> None:
        self.app, self.origins = app, origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        origin = headers.get(b"origin")
        if (origin is not None and origin.decode("latin1") not in self.origins) or headers.get(
            b"sec-fetch-site"
        ) == b"cross-site":
            await JSONResponse({"detail": "Untrusted browser origin"}, 403)(scope, receive, send)
            return
        # Count actual received bytes, including chunked requests. No handler runs until bounded.
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > LIMIT:
                await JSONResponse({"detail": "Request exceeds 2 MiB"}, 413)(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": b"".join(chunks), "more_body": False}

        async def secured_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-content-type-options", b"nosniff"),
                    (b"cache-control", b"no-store"),
                    (b"referrer-policy", b"no-referrer"),
                ]
            await send(message)

        await self.app(scope, bounded_receive, secured_send)

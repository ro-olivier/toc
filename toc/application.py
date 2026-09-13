from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from toc.infrastructure.app_logging import configureApplicationLogging
from toc.runtime import manager
from toc.transport.http_routes import httpRouter
from toc.transport.websocket_routes import websocketRouter
from settings import BASE_DIR


configureApplicationLogging()
logger = logging.getLogger("toc.main")


@asynccontextmanager
async def applicationLifespan(app: FastAPI) -> AsyncIterator[None]:
	recoveryResult = await manager.recoverInterruptedGames()

	logger.info(
		"Interrupted-game recovery completed",
		extra={
			"suspendedCount": len(recoveryResult["suspended"]),
			"finishedCount": len(recoveryResult["finished"]),
			"failedCount": len(recoveryResult["failed"]),
		},
	)

	monitorTask = asyncio.create_task(manager.monitorSessions())

	try:
		yield
	finally:
		monitorTask.cancel()

		with suppress(asyncio.CancelledError):
			await monitorTask


app = FastAPI(lifespan=applicationLifespan)
app.include_router(httpRouter)
app.include_router(websocketRouter)
app.mount("/toc/play", StaticFiles(directory=BASE_DIR / "web", html=True), name="toc-frontend")

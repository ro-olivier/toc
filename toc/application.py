from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from settings import BASE_DIR
from toc.infrastructure.app_logging import configureApplicationLogging
from toc.runtime import manager
from toc.transport.http_routes import httpRouter
from toc.transport.websocket_routes import websocketRouter


configureApplicationLogging()
logger = logging.getLogger("toc.main")


@asynccontextmanager
async def applicationLifespan(app: FastAPI):
	recoveryResult = await manager.recover_interrupted_games()

	logger.info(
		"Interrupted-game recovery completed",
		extra={
			"suspendedCount": len(recoveryResult["suspended"]),
			"finishedCount": len(recoveryResult["finished"]),
			"failedCount": len(recoveryResult["failed"]),
		},
	)

	monitorTask = asyncio.create_task(manager.monitor_sessions())

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

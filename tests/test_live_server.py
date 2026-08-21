import json
import socket
import subprocess
import sys
import time

from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest

from websockets.sync.client import connect


def findFreePort():
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as temporarySocket:
		temporarySocket.bind(("127.0.0.1", 0))
		return temporarySocket.getsockname()[1]


@pytest.fixture
def liveServer():
	projectRoot = Path(__file__).resolve().parents[1]
	port = findFreePort()

	process = subprocess.Popen(
		[
			sys.executable,
			"-m",
			"uvicorn",
			"main:app",
			"--host",
			"127.0.0.1",
			"--port",
			str(port),
			"--log-level",
			"warning",
		],
		cwd=projectRoot,
		stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT,
		text=True,
	)

	httpUrl = f"http://127.0.0.1:{port}"
	websocketUrl = f"ws://127.0.0.1:{port}"
	startupDeadline = time.monotonic() + 10

	try:
		while time.monotonic() < startupDeadline:
			if process.poll() is not None:
				output = process.stdout.read()
				pytest.fail(f"Uvicorn stopped during startup.\n{output}")

			try:
				with urlopen(f"{httpUrl}/toc", timeout=0.25) as response:
					if response.status == 200:
						break
			except URLError:
				time.sleep(0.05)
		else:
			pytest.fail("Uvicorn did not become ready within 10 seconds")

		yield {
			"httpUrl": httpUrl,
			"websocketUrl": websocketUrl,
		}

	finally:
		if process.poll() is None:
			process.terminate()

			try:
				process.wait(timeout=5)
			except subprocess.TimeoutExpired:
				process.kill()
				process.wait(timeout=5)

def test_real_uvicorn_http_and_websocket_round_trip(liveServer):
	creationRequest = Request(
		f"{liveServer['httpUrl']}/toc/api/create-game",
		data=json.dumps({}).encode("utf-8"),
		headers={"Content-Type": "application/json"},
		method="POST",
	)

	with urlopen(creationRequest, timeout=2) as response:
		assert response.status == 200
		gameId = json.load(response)["game_id"]

	with connect(
		f"{liveServer['websocketUrl']}/toc/ws/{gameId}/Alice",
		open_timeout=2,
		close_timeout=2,
		proxy=None,
	) as websocket:
		ready = json.loads(websocket.recv(timeout=2))
		lobbyState = json.loads(websocket.recv(timeout=2))

		assert ready == {"type": "ready"}

		assert lobbyState["type"] == "lobby-state"
		assert lobbyState["gameId"] == gameId
		assert lobbyState["started"] is False
		assert len(lobbyState["players"]) == 1
		assert lobbyState["players"][0]["name"] == "Alice"

		pongReceived = websocket.ping()

		assert pongReceived.wait(timeout=2)

		websocket.send(json.dumps({
			"type": "configure-player",
			"team": "0",
			"color": "red",
		}))

		configuredState = json.loads(websocket.recv(timeout=2))
		alice = next(player for player in configuredState["players"] if player["name"] == "Alice")

		assert configuredState["type"] == "lobby-state"
		assert alice["connected"] is True
		assert alice["configured"] is True
		assert alice["team"] == "0"
		assert alice["color"] == "red"
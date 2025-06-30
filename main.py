from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import Dict
import asyncio
import string
import random

from game import Game
from player import Player
from params import *

app = FastAPI()

class PlayerInputRouter:
    def __init__(self):
        self.queues = {}

    def register(self, player_name: str):
        self.queues[player_name] = asyncio.Queue()

    def unregister(self, player_name: str):
        self.queues.pop(player_name, None)

    async def add_input(self, player_name: str, message: str):
        queue = self.queues.get(player_name)
        if queue:
            await queue.put(message)

    async def wait_for_input(self, player_name: str):
        return await self.queues[player_name].get()


class ConnectionManager:
    def __init__(self):
        self.games: Dict[str, GameSession] = {}

    def _generate_game_id(self, length=4):
        charset = string.ascii_uppercase + string.digits
        while True:
            game_id = ''.join(random.choices(charset, k=length))
            if game_id not in self.games:
                return game_id

    def create_game(self, msg_router) -> str:
        game_id = self._generate_game_id()
        self.games[game_id] = GameSession(game_id, msg_router)
        return game_id

    def get_game(self, game_id: str):
        return self.games.get(game_id)

class GameSession:
    def __init__(self, game_id: str, msg_router):
        self.id = game_id
        self.players: Dict = {}
        self.started = False
        self.lock = asyncio.Lock()
        self.remaining_colors = COLORS
        self.router = msg_router

    def team_is_full(self, team: str):
        return sum([self.players[p]['team'] == team for p in self.players.keys()]) == 2

    async def broadcast(self, message: str, excluded_player : str = None):
        for player_name in self.players.keys():
            if player_name != excluded_player:
                await self.router.add_input(player_name, message)

    async def game_loop(self):
        async with self.lock:
            if self.started:
                return
            self.started = True
            await self.broadcast("Four players have joined: game is starting!\n")
            game = Game(self)
            game.setPlayers([self.players[k]['object'] for k in self.players.keys()])
            await game.start()

    async def make_player_choose_color(self, player_name) -> str:
        if len(self.remaining_colors) == 1:
            await self.router.add_input(player_name,"The only remaining color is {self.remaining_colors[0]}, hope you like it!")
            return self.remaining_colors[0]
        else:
            await self.router.add_input(player_name,
                f"Choose the color you wish to play. Available colors: {', '.join(self.remaining_colors)}.")
            while True:
                msg = await self.router.wait_for_input(player_name)
                if msg.strip() in self.remaining_colors:
                    color = msg.strip()
                    self.remaining_colors = [c for c in self.remaining_colors if c != color]
                    break
                else:
                    await self.router.add_input(player_name, "Please choose a valid color.")
            return color

@app.websocket("/toc/ws/{game_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_name: str):
    await websocket.accept()
    router.register(player_name)

    if game_id not in manager.games:
        await router.add_input(player_name,"Invalid game ID.")
        await websocket.close()
        return

    game = manager.games[game_id]

    if player_name in game.players.keys():
        await router.add_input(player_name,"Player name already taken.")
        await websocket.close()
        return

    if not game.players:
        team = "0"
        await router.add_input(player_name,"You have been assigned to team 0.")
    else:
        if game.team_is_full("0"):
            team = "1"
            await router.add_input(player_name,"Team 0 is full, you have been assigned to team 1.")
        elif game.team_is_full("1"):
            team = "0"
            await router.add_input(player_name,"Team 1 is full, you have been assigned to team 0.")
        else:
            await router.add_input(player_name,"Choose your team (0 or 1):")
            while True:
                msg = await websocket.receive_text()
                if msg.strip() in ["0", "1"]:
                    team = msg.strip()
                    await router.add_input(player_name,f"Successfully joined team {team}")
                    break
                else:
                    await router.add_input(player_name,"Invalid team. Please enter '0' or '1'.")

    color = await game.make_player_choose_color(player_name)

    game.players[player_name] = {
        "websocket": websocket,
        "team": team,
        "color": color,
        "object": Player(player_name, team, color, game, router)
    }

    await router.add_input(player_name, f'You successfully joined the game and will play in team {team} with color {color}!\n')
    await game.broadcast(f"{player_name} has joined team {team} and will play {color}.", excluded_player=player_name)

    if len(game.players) == 4:
        await game.game_loop()

    try:
        while True:
            data = await websocket.receive_text()
            await router.add_input(player_name, data)
    except WebSocketDisconnect:
        del game.players[player_name]
        router.unregister(player_name)
        await game.broadcast(f"{player_name} disconnected.")

router = PlayerInputRouter()
manager = ConnectionManager()

@app.get("/toc")
async def root():
    return {"message": "Game backend is running."}


@app.post("/toc/api/create-game")
async def create_game():
    game_id = manager.create_game(router)
    return {"game_id": game_id}

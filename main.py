from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import Dict
import asyncio
import string
import random
import json

from game import Game
from player import Player
from params import *

app = FastAPI()

class PlayerInputRouter:
    def __init__(self):
        self.input_queues = {}
        self.output_queues = {}

    def register(self, player_name: str):
        print(f'[Router] Registered user {player_name}')
        self.input_queues[player_name] = asyncio.Queue()
        self.output_queues[player_name] = asyncio.Queue()

    def unregister(self, player_name: str):
        print(f'[Router] Unregistered user {player_name}')
        self.input_queues.pop(player_name, None)
        self.output_queues.pop(player_name, None)

    async def add_input(self, player_name: str, message: str):
        print(f"[Router] add_input called for {player_name}: {message}")
        queue = self.input_queues.get(player_name)
        if queue:
            await queue.put(message)
        else:
            print(f"[Router] No input queue found for {player_name}")

    async def wait_for_input(self, player_name: str):
        msg = await self.input_queues[player_name].get()
        print(f"[Router] wait_for_input received {msg} of type {type(msg)}")
        return msg

    async def send_output(self, player_name: str, message: str):
        print(f"[Router] send_output called for {player_name}: {message}")
        queue = self.output_queues.get(player_name)
        if queue:
            await queue.put(message)
        else:
            print(f"[Router] No output queue found for {player_name}")

    async def get_output(self, player_name: str):
        return await self.output_queues[player_name].get()


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
        self.ui_queues: List = []

    def team_is_full(self, team: str):
        return sum([self.players[p]['team'] == team for p in self.players.keys()]) == 2

    async def broadcast(self, message: Dict, excluded_player : str = None):
        for player_name in self.players.keys():
            if player_name != excluded_player:
                player = self.players[player_name]['object']
                await player.send_message_to_user(message)

    async def game_loop(self):
        async with self.lock:
            if self.started:
                return
            self.started = True
            await self.broadcast({"type": "log", "msg": "Four players have joined: game is starting!"})
            game = Game(self)
            game.setPlayers([self.players[k]['object'] for k in self.players.keys()])
            await game.start()

    async def make_player_choose_color(self, player_name) -> str:
        player = self.players[player_name]['object']
        if len(self.remaining_colors) == 1:
            await player.send_message_to_user({"type": "log", "msg": f"The only remaining color is {self.remaining_colors[0]}, hope you like it!"})
            return self.remaining_colors[0]
        else:
            await player.send_message_to_user({"type": "query", "msg": 
                f"Choose the color you wish to play. Available colors: {', '.join(self.remaining_colors)}."})
            while True:
                parsed_msg = await self.router.wait_for_input(player_name)
                if parsed_msg['type'] == 'text_input' and parsed_msg['msg'].strip() in self.remaining_colors:
                    color = parsed_msg['msg'].strip()
                    self.remaining_colors = [c for c in self.remaining_colors if c != color]
                    break
                else:
                    await player.send_message_to_user({"type": "error", "msg": "Please choose a valid color."})
            return color

@app.websocket("/toc/ws/{game_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_name: str):

    # Setting up all the WebSocket and asyncio logic 
    await websocket.accept()

    game = manager.games.get(game_id)
    if not game:
        await websocket.send_json({"type": "error", "msg": "Invalid game ID."})
        await websocket.close()
        return

    router.register(player_name)

    ## Player input loop
    async def input_loop():
        try:
            while True:
                data = await websocket.receive_text()
                #print(f"[input_loop] Raw message: {data}")  # Log raw message
                try:
                    # Parse the JSON string into a Python dictionary
                    parsed_data = json.loads(data)
                    print(f"[input_loop] Received data from {player_name}: {parsed_data}")  # Now it should print the actual content

                    if parsed_data['type'] == 'debug':
                        print('[input loop] Received DEBUG command from {player_name}!!')
                        if parsed_data['msg'] == 'simulate_card_exchange_players3and4':
                            print('DEBUG : simulating card exchange between player 3 and 4')
                            p3_name = list(game.players.keys())[2]
                            p4_name = list(game.players.keys())[3]
                            p3_card = game.players[p3_name]['object'].hand.cards[0]
                            p4_card = game.players[p4_name]['object'].hand.cards[0]
                            cmd3 = json.loads(f'{{"type":"card_selection","name":"{p3_name}","value":"{p3_card.value}","suit":"{p3_card.suit}"}}')
                            cmd4 = json.loads(f'{{"type":"card_selection","name":"{p4_name}","value":"{p4_card.value}","suit":"{p4_card.suit}"}}')
                            await router.add_input(p3_name, cmd3)
                            await router.add_input(p4_name, cmd4)
                    else:
                        await router.add_input(player_name, parsed_data)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON, passing it as raw text just in case: {e}")
                    await router.add_input(player_name, data)
        except WebSocketDisconnect:
            del game.players[player_name]
            router.unregister(player_name)
            await game.broadcast({"type": "log", "msg": f"{player_name} disconnected."})
        except Exception as e:
            print(f"[input_loop] Error: {e}")

    asyncio.create_task(input_loop())

    ## Player output loop
    async def output_loop():
        while True:
            message = await router.get_output(player_name)
            await websocket.send_json(message)

    asyncio.create_task(output_loop())

    ## IO output loop
    async def send_updates(websocket: WebSocket, queue: asyncio.Queue):
        while True:
            update = await queue.get()
            await websocket.send_json(update)

    ui_queue = asyncio.Queue()
    game.ui_queues.append(ui_queue)

    sender = asyncio.create_task(send_updates(websocket, ui_queue))

    # Finalizing game setup for each player connecting

    new_player = game.players.get(player_name)
    ## If username has already been chosen, we cannot proceed. 
    if new_player:
        await websocket.send_json({"type": "error", "msg": "Player name already taken."})
        await websocket.close()
        return
    else:
        ## First creating the new_player object and updating the new player's UI with current state of the board
        new_player = Player(player_name, '', '', '', game, router)
        await new_player.send_message_to_user({"type": "full_ui_state","players": [{"name": p, "team": game.players[p]["team"], "color": game.players[p]["color"]} for p in game.players.keys()]})
        
        ## Only then we create the new player object and add it to the collection (since it will be without color or team for now, if we send it before the UI broadcast the front-end will get confused)
        game.players[player_name] = {
            "name": player_name,
            "websocket": websocket,
            "team": '',
            "color": '',
            "object": new_player
        }

    ## Figuring out and/or asking the player for team and color selection
    if len(game.players) == 1:
        # If we're dealing with the first player in the game, we can assign him/her to team 0 without loss of generality.
        team = "0"
        await new_player.send_message_to_user({"type": "log", "msg": "You have been assigned to team 0."})
    else:
        if game.team_is_full("0"):
            team = "1"
            await new_player.send_message_to_user({"type": "log", "msg": "Team 0 is full, you have been assigned to team 1."})
        elif game.team_is_full("1"):
            team = "0"
            await new_player.send_message_to_user({"type": "log", "msg": "Team 1 is full, you have been assigned to team 0."})
        else:
            await new_player.send_message_to_user({"type": "query", "msg": "Choose your team (0 or 1):"})
            while True:
                msg = await websocket.receive_text()
                parsed_msg = json.loads(msg)
                if parsed_msg['type'] == 'text_input' and parsed_msg['msg'].strip() in ["0", "1"]:
                    team = parsed_msg['msg'].strip()
                    await new_player.send_message_to_user({"type": "log", "msg": f"Successfully joined team {team}"})
                    break
                else:
                    await new_player.send_message_to_user({"type": "error", "msg": "Invalid team. Please enter '0' or '1'."})

    color = await game.make_player_choose_color(player_name)

    ## Setting the information we got into the various objects which need to be aware of the selections
    new_player.setColor(color)
    new_player.setTeam(team)

    # Now that we have color and team, we can set it
    game.players[player_name]['color'] = color
    game.players[player_name]['object'].setColor(color)
    game.players[player_name]['team'] = team
    game.players[player_name]['object'].setTeam(team)


    ## Broadcasting the join-info to new player, the UIs and the other players
    await new_player.send_message_to_user({"type": "log", "msg": f"You successfully joined the game and will play in team {team} with color {color}!"})
    await game.broadcast({"type": "log", "msg": f"{player_name} has joined team {team} and will play {color}."}, excluded_player=player_name)
    await game.broadcast({"type": "assign-player", "name": player_name, "team": team, "color": color})

    ## When we have 4 players, the game can start!
    if len(game.players) == 4:
        await game.game_loop()


router = PlayerInputRouter()
manager = ConnectionManager()

@app.get("/toc")
async def root():
    return {"message": "Game backend is running."}


@app.post("/toc/api/create-game")
async def create_game():
    game_id = manager.create_game(router)
    return {"game_id": game_id}

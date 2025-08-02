from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import Dict
import asyncio
import string
import random
import json
from time import sleep

from game import Game
from player import Player
from params import *

app = FastAPI()

class DuplicateNameError(Exception):
    pass

class PlayerInputRouter:
    def __init__(self):
        self.input_queues = {}
        self.output_queues = {}
        self.recycleBin = {}

    def register(self, player_name: str):
        if player_name in self.input_queues:
            print(f'[Router] Attempted to re-registered a user with name {player_name}!')
            raise DuplicateNameError
        else:
            print(f'[Router] Registered user {player_name}')
            self.input_queues[player_name] = asyncio.Queue()
            self.output_queues[player_name] = asyncio.Queue()

    def registerAgain(self, player_name: str):
        print(f'[Router] Reregistering user {player_name}')
        self.input_queues[player_name] = self.recycleBin[player_name]['in']
        self.output_queues[player_name] = self.recycleBin[player_name]['out']

    def unregister(self, player_name: str):
        print(f'[Router] Unregistered user {player_name}')
        self.recycleBin[player_name] = {'in': self.input_queues.pop(player_name, None), 'out': self.output_queues.pop(player_name, None)}

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
        self.order: List = []
        self.game = None

    def fullUI(self) -> dict:
        if self.game:
            if self.game.activePlayer:
                active_player_name = self.game.activePlayer.name
            else:
                active_player_name = ""

            return {"type": "full_ui_state", "players": [{"name": p, "team": self.players[p]["team"], "color": self.players[p]["color"], "number_of_cards": self.players[p]["object"].hand.size} for p in self.players], "pieces": self.game.board.getAllPiecesOnTheBoard(), "active_player": active_player_name}
        else:
            return {"type": "full_ui_state", "players": [{"name": p, "team": self.players[p]["team"], "color": self.players[p]["color"], "number_of_cards": self.players[p]["object"].hand.size} for p in self.players], "pieces": [], "active_player": ""}


    def team_is_full(self, team: str) -> bool:
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
            await self.broadcast({"type": "log", "msg": "Four players have joined: game is starting!\n"})
            self.game = Game(self, [self.players[p_name]['color'] for p_name in self.order])
            # players are set in the order defined by the array passed by the UI
            self.game.setPlayers([self.players[p_name]['object'] for p_name in self.order])
            await self.game.start()

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

    gameSession = manager.games.get(game_id)    
    # Setting up all the WebSocket and asyncio logic 
    await websocket.accept()

    if not gameSession:
        print('Closing with 4001 code')
        await websocket.close(code=4001)
        return

    existing_player = gameSession.players.get(player_name)
    if not existing_player:
        try:
            router.register(player_name)
        except DuplicateNameError:
            ## If username has already been chosen, we cannot proceed.
            print('Closing with 4002 code')
            await websocket.close(code=4002)
            return
    else:
        if not existing_player['active']:
            try:
                router.registerAgain(player_name)
            except:
                print('Closing with 4003 code')
                await websocket.close(code=4003)
                return

    await websocket.send_json({"type": "ready"})

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
                        print(f'[input loop] Received DEBUG command from {player_name}!!')
                        if parsed_data['msg'] == 'simulate_card_exchange_players3and4':
                            print('DEBUG : simulating card exchange between player 3 and 4')
                            p3_name = list(gameSession.players.keys())[2]
                            p4_name = list(gameSession.players.keys())[3]
                            p3_card = gameSession.players[p3_name]['object'].hand.cards[0]
                            p4_card = gameSession.players[p4_name]['object'].hand.cards[0]
                            cmd3 = json.loads(f'{{"type":"card_selection","name":"{p3_name}","value":"{p3_card.value}","suit":"{p3_card.suit}"}}')
                            cmd4 = json.loads(f'{{"type":"card_selection","name":"{p4_name}","value":"{p4_card.value}","suit":"{p4_card.suit}"}}')
                            await router.add_input(p3_name, cmd3)
                            await router.add_input(p4_name, cmd4)
                        if parsed_data['msg'] == 'force-play':
                            print('DEBUG : Forcing the current player to play the first available move')
                            await gameSession.game.activePlayer.forceRandomMove()

                    elif parsed_data['type'] == 'everybody_is_here':
                            # We're dealing with the special message at the end of the game setup phase where the front-end of player 4 is giving the back-end the order in which the players have decided to play. This data is used to update the order in which items are in the game.players array.
                        if len(gameSession.order) == 0: # we only need to update the game.order once, and we don't want this check to be mutualized with the parsed_data type check otherwise multiple msg will reach the router and this will break the card exchange process which comes after
                            gameSession.order = parsed_data['order']
                            await try_notify_order_ready(gameSession, orderIsSet_condition)
                    else:
                        await router.add_input(player_name, parsed_data)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON, passing it as raw text just in case: {e}")
                    await router.add_input(player_name, data)
        except WebSocketDisconnect:
            gameSession.players[player_name]['active'] = False
            router.unregister(player_name)
            await gameSession.broadcast({"type": "log", "msg": f"{player_name} disconnected."}, excluded_player=player_name)
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
    gameSession.ui_queues.append(ui_queue)

    sender = asyncio.create_task(send_updates(websocket, ui_queue))

    # Finalizing game setup for each player connecting
    
    ## We're checking the player doesn't exist already, just in case
    if not existing_player:
        ## First creating the new_player object and updating the new player's UI with current state of the board
        new_player = Player(player_name, '', '', '', gameSession, router)
        await new_player.send_message_to_user(gameSession.fullUI())
        
        ## Only then we create the new player object and add it to the collection (since it will be without color or team for now, if we send it before the UI broadcast the front-end will get confused)
        gameSession.players[player_name] = {
            "name": player_name,
            "websocket": websocket,
            "team": '',
            "color": '',
            "object": new_player,
            "active": True
        }

        ## Figuring out and/or asking the player for team and color selection
        if len(gameSession.players) == 1:
            # If we're dealing with the first player in the game, we can assign him/her to team 0 without loss of generality.
            team = "0"
            await new_player.send_message_to_user({"type": "log", "msg": "You have been assigned to team 0."})
        else:
            if gameSession.team_is_full("0"):
                team = "1"
                await new_player.send_message_to_user({"type": "log", "msg": "Team 0 is full, you have been assigned to team 1."})
            elif gameSession.team_is_full("1"):
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

        color = await gameSession.make_player_choose_color(player_name)

        ## Setting the information we got into the various objects which need to be aware of the selections
        new_player.setColor(color)
        new_player.setTeam(team)

        # Now that we have color and team, we can set it
        gameSession.players[player_name]['color'] = color
        gameSession.players[player_name]['object'].setColor(color)
        gameSession.players[player_name]['team'] = team
        gameSession.players[player_name]['object'].setTeam(team)
        gameSession.players[player_name]['active'] = True


        ## Broadcasting the join-info to new player, the UIs and the other players
        await new_player.send_message_to_user({"type": "log", "msg": f"You successfully joined the game and will play in team {team} with color {color}!\n"})
        await gameSession.broadcast({"type": "log", "msg": f"{player_name} has joined team {team} and will play {color}.\n"}, excluded_player=player_name)
        await gameSession.broadcast({"type": "assign-player", "name": player_name, "team": team, "color": color})

    else:
        # and we're also checking if this is not a disconnect player who is coming back!
        if not existing_player['active']:
            existing_player['websocket'] = websocket
            existing_player['active'] = True
            await existing_player['object'].send_message_to_user(gameSession.fullUI())
            await existing_player['object'].send_message_to_user({"type": "log", "msg": f"You successfully rejoined the game in team {existing_player['team']} with color {existing_player['color']}!\n"})
            await existing_player['object'].sendHandAgain()
            await gameSession.broadcast({"type": "log", "msg": f"{player_name} has rejoined team {existing_player['team']} and plays {existing_player['color']}.\n"}, excluded_player=player_name)

    ## When we have 4 players, the game can start if the game.order variable has been set!
    if len(gameSession.players) == 4:
        ## We wait for the lock on the game.order to be lifted because this ws message will (most likely) come later than the check on len(game.players)
        async with orderIsSet_condition:
            await orderIsSet_condition.wait_for(lambda: len(gameSession.order) == 4)
        await gameSession.game_loop()


router = PlayerInputRouter()
manager = ConnectionManager()
orderIsSet_condition = asyncio.Condition()

# Helper function for the lock on game.order at the beginning of the game
async def try_notify_order_ready(gameSession, condition):
    async with condition:
        if len(gameSession.order) == 4:
            condition.notify_all()

@app.get("/toc")
async def root():
    return {"message": "Game backend is running."}


@app.post("/toc/api/create-game")
async def create_game():
    game_id = manager.create_game(router)
    return {"game_id": game_id}

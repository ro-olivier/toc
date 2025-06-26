from game import Game
from player import Player
from params import *


if __name__ == "__main__":

	game = Game()

	players = []
	names = []
	for i in range(0, NUMBER_OF_PLAYERS):
		player_name = ''
		while player_name == '' or player_name in names:
			player_name = input(f'Please provide a unique name for player {i} (playing {COLORS[i]}): ')
		
		player = Player(player_name, str(i%NUMBER_OF_TEAMS), COLORS[i])
		players.append(player)

	game.setPlayers(players)

	print('Ready to start the game...\n')
	print(str(game))
	game.start()
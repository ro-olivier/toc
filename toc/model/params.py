SUITS = ['♥️', '♠️', '♦️', '♣️']
VALUES = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
JOKER_VALUE = "JOKER"
JOKER_COLORS = ("red", "black")
COLORS = ['red', 'blue', 'green', 'yellow']
AVAILABLE_COLORS = COLORS + ['orange', 'purple', 'pink', 'cyan', 'lime', 'brown', 'black', 'white']
SPOTS_PER_HOUSE = 4
MOVE_DESCRIPTION = {
	'OUT' : 'Take a piece out.', 
	'MOVE' : 'Move x time(s) forward.', 
	'SWITCH' : 'Switch piece with piece of player x in spot x.', 
	'CHANGE_CARD' : 'Pick another card', 
	'BACK' : 'Move 4 spots backward.', 
	'ENTER' : 'Enter house spot number x.', 
	'SEVEN': 'Play a seven split.',
	'FIVE': 'Move an opponent\'s piece 5 times forward.',
	'HOP': 'Hop from one position numbered 7 to the next.',
	}
IDENTIFY_TIMEOUT_SECONDS = 5
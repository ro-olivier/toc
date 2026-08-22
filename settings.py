from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
GAME_DATA_DIRECTORY = Path(os.environ.get("TOC_DATA_DIRECTORY", BASE_DIR / "game-data"))
CLIENT_MESSAGE_TYPES = frozenset({
	"configure-player",
	"debug",
	"text_input",
	"card_selection",
	"spot_selection",
	"seven_hop_choice",
	"cancel_move_selection",
})
LOBBY_LIFETIME_SECONDS = 15 * 60
GAME_INACTIVITY_SECONDS = 15 * 60
ALL_PLAYERS_DISCONNECTED_GRACE_SECONDS = 30
SESSION_MONITOR_INTERVAL_SECONDS = 5

NO_GAME_FOUND_CODE = 4001
NO_PLAYER_CONTEXT_FOUND_CODE = 4002
GAME_ALREADY_FULL_CODE = 4004
CONNECTION_IDENTIFICATION_ERROR_CODE = 4005
LOBBY_EXPIRED_CLOSE_CODE = 4006
GAME_SUSPENDED_CLOSE_CODE = 4007
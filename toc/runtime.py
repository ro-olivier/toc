from settings import GAME_DATA_DIRECTORY
from toc.persistence.archive_store import CompressedJsonStore
from toc.session.connection_manager import ConnectionManager
from toc.session.input_router import PlayerInputRouter


router = PlayerInputRouter()
archiveStore = CompressedJsonStore(GAME_DATA_DIRECTORY)
manager = ConnectionManager(archiveStore=archiveStore)

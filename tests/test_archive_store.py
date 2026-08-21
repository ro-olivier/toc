import json
import os
import stat

import pytest

from toc.persistence.archive_store import ArchiveCategory, ArchiveCorruptionError, CompressedJsonStore
from toc.infrastructure.identity import createSessionId


@pytest.fixture
def archiveStore(tmp_path):
	return CompressedJsonStore(tmp_path / "game-data")


def test_compressed_archive_survives_round_trip(archiveStore):
	sessionId = createSessionId()

	payload = {
		"sessionId": sessionId,
		"players": [
			{"name": "Alice", "color": "red"},
			{"name": "Élodie", "color": "blue"},
		],
	}

	path = archiveStore.write(ArchiveCategory.ACTIVE, sessionId, payload)

	assert path.exists()
	assert archiveStore.read(ArchiveCategory.ACTIVE, sessionId) == payload


def test_archive_is_actually_compressed(archiveStore):
	sessionId = createSessionId()

	payload = {
		"events": [
			{
				"type": "piece-moved",
				"details": {
					"player": "Alice",
					"origin": "red-1",
					"target": "red-7",
				},
			}
			for _ in range(1000)
		],
	}

	uncompressedSize = len(json.dumps(payload).encode("utf-8"))
	path = archiveStore.write(ArchiveCategory.ACTIVE, sessionId, payload)

	assert path.stat().st_size < uncompressedSize


def test_archive_file_is_private(archiveStore):
	sessionId = createSessionId()
	path = archiveStore.write(ArchiveCategory.SUSPENDED, sessionId, {"status": "suspended"})

	assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_writing_again_atomically_replaces_archive(archiveStore):
	sessionId = createSessionId()

	archiveStore.write(ArchiveCategory.ACTIVE, sessionId, {"version": 1})
	archiveStore.write(ArchiveCategory.ACTIVE, sessionId, {"version": 2})

	assert archiveStore.read(ArchiveCategory.ACTIVE, sessionId) == {"version": 2}


def test_failed_replacement_preserves_previous_archive(archiveStore, monkeypatch):
	sessionId = createSessionId()
	originalPayload = {"version": 1}

	archiveStore.write(ArchiveCategory.ACTIVE, sessionId, originalPayload)

	def failReplacement(source, destination):
		raise OSError("Deliberate replacement failure")

	monkeypatch.setattr("toc.persistence.archive_store.os.replace", failReplacement)

	with pytest.raises(OSError, match="Deliberate replacement failure"):
		archiveStore.write(ArchiveCategory.ACTIVE, sessionId, {"version": 2})

	assert archiveStore.read(ArchiveCategory.ACTIVE, sessionId) == originalPayload

	temporaryFiles = list(archiveStore.pathFor(ArchiveCategory.ACTIVE, sessionId).parent.glob(".*.tmp"))

	assert temporaryFiles == []


def test_corrupt_archive_is_rejected(archiveStore):
	sessionId = createSessionId()
	path = archiveStore.pathFor(ArchiveCategory.ACTIVE, sessionId)

	path.write_bytes(b"this is not a gzip file")

	with pytest.raises(ArchiveCorruptionError, match="is corrupt"):
		archiveStore.read(ArchiveCategory.ACTIVE, sessionId)


@pytest.mark.parametrize("documentId", ["../escape", "../../etc/passwd", "", "not-a-uuid"])
def test_invalid_document_id_is_rejected(archiveStore, documentId):
	with pytest.raises(ValueError, match="Invalid archive document ID"):
		archiveStore.write(ArchiveCategory.ACTIVE, documentId, {})


@pytest.mark.parametrize("payload", [[], "text", None, {"invalid": object()}, {"invalid": float("nan")}])
def test_non_json_archive_payload_is_rejected(archiveStore, payload):
	with pytest.raises(ValueError):
		archiveStore.write(ArchiveCategory.ACTIVE, createSessionId(), payload)
import gzip
import json
import os

from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4


class ArchiveCategory(StrEnum):
	ACTIVE = "active"
	SUSPENDED = "suspended"
	FINISHED = "finished"


class ArchiveCorruptionError(ValueError):
	pass


def _rejectInvalidJsonConstant(value):
	raise ValueError(f"Invalid JSON constant: {value}")


class CompressedJsonStore:
	def __init__(self, rootDirectory):
		self._rootDirectory = Path(rootDirectory)

		for category in ArchiveCategory:
			(self._rootDirectory / category.value).mkdir(parents=True, exist_ok=True)

	def pathFor(self, category: ArchiveCategory, documentId: str) -> Path:
		if not isinstance(category, ArchiveCategory):
			raise ValueError("Invalid archive category")

		if type(documentId) is not str:
			raise ValueError("Invalid archive document ID")

		try:
			normalisedId = UUID(hex=documentId).hex
		except (ValueError, AttributeError) as error:
			raise ValueError("Invalid archive document ID") from error

		if normalisedId != documentId:
			raise ValueError("Invalid archive document ID")

		return self._rootDirectory / category.value / f"{documentId}.json.gz"

	def write(self, category: ArchiveCategory, documentId: str, payload: dict) -> Path:
		if type(payload) is not dict:
			raise ValueError("Archive payload must be an object")

		try:
			encodedPayload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False).encode("utf-8")
		except (TypeError, ValueError) as error:
			raise ValueError("Archive payload is not JSON-compatible") from error

		finalPath = self.pathFor(category, documentId)
		temporaryPath = finalPath.parent / f".{documentId}.{uuid4().hex}.tmp"

		try:
			with open(temporaryPath, "xb") as rawFile:
				os.chmod(temporaryPath, 0o600)

				with gzip.GzipFile(fileobj=rawFile, mode="wb", compresslevel=6, mtime=0) as compressedFile:
					compressedFile.write(encodedPayload)

				rawFile.flush()
				os.fsync(rawFile.fileno())

			os.replace(temporaryPath, finalPath)
			self._syncDirectory(finalPath.parent)

		except Exception:
			temporaryPath.unlink(missing_ok=True)
			raise

		return finalPath

	def read(self, category: ArchiveCategory, documentId: str) -> dict:
		path = self.pathFor(category, documentId)

		try:
			with gzip.open(path, "rt", encoding="utf-8") as compressedFile:
				payload = json.load(compressedFile, parse_constant=_rejectInvalidJsonConstant)

		except FileNotFoundError:
			raise

		except (gzip.BadGzipFile, EOFError, UnicodeDecodeError, json.JSONDecodeError, OSError, ValueError) as error:
			raise ArchiveCorruptionError(f"Archive '{documentId}' is corrupt") from error

		if type(payload) is not dict:
			raise ArchiveCorruptionError(f"Archive '{documentId}' does not contain an object")

		return payload

	def _syncDirectory(self, directory: Path) -> None:
		if not hasattr(os, "O_DIRECTORY"):
			return

		directoryDescriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)

		try:
			os.fsync(directoryDescriptor)
		finally:
			os.close(directoryDescriptor)
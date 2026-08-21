import json
import logging
import os
import sys

from datetime import datetime, timezone


CONTEXT_FIELDS = (
	"sessionId",
	"joinCode",
	"playerId",
	"routerId",
	"playerName",
	"messageType",
	"event",
)


class TocJsonFormatter(logging.Formatter):
	def format(self, record):
		payload = {
			"timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
			"level": record.levelname,
			"logger": record.name,
			"message": record.getMessage(),
		}

		for fieldName in CONTEXT_FIELDS:
			if hasattr(record, fieldName):
				payload[fieldName] = getattr(record, fieldName)

		if record.exc_info:
			payload["exception"] = self.formatException(record.exc_info)

		return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configureApplicationLogging() -> None:
	tocLogger = logging.getLogger("toc")

	if tocLogger.handlers:
		return

	levelName = os.environ.get("TOC_LOG_LEVEL", "INFO").upper()
	level = getattr(logging, levelName, logging.INFO)

	handler = logging.StreamHandler(sys.stdout)
	handler.setFormatter(TocJsonFormatter())

	tocLogger.addHandler(handler)
	tocLogger.setLevel(level)
	tocLogger.propagate = False
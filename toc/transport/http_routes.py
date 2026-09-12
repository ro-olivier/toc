from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from settings import MAX_PLAYER_NAME_LENGTH
from toc.infrastructure.messages import MESSAGE_KEYS, build_message
from toc.model.game_mode import DEFAULT_GAME_MODE, getGameModeDefinition
from toc.model.rules import DEFAULT_RULE_PRESET, RULE_PRESETS, get_rule_schema, resolve_ruleset
from toc.runtime import manager, router


httpRouter = APIRouter()


@httpRouter.get("/toc")
async def root():
	return {"message": "Game backend is running."}


@httpRouter.get("/toc/api/rule-presets")
async def get_rule_presets():
	return {
		"default": DEFAULT_RULE_PRESET,
		"presets": {name: rules.to_dict() for name, rules in RULE_PRESETS.items()},
		"schema": get_rule_schema(),
		"messageKeys": sorted(MESSAGE_KEYS),
	}


@httpRouter.get("/toc/api/open-lobbies")
async def get_open_lobbies():
	return {"lobbies": manager.get_open_lobbies()}


@httpRouter.post("/toc/api/create-game")
async def create_game(payload: Any = Body(default=None)):
	if payload is None:
		payload = {}

	if type(payload) is not dict:
		detail = build_message("http-error", "errors.creation_data_object", "Game creation data must be an object.")
		raise HTTPException(status_code=422, detail=detail)

	unknownFields = set(payload) - {"preset", "rules", "mode", "layout", "creatorName"}

	if unknownFields:
		fields = ", ".join(sorted(unknownFields))
		detail = build_message("http-error", "errors.unknown_creation_fields", f"Unknown game creation fields: {fields}", {"fields": fields})
		raise HTTPException(status_code=422, detail=detail)

	presetName = payload.get("preset", DEFAULT_RULE_PRESET)
	modeName = payload.get("mode", DEFAULT_GAME_MODE)
	layoutName = payload.get("layout")

	creatorName = ""

	if "creatorName" in payload:
		rawCreatorName = payload["creatorName"]

		if type(rawCreatorName) is not str or not rawCreatorName.strip() or len(rawCreatorName.strip()) > MAX_PLAYER_NAME_LENGTH:
			detail = build_message("http-error", "errors.invalid_creator_name", f"Creator name must contain between 1 and {MAX_PLAYER_NAME_LENGTH} characters.")
			raise HTTPException(status_code=422, detail=detail)

		creatorName = rawCreatorName.strip()

	try:
		rules = resolve_ruleset(presetName, payload.get("rules"))
		modeDefinition = getGameModeDefinition(modeName, layoutName)
	except ValueError as error:
		detail = build_message("http-error", "errors.invalid_game_configuration", str(error))
		raise HTTPException(status_code=422, detail=detail) from error

	gameId = manager.create_game(router, rules, presetName, modeDefinition, creatorName)

	return {
		"game_id": gameId,
		"creatorName": creatorName,
		"preset": presetName,
		"rules": rules.to_dict(),
		"gameMode": modeDefinition.to_dict(),
	}

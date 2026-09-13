from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from toc.infrastructure.messages import MESSAGE_KEYS, buildMessage
from toc.model.game_mode import DEFAULT_GAME_MODE, getGameModeDefinition
from toc.model.rules import DEFAULT_RULE_PRESET, RULE_PRESETS, getRuleSchema, resolveRuleset
from toc.runtime import manager, router
from settings import MAX_PLAYER_NAME_LENGTH


httpRouter = APIRouter()


@httpRouter.get("/toc")
async def root() -> dict[str, str]:
	return {"message": "Game backend is running."}


@httpRouter.get("/toc/api/rule-presets")
async def getRulePresets() -> dict[str, object]:
	return {
		"default": DEFAULT_RULE_PRESET,
		"presets": {name: rules.to_dict() for name, rules in RULE_PRESETS.items()},
		"schema": getRuleSchema(),
		"messageKeys": sorted(MESSAGE_KEYS),
	}


@httpRouter.get("/toc/api/open-lobbies")
async def getOpenLobbies() -> dict[str, list[dict[str, object]]]:
	return {"lobbies": manager.getOpenLobbies()}


@httpRouter.post("/toc/api/create-game")
async def createGame(payload: object = Body(default=None)) -> dict[str, object]:
	if payload is None:
		payload = {}

	if type(payload) is not dict:
		detail = buildMessage("http-error", "errors.creation_data_object", "Game creation data must be an object.")
		raise HTTPException(status_code=422, detail=detail)

	unknownFields = set(payload) - {"preset", "rules", "mode", "layout", "creatorName"}

	if unknownFields:
		fields = ", ".join(sorted(unknownFields))
		detail = buildMessage("http-error", "errors.unknown_creation_fields", f"Unknown game creation fields: {fields}", {"fields": fields})
		raise HTTPException(status_code=422, detail=detail)

	presetName = payload.get("preset", DEFAULT_RULE_PRESET)
	modeName = payload.get("mode", DEFAULT_GAME_MODE)
	layoutName = payload.get("layout")

	creatorName = ""

	if "creatorName" in payload:
		rawCreatorName = payload["creatorName"]

		if type(rawCreatorName) is not str or not rawCreatorName.strip() or len(rawCreatorName.strip()) > MAX_PLAYER_NAME_LENGTH:
			detail = buildMessage("http-error", "errors.invalid_creator_name", f"Creator name must contain between 1 and {MAX_PLAYER_NAME_LENGTH} characters.")
			raise HTTPException(status_code=422, detail=detail)

		creatorName = rawCreatorName.strip()

	try:
		rules = resolveRuleset(presetName, payload.get("rules"))
		modeDefinition = getGameModeDefinition(modeName, layoutName)
	except ValueError as error:
		detail = buildMessage("http-error", "errors.invalid_game_configuration", str(error))
		raise HTTPException(status_code=422, detail=detail) from error

	gameId = manager.createGame(router, rules, presetName, modeDefinition, creatorName)

	return {
		"gameId": gameId,
		"creatorName": creatorName,
		"preset": presetName,
		"rules": rules.to_dict(),
		"gameMode": modeDefinition.to_dict(),
	}

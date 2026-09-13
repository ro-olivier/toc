import {app, constants, dom, i18n, state} from "./context.js";
import "./i18n.js";
import "./ui.js";
import "./lobby.js";
import "./socket.js";
import "./board.js";
import "./cards.js";

dom.nameInput.value = state.stored_player_name ?? "";

app.initializeLanguageInterface();
app.showStoredStartNotice();

dom.rulePresetSelect.addEventListener("change", app.updateRulesetEditorVisibility);
dom.resetCustomRules.addEventListener("click", () => app.applyRuleValues(state.ruleConfiguration.presets[state.ruleConfiguration.default]));
app.initializeRuleSelector();

dom.refreshLobbiesBtn.addEventListener("click", () => app.refreshOpenLobbies());
app.refreshOpenLobbies();

dom.resumeGameBtn.addEventListener("click", async () => {
  if (!state.stored_player_name || !state.stored_game_id) return;
  await app.connectToGame(state.stored_game_id, state.stored_player_name, true);
});

window.setInterval(() => {
  if (!dom.startScreen.classList.contains("hidden")) app.refreshOpenLobbies(false);
}, 15000);

dom.createBtn.addEventListener("click", async () => {
  const name = dom.nameInput.value.trim();
  if (!name) {
    app.showError(i18n.t("errors.name_required"));
    return;
  }

  app.clearError();
  dom.createBtn.disabled = true;

  try {
    const payload = {preset: dom.rulePresetSelect.value, creatorName: name};
    const selectedMode = dom.gameModeSelect.selectedOptions[0];
    payload.mode = selectedMode.dataset.mode;
    if (selectedMode.dataset.layout) payload.layout = selectedMode.dataset.layout;
    if (dom.rulePresetSelect.value === "custom") payload.rules = app.collectCustomRuleValues();

    const response = await fetch("/toc/api/create-game", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(app.getHttpErrorMessage(data));

    const gameId = data.gameId;
    app.log({
      messageKey: "connection.created_game",
      parameters: {gameId},
      fallback: `Created game ID: ${gameId}`,
    });
    await app.connectToGame(gameId, name);
  } catch (error) {
    app.showError(error.message || i18n.t("errors.game_creation_failed"));
    dom.createBtn.disabled = false;
  }
});

if (dom.cancelCardSelection) {
  dom.cancelCardSelection.addEventListener("click", event => {
    event.stopPropagation();
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN || !state.activeRequestId) return;

    const message = {id: crypto.randomUUID(), requestId: state.activeRequestId, type: "cancel_move_selection"};
    state.ws.send(JSON.stringify(message));
    app.setCancelSelectionVisible(false);
    app.clearSpotSelection();
    app.setTranslatedText(dom.turnInstruction, "game.returning_to_cards");
  });
}

dom.lobbyChoiceForm.addEventListener("submit", event => {
  event.preventDefault();

  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    dom.lobbyError.textContent = i18n.t("errors.connection_not_open");
    dom.lobbyError.classList.remove("hidden");
    return;
  }

  dom.lobbyError.classList.add("hidden");
  dom.confirmLobbyChoice.disabled = true;
  dom.lobbyStatus.textContent = i18n.t("lobby.confirming");

  const colors = Array.from(dom.colorSelects.querySelectorAll("select"), select => select.value);
  state.ws.send(JSON.stringify({
    id: crypto.randomUUID(),
    type: "configure-player",
    team: dom.teamSelect.value,
    colors,
  }));
});

if (typeof ResizeObserver === "function") {
  const boardResizeObserver = new ResizeObserver(app.fitBoardToViewport);
  boardResizeObserver.observe(dom.boardViewportElement);
} else {
  window.addEventListener("resize", app.fitBoardToViewport);
}
requestAnimationFrame(app.fitBoardToViewport);

document.addEventListener("click", () => {
  if (!state.selectedCard) return;
  state.selectedCard.classList.remove("selected");
  state.selectedCard = null;
});

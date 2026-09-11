import {app, constants, dom, i18n, state} from "./context.js";

app.showStoredStartNotice = function showStoredStartNotice() {
  const messageKey = window.sessionStorage.getItem(constants.START_NOTICE_STORAGE_KEY);
  if (!messageKey) return;

  window.sessionStorage.removeItem(constants.START_NOTICE_STORAGE_KEY);
  app.setTranslatedText(dom.errorMsg, messageKey);
  dom.errorMsg.classList.remove("hidden");
};

app.setCancelSelectionVisible = function setCancelSelectionVisible(visible) {
  if (!dom.cancelCardSelection) return;

  dom.cancelCardSelection.classList.toggle("hidden", !visible);
  dom.cancelCardSelection.disabled = !visible;
};

app.showGameUI = function showGameUI() {
  dom.startScreen.classList.add("hidden");
  dom.lobbyScreen.classList.add("hidden");
  dom.gameScreen.classList.remove("hidden");
};

app.showLobbyUI = function showLobbyUI() {
  dom.startScreen.classList.add("hidden");
  dom.gameScreen.classList.add("hidden");
  dom.lobbyScreen.classList.remove("hidden");
};

app.showError = function showError(message) {
  if (!dom.lobbyScreen.classList.contains("hidden")) {
    app.setRawText(dom.lobbyError, message);
    dom.lobbyError.classList.remove("hidden");
    return;
  }

  if (!dom.gameScreen.classList.contains("hidden")) {
    app.error(message);
    return;
  }

  app.setRawText(dom.errorMsg, message);
  dom.errorMsg.classList.remove("hidden");
};

app.clearError = function clearError() {
  app.setRawText(dom.errorMsg, "");
  dom.errorMsg.classList.add("hidden");
  app.setRawText(dom.lobbyError, "");
  dom.lobbyError.classList.add("hidden");
};

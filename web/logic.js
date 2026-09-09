const nameInput = document.getElementById("name-input");
const createBtn = document.getElementById("create-btn");
const resumeGamePanel = document.getElementById("resume-game-panel");
const resumeGameDescription = document.getElementById("resume-game-description");
const resumeGameBtn = document.getElementById("resume-game-btn");
const sendBtn = document.getElementById("send-btn");
const commandInput = document.getElementById("command-input");
const terminal = document.getElementById("terminal");
const startScreen = document.getElementById("start-screen");
const lobbyScreen = document.getElementById("lobby-screen");
const gameScreen = document.getElementById("game-screen");
const refreshLobbiesBtn = document.getElementById("refresh-lobbies-btn");
const openLobbiesStatus = document.getElementById("open-lobbies-status");
const openLobbiesList = document.getElementById("open-lobbies-list");
const errorMsg = document.getElementById("error-msg");
const lobbyGameId = document.getElementById("lobby-game-id");
const lobbyPlayerCount = document.getElementById("lobby-player-count");
const lobbyPlayers = document.getElementById("lobby-players");
const lobbyChoiceForm = document.getElementById("lobby-choice-form");
const rulePresetSelect = document.getElementById("rule-preset-select");
const rulePresetSummary = document.getElementById("rule-preset-summary");
const customRulesEditor = document.getElementById("custom-rules-editor");
const customRulesFields = document.getElementById("custom-rules-fields");
const resetCustomRules = document.getElementById("reset-custom-rules");
const lobbyRulesPanel = document.getElementById("lobby-rules-panel");
const lobbyRulesPreset = document.getElementById("lobby-rules-preset");
const lobbyRulesList = document.getElementById("lobby-rules-list");
const gameRulesPanel = document.getElementById("game-rules-panel");
const gameRulesPreset = document.getElementById("game-rules-preset");
const gameRulesList = document.getElementById("game-rules-list");
const teamSelect = document.getElementById("team-select");
const gameModeSelect = document.getElementById("game-mode-select");
const colorSelects = document.getElementById("color-selects");
const confirmLobbyChoice = document.getElementById("confirm-lobby-choice");
const lobbyStatus = document.getElementById("lobby-status");
const lobbyError = document.getElementById("lobby-error");
const gameIdDisplay = document.getElementById("game-id-display");
const dealerName = document.getElementById("dealer-name");
const connectionStatus = document.getElementById("connection-status");
const connectionStatusText = document.getElementById("connection-status-text");
const currentPlayerName = document.getElementById("current-player-name");
const turnInstruction = document.getElementById("turn-instruction");
const turnBanner = document.querySelector(".turn-banner");
const cancelCardSelection = document.getElementById("cancel-card-selection");
const localHandSlot = document.getElementById("local-hand-slot");
const emptyHandMessage = document.getElementById("empty-hand-message");
const board = document.getElementById('board');
const discardPile = document.getElementById("discard-pile");
const discardPileCard = document.getElementById("discard-pile-card");


const selectableSpotHandlers = new Map();

let ws = null;
SERVER_UNREACHABLE_CODE = 1006
NO_GAME_FOUND_CODE = 4001
NO_PLAYER_CONTEXT_FOUND_CODE = 4002
GAME_ALREADY_FULL_CODE = 4004
CONNECTION_IDENTIFICATION_ERROR_CODE = 4005
LOBBY_EXPIRED_CLOSE_CODE = 4006
GAME_SUSPENDED_CLOSE_CODE = 4007
const START_NOTICE_STORAGE_KEY = "toc.startNotice";

let local_player_name = null;
let local_game_Id = null;
let local_player = null;
let local_card_box = null;
let local_info_box = null;
let currentLobbyState = null;

let ruleConfiguration = null;
let displayedRuleset = null;

const RULE_GROUPS = {
  round: "rules.groups.round",
  board: "rules.groups.board",
  special: "rules.groups.special",
  seven: "rules.groups.seven",
};

const RULE_UI = {
  card_exchange: {group: "round"},
  shuffle_cards: {group: "round"},
  rotation: {group: "round"},
  deal_card_counts: {group: "round"},
  cannot_play_folds_entire_hand: {group: "round"},
  exit_spot_is_protected_and_blocking: {group: "board"},
  house_spots_are_blocking_and_protected: {group: "board"},
  landing_on_occupied_spot_kicks_piece: {group: "board"},
  track_region_length: {group: "board"},
  enter_house_at_spot: {group: "board"},
  four_can_move_backward: {group: "special"},
  can_enter_house_backward: {group: "special"},
  five_behaviour: {group: "special"},
  jacks_can_switch: {group: "special"},
  jacks_can_switch_then_seven_hop: {group: "special"},
  ace_values: {group: "special"},
  king_kicks_pieces_on_path: {group: "special"},
  joker_kicks_pieces_on_path: {group: "special"},
  seven_can_split: {group: "seven"},
  seven_split_kicks_pieces_on_path: {group: "seven"},
  seven_hopping: {group: "seven"},
  five_hop_decider: {group: "seven"},
  seven_hopping_on_four_backward_goes_backward: {group: "seven"},
};

let stored_player_name = window.localStorage.getItem("session_player_name");
let stored_game_id = window.localStorage.getItem("session_game_ID");

let activeRequestId = null;

nameInput.value = stored_player_name !== null ? stored_player_name : '';

const tocI18n = window.tocI18n;
const languageSelect = document.getElementById("language-select");

let openLobbies = [];
let openLobbiesRequestInProgress = false;

function refreshResumeGamePanel() {
  const canResume = Boolean(stored_player_name && stored_game_id);

  resumeGamePanel.classList.toggle("hidden", !canResume);

  if (!canResume) return;

  const displayedGameName = formatGameName(stored_game_id);

  setTranslatedText(resumeGameDescription, "start.resume_description", {
    player: stored_player_name,
    game: displayedGameName,
  });

  resumeGameBtn.textContent = tocI18n.t("start.resume_button", {
    game: displayedGameName,
  });
}

function translateStaticInterface() {
  document.title = tocI18n.t("app.title");

  document.querySelectorAll("[data-i18n]").forEach(element => {
    element.textContent = tocI18n.t(element.dataset.i18n);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach(element => {
    element.placeholder = tocI18n.t(element.dataset.i18nPlaceholder);
  });

  document.querySelectorAll("[data-i18n-dynamic]").forEach(element => {
    const parameters = element.dataset.i18nParameters ? JSON.parse(element.dataset.i18nParameters) : {};
    element.textContent = tocI18n.t(element.dataset.i18nDynamic, parameters);
  });

  document.querySelectorAll("[data-i18n-title]").forEach(element => {
    const translation = tocI18n.t(element.dataset.i18nTitle);
    element.title = translation;
    element.setAttribute("aria-label", translation);
  });
}

function refreshLanguageInterface() {
  translateStaticInterface();

  Array.from(languageSelect.options).forEach(option => {
    option.textContent = tocI18n.t(`language.${option.value}`);
  });

  if (ruleConfiguration) {
    const customValues = customRulesFields.querySelector("[data-rule-name]") ? collectCustomRuleValues() : ruleConfiguration.presets[ruleConfiguration.default];
    const customOption = Array.from(rulePresetSelect.options).find(option => option.value === "custom");

    if (customOption) customOption.textContent = tocI18n.t("rules.custom_option");

    renderCustomRuleControls(ruleConfiguration.schema, customValues);
    updateRulesetEditorVisibility();
  }

  renderOpenLobbies();
  refreshResumeGamePanel();

  if (displayedRuleset) renderRulesetDisplays(displayedRuleset);

  if (currentLobbyState && !lobbyScreen.classList.contains("hidden")) {
    renderLobbyState(currentLobbyState);
  }

  backendMessageElements.forEach((message, element) => {
    element.textContent = getMessage(message);
  });

  renderActivityLog();
}

function formatGameName(gameName) {
  return gameName
    .split("-")
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function getGameModeLabel(mode) {
  if (!mode?.name) return "";

  if (mode.name === "duel_four" && mode.layout) {
    return tocI18n.t(`game_modes.duel_four_${mode.layout}`);
  }

  return tocI18n.t(`game_modes.${mode.name}`);
}

function renderOpenLobbies() {
  openLobbiesList.replaceChildren();

  if (openLobbies.length === 0) {
    setTranslatedText(openLobbiesStatus, "lobby_browser.none");
    openLobbiesStatus.classList.remove("hidden");
    return;
  }

  openLobbiesStatus.classList.add("hidden");

  openLobbies.forEach(lobby => {
    const card = document.createElement("article");
    const details = document.createElement("div");
    const gameName = document.createElement("h3");
    const creator = document.createElement("p");
    const metadata = document.createElement("div");
    const mode = document.createElement("span");
    const playerCount = document.createElement("span");
    const joinButton = document.createElement("button");

    card.className = "open-lobby-card";
    details.className = "open-lobby-details";
    gameName.className = "open-lobby-name";
    creator.className = "open-lobby-creator";
    metadata.className = "open-lobby-metadata";
    mode.className = "open-lobby-mode";
    playerCount.className = "open-lobby-player-count";
    joinButton.className = "open-lobby-join";

    gameName.textContent = formatGameName(lobby.gameName);
    creator.textContent = tocI18n.t("lobby_browser.created_by", {player: lobby.creatorName || "—"});
    mode.textContent = getGameModeLabel(lobby.mode);
    playerCount.textContent = tocI18n.t("lobby_browser.player_count", {
      count: lobby.playerCount,
      capacity: lobby.playerCapacity,
    });
    joinButton.type = "button";
    joinButton.textContent = tocI18n.t("lobby_browser.join");

    joinButton.addEventListener("click", async () => {
      const playerName = nameInput.value.trim();

      if (!playerName) {
        showError(tocI18n.t("errors.name_required"));
        nameInput.focus();
        return;
      }

      clearError();
      await connectToGame(lobby.gameName, playerName);
    });

    metadata.append(mode, playerCount);
    details.append(gameName, creator, metadata);
    card.append(details, joinButton);
    openLobbiesList.appendChild(card);
  });
}

async function refreshOpenLobbies(showLoading = true) {
  if (openLobbiesRequestInProgress) return;

  openLobbiesRequestInProgress = true;
  refreshLobbiesBtn.disabled = true;

  if (showLoading) {
    setTranslatedText(openLobbiesStatus, "lobby_browser.loading");
    openLobbiesStatus.classList.remove("hidden");
  }

  try {
    const response = await fetch("/toc/api/open-lobbies", {cache: "no-store"});

    if (!response.ok) {
      throw new Error(`Open-lobby request failed with status ${response.status}`);
    }

    const data = await response.json();

    if (!Array.isArray(data.lobbies)) {
      throw new Error("Invalid open-lobby response");
    }

    openLobbies = data.lobbies;
    renderOpenLobbies();
  } catch (error) {
    console.error(error);
    openLobbies = [];
    openLobbiesList.replaceChildren();
    setTranslatedText(openLobbiesStatus, "lobby_browser.unavailable");
    openLobbiesStatus.classList.remove("hidden");
  } finally {
    openLobbiesRequestInProgress = false;
    refreshLobbiesBtn.disabled = false;
  }
}

function refreshLocalHandLabels() {
  playerAssignments.filter(player => isLocalSeat(player.seatId)).forEach(player => {
    getCardBoxFromId(player.seatId).dataset.colorLabel = formatColorName(player.color);
  });
}


function initializeLanguageInterface() {
    tocI18n.supportedLanguages.forEach(language => {
    const option = document.createElement("option");
    option.value = language;
    languageSelect.appendChild(option);
  });

  languageSelect.value = tocI18n.getLanguage();
  refreshLanguageInterface();

  languageSelect.addEventListener("change", () => tocI18n.setLanguage(languageSelect.value));
  window.addEventListener("toc-language-change", refreshLanguageInterface);
  window.addEventListener("toc-language-change", refreshLocalHandLabels);

}

function showStoredStartNotice() {
  const messageKey = window.sessionStorage.getItem(START_NOTICE_STORAGE_KEY);
  if (!messageKey) return;

  window.sessionStorage.removeItem(START_NOTICE_STORAGE_KEY);
  setTranslatedText(errorMsg, messageKey);
  errorMsg.classList.remove("hidden");
}

function setTranslatedText(element, key, parameters = {}) {
  backendMessageElements.delete(element);
  element.dataset.i18nDynamic = key;
  element.dataset.i18nParameters = JSON.stringify(parameters);
  element.textContent = tocI18n.t(key, parameters);
}

function setRawText(element, text) {
  backendMessageElements.delete(element);
  delete element.dataset.i18nDynamic;
  delete element.dataset.i18nParameters;
  element.textContent = text;
}


function buildWebSocketUrl(gameId, playerName) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";

  return (
    `${protocol}://${window.location.host}/toc/ws/` +
    `${encodeURIComponent(gameId)}/` +
    `${encodeURIComponent(playerName)}`
  );
}

function getResumeTokenStorageKey(gameId, playerName) {
  return `toc.resumeToken.${encodeURIComponent(gameId)}.${encodeURIComponent(playerName)}`;
}

function returnToStartAfterServerClose(messageKey, gameId, playerName, clearGameCredentials) {
  window.sessionStorage.setItem(START_NOTICE_STORAGE_KEY, messageKey);

  if (clearGameCredentials) {
    window.localStorage.removeItem(getResumeTokenStorageKey(gameId, playerName));
    window.localStorage.removeItem("session_game_ID");
  }

  window.location.reload();
}

////// Input-Output / WebSocket handling //////
const backendMessageElements = new Map();
const activityMessages = [];

function getMessage(message) {
  if (typeof message === "string") return message;

  if (!message?.messageKey) {
    console.warn("Received a player-facing message without messageKey:", message);
    return message?.fallback || "";
  }

  const parameters = {...(message.parameters || {})};
  if (parameters.color) parameters.color = formatColorName(parameters.color);

  const translatedMessage = tocI18n.t(message.messageKey, parameters);

  if (translatedMessage !== message.messageKey) return translatedMessage;

  console.warn(`Missing translation: ${message.messageKey}`);
  return message.fallback || message.messageKey;
}

function getHttpErrorMessage(responseData) {
  const detail = responseData?.detail;

  if (detail && typeof detail === "object" && !Array.isArray(detail) && detail.messageKey) {
    return getMessage(detail);
  }

  if (typeof detail === "string") return detail;

  return tocI18n.t("errors.game_creation_failed");
}

function setMessageText(element, message) {
  if (typeof message === "string") {
    setRawText(element, message);
    return;
  }

  delete element.dataset.i18nDynamic;
  delete element.dataset.i18nParameters;
  backendMessageElements.set(element, message);
  element.textContent = getMessage(message);
}

function renderActivityLog() {
  terminal.textContent = activityMessages.map(entry => {
    const prefix = entry.isError ? tocI18n.t("common.error_prefix") : "";
    return `${prefix}${getMessage(entry.message)}`;
  }).join("\n");

  terminal.scrollTop = terminal.scrollHeight;
}

function log(message, isError = false) {
  activityMessages.push({message, isError});
  renderActivityLog();
}

function query(message) {
  setMessageText(turnInstruction, message);
  turnInstruction.classList.remove("error-state");
  log(message);
}

function error(message) {
  setMessageText(turnInstruction, message);
  turnInstruction.classList.add("error-state");
  log(message, true);
}

function setCancelSelectionVisible(visible) {
  if (!cancelCardSelection) return;

  cancelCardSelection.classList.toggle("hidden", !visible);
  cancelCardSelection.disabled = !visible;
}

function showGameUI() {
  startScreen.classList.add("hidden");
  lobbyScreen.classList.add("hidden");
  gameScreen.classList.remove("hidden");
}

function showLobbyUI() {
  startScreen.classList.add("hidden");
  gameScreen.classList.add("hidden");
  lobbyScreen.classList.remove("hidden");
}

function showError(message) {
  if (!lobbyScreen.classList.contains("hidden")) {
    setRawText(lobbyError, message);
    lobbyError.classList.remove("hidden");
    return;
  }

  if (!gameScreen.classList.contains("hidden")) {
    error(message);
    return;
  }

  setRawText(errorMsg, message);
  errorMsg.classList.remove("hidden");
}

function clearError() {
  setRawText(errorMsg, "");
  errorMsg.classList.add("hidden");
  setRawText(lobbyError, "");
  lobbyError.classList.add("hidden");
}

async function connectToGame(gameId, name, rejoin = false) {
  clearError();
  gameId = gameId.trim().toLowerCase();
  const wsUrl = buildWebSocketUrl(gameId, name);
  try {
    ws = new WebSocket(wsUrl);
  } catch (err) {
    console.error(err);
    createBtn.disabled = ruleConfiguration === null;
    showError(tocI18n.t("errors.websocket_error"));
    return;
  }

  const resumeTokenStorageKey = getResumeTokenStorageKey(gameId, name);
  const resumeToken = window.localStorage.getItem(resumeTokenStorageKey);

  ws.onopen = () => {
    ws.send(JSON.stringify({
      type: "identify",
      resumeToken: resumeToken,
    }));
  };

  ws.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      // Fallback for plaintext messages
      const loggableData = data.type === "ready" ? {...data, resumeToken: "[redacted]"} : data;
      console.log("[WebSocket] Received:", loggableData);
      return;
    }
    console.log('[ws.oneMessage top handler] Received the following message from back-end:' + JSON.stringify(data))

    const actingSeatId = getMessageSeatId(data);
    switch (data.type) {
      case 'ready':

        if (typeof data.resumeToken === "string" && data.resumeToken !== "") {
          window.localStorage.setItem(resumeTokenStorageKey, data.resumeToken);
        }

        stored_player_name = name;
        stored_game_id = gameId;

        window.localStorage.setItem("session_player_name", stored_player_name);
        window.localStorage.setItem("session_game_ID", stored_game_id);

        log({
          messageKey: "connection.connected_as",
          parameters: {gameId, player: name},
          fallback: `Connected to game ${gameId} as ${name}.`,
        });
        setTranslatedText(connectionStatusText, "connection.connected");
        local_player_name = name;
        local_game_Id = gameId;
        gameIdDisplay.textContent = gameId;
        connectionStatus.classList.add("connected");
        showLobbyUI();
        break;

      case 'lobby-state':
        configureBoardGeometry(data.trackRegionCount, data.trackRegionLength, data.enterHouseAtSpot);
        renderLobbyState(data);
        break;

      case 'lobby-error':
        setMessageText(lobbyError, data);
        lobbyError.classList.remove("hidden");
        confirmLobbyChoice.disabled = false;
        break;
      
      case 'assign-player':
        assignPlayer(data.seatId || data.name, data.name, data.team, data.color);
        break;

      case "full-ui-state":
        configureBoardGeometry(data.trackRegionCount, data.trackRegionLength, data.enterHouseAtSpot);
        renderRulesetDisplays(data.ruleset);

        data.players.forEach((player, seatIndex) => {
          assignPlayer(player.seatId, player.name, player.team, player.color, seatIndex);

          if (player.number_of_cards === 0) {
            hideCardBlock(player.seatId);
          } else {
            displayHiddenCards(player.seatId, player.number_of_cards);
          }
        });

        data.pieces.forEach(piece => {
          placePieceOnSpot(piece.seatId || piece.playerId, piece.spotIndex);
        });

        displayActivePlayer(data.activeSeatId || data.active_player);

        if (data.lastPlayedCard) {
          showCardOnDiscardPile(data.lastPlayedCard.value, data.lastPlayedCard.suit);
        } else {
          clearDiscardPile();
        }
        break;

      case "draw":
        // When we receive the draw order, we only display the (hidden) cards of the players unless they are already displayed
        playerAssignments.forEach(player => {
          displayHiddenCards(player.seatId, data.cards.length);
        });
        break;

      case "reveal":
        setupPlayerCards(actingSeatId, data.cards);
        break;

      case "dealer":
        toogleDealerOnPlayerBlock(actingSeatId);
        break;

      case "receive-card-from-friend":
        replaceCard(actingSeatId, data.value, data.suit);
        break;

      case 'move':
        placePieceOnSpot(actingSeatId, data.spotIndex);
        break;

      case "fold":
        foldAllCardsOfPlayer(actingSeatId);
        log(data);
        break;

      case "discard":
        animateCardToDiscardPile(actingSeatId, data.value, data.suit);
        removeCard(actingSeatId, data.value, data.suit);
        log(data);
        break;

      case "log":
        log(data);
        break;

      case 'forced-play':
        log(data);
        break;

      case "next-player":
        disableCardSelection();
        setCancelSelectionVisible(false);
        clearSpotSelection();
        displayActivePlayer(actingSeatId);
        log(data);
        break;

      case "play": {
        setCancelSelectionVisible(false);
        clearSpotSelection();

        
        const movedSeatId = getMessageSeatId(data, "moved") || actingSeatId;

        animateCardToDiscardPile(actingSeatId, data.value, data.suit);
        removeCard(actingSeatId, data.value, data.suit);

        if (data.value === "J") {
          switchPieces(movedSeatId, data.origin, data.target);
        } else {
          movePieceFromSpotToSpot(movedSeatId, data.origin, data.target);
        }

        log(data);
        break;
      }

      case "seven-start":
        setCancelSelectionVisible(false);
        animateCardToDiscardPile(actingSeatId, data.value, data.suit);
        removeCard(actingSeatId, data.value, data.suit);
        log(data);
        break;

      case "seven-step":
        movePieceFromSpotToSpot(getMessageSeatId(data, "moved") || actingSeatId, data.origin, data.target);
        break;

      case "query-seven-hop":
        disableCardSelection();
        selectLocalSeat(actingSeatId);
        activeRequestId = data.requestId;
        setCancelSelectionVisible(false);
        clearSpotSelection();
        query(data);
        requestSevenHop(data.origin, data.target);
        break;

      case "seven-hop":
        movePieceFromSpotToSpot(getMessageSeatId(data, "moved"), data.origin, data.target);
        break;

      case "path-kicks":
        data.positions.forEach((positionId) => {
          const position = document.getElementById(positionId);
          if (position) resetEmptyPosition(position);
        });
        break;

      case "query-origin":
        disableCardSelection();
        selectLocalSeat(actingSeatId);
        activeRequestId = data.requestId;
        setCancelSelectionVisible(Boolean(data.canCancel));
        query(data);
        requestSpotSelection(data.originOptions);
        break;

      case "query-target":
        disableCardSelection();
        selectLocalSeat(actingSeatId);
        activeRequestId = data.requestId;
        setCancelSelectionVisible(Boolean(data.canCancel));
        query(data);
        requestSpotSelection(data.targetOptions);
        break;

      case "query-card":
        selectLocalSeat(actingSeatId);
        activeRequestId = data.requestId;
        setCancelSelectionVisible(false);
        clearSpotSelection();
        query(data);
        showAllCardUp();
        requestCardSelection();
        break;

      case "query-card-exchange":
        selectLocalSeat(actingSeatId);
        activeRequestId = data.requestId;
        setCancelSelectionVisible(false);
        clearSpotSelection();
        query(data);
        showAllCardUp();
        requestCardExchangeSelection();
        break;

      case "query":
        if (data.requestId) activeRequestId = data.requestId;
        query(data);
        break;

      case "reject-card-selection":
        selectLocalSeat(actingSeatId);
        error(data);
        showAllCardUp();
        requestCardSelection();
        break;

      case "discard-pile-cleared":
        clearDiscardPile();
        break;

      case "game-over":
        disableCardSelection();
        setCancelSelectionVisible(false);
        clearSpotSelection();
        displayNoActivePlayers();
        setTranslatedText(currentPlayerName, "game.game_over");
        setRawText(turnInstruction, data.msg);
        log(data);
        break;

      case 'error':
        error(data);
        break;

      default:
        log(`Unknown message: ${event.data}`);
    }
  };
  
  ws.onclose = (event) => {
	setCancelSelectionVisible(false);
	clearSpotSelection();
	connectionStatus.classList.remove("connected");
	setTranslatedText(connectionStatusText, "connection.disconnected");
  createBtn.disabled = ruleConfiguration === null;

    switch (event.code) {
      case NO_GAME_FOUND_CODE:
        showError(tocI18n.t("errors.invalid_game_id"));
        break;
      case NO_PLAYER_CONTEXT_FOUND_CODE:
        showError(tocI18n.t("errors.player_name_taken"));
        break;
      case GAME_ALREADY_FULL_CODE:
        showError(tocI18n.t("errors.game_full"));
        break;
      case CONNECTION_IDENTIFICATION_ERROR_CODE:
        showError(tocI18n.t("errors.invalid_resume_token"));
        break;
      case SERVER_UNREACHABLE_CODE:
        showError(tocI18n.t("errors.server_unreachable"));
        break;
      case LOBBY_EXPIRED_CLOSE_CODE:
        returnToStartAfterServerClose("errors.lobby_expired", gameId, name, true);
        return;

      case GAME_SUSPENDED_CLOSE_CODE:
        returnToStartAfterServerClose("errors.game_suspended", gameId, name, false);
        return;
      default:
        showError(tocI18n.t("errors.connection_closed", {code: event.code}));
    }
  };

  ws.onerror = () => {
    showError(tocI18n.t("errors.websocket_error"));
  };
}

function formatPresetName(name) {
  const translationKey = `rules.presets.${name}`;
  const translatedName = tocI18n.t(translationKey);
  return translatedName === translationKey ? name.charAt(0).toUpperCase() + name.slice(1).replaceAll("_", " ") : translatedName;
}

function formatColorName(color) {
  const translationKey = `colors.${color}`;
  const translatedColor = tocI18n.t(translationKey);
  return translatedColor === translationKey ? color : translatedColor;
}

function formatRuleChoice(ruleName, value) {
  const valueKey = Array.isArray(value) ? value.join("_") : String(value);
  const translationKey = `rules.choices.${ruleName}.${valueKey}`;
  const translatedValue = tocI18n.t(translationKey);
  return translatedValue === translationKey ? String(value).replaceAll("_", " ") : translatedValue;
}

function createRuleTitle(ruleName, controlId = null) {
  const labelText = tocI18n.t(`rules.labels.${ruleName}`);
  const description = tocI18n.t(`rules.descriptions.${ruleName}`);

  const title = document.createElement("div");
  title.className = "rule-title";

  const label = document.createElement(controlId ? "label" : "span");
  label.textContent = labelText;
  if (controlId) label.htmlFor = controlId;
  title.appendChild(label);

  if (description !== `rules.descriptions.${ruleName}`) {
    const helpWrapper = document.createElement("span");
    helpWrapper.className = "rule-help-wrapper";

    const help = document.createElement("button");
    help.type = "button";
    help.className = "rule-help-trigger";
    help.textContent = "?";
    help.setAttribute("aria-label", `${labelText}: ${description}`);

    const tooltip = document.createElement("span");
    tooltip.className = "rule-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.textContent = description;

    helpWrapper.append(help, tooltip);
    title.appendChild(helpWrapper);
  }

  return title;
}

function synchronizeHouseEntryControls() {
  const trackControl = customRulesFields.querySelector('[data-rule-name="track_region_length"]');
  const entryControl = customRulesFields.querySelector('[data-rule-name="enter_house_at_spot"]');
  if (!trackControl || !entryControl) return;

  const regionLength = JSON.parse(trackControl.value);

  Array.from(entryControl.options).forEach(option => {
    option.disabled = JSON.parse(option.value) > regionLength;
  });

  if (JSON.parse(entryControl.value) > regionLength) entryControl.value = JSON.stringify(regionLength);
}

function applyRuleValues(values) {
  customRulesFields.querySelectorAll("[data-rule-name]").forEach(control => {
    const value = values[control.dataset.ruleName];

    if (control.type === "checkbox") {
      control.checked = value;
    } else {
      control.value = JSON.stringify(value);
    }
  });

  synchronizeHouseEntryControls();
}

function renderCustomRuleControls(schema, values) {
  customRulesFields.replaceChildren();

  Object.entries(RULE_GROUPS).forEach(([groupName, groupLabel]) => {
    const ruleNames = Object.keys(schema).filter(ruleName => RULE_UI[ruleName]?.group === groupName);
    if (ruleNames.length === 0) return;

    const group = document.createElement("section");
    group.className = "rule-group";

    const heading = document.createElement("h3");
    heading.textContent = tocI18n.t(groupLabel);
    group.appendChild(heading);

    ruleNames.forEach(ruleName => {
      const definition = schema[ruleName];
      const row = document.createElement("div");
      row.className = "rule-control";
      const controlId = `rule-control-${ruleName}`;
      row.appendChild(createRuleTitle(ruleName, controlId));

      let control;

      if (definition.type === "boolean") {
        control = document.createElement("input");
        control.type = "checkbox";
      } else {
        control = document.createElement("select");
        control.className = "rule-choice";

        definition.options.forEach(value => {
          const option = document.createElement("option");
          option.value = JSON.stringify(value);
          option.textContent = formatRuleChoice(ruleName, value);
          control.appendChild(option);
        });
      }

      control.id = controlId;
      control.dataset.ruleName = ruleName;
      row.appendChild(control);
      group.appendChild(row);
    });

    customRulesFields.appendChild(group);
  });

  const renderedRuleNames = new Set(Array.from(customRulesFields.querySelectorAll("[data-rule-name]"), control => control.dataset.ruleName));
  const missingRuleNames = Object.keys(schema).filter(ruleName => !renderedRuleNames.has(ruleName));

  if (missingRuleNames.length > 0) throw new Error(`Missing rule UI definitions: ${missingRuleNames.join(", ")}`);

  applyRuleValues(values);
  customRulesFields.querySelector('[data-rule-name="track_region_length"]').addEventListener("change", synchronizeHouseEntryControls);
}

function collectCustomRuleValues() {
  const values = {};

  customRulesFields.querySelectorAll("[data-rule-name]").forEach(control => {
    values[control.dataset.ruleName] = control.type === "checkbox" ? control.checked : JSON.parse(control.value);
  });

  return values;
}

function renderRulesetDisplay(panel, badge, list, ruleset) {
  if (!ruleset?.values) {
    panel.classList.add("hidden");
    return;
  }

  panel.classList.remove("hidden");
  badge.textContent = formatPresetName(ruleset.preset);
  list.replaceChildren();

  Object.entries(RULE_GROUPS).forEach(([groupName, groupLabel]) => {
    const ruleNames = Object.keys(ruleset.values).filter(ruleName => RULE_UI[ruleName]?.group === groupName);
    if (ruleNames.length === 0) return;

    const group = document.createElement("section");
    group.className = "rules-display-group";

    const heading = document.createElement("h3");
    heading.textContent = tocI18n.t(groupLabel);
    group.appendChild(heading);

    ruleNames.forEach(ruleName => {
      const value = ruleset.values[ruleName];
      const row = document.createElement("div");
      const displayedValue = document.createElement("span");

      row.className = "rules-display-row";
      displayedValue.className = `rules-display-value${typeof value === "boolean" ? value ? " enabled" : " disabled" : ""}`;
      displayedValue.textContent = typeof value === "boolean" ? value ? tocI18n.t("common.enabled") : tocI18n.t("common.disabled") : formatRuleChoice(ruleName, value);

      row.append(createRuleTitle(ruleName), displayedValue);
      group.appendChild(row);
    });

    list.appendChild(group);
  });
}

function renderRulesetDisplays(ruleset) {
  displayedRuleset = ruleset;
  renderRulesetDisplay(lobbyRulesPanel, lobbyRulesPreset, lobbyRulesList, ruleset);
  renderRulesetDisplay(gameRulesPanel, gameRulesPreset, gameRulesList, ruleset);
}

function updateRulesetEditorVisibility() {
  const isCustom = rulePresetSelect.value === "custom";
  customRulesEditor.classList.toggle("hidden", !isCustom);
  rulePresetSummary.textContent = isCustom ? tocI18n.t("rules.custom_summary") : tocI18n.t("rules.preset_summary", {preset: formatPresetName(rulePresetSelect.value)});
}

async function initializeRuleSelector() {
  try {
    const response = await fetch("/toc/api/rule-presets");
    if (!response.ok) throw new Error("Could not load rule presets.");

    ruleConfiguration = await response.json();
    
    const missingMessageKeys = tocI18n.getMissingTranslationKeys(ruleConfiguration.messageKeys || []);
    if (missingMessageKeys.length) {
      console.error(`Missing backend translations: ${missingMessageKeys.join(", ")}`);
    }
    
    const defaultValues = ruleConfiguration.presets[ruleConfiguration.default];

    rulePresetSelect.replaceChildren();

    Object.keys(ruleConfiguration.presets).forEach(presetName => {
      const option = document.createElement("option");
      option.value = presetName;
      option.textContent = formatPresetName(presetName);
      rulePresetSelect.appendChild(option);
    });

    const customOption = document.createElement("option");
    customOption.value = "custom";
    customOption.textContent = tocI18n.t("rules.custom_option");
    rulePresetSelect.appendChild(customOption);

    renderCustomRuleControls(ruleConfiguration.schema, defaultValues);
    rulePresetSelect.value = ruleConfiguration.default;
    rulePresetSelect.disabled = false;
    createBtn.disabled = false;
    updateRulesetEditorVisibility();
  } catch (err) {
    console.error(err);
    rulePresetSummary.textContent = tocI18n.t("rules.load_error");
    showError(tocI18n.t("errors.rules_load_failed"));
  }
}

initializeLanguageInterface();
showStoredStartNotice();

rulePresetSelect.addEventListener("change", updateRulesetEditorVisibility);
resetCustomRules.addEventListener("click", () => applyRuleValues(ruleConfiguration.presets[ruleConfiguration.default]));
initializeRuleSelector();

refreshLobbiesBtn.addEventListener("click", () => refreshOpenLobbies());

refreshOpenLobbies();

resumeGameBtn.addEventListener("click", async () => {
  if (!stored_player_name || !stored_game_id) return;

  await connectToGame(stored_game_id, stored_player_name, true);
});

window.setInterval(() => {
  if (!startScreen.classList.contains("hidden")) {
    refreshOpenLobbies(false);
  }
}, 15000);

createBtn.addEventListener("click", async () => {
  const name = nameInput.value.trim();
  if (!name) {
    showError(tocI18n.t("errors.name_required"));
    return;
  }

  clearError();
  createBtn.disabled = true;

  try {
    const payload = {preset: rulePresetSelect.value, creatorName: name};
    const selectedMode = gameModeSelect.selectedOptions[0];

    payload.mode = selectedMode.dataset.mode;

    if (selectedMode.dataset.layout) {
      payload.layout = selectedMode.dataset.layout;
    }

    if (rulePresetSelect.value === "custom") {
      payload.rules = collectCustomRuleValues();
    }

    const res = await fetch("/toc/api/create-game", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(getHttpErrorMessage(data));

    const gameId = data.game_id;
    log({
      messageKey: "connection.created_game",
      parameters: {gameId},
      fallback: `Created game ID: ${gameId}`,
    });
    await connectToGame(gameId, name);
  } catch (err) {
    showError(err.message || tocI18n.t("errors.game_creation_failed"));
    createBtn.disabled = false;
  }
});

if (cancelCardSelection) {
  cancelCardSelection.addEventListener("click", (event) => {
    event.stopPropagation();

    if (!ws || ws.readyState !== WebSocket.OPEN || !activeRequestId) return;

    const message = {"id": crypto.randomUUID(), "requestId": activeRequestId, "type": "cancel_move_selection"};
    ws.send(JSON.stringify(message));
    setCancelSelectionVisible(false);
    clearSpotSelection();
    setTranslatedText(turnInstruction, "game.returning_to_cards");
  });
}

sendBtn.addEventListener("click", () => {
  const commandInputContent = commandInput.value.trim();
  // simulation only, not for production
  if (commandInputContent) {
    switch (commandInputContent) {
      case 'simulate':
        simulate();
        break;
      case 'simulate2':
        message = {"id": crypto.randomUUID(), "type": "debug", "msg": "simulate_card_exchange_players3and4"};
        message_json = JSON.stringify(message);
        console.log('[commandInputContent click eventListener] Sending DEBUG command to back-end:' + message_json);
        ws.send(message_json);
        break;
      case 'force':
        message = {"id": crypto.randomUUID(), "type": "debug", "msg": "force-play"};
        message_json = JSON.stringify(message);
        console.log('[commandInputContent click eventListener] Sending DEBUG command to back-end:' + message_json);
        ws.send(message_json);
        break;
      default:
        if (commandInputContent && ws && ws.readyState === WebSocket.OPEN) {
          message = {"id": crypto.randomUUID(), "type": "text_input", "msg": commandInputContent};
          message_json = JSON.stringify(message);
          console.log('[commandInputContent click eventListener] Sending following content to back-end:' + message_json);
          ws.send(message_json);
          //log(`< ${message}`);
          commandInput.value = "";
        }
        break;
    }
  }
});

commandInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendBtn.click();
});

lobbyChoiceForm.addEventListener("submit", (event) => {
  event.preventDefault();

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    lobbyError.textContent = tocI18n.t("errors.connection_not_open");
    lobbyError.classList.remove("hidden");
    return;
  }

  lobbyError.classList.add("hidden");
  confirmLobbyChoice.disabled = true;
  lobbyStatus.textContent = tocI18n.t("lobby.confirming");

  const colors = Array.from(colorSelects.querySelectorAll("select"), select => select.value);

  const message = {
    "id": crypto.randomUUID(),
    "type": "configure-player",
    "team": teamSelect.value,
    "colors": colors,
  };

  ws.send(JSON.stringify(message));
});

function renderLobbyTeamOptions(state) {
  const previousTeam = teamSelect.value;
  teamSelect.replaceChildren();

  Object.keys(state.teamCounts).forEach(team => {
    const option = document.createElement("option");

    option.value = team;
    option.textContent = tocI18n.t(`lobby.team_${team}`);
    option.disabled = state.teamCounts[team] >= state.teamCapacity;
    teamSelect.appendChild(option);
  });

  const previousOption = Array.from(teamSelect.options).find(option => option.value === previousTeam && !option.disabled);
  const firstAvailableOption = Array.from(teamSelect.options).find(option => !option.disabled);

  if (previousOption) {
    teamSelect.value = previousOption.value;
  } else if (firstAvailableOption) {
    teamSelect.value = firstAvailableOption.value;
  }
}

function synchronizeLobbyColorOptions() {
  const selects = Array.from(colorSelects.querySelectorAll("select"));
  const selectedValues = selects.map(select => select.value);

  selects.forEach((select, selectIndex) => {
    Array.from(select.options).forEach(option => {
      option.disabled = selectedValues.some((value, valueIndex) => valueIndex !== selectIndex && value === option.value);
    });
  });
}

function renderLobbyColorOptions(state) {
  const colorCount = state.seatsPerParticipant;

  if (!Number.isInteger(colorCount) || colorCount < 1) {
    console.error("Invalid seats-per-participant value in lobby state.", state);
    return;
  }

  const previousValues = Array.from(colorSelects.querySelectorAll("select"), select => select.value);
  colorSelects.replaceChildren();

  for (let colorIndex = 0; colorIndex < colorCount; colorIndex++) {
    const field = document.createElement("label");
    const labelText = document.createElement("span");
    const select = document.createElement("select");

    field.className = "lobby-color-field";
    labelText.textContent = colorCount === 1 ? tocI18n.t("lobby.colour") : tocI18n.t("lobby.colour_number", {number: colorIndex + 1});
    select.className = "lobby-select";
    select.dataset.colorIndex = colorIndex;

    state.availableColors.forEach(color => {
      const option = document.createElement("option");
      option.value = color;
      option.textContent = formatColorName(color);
      select.appendChild(option);
    });

    const previousValue = previousValues[colorIndex];

    if (previousValue && state.availableColors.includes(previousValue)) {
      select.value = previousValue;
    } else if (state.availableColors[colorIndex]) {
      select.value = state.availableColors[colorIndex];
    }

    select.addEventListener("change", synchronizeLobbyColorOptions);
    field.append(labelText, select);
    colorSelects.appendChild(field);
  }

  synchronizeLobbyColorOptions();
}

function renderLobbyState(state) {
  currentLobbyState = state;
  lobbyGameId.textContent = state.gameId;
  lobbyPlayerCount.textContent = tocI18n.t("lobby.players_count", {count: state.players.length, capacity: state.participantCapacity});
  lobbyPlayers.replaceChildren();
  renderRulesetDisplays(state.ruleset);

  state.players.forEach((player) => {
    const row = document.createElement("div");
    const connection = document.createElement("span");
    const name = document.createElement("span");
    const choice = document.createElement("span");

    row.className = "lobby-player";
    connection.className = `lobby-connection${player.connected ? " connected" : ""}`;
    name.className = "lobby-player-name";
    choice.className = "lobby-player-choice";
    name.textContent = player.name === local_player_name ? tocI18n.t("game.player_you", {player: player.name}) : player.name;
    const colorNames = (player.colors || [player.color]).filter(Boolean).map(formatColorName).join(", ");
    choice.textContent = player.configured ? tocI18n.t("lobby.configured_choice", {team: player.team, color: colorNames}) : tocI18n.t("lobby.choosing");

    row.append(connection, name, choice);
    lobbyPlayers.appendChild(row);
  });

  const localPlayer = state.players.find((player) => player.name === local_player_name);

  if (state.started) {
    const seatsById = new Map();

    state.players.forEach(player => {
      player.seats.forEach(seat => {
        seatsById.set(seat.seatId, {
          seatId: seat.seatId,
          name: player.name,
          team: player.team,
          color: seat.color,
        });
      });
    });

    state.seatOrder.forEach((seatId, seatIndex) => {
      const seat = seatsById.get(seatId);
      if (seat) assignPlayer(seat.seatId, seat.name, seat.team, seat.color, seatIndex);
    });

    showGameUI();
    return;
  }

  showLobbyUI();

  if (!localPlayer || localPlayer.configured) {
    lobbyChoiceForm.classList.add("hidden");
    lobbyStatus.textContent = localPlayer ? tocI18n.t("lobby.confirmed_waiting") : tocI18n.t("lobby.joining");
    return;
  }

  lobbyChoiceForm.classList.remove("hidden");
  confirmLobbyChoice.disabled = false;
  lobbyError.classList.add("hidden");

  renderLobbyTeamOptions(state);
  renderLobbyColorOptions(state);

  confirmLobbyChoice.disabled = state.availableColors.length < state.seatsPerParticipant;
  lobbyStatus.textContent = state.players.length < state.participantCapacity ? tocI18n.t("lobby.choose_while_waiting") : tocI18n.t("lobby.choose_to_start");
}

function sendCardSelection(seatId, rank, suit) {
  const message = {
    "id": crypto.randomUUID(),
    "requestId": activeRequestId,
    "type": "card_selection",
    "name": local_player_name,
    "seatId": seatId,
    "value": rank,
    "suit": suit,
  };

  ws.send(JSON.stringify(message));
}

function sendSpotSelection(seatId, spot) {
  const message = {
    "id": crypto.randomUUID(),
    "requestId": activeRequestId,
    "type": "spot_selection",
    "name": local_player_name,
    "seatId": seatId,
    "result": spot,
  };

  ws.send(JSON.stringify(message));
}

function sendSevenHopChoice(result) {
  const message = {"id": crypto.randomUUID(), "requestId": activeRequestId, "type": "seven_hop_choice", "name": local_player_name, "result": result};
  console.log('[sendSevenHopChoice] Sending following content to back-end:' + JSON.stringify(message));
  ws.send(JSON.stringify(message));
}

function requestSevenHop(originSpot, targetSpot) {
  const shouldHop = window.confirm(tocI18n.t("prompts.seven_hop", {origin: originSpot, target: targetSpot}));
  sendSevenHopChoice(shouldHop);
}


////// User Interface handling //////
let totalRegions = 4;
let spotsPerRegion = 18;
let enterHouseAtSpot = 18;
let totalSpots = totalRegions * spotsPerRegion;

const radius = 250;
const centerX = 300;
const centerY = 300;

const houseLabels = ['T', 'O', 'C', '!'];
const spotsPerHouse = houseLabels.length;
const houseDistance = 40;

const spotElements = [];
const houseElements = [];

const seatLayouts = {
  2: [
    {position: 'bottom-right', regionIndex: 0},
    {position: 'top-left', regionIndex: 1},
  ],
  4: [
    {position: 'top-left', regionIndex: 2},
    {position: 'top-right', regionIndex: 3},
    {position: 'bottom-right', regionIndex: 0},
    {position: 'bottom-left', regionIndex: 1},
  ],
  6: [
    {position: 'bottom-right', regionIndex: 0},
    {position: 'bottom-center', regionIndex: 1},
    {position: 'bottom-left', regionIndex: 2},
    {position: 'top-left', regionIndex: 3},
    {position: 'top-center', regionIndex: 4},
    {position: 'top-right', regionIndex: 5},
  ],
};
const positionMap = {
  'top-left': {
    info_box: document.getElementById('player-info-top-left'),
    card_box: document.getElementById('card-box-top-left'),
  },
  'top-center': {
    info_box: document.getElementById('player-info-top-center'),
    card_box: document.getElementById('card-box-top-center'),
  },
  'top-right': {
    info_box: document.getElementById('player-info-top-right'),
    card_box: document.getElementById('card-box-top-right'),
  },
  'bottom-left': {
    info_box: document.getElementById('player-info-bottom-left'),
    card_box: document.getElementById('card-box-bottom-left'),
  },
  'bottom-center': {
    info_box: document.getElementById('player-info-bottom-center'),
    card_box: document.getElementById('card-box-bottom-center'),
  },
  'bottom-right': {
    info_box: document.getElementById('player-info-bottom-right'),
    card_box: document.getElementById('card-box-bottom-right'),
  },
};

const playerAssignments = []; // { seatId, name, team, color, position }
const usedColors = [];
const usedPositions = [];
let selectedCard = null;
const pendingExchangeCards = new Map();

const PLAYER_ACCENT_RGB = {
  red: "220, 38, 38",
  green: "22, 163, 74",
  blue: "37, 99, 235",
  yellow: "234, 179, 8",
  orange: "234, 88, 12",
  purple: "147, 51, 234",
  pink: "219, 39, 119",
  cyan: "8, 145, 178",
  lime: "101, 163, 13",
  brown: "146, 64, 14",
  black: "100, 116, 139",
  white: "226, 232, 240",
};

let cardAnimationId = 0;

// Click anywhere outside of cards to cancel card selection
document.addEventListener('click', () => {
  if (selectedCard) {
    selectedCard.classList.remove('selected');
    selectedCard = null;
  }
});


function configureBoardGeometry(regionCount, regionLength, houseEntryPosition) {
  if (!Number.isInteger(regionCount) || regionCount < 2) return;
  if (!Number.isInteger(regionLength) || regionLength <= 0) return;
  if (!Number.isInteger(houseEntryPosition) || houseEntryPosition < 1 || houseEntryPosition > regionLength) return;

  if (regionCount === totalRegions && regionLength === spotsPerRegion && houseEntryPosition === enterHouseAtSpot) {
    return;
  }

  if (spotElements.length > 0) {
    console.error("Cannot change board geometry after the board has been drawn.", {
      currentRegionCount: totalRegions,
      requestedRegionCount: regionCount,
      currentRegionLength: spotsPerRegion,
      requestedRegionLength: regionLength,
      currentHouseEntry: enterHouseAtSpot,
      requestedHouseEntry: houseEntryPosition,
    });
    return;
  }

  totalRegions = regionCount;
  spotsPerRegion = regionLength;
  totalSpots = totalRegions * spotsPerRegion;
  enterHouseAtSpot = houseEntryPosition;
}

//// Board and pieces drawing and update functions ////
function drawRegion(color, regionIndex) {
  const angleOffset = (regionIndex / totalRegions) * 2 * Math.PI;

  const regionSpots = [];

  for (let spotIndex = 0; spotIndex < spotsPerRegion; spotIndex++) {
    const angle = angleOffset + (spotIndex / totalSpots) * 2 * Math.PI;
    const x = centerX + radius * Math.cos(angle) - 15;
    const y = centerY + radius * Math.sin(angle) - 15;

    const spot = document.createElement('div');
    spot.className = `spot ${color}`;
    spot.style.left = `${x}px`;
    spot.style.top = `${y}px`;
    spot.innerText = spotIndex === 0 ? '' : spotIndex;
    spot.id = `spot-${color}-${spotIndex}`;
    spot.color = color;
    spot.index = String(spotIndex);

    if (spotIndex === 0) {
      spot.classList.add('out-spot');

      const houseEntryOffset = enterHouseAtSpot - spotsPerRegion;
      const houseAngle = angleOffset + (houseEntryOffset / totalSpots) * 2 * Math.PI;

      for (let houseIndex = 0; houseIndex < spotsPerHouse; houseIndex++) {
        const innerRadius = radius - houseDistance * (houseIndex + 1);
        const houseX = centerX + innerRadius * Math.cos(houseAngle) - 15;
        const houseY = centerY + innerRadius * Math.sin(houseAngle) - 15;

        const houseSpot = document.createElement('div');
        houseSpot.className = `spot house ${color}`;
        houseSpot.style.left = `${houseX}px`;
        houseSpot.style.top = `${houseY}px`;
        houseSpot.innerText = houseLabels[houseIndex];
        houseSpot.id = `house-${color}-${houseIndex}`;

        board.appendChild(houseSpot);
        houseElements.push(houseSpot);
      }
    }

    board.appendChild(spot);
    regionSpots.push(spot);
  }

  spotElements.push(...regionSpots);
}

function placePieceOnSpot(playerId, targetSpot) {
  movePieceFromSpotToSpot(playerId, targetSpot, targetSpot);
}

function resetEmptyPosition(position) {
  if (position.classList.contains("house")) {
    const houseNumber = Number(position.id.split("-").at(-1));
    position.textContent = houseLabels[houseNumber];
    return;
  }

  position.textContent = Number(position.index) % spotsPerRegion === 0 ? "" : position.index;
}

function movePieceFromSpotToSpot(playerId, originSpot, targetSpot) {
  const playerClass = getPlayerClass(playerId);

  if (originSpot !== targetSpot) {
    // This is the case when the move played is anything other than an "OUT" move, in which case we have to remove a piece from a previous spot before adding it to the new spot
    const origin_spot =  document.getElementById(originSpot);
    const old = origin_spot.querySelector(`[data-player="${playerId}"]`);
    if (old && old.parentElement) { // this test is almost certainly unnecessary, but just in case, ...we don't want to go change the content of other spots on the board
      resetEmptyPosition(origin_spot); // reseting the value inside the spot
    }
  }

  const target_spot = document.getElementById(targetSpot);
  const piece = document.createElement('div');
  piece.classList.add('piece', playerClass);
  piece.dataset.player = playerId;
  
  target_spot.innerHTML = '';
  target_spot.appendChild(piece);
}

function switchPieces(playerId, originSpot, targetSpot) {
  const target_spot = document.getElementById(targetSpot);
  const targetPlayerId = target_spot.querySelector('.piece').dataset.player;

  movePieceFromSpotToSpot(playerId, originSpot, targetSpot);
  movePieceFromSpotToSpot(targetPlayerId, targetSpot, originSpot);
}

function removeGlowOnEverySpot() {
  document.querySelectorAll('.glow').forEach((spot) => {
    spot.classList.remove('glow');
  });
}

function clearSpotSelection() {
  selectableSpotHandlers.forEach((handler, position) => position.removeEventListener("click", handler));
  selectableSpotHandlers.clear();
  removeGlowOnEverySpot();
}


//// Player-sits-down-at-the-table function //// 
function assignPlayer(seatId, name, team, color, seatIndex = playerAssignments.length) {
  const existingPlayer = playerAssignments.find(player => player.seatId === seatId);
  if (existingPlayer) return existingPlayer;

  const seatLayout = seatLayouts[totalRegions]?.[seatIndex];

  if (!seatLayout) {
    console.error(`No ${totalRegions}-seat board position is available for seat "${seatId}".`);
    return null;
  }

  const {position, regionIndex} = seatLayout;
  const newPlayer = {seatId, name, team, color, position, regionIndex, handCardBox: null};

  playerAssignments.push(newPlayer);
  usedColors.push(color);
  usedPositions.push(position);

  updatePlayerBlock(newPlayer);
  positionMap[position].info_box.style.display = 'flex';
  drawRegion(color, regionIndex);

  const playerColorRgb = PLAYER_ACCENT_RGB[color] || "100, 116, 139";

  positionMap[position].info_box.style.setProperty("--player-color-rgb", playerColorRgb);
  positionMap[position].card_box.style.setProperty("--player-color-rgb", playerColorRgb);

  if (name === local_player_name) {
    const infoBox = positionMap[position].info_box;
    const handCardBox = document.createElement("div");

    infoBox.classList.add("local-player");

    handCardBox.className = "card-box local-hand";
    handCardBox.dataset.seatId = seatId;
    handCardBox.dataset.colorLabel = formatColorName(color);
    handCardBox.style.setProperty("--hand-color-rgb", PLAYER_ACCENT_RGB[color] || "100, 116, 139");

    newPlayer.handCardBox = handCardBox;
    localHandSlot.appendChild(handCardBox);

    const localHandCount = playerAssignments.filter(player => isLocalSeat(player.seatId)).length;
    localHandSlot.classList.toggle("multiple-hands", localHandCount > 1);

    if (!local_player) selectLocalSeat(seatId);
  }
}


//// Helper functions ////
function getMessageSeatId(message, prefix = "") {
  const seatField = prefix ? `${prefix}SeatId` : "seatId";
  const legacyField = prefix ? `${prefix}PlayerId` : "playerId";
  return message[seatField] || message[legacyField];
}

function getPlayerFromId(seatId) {
  const player = playerAssignments.find(player => player.seatId === seatId);

  if (!player) {
    console.warn(`[getPlayerFromId] No seat found with ID "${seatId}"`, JSON.stringify(playerAssignments));
    return null;
  }

  return player;
}

function isLocalSeat(seatId) {
  return getPlayerFromId(seatId)?.name === local_player_name;
}

function selectLocalSeat(seatId) {
  const player = getPlayerFromId(seatId);

  if (!player || player.name !== local_player_name) return false;

  local_player = player;
  local_card_box = player.handCardBox || positionMap[player.position].card_box;
  local_info_box = positionMap[player.position].info_box;
  return true;
}

function getBoardCardBoxFromId(seatId) {
  const player = getPlayerFromId(seatId);
  return player ? positionMap[player.position].card_box : null;
}

function getCardBoxFromId(seatId) {
  const player = getPlayerFromId(seatId);
  if (!player) return null;

  return player.handCardBox || positionMap[player.position].card_box;
}

function getOppositePosition(pos) {
  const opposites = {
    'top-left': 'bottom-right',
    'top-right': 'bottom-left',
    'bottom-left': 'top-right',
    'bottom-right': 'top-left'
  };
  return opposites[pos];
}

function getAdjacentFreePosition(pos) {
  const adjacency = {
    'top-left':    ['top-right', 'bottom-left'],
    'top-right':   ['top-left', 'bottom-right'],
    'bottom-left': ['top-left', 'bottom-right'],
    'bottom-right':['top-right', 'bottom-left']
  };
  const candidates = adjacency[pos];
  return candidates.find(p => !usedPositions.includes(p));
}

function getPlayerClass(seatId) {
  const player = getPlayerFromId(seatId);
  return player ? `player-${player.color}` : '';
}


//// Simple UI update functions ////
function hideCardBlock(seatId) {
  const cardBox = getCardBoxFromId(seatId);
  const boardCardBox = getBoardCardBoxFromId(seatId);
  const boxes = new Set([cardBox, boardCardBox]);

  boxes.forEach(block => {
    if (!block) return;

    block.replaceChildren();
    block.dataset.cardCount = "0";
    block.style.display = "none";
  });

  if (isLocalSeat(seatId)) {
    setTranslatedText(emptyHandMessage, "game.waiting_for_next_deal");
    emptyHandMessage.classList.remove("hidden");
  }
}

function updatePlayerBlock(player, isDealer = false) {
  const block = positionMap[player.position].info_box;
  const identity = document.createElement("div");
  const name = document.createElement("span");
  const team = document.createElement("span");

  block.style.setProperty("--player-color-rgb", PLAYER_ACCENT_RGB[player.color] || "100, 116, 139");

  identity.className = "player-identity";
  name.className = "player-name";
  team.className = "player-team";
  name.textContent = player.name;
  setTranslatedText(team, `lobby.team_${player.team}`);
  identity.append(name, team);
  block.replaceChildren(identity);

  if (isDealer) {
    const dealerBadge = document.createElement("span");
    dealerBadge.className = "dealer-badge";
    dealerBadge.dataset.i18nTitle = "game.dealer";
    dealerBadge.title = tocI18n.t("game.dealer");
    dealerBadge.setAttribute("aria-label", tocI18n.t("game.dealer"));
    block.appendChild(dealerBadge);
  }

  const playerClass = getPlayerClass(player.seatId);
  if (block.dataset.playerColorClass) block.classList.remove(block.dataset.playerColorClass);
  block.classList.add(playerClass);
  block.dataset.playerColorClass = playerClass;
}


function toogleDealerOnPlayerBlock(seatId) {
  const dealer = getPlayerFromId(seatId);
  dealerName.textContent = dealer?.name || seatId;

  playerAssignments.forEach(player => {
    updatePlayerBlock(player, player.seatId === seatId);
  });
}

function displayActivePlayer(seatId) {
  if (!seatId) {
    setTranslatedText(currentPlayerName, "game.waiting_to_start");
    setTranslatedText(turnInstruction, "game.next_action");
    return;
  }

  const player = getPlayerFromId(seatId);
  if (!player) return;

  const localSeat = player.name === local_player_name;

  if (localSeat) {
    setTranslatedText(currentPlayerName, "game.player_you", {player: player.name});
    setTranslatedText(turnInstruction, "game.your_turn");
    selectLocalSeat(seatId);
  } else {
    setRawText(currentPlayerName, player.name);
    setTranslatedText(turnInstruction, "game.waiting_for_player", {player: player.name});
  }

  turnInstruction.classList.remove("error-state");
  turnBanner.classList.toggle("your-turn", localSeat);

  playerAssignments.forEach(assignedPlayer => {
    const isActive = assignedPlayer.seatId === seatId;
    const infoBox = positionMap[assignedPlayer.position].info_box;
    const boardCardBox = positionMap[assignedPlayer.position].card_box;

    infoBox.classList.toggle("active", isActive);
    boardCardBox.classList.toggle("active", isActive);
  });
}

function displayNoActivePlayers() {
	setTranslatedText(currentPlayerName, "game.no_active_player");
	turnBanner.classList.remove("your-turn");

  playerAssignments.forEach(player => {
    positionMap[player.position].info_box.classList.remove("active");
    positionMap[player.position].card_box.classList.remove("active");
  });
}


//// Card UI update functions ////
function setupPlayerCards(playerId, cards) {
  const cardBox = getCardBoxFromId(playerId)
  cardBox.querySelectorAll('.card-container').forEach((cardContainer, i) => {

    const cardBlock = cardContainer.querySelector('.card');

    const rank = cards[i].value
    const suit = cards[i].suit

    cardBlock.appendChild(createCardFront(rank, suit));

    cardContainer.rank = rank;
    cardContainer.suit = suit;
    cardContainer.playerId = playerId;

    setTimeout(() => {
      cardContainer.classList.add('flip');
    }, 250 * i);
  });
}

function createCardFront(rank, suit) {
  const cardFront = document.createElement("div");
  cardFront.className = "card-front";

  if (rank === "JOKER") {
    cardFront.classList.add("joker-card", `joker-card-${suit}`);

    const topCorner = document.createElement("span");
    const symbol = document.createElement("span");
    const label = document.createElement("span");
    const bottomCorner = document.createElement("span");

    topCorner.className = "joker-corner joker-corner-top";
    symbol.className = "joker-symbol";
    label.className = "joker-label";
    bottomCorner.className = "joker-corner joker-corner-bottom";

    topCorner.textContent = "J";
    symbol.textContent = "★";
    label.textContent = "JOKER";
    bottomCorner.textContent = "J";

    cardFront.append(topCorner, symbol, label, bottomCorner);
    return cardFront;
  }

  const valueElement = document.createElement("div");
  const suitElement = document.createElement("div");

  valueElement.className = "card-value";
  suitElement.className = "card-suit";
  valueElement.textContent = rank;
  suitElement.textContent = suit;

  cardFront.append(valueElement, suitElement);
  return cardFront;
}

function createVisibleCardContainer(rank, suit) {
  const cardContainer = document.createElement("div");
  const card = document.createElement("div");

  cardContainer.className = "card-container flip";
  card.className = "card";

  card.appendChild(createCardFront(rank, suit));
  cardContainer.appendChild(card);

  return cardContainer;
}

function clearDiscardPile() {
  cardAnimationId++;
  discardPileCard.replaceChildren();
  delete discardPileCard.dataset.rank;
  delete discardPileCard.dataset.suit;
}

function showCardOnDiscardPile(rank, suit) {
  cardAnimationId++;

  discardPileCard.replaceChildren(createVisibleCardContainer(rank, suit));
  discardPileCard.dataset.rank = rank;
  discardPileCard.dataset.suit = suit;
}

function animateCardToDiscardPile(seatId, rank, suit) {
  const boardCardBox = getBoardCardBoxFromId(seatId);
  const regularCardBox = getCardBoxFromId(seatId);
  const sourceCard = boardCardBox?.querySelector(".card-container") || regularCardBox?.querySelector(".card-container");
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (!sourceCard || !discardPileCard || prefersReducedMotion || typeof sourceCard.animate !== "function") {
    showCardOnDiscardPile(rank, suit);
    return;
  }

  const sourceBounds = sourceCard.getBoundingClientRect();
  const targetBounds = discardPileCard.getBoundingClientRect();

  if (sourceBounds.width === 0 || sourceBounds.height === 0 || targetBounds.width === 0 || targetBounds.height === 0) {
    showCardOnDiscardPile(rank, suit);
    return;
  }

  const expandedLeft = sourceBounds.left + sourceBounds.width / 2 - targetBounds.width / 2;
  const expandedTop = sourceBounds.top + sourceBounds.height / 2 - targetBounds.height / 2;
  const animationId = ++cardAnimationId;
  const flyingCard = createVisibleCardContainer(rank, suit);

  flyingCard.classList.add("played-card-animation");
  flyingCard.style.left = `${sourceBounds.left}px`;
  flyingCard.style.top = `${sourceBounds.top}px`;
  flyingCard.style.width = `${sourceBounds.width}px`;
  flyingCard.style.height = `${sourceBounds.height}px`;

  document.body.appendChild(flyingCard);
  setCardPlayEmphasis(seatId, true);

  const animation = flyingCard.animate([
    {
      left: `${sourceBounds.left}px`,
      top: `${sourceBounds.top}px`,
      width: `${sourceBounds.width}px`,
      height: `${sourceBounds.height}px`,
      opacity: 0,
      transform: "rotate(-10deg) scale(0.8)",
    },
    {
      offset: 0.16,
      left: `${expandedLeft}px`,
      top: `${expandedTop}px`,
      width: `${targetBounds.width}px`,
      height: `${targetBounds.height}px`,
      opacity: 1,
      transform: "rotate(-7deg) scale(1.08)",
    },
    {
      offset: 0.36,
      left: `${expandedLeft}px`,
      top: `${expandedTop}px`,
      width: `${targetBounds.width}px`,
      height: `${targetBounds.height}px`,
      opacity: 1,
      transform: "rotate(-7deg) scale(1.08)",
    },
    {
      left: `${targetBounds.left}px`,
      top: `${targetBounds.top}px`,
      width: `${targetBounds.width}px`,
      height: `${targetBounds.height}px`,
      opacity: 1,
      transform: "rotate(0deg) scale(1)",
    },
  ], {
    duration: 900,
    easing: "cubic-bezier(0.22, 1, 0.36, 1)",
    fill: "forwards",
  });

  animation.finished.catch(() => {}).finally(() => {
    flyingCard.remove();
    setCardPlayEmphasis(seatId, false);

    if (animationId === cardAnimationId) {
      showCardOnDiscardPile(rank, suit);
    }
  });
}

function renderHiddenCards(block, numberOfCards) {
  if (!block || block.dataset.cardCount === String(numberOfCards)) return;

  block.replaceChildren();
  block.dataset.cardCount = String(numberOfCards);
  block.style.display = numberOfCards > 0 ? "flex" : "none";

  for (let cardIndex = 0; cardIndex < numberOfCards; cardIndex++) {
    const cardContainer = document.createElement("div");
    const card = document.createElement("div");
    const cardBack = document.createElement("div");
    const backImg = document.createElement("img");

    cardContainer.className = "card-container";
    card.className = "card";
    cardBack.className = "card-back";
    backImg.src = "assets/card.jpg";

    cardBack.appendChild(backImg);
    card.appendChild(cardBack);
    cardContainer.appendChild(card);
    block.appendChild(cardContainer);
  }
}

function displayHiddenCards(seatId, numberOfCards) {
  const cardBox = getCardBoxFromId(seatId);
  const boardCardBox = getBoardCardBoxFromId(seatId);

  renderHiddenCards(cardBox, numberOfCards);

  if (boardCardBox !== cardBox) {
    renderHiddenCards(boardCardBox, numberOfCards);
  }

  if (isLocalSeat(seatId) && numberOfCards > 0) {
    emptyHandMessage.classList.add("hidden");
  }
}

function showAllCardUp() {
  if (!local_card_box) return;

  local_card_box.querySelectorAll(".card-container").forEach(cardContainer => {
    cardContainer.classList.add('flip');
  });
}

function foldAllCardsOfPlayer(playerId) {
  const block = getCardBoxFromId(playerId);
  block.querySelectorAll(".card-container").forEach((cardContainer, i) => {
    setTimeout(100);
    requestAnimationFrame(() => {
      cardContainer.classList.remove('flip');
    });
    block.removeChild(cardContainer);
    cardContainer.removeEventListener('click', clickCardClickListener);
    block.style.display = 'none';
  });

  if (isLocalSeat(playerId)) {
    setTranslatedText(emptyHandMessage, "game.waiting_for_next_deal");
    emptyHandMessage.classList.remove("hidden");
  }

  block.dataset.cardCount = "0";

  const boardCardBox = getBoardCardBoxFromId(playerId);

  if (boardCardBox && boardCardBox !== block) {
    boardCardBox.replaceChildren();
    boardCardBox.dataset.cardCount = "0";
    boardCardBox.style.display = "none";
  }
}

function replaceCard(seatId, rank, suit) {
  const cardContainer = pendingExchangeCards.get(seatId);
  pendingExchangeCards.delete(seatId);

  if (!cardContainer) {
    console.warn(`No pending exchanged card was found for seat "${seatId}".`);
    return;
  }

  const previousCardFront = cardContainer.querySelector(".card-front");
  const cardBlock = cardContainer.querySelector(".card");

  previousCardFront?.remove();
  cardBlock.appendChild(createCardFront(rank, suit));

  cardContainer.rank = rank;
  cardContainer.suit = suit;

  requestAnimationFrame(() => {
    cardContainer.classList.add('flip');
  });
}

function removeCard(seatId, value, suit) {
  const block = getCardBoxFromId(seatId);
  if (!block) return;

  let cardToRemove = null;

  if (isLocalSeat(seatId)) {
    cardToRemove = Array.from(block.children).find(cardContainer => cardContainer.suit === suit && cardContainer.rank === value);
  } else {
    cardToRemove = block.firstElementChild;
  }

  if (!cardToRemove) {
    console.warn(`Could not find card ${value}${suit} for seat "${seatId}".`);
    return;
  }

  cardToRemove.remove();
  block.dataset.cardCount = String(block.children.length);

  const boardCardBox = getBoardCardBoxFromId(seatId);

  if (boardCardBox && boardCardBox !== block) {
    boardCardBox.firstElementChild?.remove();
    boardCardBox.dataset.cardCount = String(boardCardBox.children.length);

    if (boardCardBox.children.length === 0) {
      boardCardBox.style.display = "none";
    }
  }
}


//// Listeners and interaction functions ////
function switchCardClickListener(event) {
  const rank = event.currentTarget.rank;
  const suit = event.currentTarget.suit;
  const playerId = event.currentTarget.playerId;
  const cardContainer = event.currentTarget;

  event.stopPropagation(); // Prevent document click from firing
  if (selectedCard === event.currentTarget) {
    // Second click confirms selection
    cardContainer.classList.remove('selected');
    cardContainer.classList.remove('flip');
    pendingExchangeCards.set(playerId, cardContainer);
    selectedCard = null;
    disableCardSelection();
    // only triggering the WS call to replace the card after twice the amount of time it takes for the front-to-back flip animation to execute, to make sure we do play the animation
    setTimeout(() => {
      sendCardSelection(playerId, rank, suit);
    }, 500);

  } else {
    // First click triggers highlight
    if (selectedCard) selectedCard.classList.remove('selected');
    selectedCard = cardContainer;
    cardContainer.classList.add('selected');
  }
}

function clickCardClickListener(event) {
  // This triggers when any block within the card is clicked, so the event.currentTarget can be the card-suit, card-value or card-front containers.
  // It is fine, we are just going to go up one container if we're hitting on the card-suit or card-value
  event.stopPropagation(); // Prevent document click from firing

  switch (event.currentTarget.classList[0]) {

  case 'card-value':
  case 'card-suit':
    var cardContainer = event.currentTarget.parentElement.parentElement.parentElement;
    break;
  
  case 'card-front':
    var cardContainer = event.currentTarget.parentElement.parentElement;
    break;

  case 'card':
    var cardContainer = event.currentTarget.parentElement;
    break;

  case 'card-container':
  case 'flip':
  case 'selected':
    var cardContainer = event.currentTarget
    break;
  }

  const t_suit = cardContainer.suit;
  const t_value = cardContainer.rank;

  if (selectedCard === cardContainer) {
    // Second click confirms selection
    const seatId = local_player.seatId;

    cardContainer.classList.remove('selected');
    cardContainer.classList.remove('flip');
    selectedCard = null;
    disableCardSelection();
    sendCardSelection(seatId, t_value, t_suit);
  } else {
    // First click triggers highlight
    if (selectedCard) selectedCard.classList.remove("selected");
    selectedCard = cardContainer;
    cardContainer.classList.add('selected');
  }
}

function requestSpotSelection(spotOptions) {
  clearSpotSelection();

  console.debug("[requestSpotSelection] Highlighting positions", {
    seatId: local_player?.seatId,
    color: local_player?.color,
    spotOptions,
  });

  spotOptions.forEach(option => {
    const position = document.getElementById(option);

    if (!position) {
      console.error(`[requestSpotSelection] Board position "${option}" does not exist in the DOM.`);
      return;
    }

    const handler = event => {
      event.stopPropagation();

      const selectedPositionId = event.currentTarget.id;

      clearSpotSelection();
      sendSpotSelection(local_player.seatId, selectedPositionId);
    };

    position.classList.add("glow");
    position.addEventListener("click", handler);
    selectableSpotHandlers.set(position, handler);
  });
}

function disableCardSelection() {
  localHandSlot.querySelectorAll(".card-box.local-hand").forEach(cardBox => {
    cardBox.classList.remove("awaiting-selection");

    cardBox.querySelectorAll(".card-container").forEach(cardContainer => {
      cardContainer.classList.remove("hover-effect", "selected");
      cardContainer.removeEventListener("click", clickCardClickListener);
      cardContainer.removeEventListener("click", switchCardClickListener);
    });
  });

  selectedCard = null;
}

function enableCardSelection(listener) {
  disableCardSelection();

  if (!local_card_box) return;

  local_card_box.classList.add("awaiting-selection");

  local_card_box.querySelectorAll(".card-container").forEach(cardContainer => {
    cardContainer.classList.add("hover-effect");
    cardContainer.addEventListener("click", listener);
  });
}

function requestCardSelection() {
  enableCardSelection(clickCardClickListener);
}

function requestCardExchangeSelection() {
  enableCardSelection(switchCardClickListener);
}


////// Simulation/debug methods: to be removed in Prod //////
function simulate(gameId = local_game_Id) {

  // player 3
  const wsUrl3 = buildWebSocketUrl(gameId, "p3");
  try {
    ws3 = new WebSocket(wsUrl3);
  } catch (err) {
    showError("Failed to construct WebSocket URL for player 3.");
  }

  ws3.onopen = () => {
    log(`Simulated p3 joined game ${gameId}.`);
    ws3.send(JSON.stringify({"id":"b7874d18-b2d3-47c3-92b6-a621aa4f1471","type":"text_input","msg":"green"}));
  };
    
  // player4
  const wsUrl4 = buildWebSocketUrl(gameId, "p4");
  try {
    ws4 = new WebSocket(wsUrl4);
  } catch (err) {
    showError("Failed to construct WebSocket URL for player 4.");
  }

  ws4.onopen = () => {
    log(`Simulated p4 joined game ${gameId}.`);
  };
}

function setCardPlayEmphasis(seatId, enabled) {
  const player = getPlayerFromId(seatId);
  if (!player) return;

  const playerPosition = positionMap[player.position];

  playerPosition.info_box.classList.toggle("playing-card", enabled);
  playerPosition.card_box.classList.toggle("playing-card", enabled);
}
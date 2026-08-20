const nameInput = document.getElementById("name-input");
const gameIdInput = document.getElementById("game-id-input");
const createBtn = document.getElementById("create-btn");
const joinBtn = document.getElementById("join-btn");
const sendBtn = document.getElementById("send-btn");
const commandInput = document.getElementById("command-input");
const terminal = document.getElementById("terminal");
const startScreen = document.getElementById("start-screen");
const lobbyScreen = document.getElementById("lobby-screen");
const gameScreen = document.getElementById("game-screen");
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
const colorSelect = document.getElementById("color-select");
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


const selectableSpotHandlers = new Map();

let ws = null;
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
gameIdInput.value = stored_game_id !== null ? stored_game_id : '';
joinBtn.disabled = (stored_player_name && stored_game_id) !== null ? false : true;

const tocI18n = window.tocI18n;
const languageSelect = document.getElementById("language-select");

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

  if (displayedRuleset) renderRulesetDisplays(displayedRuleset);

  if (currentLobbyState && !lobbyScreen.classList.contains("hidden")) renderLobbyState(currentLobbyState);

    backendMessageElements.forEach((message, element) => {
    element.textContent = getMessage(message);
  });

  renderActivityLog();
}

function initializeLanguageInterface() {
  console.log("initializeLanguageInterface was executed");
  tocI18n.supportedLanguages.forEach(language => {
    const option = document.createElement("option");
    option.value = language;
    languageSelect.appendChild(option);
  });

  languageSelect.value = tocI18n.getLanguage();
  refreshLanguageInterface();

  languageSelect.addEventListener("change", () => tocI18n.setLanguage(languageSelect.value));
  window.addEventListener("toc-language-change", refreshLanguageInterface);
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
  const wsUrl = buildWebSocketUrl(gameId, name);
  try {
    ws = new WebSocket(wsUrl);
  } catch (err) {
    console.error(err);
    createBtn.disabled = ruleConfiguration === null;
    showError(tocI18n.t("errors.websocket_error"));
    return;
  }

  window.localStorage.setItem("session_player_name", name);
  window.localStorage.setItem("session_game_ID", gameId);

  ws.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      // Fallback for plaintext messages
      log(`> ${event.data}`);
      return;
    }
    console.log('[ws.oneMessage top handler] Received the following message from back-end:' + JSON.stringify(data))

    switch (data.type) {
      case 'ready':
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
        configureBoardGeometry(data.trackRegionLength, data.enterHouseAtSpot);
        renderLobbyState(data);
        break;

      case 'lobby-error':
        setMessageText(lobbyError, data);
        lobbyError.classList.remove("hidden");
        confirmLobbyChoice.disabled = false;
        break;
      
      case 'assign-player':
        assignPlayer(data.name, data.team, data.color);
        break;

      case "full-ui-state":
        configureBoardGeometry(data.trackRegionLength, data.enterHouseAtSpot);
        renderRulesetDisplays(data.ruleset);

        data.players.forEach(p => {
          assignPlayer(p.name, p.team, p.color);
          if (p.number_of_cards == 0) {
            hideCardBlock(p.name); 
          } else {
            displayHiddenCards(p.name, p.number_of_cards);
          }
        });
        data.pieces.forEach(piece => {
          placePieceOnSpot(piece.playerId, piece.spotIndex);
        })
        displayActivePlayer(data.active_player);
        break;

      case "draw":
        // When we receive the draw order, we only display the (hidden) cards of the players unless they are already displayed
        playerAssignments.forEach(p => {
          displayHiddenCards(p.name, data.cards.length);
        });
        break;

      case "reveal":
        // When we receive the reveal order, the card of the player whose UI this is are revealed (to him only)
        setTimeout(() => {
          setupPlayerCards(data.playerId, data.cards);
        }, 1500);
        break;

      case "dealer":
        toogleDealerOnPlayerBlock(data.playerId);
        setRawText(dealerName, data.playerId);
        break;

      case "receive-card-from-friend":
        replaceCard(data.value, data.suit);
        break

      case 'move':
        placePieceOnSpot(data.playerId, data.spotIndex);
        break;

      case "fold":
        foldAllCardsOfPlayer(data.playerId);
        log(data);
        break;

      case 'discard':
        removeCard(data.playerId, data.value, data.suit);
        log(data);
        break;

      case "log":
        log(data);
        break;

      case 'forced-play':
        log(data);
        break;

      case 'next-player':
        setCancelSelectionVisible(false);
        clearSpotSelection();
        displayActivePlayer(data.playerId);
        log(data);
        break;

      case "play":
        setCancelSelectionVisible(false);
        clearSpotSelection();
        removeCard(data.playerId, data.value, data.suit);

        if (data.value === "J") {
          switchPieces(data.movedPlayerId || data.playerId, data.origin, data.target);
        } else {
          const movedPlayerId = data.movedPlayerId || data.playerId;
          movePieceFromSpotToSpot(movedPlayerId, data.origin, data.target);
        }

        log(data);
        break;

      case "seven-start":
        setCancelSelectionVisible(false);
        removeCard(data.playerId, data.value, data.suit);
        log(data);
        break;

      case "seven-step":
        movePieceFromSpotToSpot(data.movedPlayerId || data.playerId, data.origin, data.target);
        break;

      case "query-seven-hop":
        activeRequestId = data.requestId;
        setCancelSelectionVisible(false);
        clearSpotSelection();
        query(data);
        requestSevenHop(data.origin, data.target);
        break;

      case "seven-hop":
        movePieceFromSpotToSpot(data.movedPlayerId, data.origin, data.target);
        break;

      case "path-kicks":
        data.positions.forEach((positionId) => {
          const position = document.getElementById(positionId);
          if (position) resetEmptyPosition(position);
        });
        break;

      case "query-origin":
        activeRequestId = data.requestId;
        setCancelSelectionVisible(Boolean(data.canCancel));
        query(data);
        requestSpotSelection(data.originOptions);
        break;

      case "query-target":
        activeRequestId = data.requestId;
        setCancelSelectionVisible(Boolean(data.canCancel));
        query(data);
        requestSpotSelection(data.targetOptions);
        break;

      case "query-card":
        activeRequestId = data.requestId;
        setCancelSelectionVisible(false);
        clearSpotSelection();
        query(data);
        showAllCardUp();
        requestCardSelection();
        break;

      case "query-card-exchange":
        activeRequestId = data.requestId;
        setCancelSelectionVisible(false);
        clearSpotSelection();
        query(data);
        showAllCardUp();
        break;

      case "query":
        if (data.requestId) activeRequestId = data.requestId;
        query(data);
        break;

      case "reject-card-selection":
        error(data);
        showAllCardUp();
        break;

      case "game-over":
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
      case 4001:
        showError(tocI18n.t("errors.invalid_game_id"));
        break;
      case 4002:
        showError(tocI18n.t("errors.player_name_taken"));
        break;
      case 4004:
        showError(tocI18n.t("errors.game_full"));
        break;
      case 1006:
        showError(tocI18n.t("errors.server_unreachable"));
        break;
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

rulePresetSelect.addEventListener("change", updateRulesetEditorVisibility);
resetCustomRules.addEventListener("click", () => applyRuleValues(ruleConfiguration.presets[ruleConfiguration.default]));
initializeRuleSelector();

createBtn.addEventListener("click", async () => {
  const name = nameInput.value.trim();
  if (!name) {
    showError(tocI18n.t("errors.name_required"));
    return;
  }

  clearError();
  createBtn.disabled = true;

  try {
    const payload = {preset: rulePresetSelect.value};
    if (rulePresetSelect.value === "custom") payload.rules = collectCustomRuleValues();

    const res = await fetch("/toc/api/create-game", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || tocI18n.t("errors.game_creation_failed"));

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

joinBtn.addEventListener("click", async () => {
  const name = nameInput.value.trim();
  const gameId = gameIdInput.value.trim();
  if (!name || !gameId) {
    showError(tocI18n.t("errors.name_and_game_id_required"));
    return;
  }
  await connectToGame(gameId, name);
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

gameIdInput.addEventListener("input", () => {
  joinBtn.disabled = gameIdInput.value.trim() === "";
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

  const message = {"id": crypto.randomUUID(), "type": "configure-player", "team": teamSelect.value, "color": colorSelect.value};
  ws.send(JSON.stringify(message));
});

function renderLobbyState(state) {
  currentLobbyState = state;
  lobbyGameId.textContent = state.gameId;
  lobbyPlayerCount.textContent = tocI18n.t("lobby.players_count", {count: state.players.length, capacity: 4});
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
    choice.textContent = player.configured ? tocI18n.t("lobby.configured_choice", {team: player.team, color: formatColorName(player.color)}) : tocI18n.t("lobby.choosing");

    row.append(connection, name, choice);
    lobbyPlayers.appendChild(row);
  });

  const localPlayer = state.players.find((player) => player.name === local_player_name);

  if (state.started) {
    state.players.filter((player) => player.configured).forEach((player) => assignPlayer(player.name, player.team, player.color));
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

  Array.from(teamSelect.options).forEach((option) => {
    option.disabled = state.teamCounts[option.value] >= state.teamCapacity;
  });

  if (teamSelect.selectedOptions[0]?.disabled) {
    const availableTeam = Array.from(teamSelect.options).find((option) => !option.disabled);
    if (availableTeam) teamSelect.value = availableTeam.value;
  }

  colorSelect.replaceChildren();
  state.availableColors.forEach((color) => {
    const option = document.createElement("option");
    option.value = color;
    option.textContent = formatColorName(color);
    colorSelect.appendChild(option);
  });

  confirmLobbyChoice.disabled = state.availableColors.length === 0;
  lobbyStatus.textContent = state.players.length < 4 ? tocI18n.t("lobby.choose_while_waiting") : tocI18n.t("lobby.choose_to_start");
}

function sendCardSelection(player_name, rank, suit) {
  const message = {"id": crypto.randomUUID(), "requestId": activeRequestId, "type": "card_selection", "name": player_name, "value": rank, "suit": suit};
  const message_json = JSON.stringify(message);
  console.log('[sendCardSelection] Sending following content to back-end:' + message_json);
  ws.send(message_json);
}

function sendSpotSelection(player_name, spot) {
  const message = {"id": crypto.randomUUID(), "requestId": activeRequestId, "type": "spot_selection", "name": player_name, "result": spot};
  const message_json = JSON.stringify(message);
  console.log('[sendSpotSelection] Sending following content to back-end:' + message_json);
  ws.send(message_json);
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
const regions = ['red', 'green', 'yellow', 'blue'];
const totalRegions = 4;
let spotsPerRegion = 18;
let enterHouseAtSpot = 18;
let totalSpots = totalRegions * spotsPerRegion;

const radius = 250;
const centerX = 300;
const centerY = 300;

const houseLabels = ['T', 'O', 'C', '!'];
const houseDistance = 40;

const spotElements = [];
const houseElements = [];

const positions = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
const positionMap = {
  'top-left':    { index: 2, info_box: document.getElementById('player-info-top-left'), card_box: document.getElementById('card-box-top-left') },
  'top-right':   { index: 3, info_box: document.getElementById('player-info-top-right'), card_box: document.getElementById('card-box-top-right') },
  'bottom-left': { index: 1, info_box: document.getElementById('player-info-bottom-left'), card_box: document.getElementById('card-box-bottom-left') },
  'bottom-right':{ index: 0, info_box: document.getElementById('player-info-bottom-right'), card_box: document.getElementById('card-box-bottom-right') },
};

const playerAssignments = []; // { name, team, color, position }
const usedColors = [];
const usedPositions = [];
let selectedCard = null;

// Click anywhere outside of cards to cancel card selection
document.addEventListener('click', () => {
  if (selectedCard) {
    selectedCard.classList.remove('selected');
    selectedCard = null;
  }
});


function configureBoardGeometry(regionLength, houseEntryPosition) {
  if (!Number.isInteger(regionLength) || regionLength <= 0) return;
  if (!Number.isInteger(houseEntryPosition) || houseEntryPosition < 1 || houseEntryPosition > regionLength) return;
  if (regionLength === spotsPerRegion && houseEntryPosition === enterHouseAtSpot) return;

  if (spotElements.length > 0) {
    console.error("Cannot change board geometry after the board has been drawn.");
    return;
  }

  spotsPerRegion = regionLength;
  totalSpots = totalRegions * spotsPerRegion;
  enterHouseAtSpot = houseEntryPosition;
}

//// Board and pieces drawing and update functions ////
function drawQuadrant(position, color) {
  const regionIndex = positionMap[position].index;
  const angleOffset = (regionIndex / 4) * 2 * Math.PI;

  const quadrantSpots = [];
  const quadrantHouses = [];

  for (let i = 0; i < spotsPerRegion; i++) {
    const angle = angleOffset + (i / (spotsPerRegion * totalRegions)) * 2 * Math.PI; // (spotsPerRegion * totalRegions) = total spots in circle
    const x = centerX + radius * Math.cos(angle) - 15;
    const y = centerY + radius * Math.sin(angle) - 15;

    const spot = document.createElement('div');
    spot.className = `spot ${color}`;
    spot.style.left = `${x}px`;
    spot.style.top = `${y}px`;
    spot.innerText = (i == 0) ? '' : i;
    spot.id = `spot-${color}-${i}`;
    spot.color = `${color}`
    spot.index = `${i}`

    if (i === 0) {
      spot.classList.add('out-spot');

      const houseEntryOffset = enterHouseAtSpot - spotsPerRegion;
      const houseAngle = angleOffset + (houseEntryOffset / totalSpots) * 2 * Math.PI;

      for (let j = 0; j < totalRegions; j++) {
        const innerRadius = radius - houseDistance * (j + 1);
        const gx = centerX + innerRadius * Math.cos(houseAngle) - 15;
        const gy = centerY + innerRadius * Math.sin(houseAngle) - 15;

        const houseSpot = document.createElement('div');
        houseSpot.className = `spot house ${color}`;
        houseSpot.style.left = `${gx}px`;
        houseSpot.style.top = `${gy}px`;
        houseSpot.innerText = houseLabels[j];
        houseSpot.id = `house-${color}-${j}`;

        board.appendChild(houseSpot);
        houseElements.push(houseSpot);
      }
    }

    board.appendChild(spot);
    quadrantSpots.push(spot);
  }

  // Update master spotElements list
  spotElements.push(...quadrantSpots);
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
function assignPlayer(name, team, color) {
  // if the player is already in the playerAssignements array, we don't add it again. 
  // This can happen because the full_ui uses the assignPlayer method (#TODO: refactor this?)
  const player_test = playerAssignments.find(p => p.name === name);
  if (player_test) return;

  const newPlayer = { name, team, color };

  if (playerAssignments.length === 0) {
    newPlayer.position = 'top-left';
  } else {
    const teammate = playerAssignments.find(p => p.team === team);
    if (teammate) {
      newPlayer.position = getOppositePosition(teammate.position);
    } else {
      const opponent = playerAssignments.find(p => p.team !== team);
      newPlayer.position = getAdjacentFreePosition(opponent.position);
    }
  }

  playerAssignments.push(newPlayer);

  usedColors.push(color);
  usedPositions.push(newPlayer.position);

  updatePlayerBlock(newPlayer);
  positionMap[newPlayer.position].info_box.style.display = 'flex';
  drawQuadrant(newPlayer.position, color);

  // Setting a few short-hands for cleaner code
  local_player = playerAssignments.find(p => p.name === local_player_name);
  if (local_player) {
    local_card_box = positionMap[local_player.position].card_box
    local_info_box = positionMap[local_player.position].info_box
    local_info_box.classList.add("local-player");

    if (!local_card_box.classList.contains("local-hand")) {
      local_card_box.classList.add("local-hand");
      localHandSlot.appendChild(local_card_box);
    }
  }
}


//// Helper functions ////
function getPlayerFromId(playerId) {
  const player = playerAssignments.find(p => p.name === playerId);
  if (!player) {
    console.warn(`[getPlayerFromId] No player found with ID "${playerId}"`, JSON.stringify(playerAssignments));
    return; // or handle this gracefully
  }
  return player
}

function getCardBoxFromId(playerId) {
  const player = getPlayerFromId(playerId);
  return positionMap[player.position].card_box;
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

function getPlayerClass(playerId) {
  const player = getPlayerFromId(playerId);
  return player ? `player-${player.color}` : '';
}


//// Simple UI update functions ////
function hideCardBlock(playerId) {
  const player = getPlayerFromId(playerId);
  positionMap[player.position].card_box.style.display = 'none';

  if (playerId === local_player_name) {
    setTranslatedText(emptyHandMessage, "game.waiting_for_next_deal");
    emptyHandMessage.classList.remove("hidden");
  }
}

function updatePlayerBlock(player, isDealer = false) {
  const block = positionMap[player.position].info_box;
  const identity = document.createElement("div");
  const name = document.createElement("span");
  const team = document.createElement("span");

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

  const playerClass = getPlayerClass(player.name);
  block.classList.remove("player-red", "player-green", "player-blue", "player-yellow");
  block.classList.add(playerClass);
}

function updateRegionColor(position, color) {
  const regionIndex = positionMap[position].index;
  const regionSpots = spotElements.slice(regionIndex * spotsPerRegion, (regionIndex + 1) * spotsPerRegion);
  const regionHouseSpots = houseElements.slice(regionIndex * totalRegions, (regionIndex + 1) * totalRegions);
  regionSpots.forEach(s => s.classList.add(color));
  regionHouseSpots.forEach(s => s.classList.add(color));
}

function toogleDealerOnPlayerBlock(playerId) {
	dealerName.textContent = playerId;

  playerAssignments.forEach(p => {
    if (p.name === playerId) {
      updatePlayerBlock(p, true);
    } else {
      updatePlayerBlock(p);
    }
  });
}

function displayActivePlayer(playerId) {
  if (!playerId) {
    setTranslatedText(currentPlayerName, "game.waiting_to_start");
    setTranslatedText(turnInstruction, "game.next_action");
    return;
  }

  if (playerId === local_player_name) {
    setTranslatedText(currentPlayerName, "game.player_you", {player: playerId});
    setTranslatedText(turnInstruction, "game.your_turn");
  } else {
    setRawText(currentPlayerName, playerId);
    setTranslatedText(turnInstruction, "game.waiting_for_player", {player: playerId});
  }
  turnInstruction.classList.remove("error-state");
  turnBanner.classList.toggle("your-turn", playerId === local_player_name);

  playerAssignments.forEach(p => {
    const block = positionMap[p.position].info_box;
    if (p.name === playerId) {
      block.classList.add('active');
    } else {
      block.classList.remove('active');
    }
  });
}

function displayNoActivePlayers() {
	setTranslatedText(currentPlayerName, "game.no_active_player");
	turnBanner.classList.remove("your-turn");

  playerAssignments.forEach(p => {
    const block = positionMap[p.position].info_box;
    block.classList.remove('active');
  });
}


//// Card UI update functions ////
function setupPlayerCards(playerId, cards) {
  const cardBox = getCardBoxFromId(playerId)
  cardBox.querySelectorAll('.card-container').forEach((cardContainer, i) => {

    cardContainer.classList.add('hover-effect');

    cardBlock = cardContainer.querySelector('.card');

    const rank = cards[i].value
    const suit = cards[i].suit

    const cardFront = document.createElement('div');
    cardFront.className = 'card-front';
    cardFront.innerHTML = `
      <div class="card-value">${rank}</div>
      <div class="card-suit">${suit}</div>
    `;

    cardBlock.appendChild(cardFront);

    cardContainer.addEventListener('click', switchCardClickListener);
    cardContainer.rank = rank;
    cardContainer.suit = suit;
    cardContainer.playerId = playerId;

    setTimeout(() => {
      cardContainer.classList.add('flip');
    }, 250 * i);
  });
}

function displayHiddenCards(playerId, number_of_cards) {
  const block = getCardBoxFromId(playerId);

  if (playerId === local_player_name) {
    emptyHandMessage.classList.add("hidden");
  }
  
  for (let i = 0; i < number_of_cards; i++) {
    block.style.display = 'flex';
    setTimeout(() => {
      const cardContainer = document.createElement('div');
      cardContainer.className = 'card-container';

      const card = document.createElement('div');
      card.className = 'card';

      const cardBack = document.createElement('div');
      cardBack.className = 'card-back';

      const backImg = document.createElement('img');
      backImg.src = 'assets/card.jpg';

      cardBack.appendChild(backImg);
      card.appendChild(cardBack);
      cardContainer.appendChild(card);
      block.appendChild(cardContainer);
    }, 250 * i);
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

  if (playerId === local_player_name) {
    setTranslatedText(emptyHandMessage, "game.waiting_for_next_deal");
    emptyHandMessage.classList.remove("hidden");
  }
}

function replaceCard(rank, suit) {
  // Getting the info of which card to replace is tricky, this way is much simpler than to actually look for the card based on the previous values, which would need to be passed by the back-end, which is ugly.
  const cardContainer = window.flipped_card;
  window.flipped_card = null;
  const cardFront = cardContainer.querySelector('.card-front');
  cardFront.innerHTML = `
    <div class="card-value">${rank}</div>
    <div class="card-suit">${suit}</div>
  `;
  setTimeout(100);
  requestAnimationFrame(() => {
    cardContainer.classList.add('flip');
  });
}

function removeCard(playerId, value, suit) {
  const block = getCardBoxFromId(playerId);

  // If the code is running the player own's UI then we remove the actual card, but for other players we remove any card (because other player's UI don't know the card value so we don't really care what card we remove).
  if (playerId !== local_player_name) {
    block.removeChild(block.children[0]);
  } else {
      for (cardContainer of block.children) {
      t_suit = cardContainer.children[0].querySelector('.card-front').querySelector('.card-suit').innerHTML;
      t_value = cardContainer.children[0].querySelector('.card-front').querySelector('.card-value').innerHTML;
      if (t_suit === suit && t_value === value) block.removeChild(cardContainer);
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
    window.flipped_card = cardContainer // storing that for later when we receive the new card from the team-mate
    selectedCard = null;
    // we loop over all cards and remove the switchCardClickListener event listener now that the switch has been triggered.
    event.currentTarget.parentElement.querySelectorAll('.card-container').forEach(c => {
        c.removeEventListener('click', switchCardClickListener);
        console.log('[switchCardClickListener] Removed switchCardClickListener.');
    });
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

  const t_suit = cardContainer.children[0].querySelector('.card-front').querySelector('.card-suit').innerHTML;
  const t_value = cardContainer.children[0].querySelector('.card-front').querySelector('.card-value').innerHTML;

  if (selectedCard === cardContainer) {
    // Second click confirms selection
    cardContainer.classList.remove('selected');
    cardContainer.classList.remove('flip');
    selectedCard = null;
    sendCardSelection(local_player_name, t_value, t_suit);
  } else {
    // First click triggers highlight
    if (selectedCard) selectedCard.classList.add('selected');
    selectedCard = cardContainer;
    cardContainer.classList.add('selected');
  }
}

function requestSpotSelection(spotOptions) {
  clearSpotSelection();

  spotOptions.forEach((option) => {
    const position = document.getElementById(option);
    if (!position) return;

    const handler = (event) => {
      event.stopPropagation();

      const selectedPositionId = event.currentTarget.id;

      clearSpotSelection();
      sendSpotSelection(local_player_name, selectedPositionId);
    };

    position.classList.add("glow");
    position.addEventListener("click", handler);
    selectableSpotHandlers.set(position, handler);
  });
}

function requestCardSelection() {
  local_card_box.querySelectorAll('.card-container').forEach(c => {
    c.addEventListener('click', clickCardClickListener);
    console.log('[requestCardSelection] Added clickCardClickListener.');
  });       
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

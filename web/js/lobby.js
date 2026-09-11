import {app, constants, dom, i18n, state} from "./context.js";

app.refreshResumeGamePanel = function refreshResumeGamePanel() {
  const canResume = Boolean(state.stored_player_name && state.stored_game_id);

  dom.resumeGamePanel.classList.toggle("hidden", !canResume);

  if (!canResume) return;

  const displayedGameName = app.formatGameName(state.stored_game_id);

  app.setTranslatedText(dom.resumeGameDescription, "start.resume_description", {
    player: state.stored_player_name,
    game: displayedGameName,
  });

  dom.resumeGameBtn.textContent = i18n.t("start.resume_button", {
    game: displayedGameName,
  });
};

app.formatGameName = function formatGameName(gameName) {
  return gameName
    .split("-")
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

app.getGameModeLabel = function getGameModeLabel(mode) {
  if (!mode?.name) return "";

  if (mode.name === "duel_four" && mode.layout) {
    return i18n.t(`game_modes.duel_four_${mode.layout}`);
  }

  return i18n.t(`game_modes.${mode.name}`);
};

app.renderOpenLobbies = function renderOpenLobbies() {
  dom.openLobbiesList.replaceChildren();

  if (state.openLobbies.length === 0) {
    app.setTranslatedText(dom.openLobbiesStatus, "lobby_browser.none");
    dom.openLobbiesStatus.classList.remove("hidden");
    return;
  }

  dom.openLobbiesStatus.classList.add("hidden");

  state.openLobbies.forEach(lobby => {
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

    gameName.textContent = app.formatGameName(lobby.gameName);
    creator.textContent = i18n.t("lobby_browser.created_by", {player: lobby.creatorName || "—"});
    mode.textContent = app.getGameModeLabel(lobby.mode);
    playerCount.textContent = i18n.t("lobby_browser.player_count", {
      count: lobby.playerCount,
      capacity: lobby.playerCapacity,
    });
    joinButton.type = "button";
    joinButton.textContent = i18n.t("lobby_browser.join");

    joinButton.addEventListener("click", async () => {
      const playerName = dom.nameInput.value.trim();

      if (!playerName) {
        app.showError(i18n.t("errors.name_required"));
        dom.nameInput.focus();
        return;
      }

      app.clearError();
      await app.connectToGame(lobby.gameName, playerName);
    });

    metadata.append(mode, playerCount);
    details.append(gameName, creator, metadata);
    card.append(details, joinButton);
    dom.openLobbiesList.appendChild(card);
  });
};

app.refreshOpenLobbies = async function refreshOpenLobbies(showLoading = true) {
  if (state.openLobbiesRequestInProgress) return;

  state.openLobbiesRequestInProgress = true;
  dom.refreshLobbiesBtn.disabled = true;

  if (showLoading) {
    app.setTranslatedText(dom.openLobbiesStatus, "lobby_browser.loading");
    dom.openLobbiesStatus.classList.remove("hidden");
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

    state.openLobbies = data.lobbies;
    app.renderOpenLobbies();
  } catch (caughtError) {
    console.error(caughtError);
    state.openLobbies = [];
    dom.openLobbiesList.replaceChildren();
    app.setTranslatedText(dom.openLobbiesStatus, "lobby_browser.unavailable");
    dom.openLobbiesStatus.classList.remove("hidden");
  } finally {
    state.openLobbiesRequestInProgress = false;
    dom.refreshLobbiesBtn.disabled = false;
  }
};

app.synchronizeHouseEntryControls = function synchronizeHouseEntryControls() {
  const trackControl = dom.customRulesFields.querySelector('[data-rule-name="track_region_length"]');
  const entryControl = dom.customRulesFields.querySelector('[data-rule-name="enter_house_at_spot"]');
  if (!trackControl || !entryControl) return;

  const regionLength = JSON.parse(trackControl.value);

  Array.from(entryControl.options).forEach(option => {
    option.disabled = JSON.parse(option.value) > regionLength;
  });

  if (JSON.parse(entryControl.value) > regionLength) entryControl.value = JSON.stringify(regionLength);
};

app.applyRuleValues = function applyRuleValues(values) {
  dom.customRulesFields.querySelectorAll("[data-rule-name]").forEach(control => {
    const value = values[control.dataset.ruleName];

    if (control.type === "checkbox") {
      control.checked = value;
    } else {
      control.value = JSON.stringify(value);
    }
  });

  app.synchronizeHouseEntryControls();
};

app.renderCustomRuleControls = function renderCustomRuleControls(schema, values) {
  dom.customRulesFields.replaceChildren();

  Object.entries(constants.RULE_GROUPS).forEach(([groupName, groupLabel]) => {
    const ruleNames = Object.keys(schema).filter(ruleName => constants.RULE_UI[ruleName]?.group === groupName);
    if (ruleNames.length === 0) return;

    const group = document.createElement("section");
    group.className = "rule-group";

    const heading = document.createElement("h3");
    heading.textContent = i18n.t(groupLabel);
    group.appendChild(heading);

    ruleNames.forEach(ruleName => {
      const definition = schema[ruleName];
      const row = document.createElement("div");
      row.className = "rule-control";
      const controlId = `rule-control-${ruleName}`;
      row.appendChild(app.createRuleTitle(ruleName, controlId));

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
          option.textContent = app.formatRuleChoice(ruleName, value);
          control.appendChild(option);
        });
      }

      control.id = controlId;
      control.dataset.ruleName = ruleName;
      row.appendChild(control);
      group.appendChild(row);
    });

    dom.customRulesFields.appendChild(group);
  });

  const renderedRuleNames = new Set(Array.from(dom.customRulesFields.querySelectorAll("[data-rule-name]"), control => control.dataset.ruleName));
  const missingRuleNames = Object.keys(schema).filter(ruleName => !renderedRuleNames.has(ruleName));

  if (missingRuleNames.length > 0) throw new Error(`Missing rule UI definitions: ${missingRuleNames.join(", ")}`);

  app.applyRuleValues(values);
  dom.customRulesFields.querySelector('[data-rule-name="track_region_length"]').addEventListener("change", app.synchronizeHouseEntryControls);
};

app.collectCustomRuleValues = function collectCustomRuleValues() {
  const values = {};

  dom.customRulesFields.querySelectorAll("[data-rule-name]").forEach(control => {
    values[control.dataset.ruleName] = control.type === "checkbox" ? control.checked : JSON.parse(control.value);
  });

  return values;
};

app.renderRulesetDisplay = function renderRulesetDisplay(panel, badge, list, ruleset) {
  if (!ruleset?.values) {
    panel.classList.add("hidden");
    return;
  }

  panel.classList.remove("hidden");
  badge.textContent = app.formatPresetName(ruleset.preset);
  list.replaceChildren();

  Object.entries(constants.RULE_GROUPS).forEach(([groupName, groupLabel]) => {
    const ruleNames = Object.keys(ruleset.values).filter(ruleName => constants.RULE_UI[ruleName]?.group === groupName);
    if (ruleNames.length === 0) return;

    const group = document.createElement("section");
    group.className = "rules-display-group";

    const heading = document.createElement("h3");
    heading.textContent = i18n.t(groupLabel);
    group.appendChild(heading);

    ruleNames.forEach(ruleName => {
      const value = ruleset.values[ruleName];
      const row = document.createElement("div");
      const displayedValue = document.createElement("span");

      row.className = "rules-display-row";
      displayedValue.className = `rules-display-value${typeof value === "boolean" ? value ? " enabled" : " disabled" : ""}`;
      displayedValue.textContent = typeof value === "boolean" ? value ? i18n.t("common.enabled") : i18n.t("common.disabled") : app.formatRuleChoice(ruleName, value);

      row.append(app.createRuleTitle(ruleName), displayedValue);
      group.appendChild(row);
    });

    list.appendChild(group);
  });
};

app.renderRulesetDisplays = function renderRulesetDisplays(ruleset) {
  state.displayedRuleset = ruleset;
  app.renderRulesetDisplay(dom.lobbyRulesPanel, dom.lobbyRulesPreset, dom.lobbyRulesList, ruleset);
  app.renderRulesetDisplay(dom.gameRulesPanel, dom.gameRulesPreset, dom.gameRulesList, ruleset);
};

app.updateRulesetEditorVisibility = function updateRulesetEditorVisibility() {
  const isCustom = dom.rulePresetSelect.value === "custom";
  dom.customRulesEditor.classList.toggle("hidden", !isCustom);
  dom.rulePresetSummary.textContent = isCustom ? i18n.t("rules.custom_summary") : i18n.t("rules.preset_summary", {preset: app.formatPresetName(dom.rulePresetSelect.value)});
};

app.initializeRuleSelector = async function initializeRuleSelector() {
  try {
    const response = await fetch("/toc/api/rule-presets");
    if (!response.ok) throw new Error("Could not load rule presets.");

    state.ruleConfiguration = await response.json();
    
    const missingMessageKeys = i18n.getMissingTranslationKeys(state.ruleConfiguration.messageKeys || []);
    if (missingMessageKeys.length) {
      console.error(`Missing backend translations: ${missingMessageKeys.join(", ")}`);
    }
    
    const defaultValues = state.ruleConfiguration.presets[state.ruleConfiguration.default];

    dom.rulePresetSelect.replaceChildren();

    Object.keys(state.ruleConfiguration.presets).forEach(presetName => {
      const option = document.createElement("option");
      option.value = presetName;
      option.textContent = app.formatPresetName(presetName);
      dom.rulePresetSelect.appendChild(option);
    });

    const customOption = document.createElement("option");
    customOption.value = "custom";
    customOption.textContent = i18n.t("rules.custom_option");
    dom.rulePresetSelect.appendChild(customOption);

    app.renderCustomRuleControls(state.ruleConfiguration.schema, defaultValues);
    dom.rulePresetSelect.value = state.ruleConfiguration.default;
    dom.rulePresetSelect.disabled = false;
    dom.createBtn.disabled = false;
    app.updateRulesetEditorVisibility();
  } catch (err) {
    console.error(err);
    dom.rulePresetSummary.textContent = i18n.t("rules.load_error");
    app.showError(i18n.t("errors.rules_load_failed"));
  }
};

app.renderLobbyTeamOptions = function renderLobbyTeamOptions(lobbyState) {
  const previousTeam = dom.teamSelect.value;
  dom.teamSelect.replaceChildren();

  Object.keys(lobbyState.teamCounts).forEach(team => {
    const option = document.createElement("option");

    option.value = team;
    option.textContent = i18n.t(`lobby.team_${team}`);
    option.disabled = lobbyState.teamCounts[team] >= lobbyState.teamCapacity;
    dom.teamSelect.appendChild(option);
  });

  const previousOption = Array.from(dom.teamSelect.options).find(option => option.value === previousTeam && !option.disabled);
  const firstAvailableOption = Array.from(dom.teamSelect.options).find(option => !option.disabled);

  if (previousOption) {
    dom.teamSelect.value = previousOption.value;
  } else if (firstAvailableOption) {
    dom.teamSelect.value = firstAvailableOption.value;
  }
};

app.synchronizeLobbyColorOptions = function synchronizeLobbyColorOptions() {
  const selects = Array.from(dom.colorSelects.querySelectorAll("select"));
  const selectedValues = selects.map(select => select.value);

  selects.forEach((select, selectIndex) => {
    Array.from(select.options).forEach(option => {
      option.disabled = selectedValues.some((value, valueIndex) => valueIndex !== selectIndex && value === option.value);
    });
  });
};

app.renderLobbyColorOptions = function renderLobbyColorOptions(lobbyState) {
  const colorCount = lobbyState.seatsPerParticipant;

  if (!Number.isInteger(colorCount) || colorCount < 1) {
    console.error("Invalid seats-per-participant value in lobby state.", lobbyState);
    return;
  }

  const previousValues = Array.from(dom.colorSelects.querySelectorAll("select"), select => select.value);
  dom.colorSelects.replaceChildren();

  for (let colorIndex = 0; colorIndex < colorCount; colorIndex++) {
    const field = document.createElement("label");
    const labelText = document.createElement("span");
    const select = document.createElement("select");

    field.className = "lobby-color-field";
    labelText.textContent = colorCount === 1 ? i18n.t("lobby.colour") : i18n.t("lobby.colour_number", {number: colorIndex + 1});
    select.className = "lobby-select";
    select.dataset.colorIndex = colorIndex;

    lobbyState.availableColors.forEach(color => {
      const option = document.createElement("option");
      option.value = color;
      option.textContent = app.formatColorName(color);
      select.appendChild(option);
    });

    const previousValue = previousValues[colorIndex];

    if (previousValue && lobbyState.availableColors.includes(previousValue)) {
      select.value = previousValue;
    } else if (lobbyState.availableColors[colorIndex]) {
      select.value = lobbyState.availableColors[colorIndex];
    }

    select.addEventListener("change", app.synchronizeLobbyColorOptions);
    field.append(labelText, select);
    dom.colorSelects.appendChild(field);
  }

  app.synchronizeLobbyColorOptions();
};

app.renderLobbyState = function renderLobbyState(lobbyState) {
  state.currentLobbyState = lobbyState;
  dom.lobbyGameId.textContent = lobbyState.gameId;
  dom.lobbyPlayerCount.textContent = i18n.t("lobby.players_count", {count: lobbyState.players.length, capacity: lobbyState.participantCapacity});
  dom.lobbyPlayers.replaceChildren();
  app.renderRulesetDisplays(lobbyState.ruleset);

  lobbyState.players.forEach((player) => {
    const row = document.createElement("div");
    const connection = document.createElement("span");
    const name = document.createElement("span");
    const choice = document.createElement("span");

    row.className = "lobby-player";
    connection.className = `lobby-connection${player.connected ? " connected" : ""}`;
    name.className = "lobby-player-name";
    choice.className = "lobby-player-choice";
    name.textContent = player.name === state.local_player_name ? i18n.t("game.player_you", {player: player.name}) : player.name;
    const colorNames = (player.colors || [player.color]).filter(Boolean).map(app.formatColorName).join(", ");
    choice.textContent = player.configured ? i18n.t("lobby.configured_choice", {team: player.team, color: colorNames}) : i18n.t("lobby.choosing");

    row.append(connection, name, choice);
    dom.lobbyPlayers.appendChild(row);
  });

  const localPlayer = lobbyState.players.find((player) => player.name === state.local_player_name);

  if (lobbyState.started) {
    const seatsById = new Map();

    lobbyState.players.forEach(player => {
      player.seats.forEach(seat => {
        seatsById.set(seat.seatId, {
          seatId: seat.seatId,
          name: player.name,
          team: player.team,
          color: seat.color,
        });
      });
    });

    lobbyState.seatOrder.forEach((seatId, seatIndex) => {
      const seat = seatsById.get(seatId);
      if (seat) app.assignPlayer(seat.seatId, seat.name, seat.team, seat.color, seatIndex);
    });

    app.showGameUI();
    return;
  }

  app.showLobbyUI();

  if (!localPlayer || localPlayer.configured) {
    dom.lobbyChoiceForm.classList.add("hidden");
    dom.lobbyStatus.textContent = localPlayer ? i18n.t("lobby.confirmed_waiting") : i18n.t("lobby.joining");
    return;
  }

  dom.lobbyChoiceForm.classList.remove("hidden");
  dom.confirmLobbyChoice.disabled = false;
  dom.lobbyError.classList.add("hidden");

  app.renderLobbyTeamOptions(lobbyState);
  app.renderLobbyColorOptions(lobbyState);

  dom.confirmLobbyChoice.disabled = lobbyState.availableColors.length < lobbyState.seatsPerParticipant;
  dom.lobbyStatus.textContent = lobbyState.players.length < lobbyState.participantCapacity ? i18n.t("lobby.choose_while_waiting") : i18n.t("lobby.choose_to_start");
};

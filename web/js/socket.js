import {app, constants, dom, i18n, state} from "./context.js";

app.buildWebSocketUrl = function buildWebSocketUrl(gameId, playerName) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";

  return (
    `${protocol}://${window.location.host}/toc/ws/` +
    `${encodeURIComponent(gameId)}/` +
    `${encodeURIComponent(playerName)}`
  );
};

app.getResumeTokenStorageKey = function getResumeTokenStorageKey(gameId, playerName) {
  return `toc.resumeToken.${encodeURIComponent(gameId)}.${encodeURIComponent(playerName)}`;
};

app.returnToStartAfterServerClose = function returnToStartAfterServerClose(messageKey, gameId, playerName, clearGameCredentials) {
  window.sessionStorage.setItem(constants.START_NOTICE_STORAGE_KEY, messageKey);

  if (clearGameCredentials) {
    window.localStorage.removeItem(app.getResumeTokenStorageKey(gameId, playerName));
    window.localStorage.removeItem("session_game_ID");
  }

  window.location.reload();
};

app.connectToGame = async function connectToGame(gameId, name, rejoin = false) {
  app.clearError();
  gameId = gameId.trim().toLowerCase();
  const wsUrl = app.buildWebSocketUrl(gameId, name);
  try {
    state.ws = new WebSocket(wsUrl);
  } catch (err) {
    console.error(err);
    dom.createBtn.disabled = state.ruleConfiguration === null;
    app.showError(i18n.t("errors.websocket_error"));
    return;
  }

  const resumeTokenStorageKey = app.getResumeTokenStorageKey(gameId, name);
  const resumeToken = window.localStorage.getItem(resumeTokenStorageKey);

  state.ws.onopen = () => {
    state.ws.send(JSON.stringify({
      type: "identify",
      resumeToken: resumeToken,
    }));
  };

  state.ws.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      console.warn("[WebSocket] Received invalid JSON:", event.data);
      return;
    }
    console.log('[ws.oneMessage top handler] Received the following message from back-end:' + JSON.stringify(data))

    const actingSeatId = app.getMessageSeatId(data);
    switch (data.type) {
      case 'ready':

        if (typeof data.resumeToken === "string" && data.resumeToken !== "") {
          window.localStorage.setItem(resumeTokenStorageKey, data.resumeToken);
        }

        state.stored_player_name = name;
        state.stored_game_id = gameId;

        window.localStorage.setItem("session_player_name", state.stored_player_name);
        window.localStorage.setItem("session_game_ID", state.stored_game_id);

        app.log({
          messageKey: "connection.connected_as",
          parameters: {gameId, player: name},
          fallback: `Connected to game ${gameId} as ${name}.`,
        });
        app.setTranslatedText(dom.connectionStatusText, "connection.connected");
        state.local_player_name = name;
        state.local_game_Id = gameId;
        dom.gameIdDisplay.textContent = gameId;
        dom.connectionStatus.classList.add("connected");
        app.showLobbyUI();
        break;

      case 'lobby-state':
        app.configureBoardGeometry(data.trackRegionCount, data.trackRegionLength, data.enterHouseAtSpot);
        app.renderLobbyState(data);
        break;

      case 'lobby-error':
        app.setMessageText(dom.lobbyError, data);
        dom.lobbyError.classList.remove("hidden");
        dom.confirmLobbyChoice.disabled = false;
        break;
      
      case 'assign-player':
        app.assignPlayer(data.seatId || data.name, data.name, data.team, data.color);
        break;

      case "full-ui-state":
        app.configureBoardGeometry(data.trackRegionCount, data.trackRegionLength, data.enterHouseAtSpot);
        app.renderRulesetDisplays(data.ruleset);

        data.players.forEach((player, seatIndex) => {
          app.assignPlayer(player.seatId, player.name, player.team, player.color, seatIndex);

          if (player.number_of_cards === 0) {
            app.hideCardBlock(player.seatId);
          } else {
            app.displayHiddenCards(player.seatId, player.number_of_cards);
          }
        });

        data.pieces.forEach(piece => {
          app.placePieceOnSpot(piece.seatId || piece.playerId, piece.spotIndex);
        });

        app.displayActivePlayer(data.activeSeatId || data.active_player);

        if (data.lastPlayedCard) {
          app.showCardOnDiscardPile(data.lastPlayedCard.value, data.lastPlayedCard.suit);
        } else {
          app.clearDiscardPile();
        }
        break;

      case "draw":
        // When we receive the draw order, we only display the (hidden) cards of the players unless they are already displayed
        state.playerAssignments.forEach(player => {
          app.displayHiddenCards(player.seatId, data.cards.length);
        });
        break;

      case "reveal":
        app.setupPlayerCards(actingSeatId, data.cards);
        break;

      case "dealer":
        app.toogleDealerOnPlayerBlock(actingSeatId);
        break;

      case "receive-card-from-friend":
        app.replaceCard(actingSeatId, data.value, data.suit);
        break;

      case 'move':
        app.placePieceOnSpot(actingSeatId, data.spotIndex);
        break;

      case "fold":
        app.foldAllCardsOfPlayer(actingSeatId);
        app.log(data);
        break;

      case "discard":
        app.animateCardToDiscardPile(actingSeatId, data.value, data.suit);
        app.removeCard(actingSeatId, data.value, data.suit);
        app.log(data);
        break;

      case "log":
        app.log(data);
        break;

      case 'forced-play':
        app.log(data);
        break;

      case "next-player":
        app.disableCardSelection();
        app.setCancelSelectionVisible(false);
        app.clearSpotSelection();
        app.displayActivePlayer(actingSeatId);
        app.log(data);
        break;

      case "play": {
        app.setCancelSelectionVisible(false);
        app.clearSpotSelection();

        
        const movedSeatId = app.getMessageSeatId(data, "moved") || actingSeatId;

        app.animateCardToDiscardPile(actingSeatId, data.value, data.suit);
        app.removeCard(actingSeatId, data.value, data.suit);

        if (data.value === "J") {
          app.switchPieces(movedSeatId, data.origin, data.target);
        } else {
          app.movePieceFromSpotToSpot(movedSeatId, data.origin, data.target);
        }

        app.log(data);
        break;
      }

      case "seven-start":
        app.setCancelSelectionVisible(false);
        app.animateCardToDiscardPile(actingSeatId, data.value, data.suit);
        app.removeCard(actingSeatId, data.value, data.suit);
        app.log(data);
        break;

      case "seven-step":
        app.movePieceFromSpotToSpot(app.getMessageSeatId(data, "moved") || actingSeatId, data.origin, data.target);
        break;

      case "query-seven-hop":
        app.disableCardSelection();
        app.selectLocalSeat(actingSeatId);
        state.activeRequestId = data.requestId;
        app.setCancelSelectionVisible(false);
        app.clearSpotSelection();
        app.query(data);
        app.requestSevenHop(data.origin, data.target);
        break;

      case "seven-hop":
        app.movePieceFromSpotToSpot(app.getMessageSeatId(data, "moved"), data.origin, data.target);
        break;

      case "path-kicks":
        data.positions.forEach((positionId) => {
          const position = document.getElementById(positionId);
          if (position) app.resetEmptyPosition(position);
        });
        break;

      case "query-origin":
        app.disableCardSelection();
        app.selectLocalSeat(actingSeatId);
        state.activeRequestId = data.requestId;
        app.setCancelSelectionVisible(Boolean(data.canCancel));
        app.query(data);
        app.requestSpotSelection(data.originOptions);
        break;

      case "query-target":
        app.disableCardSelection();
        app.selectLocalSeat(actingSeatId);
        state.activeRequestId = data.requestId;
        app.setCancelSelectionVisible(Boolean(data.canCancel));
        app.query(data);
        app.requestSpotSelection(data.targetOptions);
        break;

      case "query-card":
        app.selectLocalSeat(actingSeatId);
        state.activeRequestId = data.requestId;
        app.setCancelSelectionVisible(false);
        app.clearSpotSelection();
        app.query(data);
        app.showAllCardUp();
        app.requestCardSelection();
        break;

      case "query-card-exchange":
        app.selectLocalSeat(actingSeatId);
        state.activeRequestId = data.requestId;
        app.setCancelSelectionVisible(false);
        app.clearSpotSelection();
        app.query(data);
        app.showAllCardUp();
        app.requestCardExchangeSelection();
        break;

      case "query":
        if (data.requestId) state.activeRequestId = data.requestId;
        app.query(data);
        break;

      case "reject-card-selection":
        app.selectLocalSeat(actingSeatId);
        app.error(data);
        app.showAllCardUp();
        app.requestCardSelection();
        break;

      case "discard-pile-cleared":
        app.clearDiscardPile();
        break;

      case "game-over":
        app.disableCardSelection();
        app.setCancelSelectionVisible(false);
        app.clearSpotSelection();
        app.displayNoActivePlayers();
        app.setTranslatedText(dom.currentPlayerName, "game.game_over");
        app.setRawText(dom.turnInstruction, data.msg);
        app.log(data);
        break;

      case 'error':
        app.error(data);
        break;

      default:
        app.log(`Unknown message: ${event.data}`);
    }
  };
  
  state.ws.onclose = (event) => {
	app.setCancelSelectionVisible(false);
	app.clearSpotSelection();
	dom.connectionStatus.classList.remove("connected");
	app.setTranslatedText(dom.connectionStatusText, "connection.disconnected");
  dom.createBtn.disabled = state.ruleConfiguration === null;

    switch (event.code) {
      case NO_GAME_FOUND_CODE:
        app.showError(i18n.t("errors.invalid_game_id"));
        break;
      case NO_PLAYER_CONTEXT_FOUND_CODE:
        app.showError(i18n.t("errors.player_name_taken"));
        break;
      case GAME_ALREADY_FULL_CODE:
        app.showError(i18n.t("errors.game_full"));
        break;
      case CONNECTION_IDENTIFICATION_ERROR_CODE:
        app.showError(i18n.t("errors.invalid_resume_token"));
        break;
      case SERVER_UNREACHABLE_CODE:
        app.showError(i18n.t("errors.server_unreachable"));
        break;
      case LOBBY_EXPIRED_CLOSE_CODE:
        app.returnToStartAfterServerClose("errors.lobby_expired", gameId, name, true);
        return;

      case GAME_SUSPENDED_CLOSE_CODE:
        app.returnToStartAfterServerClose("errors.game_suspended", gameId, name, false);
        return;
      default:
        app.showError(i18n.t("errors.connection_closed", {code: event.code}));
    }
  };

  state.ws.onerror = () => {
    app.showError(i18n.t("errors.websocket_error"));
  };
};

app.getMessageSeatId = function getMessageSeatId(message, prefix = "") {
  const seatField = prefix ? `${prefix}SeatId` : "seatId";
  const legacyField = prefix ? `${prefix}PlayerId` : "playerId";
  return message[seatField] || message[legacyField];
};

app.sendCardSelection = function sendCardSelection(seatId, rank, suit) {
  const message = {
    "id": crypto.randomUUID(),
    "requestId": state.activeRequestId,
    "type": "card_selection",
    "name": state.local_player_name,
    "seatId": seatId,
    "value": rank,
    "suit": suit,
  };

  state.ws.send(JSON.stringify(message));
};

app.sendSpotSelection = function sendSpotSelection(seatId, spot) {
  const message = {
    "id": crypto.randomUUID(),
    "requestId": state.activeRequestId,
    "type": "spot_selection",
    "name": state.local_player_name,
    "seatId": seatId,
    "result": spot,
  };

  state.ws.send(JSON.stringify(message));
};

app.sendSevenHopChoice = function sendSevenHopChoice(result) {
  const message = {"id": crypto.randomUUID(), "requestId": state.activeRequestId, "type": "seven_hop_choice", "name": state.local_player_name, "result": result};
  console.log('[sendSevenHopChoice] Sending following content to back-end:' + JSON.stringify(message));
  state.ws.send(JSON.stringify(message));
};

app.requestSevenHop = function requestSevenHop(originSpot, targetSpot) {
  const shouldHop = window.confirm(i18n.t("prompts.seven_hop", {origin: originSpot, target: targetSpot}));
  app.sendSevenHopChoice(shouldHop);
};

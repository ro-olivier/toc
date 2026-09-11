import {app, constants, dom, i18n, state} from "./context.js";

app.refreshLocalHandLabels = function refreshLocalHandLabels() {
  state.playerAssignments.filter(player => app.isLocalSeat(player.seatId)).forEach(player => {
    app.getCardBoxFromId(player.seatId).dataset.colorLabel = app.formatColorName(player.color);
  });
};

app.fitBoardToViewport = function fitBoardToViewport() {
  if (!dom.boardViewportElement || !dom.boardWrapperElement) return;

  const availableWidth = dom.boardViewportElement.clientWidth;
  if (availableWidth <= 0) return;

  const boardScale = Math.min(1, availableWidth / constants.boardLayoutWidth);

  dom.boardWrapperElement.style.transform = `scale(${boardScale})`;
  dom.boardViewportElement.style.height = `${constants.boardTopSpacing + constants.boardLayoutHeight * boardScale}px`;
};

app.getTrackRadius = function getTrackRadius(angle) {
  const configuration = constants.starBoardConfigurations[state.totalRegions];
  if (!configuration) return constants.radius;

  const armProgress = (1 + Math.cos(state.totalRegions * angle)) / 2;

  return configuration.innerRadius + configuration.armLength * Math.pow(armProgress, configuration.sharpness);
};

app.getStarStepAngles = function getStarStepAngles() {
  const cacheKey = `${state.totalRegions}:${state.spotsPerRegion}`;
  const cachedAngles = state.starStepAngleCache.get(cacheKey);
  if (cachedAngles) return cachedAngles;

  const branchAngle = (2 * Math.PI) / state.totalRegions;
  const samples = [{angle: 0, distance: 0}];
  let previousX = app.getTrackRadius(0);
  let previousY = 0;
  let totalDistance = 0;

  for (let sampleIndex = 1; sampleIndex <= constants.starCurveSamplesPerBranch; sampleIndex++) {
    const angle = (sampleIndex / constants.starCurveSamplesPerBranch) * branchAngle;
    const trackRadius = app.getTrackRadius(angle);
    const x = trackRadius * Math.cos(angle);
    const y = trackRadius * Math.sin(angle);

    totalDistance += Math.hypot(x - previousX, y - previousY);
    samples.push({angle, distance: totalDistance});
    previousX = x;
    previousY = y;
  }

  const stepAngles = [];

  for (let stepIndex = 0; stepIndex <= state.spotsPerRegion; stepIndex++) {
    const targetDistance = (stepIndex / state.spotsPerRegion) * totalDistance;
    const upperSampleIndex = samples.findIndex(sample => sample.distance >= targetDistance);
    const upperSample = samples[Math.max(upperSampleIndex, 1)];
    const lowerSample = samples[Math.max(upperSampleIndex - 1, 0)];
    const distanceDifference = upperSample.distance - lowerSample.distance;
    const interpolation = distanceDifference === 0 ? 0 : (targetDistance - lowerSample.distance) / distanceDifference;

    stepAngles.push(lowerSample.angle + (upperSample.angle - lowerSample.angle) * interpolation);
  }

  state.starStepAngleCache.set(cacheKey, stepAngles);
  return stepAngles;
};

app.getTrackAngle = function getTrackAngle(regionIndex, spotIndex) {
  if (!constants.starBoardConfigurations[state.totalRegions]) {
    return (regionIndex / state.totalRegions) * 2 * Math.PI + (spotIndex / state.totalSpots) * 2 * Math.PI;
  }

  const entryStepOffset = state.enterHouseAtSpot - state.spotsPerRegion;
  const globalStep = regionIndex * state.spotsPerRegion + spotIndex;
  const stepsAfterBranch = globalStep - entryStepOffset;
  const branchIndex = Math.floor(stepsAfterBranch / state.spotsPerRegion);
  const stepIndex = stepsAfterBranch - branchIndex * state.spotsPerRegion;

  return branchIndex * ((2 * Math.PI) / state.totalRegions) + app.getStarStepAngles()[stepIndex];
};

app.getHouseAngle = function getHouseAngle(regionIndex) {
  if (constants.starBoardConfigurations[state.totalRegions]) {
    return (regionIndex / state.totalRegions) * 2 * Math.PI;
  }

  const angleOffset = (regionIndex / state.totalRegions) * 2 * Math.PI;
  const houseEntryOffset = state.enterHouseAtSpot - state.spotsPerRegion;

  return angleOffset + (houseEntryOffset / state.totalSpots) * 2 * Math.PI;
};

app.updateBoardSurface = function updateBoardSurface() {
  const usesStarBoard = constants.starBoardConfigurations[state.totalRegions] !== undefined;

  dom.board.classList.toggle("star-board", usesStarBoard);

  if (!usesStarBoard) {
    dom.board.style.removeProperty("--board-shape");
    return;
  }

  const polygonPoints = [];

  for (let sampleIndex = 0; sampleIndex < constants.boardShapeSamples; sampleIndex++) {
    const angle = (sampleIndex / constants.boardShapeSamples) * 2 * Math.PI;
    const surfaceRadius = app.getTrackRadius(angle) + constants.boardSurfaceMargin;
    const x = ((constants.centerX + surfaceRadius * Math.cos(angle)) / (constants.centerX * 2)) * 100;
    const y = ((constants.centerY + surfaceRadius * Math.sin(angle)) / (constants.centerY * 2)) * 100;

    polygonPoints.push(`${x.toFixed(2)}% ${y.toFixed(2)}%`);
  }

  dom.board.style.setProperty("--board-shape", `polygon(${polygonPoints.join(", ")})`);
};

app.configureBoardGeometry = function configureBoardGeometry(regionCount, regionLength, houseEntryPosition) {
  if (!Number.isInteger(regionCount) || regionCount < 2) return;
  if (!Number.isInteger(regionLength) || regionLength <= 0) return;
  if (!Number.isInteger(houseEntryPosition) || houseEntryPosition < 1 || houseEntryPosition > regionLength) return;

  if (regionCount === state.totalRegions && regionLength === state.spotsPerRegion && houseEntryPosition === state.enterHouseAtSpot) {
    app.updateBoardSurface();
    return;
  }

  if (state.spotElements.length > 0) {
    console.error("Cannot change board geometry after the board has been drawn.", {
      currentRegionCount: state.totalRegions,
      requestedRegionCount: regionCount,
      currentRegionLength: state.spotsPerRegion,
      requestedRegionLength: regionLength,
      currentHouseEntry: state.enterHouseAtSpot,
      requestedHouseEntry: houseEntryPosition,
    });
    return;
  }

  state.totalRegions = regionCount;
  state.spotsPerRegion = regionLength;
  state.totalSpots = state.totalRegions * state.spotsPerRegion;
  state.enterHouseAtSpot = houseEntryPosition;

  app.updateBoardSurface();
};

app.drawRegion = function drawRegion(color, regionIndex) {

  const regionSpots = [];

  for (let spotIndex = 0; spotIndex < state.spotsPerRegion; spotIndex++) {
    const angle = app.getTrackAngle(regionIndex, spotIndex);
    const trackRadius = app.getTrackRadius(angle);
    const x = constants.centerX + trackRadius * Math.cos(angle) - 15;
    const y = constants.centerY + trackRadius * Math.sin(angle) - 15;

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

      const houseAngle = app.getHouseAngle(regionIndex);

      for (let houseIndex = 0; houseIndex < constants.spotsPerHouse; houseIndex++) {
        const innerRadius = constants.radius - constants.houseDistance * (houseIndex + 1);
        const houseX = constants.centerX + innerRadius * Math.cos(houseAngle) - 15;
        const houseY = constants.centerY + innerRadius * Math.sin(houseAngle) - 15;

        const houseSpot = document.createElement('div');
        houseSpot.className = `spot house ${color}`;
        houseSpot.style.left = `${houseX}px`;
        houseSpot.style.top = `${houseY}px`;
        houseSpot.innerText = constants.houseLabels[houseIndex];
        houseSpot.id = `house-${color}-${houseIndex}`;

        dom.board.appendChild(houseSpot);
        state.houseElements.push(houseSpot);
      }
    }

    dom.board.appendChild(spot);
    regionSpots.push(spot);
  }

  state.spotElements.push(...regionSpots);
};

app.placePieceOnSpot = function placePieceOnSpot(playerId, targetSpot) {
  app.movePieceFromSpotToSpot(playerId, targetSpot, targetSpot);
};

app.resetEmptyPosition = function resetEmptyPosition(position) {
  if (position.classList.contains("house")) {
    const houseNumber = Number(position.id.split("-").at(-1));
    position.textContent = constants.houseLabels[houseNumber];
    return;
  }

  position.textContent = Number(position.index) % state.spotsPerRegion === 0 ? "" : position.index;
};

app.movePieceFromSpotToSpot = function movePieceFromSpotToSpot(playerId, originSpot, targetSpot) {
  const playerClass = app.getPlayerClass(playerId);

  if (originSpot !== targetSpot) {
    // This is the case when the move played is anything other than an "OUT" move, in which case we have to remove a piece from a previous spot before adding it to the new spot
    const origin_spot =  document.getElementById(originSpot);
    const old = origin_spot.querySelector(`[data-player="${playerId}"]`);
    if (old && old.parentElement) { // this test is almost certainly unnecessary, but just in case, ...we don't want to go change the content of other spots on the board
      app.resetEmptyPosition(origin_spot); // reseting the value inside the spot
    }
  }

  const target_spot = document.getElementById(targetSpot);
  const piece = document.createElement('div');
  piece.classList.add('piece', playerClass);
  piece.dataset.player = playerId;
  
  target_spot.innerHTML = '';
  target_spot.appendChild(piece);
};

app.switchPieces = function switchPieces(playerId, originSpot, targetSpot) {
  const target_spot = document.getElementById(targetSpot);
  const targetPlayerId = target_spot.querySelector('.piece').dataset.player;

  app.movePieceFromSpotToSpot(playerId, originSpot, targetSpot);
  app.movePieceFromSpotToSpot(targetPlayerId, targetSpot, originSpot);
};

app.removeGlowOnEverySpot = function removeGlowOnEverySpot() {
  document.querySelectorAll('.glow').forEach((spot) => {
    spot.classList.remove('glow');
  });
};

app.clearSpotSelection = function clearSpotSelection() {
  state.selectableSpotHandlers.forEach((handler, position) => position.removeEventListener("click", handler));
  state.selectableSpotHandlers.clear();
  app.removeGlowOnEverySpot();
};

app.assignPlayer = function assignPlayer(seatId, name, team, color, seatIndex = state.playerAssignments.length) {
  const existingPlayer = state.playerAssignments.find(player => player.seatId === seatId);
  if (existingPlayer) return existingPlayer;

  const seatLayout = constants.seatLayouts[state.totalRegions]?.[seatIndex];

  if (!seatLayout) {
    console.error(`No ${state.totalRegions}-seat board position is available for seat "${seatId}".`);
    return null;
  }

  const {position, regionIndex} = seatLayout;
  const newPlayer = {seatId, name, team, color, position, regionIndex, handCardBox: null};

  state.playerAssignments.push(newPlayer);
  state.usedColors.push(color);
  state.usedPositions.push(position);

  app.updatePlayerBlock(newPlayer);
  constants.positionMap[position].info_box.style.display = 'flex';
  app.drawRegion(color, regionIndex);

  const playerColorRgb = constants.PLAYER_ACCENT_RGB[color] || "100, 116, 139";

  constants.positionMap[position].info_box.style.setProperty("--player-color-rgb", playerColorRgb);
  constants.positionMap[position].card_box.style.setProperty("--player-color-rgb", playerColorRgb);

  if (name === state.local_player_name) {
    const infoBox = constants.positionMap[position].info_box;
    const handCardBox = document.createElement("div");

    infoBox.classList.add("local-player");

    handCardBox.className = "card-box local-hand";
    handCardBox.dataset.seatId = seatId;
    handCardBox.dataset.colorLabel = app.formatColorName(color);
    handCardBox.style.setProperty("--hand-color-rgb", constants.PLAYER_ACCENT_RGB[color] || "100, 116, 139");

    newPlayer.handCardBox = handCardBox;
    dom.localHandSlot.appendChild(handCardBox);

    const localHandCount = state.playerAssignments.filter(player => app.isLocalSeat(player.seatId)).length;
    dom.localHandSlot.classList.toggle("multiple-hands", localHandCount > 1);

    if (!state.local_player) app.selectLocalSeat(seatId);
  }
};

app.getPlayerFromId = function getPlayerFromId(seatId) {
  const player = state.playerAssignments.find(player => player.seatId === seatId);

  if (!player) {
    console.warn(`[getPlayerFromId] No seat found with ID "${seatId}"`, JSON.stringify(state.playerAssignments));
    return null;
  }

  return player;
};

app.isLocalSeat = function isLocalSeat(seatId) {
  return app.getPlayerFromId(seatId)?.name === state.local_player_name;
};

app.selectLocalSeat = function selectLocalSeat(seatId) {
  const player = app.getPlayerFromId(seatId);

  if (!player || player.name !== state.local_player_name) return false;

  state.local_player = player;
  state.local_card_box = player.handCardBox || constants.positionMap[player.position].card_box;
  state.local_info_box = constants.positionMap[player.position].info_box;
  return true;
};

app.getBoardCardBoxFromId = function getBoardCardBoxFromId(seatId) {
  const player = app.getPlayerFromId(seatId);
  return player ? constants.positionMap[player.position].card_box : null;
};

app.getCardBoxFromId = function getCardBoxFromId(seatId) {
  const player = app.getPlayerFromId(seatId);
  if (!player) return null;

  return player.handCardBox || constants.positionMap[player.position].card_box;
};

app.getOppositePosition = function getOppositePosition(pos) {
  const opposites = {
    'top-left': 'bottom-right',
    'top-right': 'bottom-left',
    'bottom-left': 'top-right',
    'bottom-right': 'top-left'
  };
  return opposites[pos];
};

app.getAdjacentFreePosition = function getAdjacentFreePosition(pos) {
  const adjacency = {
    'top-left':    ['top-right', 'bottom-left'],
    'top-right':   ['top-left', 'bottom-right'],
    'bottom-left': ['top-left', 'bottom-right'],
    'bottom-right':['top-right', 'bottom-left']
  };
  const candidates = adjacency[pos];
  return candidates.find(p => !state.usedPositions.includes(p));
};

app.getPlayerClass = function getPlayerClass(seatId) {
  const player = app.getPlayerFromId(seatId);
  return player ? `player-${player.color}` : '';
};

app.updatePlayerBlock = function updatePlayerBlock(player, isDealer = false) {
  const block = constants.positionMap[player.position].info_box;
  const identity = document.createElement("div");
  const name = document.createElement("span");
  const team = document.createElement("span");

  block.style.setProperty("--player-color-rgb", constants.PLAYER_ACCENT_RGB[player.color] || "100, 116, 139");

  identity.className = "player-identity";
  name.className = "player-name";
  team.className = "player-team";
  name.textContent = player.name;
  app.setTranslatedText(team, `lobby.team_${player.team}`);
  identity.append(name, team);
  block.replaceChildren(identity);

  if (isDealer) {
    const dealerBadge = document.createElement("span");
    dealerBadge.className = "dealer-badge";
    dealerBadge.dataset.i18nTitle = "game.dealer";
    dealerBadge.title = i18n.t("game.dealer");
    dealerBadge.setAttribute("aria-label", i18n.t("game.dealer"));
    block.appendChild(dealerBadge);
  }

  const playerClass = app.getPlayerClass(player.seatId);
  if (block.dataset.playerColorClass) block.classList.remove(block.dataset.playerColorClass);
  block.classList.add(playerClass);
  block.dataset.playerColorClass = playerClass;
};

app.toogleDealerOnPlayerBlock = function toogleDealerOnPlayerBlock(seatId) {
  const dealer = app.getPlayerFromId(seatId);
  dom.dealerName.textContent = dealer?.name || seatId;

  state.playerAssignments.forEach(player => {
    app.updatePlayerBlock(player, player.seatId === seatId);
  });
};

app.displayActivePlayer = function displayActivePlayer(seatId) {
  if (!seatId) {
    app.setTranslatedText(dom.currentPlayerName, "game.waiting_to_start");
    app.setTranslatedText(dom.turnInstruction, "game.next_action");
    return;
  }

  const player = app.getPlayerFromId(seatId);
  if (!player) return;

  const localSeat = player.name === state.local_player_name;

  if (localSeat) {
    app.setTranslatedText(dom.currentPlayerName, "game.player_you", {player: player.name});
    app.setTranslatedText(dom.turnInstruction, "game.your_turn");
    app.selectLocalSeat(seatId);
  } else {
    app.setRawText(dom.currentPlayerName, player.name);
    app.setTranslatedText(dom.turnInstruction, "game.waiting_for_player", {player: player.name});
  }

  dom.turnInstruction.classList.remove("error-state");
  dom.turnBanner.classList.toggle("your-turn", localSeat);

  state.playerAssignments.forEach(assignedPlayer => {
    const isActive = assignedPlayer.seatId === seatId;
    const infoBox = constants.positionMap[assignedPlayer.position].info_box;
    const boardCardBox = constants.positionMap[assignedPlayer.position].card_box;

    infoBox.classList.toggle("active", isActive);
    boardCardBox.classList.toggle("active", isActive);
  });
};

app.displayNoActivePlayers = function displayNoActivePlayers() {
	app.setTranslatedText(dom.currentPlayerName, "game.no_active_player");
	dom.turnBanner.classList.remove("your-turn");

  state.playerAssignments.forEach(player => {
    constants.positionMap[player.position].info_box.classList.remove("active");
    constants.positionMap[player.position].card_box.classList.remove("active");
  });
};

app.requestSpotSelection = function requestSpotSelection(spotOptions) {
  app.clearSpotSelection();

  console.debug("[requestSpotSelection] Highlighting positions", {
    seatId: state.local_player?.seatId,
    color: state.local_player?.color,
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

      app.clearSpotSelection();
      app.sendSpotSelection(state.local_player.seatId, selectedPositionId);
    };

    position.classList.add("glow");
    position.addEventListener("click", handler);
    state.selectableSpotHandlers.set(position, handler);
  });
};

app.setCardPlayEmphasis = function setCardPlayEmphasis(seatId, enabled) {
  const player = app.getPlayerFromId(seatId);
  if (!player) return;

  const playerPosition = constants.positionMap[player.position];

  playerPosition.info_box.classList.toggle("playing-card", enabled);
  playerPosition.card_box.classList.toggle("playing-card", enabled);
};

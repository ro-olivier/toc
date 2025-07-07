const nameInput = document.getElementById("name-input");
const gameIdInput = document.getElementById("game-id-input");
const createBtn = document.getElementById("create-btn");
const joinBtn = document.getElementById("join-btn");
const sendBtn = document.getElementById("send-btn");
const commandInput = document.getElementById("command-input");
const terminal = document.getElementById("terminal");
const startScreen = document.getElementById("start-screen");
const gameScreen = document.getElementById("game-screen");
const errorMsg = document.getElementById("error-msg");
const board = document.getElementById('board');


// Input-Output / WebSocket handling
let ws = null;

//##TODO: for now erery messages are just written into the terminal regardless of status but it will have to be displayed in a niver way, and some queries or errors may even not be displayed as text ut as interaction/animations on screen
function log(msg) {
  terminal.textContent += msg + "\n";
  terminal.scrollTop = terminal.scrollHeight;
}

function query(msg) {
  terminal.textContent += msg + "\n";
  terminal.scrollTop = terminal.scrollHeight;
}

function error(msg) {
  terminal.textContent += msg + "\n";
  terminal.scrollTop = terminal.scrollHeight;
}

function showGameUI() {
  startScreen.classList.add("hidden");
  gameScreen.classList.remove("hidden");
}

function showError(message) {
  errorMsg.textContent = message;
  errorMsg.classList.remove("hidden");
}

function clearError() {
  errorMsg.textContent = "";
  errorMsg.classList.add("hidden");
}

async function connectToGame(gameId, name) {
  clearError();
  const wsUrl = `wss://${window.location.host}/toc/ws/${gameId}/${name}`;
  try {
    ws = new WebSocket(wsUrl);
  } catch (err) {
    showError("Failed to construct WebSocket URL.");
    return;
  }

  ws.onopen = () => {
    log(`Connected to game ${gameId} as ${name}`);
    showGameUI();
  };

  ws.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      // Fallback for plaintext messages
      log(`> ${event.data}`);
      return;
    }

    switch (data.type) {
      case 'assign-player':
        new_player_position = assignPlayer(data.name, data.team, data.color);
        ws.send({'player_name': data.name, 'player_position':new_player_position});
        break;

     case "full_ui_state":
        data.players.forEach(p => {
          assignPlayer(p.name, p.team, p.color);
        });
        break;

      case 'move':
        placePieceOnSpot(data.playerId, data.spotIndex, getPlayerClass(data.playerId));
        break;

      case 'goal-move':
        placePieceOnGoalSpot(data.playerId, data.goalSpotIndex, getPlayerClass(data.playerId));
        break;

      case 'log':
        log(data.msg);
        break;

      case 'query':
        query(data.msg);
        break;

      case 'error':
        error(data.msg);
        break;

      default:
        log(`Unknown message: ${event.data}`);
    }
  };
  ws.onclose = () => log("WebSocket connection closed.");
  ws.onerror = () => {
    showError("Failed to join game. Game ID might be invalid.");
  };
}

createBtn.addEventListener("click", async () => {
  const name = nameInput.value.trim();
  if (!name) {
    showError("Please enter your name.");
    return;
  }

  clearError();
  try {
    const res = await fetch("/toc/api/create-game", {
      method: "POST"
    });
    const data = await res.json();
    const gameId = data.game_id;
    log(`Created game ID: ${gameId}`);
    await connectToGame(gameId, name);
  } catch (err) {
    showError("Failed to create game.");
  }
});

joinBtn.addEventListener("click", async () => {
  const name = nameInput.value.trim();
  const gameId = gameIdInput.value.trim();
  if (!name || !gameId) {
    showError("Please enter both your name and a Game ID.");
    return;
  }
  await connectToGame(gameId, name);
});

sendBtn.addEventListener("click", () => {
  const message = commandInput.value.trim();
  if (message && ws && ws.readyState === WebSocket.OPEN) {
    ws.send(message);
    log(`< ${message}`);
    commandInput.value = "";
  }
});

commandInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendBtn.click();
});

gameIdInput.addEventListener("input", () => {
  joinBtn.disabled = gameIdInput.value.trim() === "";
});


// User Interface handling
const regions = ['red', 'green', 'yellow', 'blue'];
const totalRegions = 4;
const spotsPerRegion = 17;
const totalSpots = totalRegions * spotsPerRegion;

const radius = 250;
const centerX = 300;
const centerY = 300;

const goalLabels = ['T', 'O', 'C', '!'];
const goalDistance = 40;

const spotElements = [];
const goalElements = [];

const positions = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
const positionMap = {
  'top-left':    { index: 2, el: document.getElementById('player-info-top-left') },
  'top-right':   { index: 3, el: document.getElementById('player-info-top-right') },
  'bottom-left': { index: 1, el: document.getElementById('player-info-bottom-left') },
  'bottom-right':{ index: 0, el: document.getElementById('player-info-bottom-right') },
};

const playerAssignments = []; // { name, team, color, position }
const usedColors = [];
const usedPositions = [];


function drawQuadrant(position, color) {
  const regionIndex = positionMap[position].index;
  const angleOffset = (regionIndex / 4) * 2 * Math.PI;

  const quadrantSpots = [];
  const quadrantGoals = [];

  for (let i = 0; i < 17; i++) {
    const angle = angleOffset + (i / 68) * 2 * Math.PI; // 68 = total spots in circle
    const x = centerX + radius * Math.cos(angle) - 15;
    const y = centerY + radius * Math.sin(angle) - 15;

    const spot = document.createElement('div');
    spot.className = `spot ${color}`;
    spot.style.left = `${x}px`;
    spot.style.top = `${y}px`;
    spot.innerText = i + 1;
    spot.id = `spot-${color}-${i}`;

    if (i === 0) {
      spot.classList.add('out-spot');

      for (let j = 0; j < 4; j++) {
        const innerRadius = radius - goalDistance * (j + 1);
        const gx = centerX + innerRadius * Math.cos(angle) - 15;
        const gy = centerY + innerRadius * Math.sin(angle) - 15;

        const goalSpot = document.createElement('div');
        goalSpot.className = `spot goal ${color}`;
        goalSpot.style.left = `${gx}px`;
        goalSpot.style.top = `${gy}px`;
        goalSpot.innerText = goalLabels[j];
        goalSpot.id = `goal-${color}-${j}`;

        board.appendChild(goalSpot);
        goalElements.push(goalSpot);
      }
    }

    board.appendChild(spot);
    quadrantSpots.push(spot);
  }

  // Update master spotElements list
  spotElements.push(...quadrantSpots);
}




function placePieceOnSpot(playerId, spotIndex, playerClass) {
  const old = document.querySelector(`[data-player="${playerId}"]`);
  if (old && old.parentElement) old.parentElement.removeChild(old);

  const piece = document.createElement('div');
  piece.classList.add('piece', playerClass);
  piece.dataset.player = playerId;

  const spot = spotElements[spotIndex];
  spot.appendChild(piece);
}

function placePieceOnGoalSpot(playerId, goalSpotIndex, playerClass) {
  const old = document.querySelector(`[data-player="${playerId}"]`);
  if (old && old.parentElement) old.parentElement.removeChild(old);

  const piece = document.createElement('div');
  piece.classList.add('piece', playerClass);
  piece.dataset.player = playerId;

  const spot = goalElements[goalSpotIndex];
  spot.appendChild(piece);
}

function assignPlayer(name, team, color) {
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
  drawQuadrant(newPlayer.position, color);

  return newPlayer.position
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

function updatePlayerBlock(player) {
  const block = positionMap[player.position].el;
  block.innerHTML = `${player.name}<br>Team ${player.team}<br>${player.color}`;
  block.style.backgroundColor = player.color;
}

function updateRegionColor(position, color) {
  const regionIndex = positionMap[position].index;
  const regionSpots = spotElements.slice(regionIndex * 17, regionIndex * 17 + 17);
  const regionGoalSpots = goalElements.slice(regionIndex * 4, regionIndex * 4 + 4);
  regionSpots.forEach(s => s.style.backgroundColor = color);
  regionGoalSpots.forEach(s => s.style.backgroundColor = color);
}

function getPlayerClass(playerId) {
  const player = playerAssignments.find(p => p.name === playerId);
  return player ? `player-${player.color[0]}` : '';
}
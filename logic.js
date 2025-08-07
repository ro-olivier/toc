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
let local_player_name = null;
let local_game_Id = null;

let stored_player_name = window.localStorage.getItem("session_player_name");
let stored_game_id = window.localStorage.getItem("session_game_ID")

nameInput.value = stored_player_name !== null ? stored_player_name : '';
gameIdInput.value = stored_game_id !== null ? stored_game_id : '';
joinBtn.disabled = (stored_player_name && stored_game_id) !== null ? false : true;

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

async function connectToGame(gameId, name, rejoin = false) {
  clearError();
  const wsUrl = `wss://${window.location.host}/toc/ws/${gameId}/${name}`;
  try {
    ws = new WebSocket(wsUrl);
  } catch (err) {
    console.error(err);
    showError("Failed to construct WebSocket URL.");
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
        log(`Connected to game ${gameId} as ${name}`);
        local_player_name = name;
        local_game_Id = gameId;
        showGameUI();
        break;
      
      case 'assign-player':
        assignPlayer(data.name, data.team, data.color);
        break;

      case "full_ui_state":
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
        break;

      case "receive-card-from-friend":
        replaceCard(data.value, data.suit);
        break

      case 'move':
        placePieceOnSpot(data.playerId, data.spotIndex);
        break;

      case 'fold':
        foldAllCardsOfPlayer(data.playerId);
        log(data.msg);
        break;

      case 'log':
        log(data.msg);
        break;

      case 'forced-play':
        log(data.msg);
        break;

      case 'next-player':
        displayActivePlayer(data.playerId);
        log(data.msg);
        break;

      case 'play':
        removeCard(data.playerId, data.value, data.suit);
        movePieceFromSpotToSpot(data.playerId, data.origin, data.target);
        log(data.msg);
        break;

      case 'reject-card-selection':
        log(data.msg);
        showAllCardUp();
        break;

      case 'query-origin':
        //log(data.msg);
        requestSpotSelection(data.originOptions);
        break;

      case 'query-target':
        //log(data.msg);
        requestSpotSelection(data.targetOptions);
        break;

      case 'query-card':
        //log(data.msg);
        requestCardSelection();
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
  
  ws.onclose = (event) => {

    switch (event.code) {
      case 4001:
        showError("Invalid game ID.");
        break;
      case 4002:
        showError("Player name already taken.");
        break;
      case 1006:
        showError("Could not connect to server.");
        break;
      default:
        showError(`Connection closed (code ${event.code}).`);
    }
  };

  ws.onerror = () => {
    showError("WebSocket Error!");
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

function sendCardSelection(player_name, rank, suit) {
  const message = {"id": crypto.randomUUID(), "type": "card_selection", "name": player_name, "value": rank, "suit": suit};
  const message_json = JSON.stringify(message);
  console.log('[sendCardSelection] Sending following content to back-end:' + message_json);
  ws.send(message_json);
}

function sendSpotSelection(player_name, spot) {
  const message = {"id": crypto.randomUUID(), "type": "spot_selection", "name": player_name, "result": spot};
  const message_json = JSON.stringify(message);
  console.log('[sendSpotSelection] Sending following content to back-end:' + message_json);
  ws.send(message_json);
}


// User Interface handling
const regions = ['red', 'green', 'yellow', 'blue'];
const totalRegions = 4;
const spotsPerRegion = 17;
const totalSpots = totalRegions * spotsPerRegion;

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

function drawQuadrant(position, color) {
  const regionIndex = positionMap[position].index;
  const angleOffset = (regionIndex / 4) * 2 * Math.PI;

  const quadrantSpots = [];
  const quadrantHouses = [];

  for (let i = 0; i < 17; i++) {
    const angle = angleOffset + (i / 68) * 2 * Math.PI; // 68 = total spots in circle
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

      for (let j = 0; j < 4; j++) {
        const innerRadius = radius - houseDistance * (j + 1);
        const gx = centerX + innerRadius * Math.cos(angle) - 15;
        const gy = centerY + innerRadius * Math.sin(angle) - 15;

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

function movePieceFromSpotToSpot(playerId, originSpot, targetSpot) {
  const playerClass = getPlayerClass(playerId);

  if (originSpot !== targetSpot) {
    // This is the case when the move played is anything other than an "OUT" move, in which case we have to remove a piece from a previous spot before adding it to the new spot
    const origin_spot =  document.getElementById(originSpot);
    const old = origin_spot.querySelector(`[data-player="${playerId}"]`);
    if (old && old.parentElement) { // this test is almost certainly unnecessary, but just in case, ...we don't want to go change the content of other spots on the board
      old.parentElement.innerHTML = (parseInt(origin_spot.index) % 17) == 0 ? '' : parseInt(origin_spot.index); // reseting the value inside the spot
    }
  }

  const target_spot = document.getElementById(targetSpot);
  const piece = document.createElement('div');
  piece.classList.add('piece', playerClass);
  piece.dataset.player = playerId;
  
  target_spot.innerHTML = '';
  target_spot.appendChild(piece);
}

function assignPlayer(name, team, color) {

  // if player is already in the playerAssignements array, don't add it again. This can happen because the full_ui uses the assignPlayer method (#TODO: refactor this?)
  player_test = playerAssignments.find(p => p.name === name);
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
  // If 4 players have joined, the front-end needs to give the back-end the order in which the players where "seated" at the table so that the back-end can manage who plays and when / in what order. 
  // We could duplicate the seating order logic in the backend (or have the backend manage it entirely) but this is simplier that way and having the front-end do it is not that big of a risk because if a malicious user tries to mess up with this it's going to be immediately obvious to the other team since the order in which the back-end will make the users play won't match the order in which they are seated.
  if (playerAssignments.length === 4) {

    // We get players based on where they are positioned in clock-wise order starting from top-left
    p1 = playerAssignments.find(p => p.position === 'top-left');
    p2 = playerAssignments.find(p => p.position === 'top-right');
    p3 = playerAssignments.find(p => p.position === 'bottom-right');
    p4 = playerAssignments.find(p => p.position === 'bottom-left');
    
    const message = {"id": crypto.randomUUID(), "type": "everybody_is_here", "order": [p1.name, p2.name, p3.name, p4.name]};
    const message_json = JSON.stringify(message);
    console.log('[assignPlayer - everybody_is_here] Sending following content to back-end:' + message_json);
    ws.send(message_json);
  }

  usedColors.push(color);
  usedPositions.push(newPlayer.position);

  updatePlayerBlock(newPlayer);
  positionMap[newPlayer.position].card_box.style.display = 'flex';
  positionMap[newPlayer.position].info_box.style.display = 'flex';
  drawQuadrant(newPlayer.position, color);
}

function hideCardBlock(playerId) {
  const player = playerAssignments.find(p => p.name === playerId);
  if (!player) {
    console.warn(`No player found with ID "${playerId}"`, JSON.stringify(playerAssignments));
    return; // or handle this gracefully
  }
  positionMap[player.position].card_box.style.display = 'none';
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

function updatePlayerBlock(player, isDealer = false) {
  const block = positionMap[player.position].info_box;
  block.innerHTML = `${player.name}<br>Team ${player.team}`;
  if (isDealer) block.innerHTML += '<br><i>Dealer</i>'
  const playerClass = getPlayerClass(player.name);
  block.classList.add(playerClass);
}

function updateRegionColor(position, color) {
  const regionIndex = positionMap[position].index;
  const regionSpots = spotElements.slice(regionIndex * 17, regionIndex * 17 + 17);
  const regionHouseSpots = houseElements.slice(regionIndex * 4, regionIndex * 4 + 4);
  regionSpots.forEach(s => s.classList.add(color));
  regionHouseSpots.forEach(s => s.classList.add(color));
}

function toogleDealerOnPlayerBlock(playerId) {
  playerAssignments.forEach(p => {
    if (p.name === playerId) {
      updatePlayerBlock(p, true);
    } else {
      updatePlayerBlock(p);
    }
  });
}

function displayActivePlayer(playerId) {
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
  playerAssignments.forEach(p => {
    const block = positionMap[p.position].info_box;
    block.classList.remove('active');
  });
}

function getPlayerClass(playerId) {
  const player = playerAssignments.find(p => p.name === playerId);
  return player ? `player-${player.color}` : '';
}

function setupPlayerCards(playerId, cards) {
  const player = playerAssignments.find(p => p.name === playerId);
  if (!player) {
    console.warn(`No player found with ID "${playerId}"`, JSON.stringify(playerAssignments));
    return; // or handle this gracefully
  }
  positionMap[player.position].card_box.querySelectorAll('.card-container').forEach((cardContainer, i) => {

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

function displayHiddenCards(playerId, number_of_cards) {
  const player = playerAssignments.find(p => p.name === playerId);
  if (!player) {
    console.warn(`No player found with ID "${playerId}"`, JSON.stringify(playerAssignments));
    return; // or handle this gracefully
  }
  const block = positionMap[player.position].card_box;
  
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
  const player = playerAssignments.find(p => p.name === local_player_name);
  if (!player) {
    console.warn(`No player found with ID "${playerId}"`, JSON.stringify(playerAssignments));
    return; // or handle this gracefully
  }
  const block = positionMap[player.position].card_box;
  block.querySelectorAll(".card-container").forEach(cardContainer => {
    cardContainer.classList.add('flip');
  });
}

function foldAllCardsOfPlayer(playerId) {
  const player = playerAssignments.find(p => p.name === playerId);
  if (!player) {
    console.warn(`No player found with ID "${playerId}"`, JSON.stringify(playerAssignments));
    return; // or handle this gracefully
  }
  const block = positionMap[player.position].card_box;
  block.querySelectorAll(".card-container").forEach((cardContainer, i) => {
    setTimeout(100);
    requestAnimationFrame(() => {
      cardContainer.classList.remove('flip');
    });
    block.removeChild(cardContainer);
    cardContainer.removeEventListener('click', clickCardClickListener);
    block.style.display = 'none';
  });
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
  const player = playerAssignments.find(p => p.name === playerId);
  if (!player) {
    console.warn(`No player found with ID "${playerId}"`, JSON.stringify(playerAssignments));
    return; // or handle this gracefully
  }
  const block = positionMap[player.position].card_box;

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

// Click anywhere outside of cards to cancel card selection
document.addEventListener('click', () => {
  if (selectedCard) {
    selectedCard.classList.remove('selected');
    selectedCard = null;
  }
});

function requestSpotSelection(spotOptions) {

  spotOptions.forEach((option) => {
    piece = document.getElementById(option)
    piece.classList.add('glow');
    piece.addEventListener('click', () => {

      event.stopPropagation(); // Prevent document click from firing
      removeGlowOnEverySpot();
      sendSpotSelection(local_player_name, event.currentTarget.id);
      

    });
  });

}

function requestCardSelection() {
  const player = playerAssignments.find(p => p.name === local_player_name);
  if (!player) {
    console.warn(`No player found with ID "${local_player_name}"`, JSON.stringify(playerAssignments));
    return; // or handle this gracefully
  }
  const block = positionMap[player.position].card_box;

  block.querySelectorAll('.card-container').forEach(c => {
    c.addEventListener('click', clickCardClickListener);
    console.log('[requestCardSelection] Added clickCardClickListener.');
  });
          
}

function removeGlowOnEverySpot() {
  document.querySelectorAll('.glow').forEach((spot) => {
    spot.classList.remove('glow');
  });
}


function simulate(gameId = local_game_Id) {

  // player 3
  const wsUrl3 = `wss://${window.location.host}/toc/ws/${gameId}/p3`;
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
  const wsUrl4 = `wss://${window.location.host}/toc/ws/${gameId}/p4`;
  try {
    ws4 = new WebSocket(wsUrl4);
  } catch (err) {
    showError("Failed to construct WebSocket URL for player 4.");
  }

  ws4.onopen = () => {
    log(`Simulated p4 joined game ${gameId}.`);
  };

}
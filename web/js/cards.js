import {app, constants, dom, i18n, state} from "./context.js";

app.hideCardBlock = function hideCardBlock(seatId) {
  const cardBox = app.getCardBoxFromId(seatId);
  const boardCardBox = app.getBoardCardBoxFromId(seatId);
  const boxes = new Set([cardBox, boardCardBox]);

  boxes.forEach(block => {
    if (!block) return;

    block.replaceChildren();
    block.dataset.cardCount = "0";
    block.style.display = "none";
  });

  if (app.isLocalSeat(seatId)) {
    app.setTranslatedText(dom.emptyHandMessage, "game.waiting_for_next_deal");
    dom.emptyHandMessage.classList.remove("hidden");
  }
};

app.setupPlayerCards = function setupPlayerCards(playerId, cards) {
  const cardBox = app.getCardBoxFromId(playerId)
  cardBox.querySelectorAll('.card-container').forEach((cardContainer, i) => {

    const cardBlock = cardContainer.querySelector('.card');

    const rank = cards[i].value
    const suit = cards[i].suit

    cardBlock.appendChild(app.createCardFront(rank, suit));

    cardContainer.rank = rank;
    cardContainer.suit = suit;
    cardContainer.playerId = playerId;

    setTimeout(() => {
      cardContainer.classList.add('flip');
    }, 250 * i);
  });
};

app.createCardFront = function createCardFront(rank, suit) {
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
};

app.createVisibleCardContainer = function createVisibleCardContainer(rank, suit) {
  const cardContainer = document.createElement("div");
  const card = document.createElement("div");

  cardContainer.className = "card-container flip";
  card.className = "card";

  card.appendChild(app.createCardFront(rank, suit));
  cardContainer.appendChild(card);

  return cardContainer;
};

app.clearDiscardPile = function clearDiscardPile() {
  state.cardAnimationId++;
  dom.discardPileCard.replaceChildren();
  delete dom.discardPileCard.dataset.rank;
  delete dom.discardPileCard.dataset.suit;
};

app.showCardOnDiscardPile = function showCardOnDiscardPile(rank, suit) {
  state.cardAnimationId++;

  dom.discardPileCard.replaceChildren(app.createVisibleCardContainer(rank, suit));
  dom.discardPileCard.dataset.rank = rank;
  dom.discardPileCard.dataset.suit = suit;
};

app.animateCardToDiscardPile = function animateCardToDiscardPile(seatId, rank, suit) {
  const boardCardBox = app.getBoardCardBoxFromId(seatId);
  const regularCardBox = app.getCardBoxFromId(seatId);
  const sourceCard = boardCardBox?.querySelector(".card-container") || regularCardBox?.querySelector(".card-container");
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (!sourceCard || !dom.discardPileCard || prefersReducedMotion || typeof sourceCard.animate !== "function") {
    app.showCardOnDiscardPile(rank, suit);
    return;
  }

  const sourceBounds = sourceCard.getBoundingClientRect();
  const targetBounds = dom.discardPileCard.getBoundingClientRect();

  if (sourceBounds.width === 0 || sourceBounds.height === 0 || targetBounds.width === 0 || targetBounds.height === 0) {
    app.showCardOnDiscardPile(rank, suit);
    return;
  }

  const expandedLeft = sourceBounds.left + sourceBounds.width / 2 - targetBounds.width / 2;
  const expandedTop = sourceBounds.top + sourceBounds.height / 2 - targetBounds.height / 2;
  const animationId = ++state.cardAnimationId;
  const flyingCard = app.createVisibleCardContainer(rank, suit);

  flyingCard.classList.add("played-card-animation");
  flyingCard.style.left = `${sourceBounds.left}px`;
  flyingCard.style.top = `${sourceBounds.top}px`;
  flyingCard.style.width = `${sourceBounds.width}px`;
  flyingCard.style.height = `${sourceBounds.height}px`;

  document.body.appendChild(flyingCard);
  app.setCardPlayEmphasis(seatId, true);

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
    app.setCardPlayEmphasis(seatId, false);

    if (animationId === state.cardAnimationId) {
      app.showCardOnDiscardPile(rank, suit);
    }
  });
};

app.renderHiddenCards = function renderHiddenCards(block, numberOfCards) {
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
};

app.displayHiddenCards = function displayHiddenCards(seatId, numberOfCards) {
  const cardBox = app.getCardBoxFromId(seatId);
  const boardCardBox = app.getBoardCardBoxFromId(seatId);

  app.renderHiddenCards(cardBox, numberOfCards);

  if (boardCardBox !== cardBox) {
    app.renderHiddenCards(boardCardBox, numberOfCards);
  }

  if (app.isLocalSeat(seatId) && numberOfCards > 0) {
    dom.emptyHandMessage.classList.add("hidden");
  }
};

app.showAllCardUp = function showAllCardUp() {
  if (!state.local_card_box) return;

  state.local_card_box.querySelectorAll(".card-container").forEach(cardContainer => {
    cardContainer.classList.add('flip');
  });
};

app.foldAllCardsOfPlayer = function foldAllCardsOfPlayer(playerId) {
  const block = app.getCardBoxFromId(playerId);
  block.querySelectorAll(".card-container").forEach((cardContainer, i) => {
    setTimeout(100);
    requestAnimationFrame(() => {
      cardContainer.classList.remove('flip');
    });
    block.removeChild(cardContainer);
    cardContainer.removeEventListener('click', app.clickCardClickListener);
    block.style.display = 'none';
  });

  if (app.isLocalSeat(playerId)) {
    app.setTranslatedText(dom.emptyHandMessage, "game.waiting_for_next_deal");
    dom.emptyHandMessage.classList.remove("hidden");
  }

  block.dataset.cardCount = "0";

  const boardCardBox = app.getBoardCardBoxFromId(playerId);

  if (boardCardBox && boardCardBox !== block) {
    boardCardBox.replaceChildren();
    boardCardBox.dataset.cardCount = "0";
    boardCardBox.style.display = "none";
  }
};

app.replaceCard = function replaceCard(seatId, rank, suit) {
  const cardContainer = state.pendingExchangeCards.get(seatId);
  state.pendingExchangeCards.delete(seatId);

  if (!cardContainer) {
    console.warn(`No pending exchanged card was found for seat "${seatId}".`);
    return;
  }

  const previousCardFront = cardContainer.querySelector(".card-front");
  const cardBlock = cardContainer.querySelector(".card");

  previousCardFront?.remove();
  cardBlock.appendChild(app.createCardFront(rank, suit));

  cardContainer.rank = rank;
  cardContainer.suit = suit;

  requestAnimationFrame(() => {
    cardContainer.classList.add('flip');
  });
};

app.removeCard = function removeCard(seatId, value, suit) {
  const block = app.getCardBoxFromId(seatId);
  if (!block) return;

  let cardToRemove = null;

  if (app.isLocalSeat(seatId)) {
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

  const boardCardBox = app.getBoardCardBoxFromId(seatId);

  if (boardCardBox && boardCardBox !== block) {
    boardCardBox.firstElementChild?.remove();
    boardCardBox.dataset.cardCount = String(boardCardBox.children.length);

    if (boardCardBox.children.length === 0) {
      boardCardBox.style.display = "none";
    }
  }
};

app.switchCardClickListener = function switchCardClickListener(event) {
  const rank = event.currentTarget.rank;
  const suit = event.currentTarget.suit;
  const playerId = event.currentTarget.playerId;
  const cardContainer = event.currentTarget;

  event.stopPropagation(); // Prevent document click from firing
  if (state.selectedCard === event.currentTarget) {
    // Second click confirms selection
    cardContainer.classList.remove('selected');
    cardContainer.classList.remove('flip');
    state.pendingExchangeCards.set(playerId, cardContainer);
    state.selectedCard = null;
    app.disableCardSelection();
    // only triggering the WS call to replace the card after twice the amount of time it takes for the front-to-back flip animation to execute, to make sure we do play the animation
    setTimeout(() => {
      app.sendCardSelection(playerId, rank, suit);
    }, 500);

  } else {
    // First click triggers highlight
    if (state.selectedCard) state.selectedCard.classList.remove('selected');
    state.selectedCard = cardContainer;
    cardContainer.classList.add('selected');
  }
};

app.clickCardClickListener = function clickCardClickListener(event) {
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

  if (state.selectedCard === cardContainer) {
    // Second click confirms selection
    const seatId = state.local_player.seatId;

    cardContainer.classList.remove('selected');
    cardContainer.classList.remove('flip');
    state.selectedCard = null;
    app.disableCardSelection();
    app.sendCardSelection(seatId, t_value, t_suit);
  } else {
    // First click triggers highlight
    if (state.selectedCard) state.selectedCard.classList.remove("selected");
    state.selectedCard = cardContainer;
    cardContainer.classList.add('selected');
  }
};

app.disableCardSelection = function disableCardSelection() {
  dom.localHandSlot.querySelectorAll(".card-box.local-hand").forEach(cardBox => {
    cardBox.classList.remove("awaiting-selection");

    cardBox.querySelectorAll(".card-container").forEach(cardContainer => {
      cardContainer.classList.remove("hover-effect", "selected");
      cardContainer.removeEventListener("click", app.clickCardClickListener);
      cardContainer.removeEventListener("click", app.switchCardClickListener);
    });
  });

  state.selectedCard = null;
};

app.enableCardSelection = function enableCardSelection(listener) {
  app.disableCardSelection();

  if (!state.local_card_box) return;

  state.local_card_box.classList.add("awaiting-selection");

  state.local_card_box.querySelectorAll(".card-container").forEach(cardContainer => {
    cardContainer.classList.add("hover-effect");
    cardContainer.addEventListener("click", listener);
  });
};

app.requestCardSelection = function requestCardSelection() {
  app.enableCardSelection(app.clickCardClickListener);
};

app.requestCardExchangeSelection = function requestCardExchangeSelection() {
  app.enableCardSelection(app.switchCardClickListener);
};

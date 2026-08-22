(() => {
  const TRANSLATIONS = {
    en: {
      app: {
        title: "Play Toc Online!",
        name: "TOC Online",
      },
      language: {
        label: "Language",
        en: "English",
        fr: "Français",
      },
      common: {
        reset: "Reset",
        enabled: "Enabled",
        disabled: "Disabled",
        error_prefix: "Error: ",
      },
      gameplay: {
        game_starting: "Four players have joined: the game is starting!",
        deal_started: "Deal {deal} starts with {dealer} as dealer.",
        deal_finished: "Deal {deal} is finished.",
        turn_ended: "{player}'s turn is finished.",
        folded_player_skipped: "{player} previously folded and is skipped.",
        card_exchange_complete: "You gave {givenCard} to your teammate and received {receivedCard}. The round will start when the other team finishes exchanging cards.",
        team_won: "{playerOne} and {playerTwo} win!",
        next_player: "Moving on to {player} from team {team}, playing {color}.",
        player_folded: "{player} has no available move and must fold.",
        card_discarded: "{player} cannot make a move and discards one card.",
        forced_play: "You have only one legal move, so you must play {card}.",
        seven_split_started: "{player} played {card} and is starting a seven split.",
        piece_deployed: "{player} played {card} and deployed a piece on {target}.",
        pieces_switched: "{player} played {card} and switched the pieces on {origin} and {target}.",
        piece_moved: "{player} played {card}, moving {pieceOwner}'s piece from {origin} to {target}.",
      },
      prompts: {
        choose_card: "What card do you want to play?",
        card_unplayable: "You cannot play that card right now!",
        choose_origin: "What piece do you want to play this card on?",
        choose_target: "Where do you want to move this piece?",
        exchange_card: "Please choose a card to give to your teammate.",
        discard_card: "You cannot make a move. Choose one card to discard.",
        seven_hop: "Do you want to seven-hop from {origin} to {target}?",
      },
      start: {
        name_placeholder: "Enter your name",
        game_id_placeholder: "Enter Game ID (for joining)",
        create_game: "Create Game",
        join_game: "Join Game",
      },
      rules: {
        new_game_title: "Rules for the new game",
        loading: "Loading available rules…",
        load_error: "Rules could not be loaded.",
        custom_title: "Custom rules",
        custom_intro: "Settings start from the default preset.",
        custom_option: "Custom rules",
        custom_summary: "Configure every rule for this game.",
        preset_summary: "Uses the {preset} preset.",
        display_title: "Game rules",

        presets: {
          montsurvent: "Montsurvent",
          custom: "Custom",
        },

        groups: {
          round: "Round and cards",
          board: "Board",
          special: "Special cards",
          seven: "Seven and hopping",
        },

        labels: {
          card_exchange: "Exchange cards with teammate",
          shuffle_cards: "Shuffle cards",
          rotation: "Rotation direction",
          deal_card_counts: "Dealing schedule",
          cannot_play_folds_entire_hand: "No move folds entire hand",
          exit_spot_is_protected_and_blocking: "Exit spots are protected and blocking",
          house_spots_are_blocking_and_protected: "House spots are protected and blocking",
          landing_on_occupied_spot_kicks_piece: "Landing on an occupied spot kicks",
          track_region_length: "Spots per region",
          enter_house_at_spot: "House entry position",
          four_can_move_backward: "Four can move backward",
          can_enter_house_backward: "Allow backward house entry",
          five_behaviour: "Five behaviour",
          jacks_can_switch: "Jacks can switch pieces",
          jacks_can_switch_then_seven_hop: "Jack switch can seven-hop",
          ace_values: "Ace movement values",
          king_kicks_pieces_on_path: "King kicks pieces on its path",
          seven_can_split: "Seven can be split",
          seven_split_kicks_pieces_on_path: "Seven split kicks pieces on path",
          seven_hopping: "Seven-hopping",
          five_hop_decider: "Who decides hopping after a Five",
          seven_hopping_on_four_backward_goes_backward: "Backward Four hops backward",
        },

        descriptions: {
          card_exchange: "At the beginning of each deal, teammates choose and exchange one card.",
          shuffle_cards: "Controls when the discard pile is shuffled before being used as the next deck.",
          rotation: "Sets the direction used for turns, dealing and dealer rotation.",
          deal_card_counts: "Sets how many cards each player receives during the three deals of a deck cycle.",
          cannot_play_folds_entire_hand: "When enabled, a player with no legal move discards their whole hand. Otherwise they choose one card to discard.",
          exit_spot_is_protected_and_blocking: "A newly deployed piece cannot be kicked or Jack-switched and blocks pieces from crossing its position. A Five can still force it forward.",
          house_spots_are_blocking_and_protected: "Pieces cannot cross or land on occupied house spots. When disabled, landing on an occupied house spot kicks its piece.",
          landing_on_occupied_spot_kicks_piece: "When enabled, the occupying piece is kicked, even if it belongs to the acting player or their teammate. Otherwise the move is illegal.",
          track_region_length: "Sets the number of ordinary track positions associated with each player colour.",
          enter_house_at_spot: "Sets the track position from which a piece may branch into its house lane.",
          four_can_move_backward: "Allows a Four to move a piece either four positions forward or four positions backward.",
          can_enter_house_backward: "Allows a backward move crossing the configured house entrance to enter the house lane.",
          five_behaviour: "A Five can force an opponent piece forward, move one of the player's pieces normally, or allow both behaviours.",
          jacks_can_switch: "Allows a Jack to switch one of the player's track pieces with another player's track piece. Otherwise a Jack moves eleven positions.",
          jacks_can_switch_then_seven_hop: "Allows the acting player's switched piece to seven-hop when the switch places it on a seventh position.",
          ace_values: "Sets whether an Ace moves one position, eleven positions, or offers either value.",
          king_kicks_pieces_on_path: "When a King moves thirteen positions, every unprotected piece crossed on the way is kicked.",
          seven_can_split: "Allows the seven forward steps to be distributed among several pieces. All seven steps must still be completed.",
          seven_split_kicks_pieces_on_path: "When enabled, pieces are kicked after every step. Otherwise only each moved piece's final position can kick.",
          seven_hopping: "Controls whether landing on a seventh position may or must hop the piece to the next seventh position.",
          five_hop_decider: "When a Five forces an opponent onto a seventh position, this chooses who decides whether the optional hop occurs.",
          seven_hopping_on_four_backward_goes_backward: "Makes a seven-hop triggered by a backward Four go to the previous seventh position instead of the next one.",
        },

        choices: {
          shuffle_cards: {
            never: "Never",
            on_dealer_change: "When dealer changes",
            on_dealer_cycle: "After a dealer cycle",
          },
          rotation: {
            clockwise: "Clockwise",
            counterclockwise: "Counterclockwise",
          },
          deal_card_counts: {
            "5_4_4": "5 / 4 / 4",
            "4_5_4": "4 / 5 / 4",
            "4_4_5": "4 / 4 / 5",
          },
          track_region_length: {
            "18": "18 spots",
            "16": "16 spots",
          },
          enter_house_at_spot: {
            "18": "Spot 18",
            "16": "Spot 16",
          },
          five_behaviour: {
            force_move_opponent: "Force an opponent forward",
            normal_move_by_five: "Normal five-step move",
            both: "Both behaviours",
          },
          seven_hopping: {
            disabled: "Disabled",
            optional: "Optional",
            forced: "Forced",
          },
          five_hop_decider: {
            acting_player: "Acting player",
            piece_owner: "Piece owner",
          },
          ace_values: {
            "1_11": "1 or 11",
            "1": "1",
            "11": "11",
          },
        },
      },
      lobby: {
        game: "Game",
        players_count: "{count} / {capacity} players",
        choose_seat: "Choose your seat",
        team: "Team",
        team_0: "Team 0",
        team_1: "Team 1",
        colour: "Colour",
        confirm_choices: "Confirm choices",
        confirming: "Confirming your choices…",
        choosing: "Choosing…",
        configured_choice: "Team {team} · {color}",
        confirmed_waiting: "Your choices are confirmed. Waiting for the other players…",
        joining: "Joining lobby…",
        choose_while_waiting: "Choose your team and colour while the other players join.",
        choose_to_start: "Choose your team and colour to start the game.",
        errors: {
          already_confirmed: "Your lobby choices have already been confirmed.",
          invalid_team: "Please choose a valid team.",
          invalid_color: "Please choose a valid colour.",
          team_full: "Team {team} is already full.",
          color_taken: "The colour {color} has already been selected.",
        },
      },
      game: {
        dealer: "Dealer",
        waiting: "Waiting…",
        current_turn: "Current turn",
        waiting_to_start: "Waiting for the game to start",
        next_action: "The next action will appear here.",
        history: "Game history",
        latest_actions: "Latest actions",
        live: "Live",
        debug_tools: "Debug tools",
        command_placeholder: "Type a command",
        send: "Send",
        your_cards: "Your cards",
        your_hand: "Your hand",
        hand_instruction: "Select a card, then confirm it with a second click.",
        cards_when_round_starts: "Cards will appear when the round starts.",
        waiting_for_next_deal: "Waiting for the next deal.",
        your_turn: "It is your turn.",
        waiting_for_player: "Waiting for {player} to play.",
        player_you: "{player} (you)",
        no_active_player: "No active player",
        game_over: "Game over",
        cancel_selection: "Cancel card selection",
        returning_to_cards: "Returning to card selection…",
      },
      connection: {
        connected: "Connected",
        disconnected: "Disconnected",
        connected_as: "Connected to game {gameId} as {player}.",
        created_game: "Created game ID: {gameId}",
        rejoined_self: "You successfully rejoined the game in team {team} with colour {color}!",
        player_rejoined: "{player} rejoined the game.",
        player_disconnected: "{player} disconnected.", 
      },
      colors: {
        red: "Red",
        blue: "Blue",
        green: "Green",
        yellow: "Yellow",
      },
      errors: {
        name_required: "Please enter your name.",
        rules_load_failed: "Could not load game rules. Please reload the page.",
        game_creation_failed: "Failed to create game.",
        name_and_game_id_required: "Please enter both your name and a Game ID.",
        websocket_url_failed: "Failed to construct WebSocket URL.",
        invalid_game_id: "Invalid game ID.",
        player_name_taken: "Player name already taken.",
        game_full: "This game already has four players.",
        server_unreachable: "Could not connect to server.",
        connection_closed: "Connection closed (code {code}).",
        websocket_error: "WebSocket error.",
        connection_not_open: "The connection is not open.",
        internal_game_error: "The game stopped because of an internal server error.",
        invalid_json_message: "The server received an invalid JSON message.",
        invalid_message_format: "The server received an invalid message format.",
        creation_data_object: "Game creation data must be an object.",
        unknown_creation_fields: "Unknown game creation fields: {fields}",
        invalid_game_configuration: "The selected game configuration is invalid.",
        unknown_message_type: "Unknown message type: {messageType}.",
        invalid_resume_token: "This browser does not have valid credentials for that player.",
        lobby_expired: "This lobby expired after 15 minutes. Create a new game or join another one.",
        game_suspended: "This game was suspended after a period of inactivity. You can resume it using the same name and Game ID.",
      },
    },

    fr: {
      app: {
        title: "Jouer au Toc en ligne !",
        name: "TOC en ligne",
      },
      language: {
        label: "Langue",
        en: "English",
        fr: "Français",
      },
      common: {
        reset: "Réinitialiser",
        enabled: "Activé",
        disabled: "Désactivé",
        error_prefix: "Erreur : ",
      },
      gameplay: {
        game_starting: "Quatre joueurs ont rejoint la partie : la partie commence !",
        deal_started: "La donne {deal} commence avec {dealer} comme donneur.",
        deal_finished: "La donne {deal} est terminée.",
        turn_ended: "Le tour de {player} est terminé.",
        folded_player_skipped: "{player} a déjà défaussé sa main et passe son tour.",
        card_exchange_complete: "Vous avez donné {givenCard} à votre partenaire et reçu {receivedCard}. La manche commencera lorsque l'autre équipe aura terminé son échange.",
        team_won: "{playerOne} et {playerTwo} gagnent !",
        next_player: "C'est au tour de {player}, de l'équipe {team}, qui joue la couleur {color}.",
        player_folded: "{player} ne peut effectuer aucun déplacement et doit défausser sa main.",
        card_discarded: "{player} ne peut effectuer aucun déplacement et défausse une carte.",
        forced_play: "Vous n'avez qu'un seul déplacement possible : vous devez jouer {card}.",
        seven_split_started: "{player} joue {card} et commence un Sept partagé.",
        piece_deployed: "{player} joue {card} et sort un pion sur {target}.",
        pieces_switched: "{player} joue {card} et échange les pions situés sur {origin} et {target}.",
        piece_moved: "{player} joue {card} et déplace le pion de {pieceOwner} de {origin} vers {target}.",
      },
      prompts: {
        choose_card: "Quelle carte voulez-vous jouer ?",
        card_unplayable: "Vous ne pouvez pas jouer cette carte maintenant !",
        choose_origin: "Sur quel pion voulez-vous jouer cette carte ?",
        choose_target: "Où voulez-vous déplacer ce pion ?",
        exchange_card: "Choisissez une carte à donner à votre partenaire.",
        discard_card: "Vous ne pouvez effectuer aucun déplacement. Choisissez une carte à défausser.",
        seven_hop: "Voulez-vous effectuer un saut de sept de {origin} vers {target} ?",
      },
      start: {
        name_placeholder: "Entrez votre nom",
        game_id_placeholder: "Identifiant de partie (pour rejoindre)",
        create_game: "Créer une partie",
        join_game: "Rejoindre une partie",
      },
      rules: {
        new_game_title: "Règles de la nouvelle partie",
        loading: "Chargement des règles disponibles…",
        load_error: "Impossible de charger les règles.",
        custom_title: "Règles personnalisées",
        custom_intro: "Les réglages partent du preset par défaut.",
        custom_option: "Règles personnalisées",
        custom_summary: "Configurez chaque règle pour cette partie.",
        preset_summary: "Utilise le preset {preset}.",
        display_title: "Règles de la partie",

        presets: {
          montsurvent: "Montsurvent",
          custom: "Personnalisées",
        },

        groups: {
          round: "Manches et cartes",
          board: "Plateau",
          special: "Cartes spéciales",
          seven: "Sept et saut de sept",
        },

        labels: {
          card_exchange: "Échanger une carte avec son partenaire",
          shuffle_cards: "Mélange des cartes",
          rotation: "Sens de rotation",
          deal_card_counts: "Ordre des donnes",
          cannot_play_folds_entire_hand: "Impossible de jouer : défausse complète",
          exit_spot_is_protected_and_blocking: "Cases de sortie protégées et bloquantes",
          house_spots_are_blocking_and_protected: "Cases maison protégées et bloquantes",
          landing_on_occupied_spot_kicks_piece: "Arriver sur une case occupée éjecte le pion",
          track_region_length: "Cases par région",
          enter_house_at_spot: "Position d'entrée dans la maison",
          four_can_move_backward: "Le Quatre peut reculer",
          can_enter_house_backward: "Entrée dans la maison en reculant",
          five_behaviour: "Comportement du Cinq",
          jacks_can_switch: "Le Valet peut échanger des pions",
          jacks_can_switch_then_seven_hop: "Saut de sept après un Valet",
          ace_values: "Valeurs de l'As",
          king_kicks_pieces_on_path: "Le Roi éjecte les pions sur son chemin",
          seven_can_split: "Le Sept peut être partagé",
          seven_split_kicks_pieces_on_path: "Le Sept partagé éjecte sur son chemin",
          seven_hopping: "Saut de sept",
          five_hop_decider: "Décision du saut après un Cinq",
          seven_hopping_on_four_backward_goes_backward: "Un Quatre joué en arrière fait sauter en arrière",
        },

        descriptions: {
          card_exchange: "Au début de chaque donne, les partenaires choisissent et échangent une carte.",
          shuffle_cards: "Détermine quand la défausse est mélangée avant d'être utilisée comme nouvelle pioche.",
          rotation: "Détermine le sens des tours de jeu, de la distribution et du changement de donneur.",
          deal_card_counts: "Détermine le nombre de cartes reçues par chaque joueur pendant les trois donnes d'un cycle.",
          cannot_play_folds_entire_hand: "Si cette règle est activée, un joueur sans coup légal défausse toute sa main. Sinon, il choisit une seule carte à défausser.",
          exit_spot_is_protected_and_blocking: "Un pion qui vient de sortir ne peut pas être éjecté ou échangé par un Valet et empêche les autres pions de traverser sa case. Un Cinq peut toujours le forcer à avancer.",
          house_spots_are_blocking_and_protected: "Les pions ne peuvent pas traverser une case maison occupée ni s'y arrêter. Si cette règle est désactivée, arriver sur une case maison occupée éjecte son pion.",
          landing_on_occupied_spot_kicks_piece: "Si cette règle est activée, le pion présent est éjecté, même s'il appartient au joueur ou à son partenaire. Sinon, le déplacement est interdit.",
          track_region_length: "Détermine le nombre de cases ordinaires associées à la couleur de chaque joueur.",
          enter_house_at_spot: "Détermine la case du parcours depuis laquelle un pion peut entrer dans sa maison.",
          four_can_move_backward: "Permet de déplacer un pion de quatre cases vers l'avant ou de quatre cases vers l'arrière.",
          can_enter_house_backward: "Permet à un déplacement en arrière qui franchit l'entrée configurée de pénétrer dans la maison.",
          five_behaviour: "Un Cinq peut forcer un pion adverse à avancer, déplacer normalement un pion du joueur de cinq cases, ou autoriser les deux comportements.",
          jacks_can_switch: "Permet à un Valet d'échanger un pion du joueur avec le pion d'un autre joueur sur le parcours. Sinon, le Valet avance de onze cases.",
          jacks_can_switch_then_seven_hop: "Permet au pion échangé du joueur actif d'effectuer un saut de sept lorsque l'échange le place sur une septième case.",
          ace_values: "Détermine si un As avance d'une case, de onze cases, ou laisse le choix entre ces deux valeurs.",
          king_kicks_pieces_on_path: "Lorsqu'un Roi avance de treize cases, tous les pions non protégés rencontrés sur son chemin sont éjectés.",
          seven_can_split: "Permet de répartir les sept cases de déplacement entre plusieurs pions. Les sept cases doivent toujours être parcourues.",
          seven_split_kicks_pieces_on_path: "Si cette règle est activée, les pions sont éjectés après chaque étape. Sinon, seule la position finale de chaque pion déplacé peut éjecter.",
          seven_hopping: "Détermine si un pion qui arrive sur une septième case peut ou doit sauter jusqu'à la prochaine septième case.",
          five_hop_decider: "Lorsqu'un Cinq force un pion adverse à arriver sur une septième case, détermine qui décide d'effectuer le saut facultatif.",
          seven_hopping_on_four_backward_goes_backward: "Un saut de sept déclenché par un Quatre joué en arrière conduit à la septième case précédente plutôt qu'à la suivante.",
        },

        choices: {
          shuffle_cards: {
            never: "Jamais",
            on_dealer_change: "À chaque changement de donneur",
            on_dealer_cycle: "Après un tour complet des donneurs",
          },
          rotation: {
            clockwise: "Sens horaire",
            counterclockwise: "Sens antihoraire",
          },
          deal_card_counts: {
            "5_4_4": "5 / 4 / 4",
            "4_5_4": "4 / 5 / 4",
            "4_4_5": "4 / 4 / 5",
          },
          track_region_length: {
            "18": "18 cases",
            "16": "16 cases",
          },
          enter_house_at_spot: {
            "18": "Case 18",
            "16": "Case 16",
          },
          five_behaviour: {
            force_move_opponent: "Forcer un pion adverse à avancer",
            normal_move_by_five: "Déplacement normal de cinq cases",
            both: "Les deux comportements",
          },
          seven_hopping: {
            disabled: "Désactivé",
            optional: "Facultatif",
            forced: "Obligatoire",
          },
          five_hop_decider: {
            acting_player: "Le joueur qui joue",
            piece_owner: "Le propriétaire du pion",
          },
          ace_values: {
            "1_11": "1 ou 11",
            "1": "1",
            "11": "11",
          },
        },
      },
      lobby: {
        game: "Partie",
        players_count: "{count} / {capacity} joueurs",
        choose_seat: "Choisissez votre place",
        team: "Équipe",
        team_0: "Équipe 0",
        team_1: "Équipe 1",
        colour: "Couleur",
        confirm_choices: "Confirmer les choix",
        confirming: "Confirmation de vos choix…",
        choosing: "Choix en cours…",
        configured_choice: "Équipe {team} · {color}",
        confirmed_waiting: "Vos choix sont confirmés. En attente des autres joueurs…",
        joining: "Connexion au salon…",
        choose_while_waiting: "Choisissez votre équipe et votre couleur pendant que les autres joueurs rejoignent la partie.",
        choose_to_start: "Choisissez votre équipe et votre couleur pour démarrer la partie.",
        errors: {
          already_confirmed: "Vos choix dans le salon ont déjà été confirmés.",
          invalid_team: "Veuillez choisir une équipe valide.",
          invalid_color: "Veuillez choisir une couleur valide.",
          team_full: "L'équipe {team} est déjà complète.",
          color_taken: "La couleur {color} a déjà été sélectionnée.",
        },
      },
      game: {
        dealer: "Donneur",
        waiting: "En attente…",
        current_turn: "Tour actuel",
        waiting_to_start: "En attente du début de la partie",
        next_action: "La prochaine action apparaîtra ici.",
        history: "Historique de la partie",
        latest_actions: "Dernières actions",
        live: "En direct",
        debug_tools: "Outils de débogage",
        command_placeholder: "Saisissez une commande",
        send: "Envoyer",
        your_cards: "Vos cartes",
        your_hand: "Votre main",
        hand_instruction: "Sélectionnez une carte, puis confirmez avec un second clic.",
        cards_when_round_starts: "Les cartes apparaîtront au début de la manche.",
        waiting_for_next_deal: "En attente de la prochaine donne.",
        your_turn: "C'est votre tour.",
        waiting_for_player: "En attente de {player}.",
        player_you: "{player} (vous)",
        no_active_player: "Aucun joueur actif",
        game_over: "Partie terminée",
        cancel_selection: "Annuler la sélection",
        returning_to_cards: "Retour à la sélection d'une carte…",
      },
      connection: {
        connected: "Connecté",
        disconnected: "Déconnecté",
        connected_as: "Connecté à la partie {gameId} en tant que {player}.",
        created_game: "Partie créée avec l'identifiant : {gameId}",
        rejoined_self: "Vous avez rejoint la partie dans l'équipe {team} avec la couleur {color} !",
        player_rejoined: "{player} a rejoint la partie.",
        player_disconnected: "{player} s'est déconnecté.",
      },
      colors: {
        red: "Rouge",
        blue: "Bleu",
        green: "Vert",
        yellow: "Jaune",
      },
      errors: {
        name_required: "Veuillez entrer votre nom.",
        rules_load_failed: "Impossible de charger les règles du jeu. Veuillez actualiser la page.",
        game_creation_failed: "Impossible de créer la partie.",
        name_and_game_id_required: "Veuillez saisir votre nom et un identifiant de partie.",
        websocket_url_failed: "Impossible de construire l'adresse WebSocket.",
        invalid_game_id: "Identifiant de partie invalide.",
        player_name_taken: "Ce nom de joueur est déjà utilisé.",
        game_full: "Cette partie compte déjà quatre joueurs.",
        server_unreachable: "Impossible de se connecter au serveur.",
        connection_closed: "Connexion fermée (code {code}).",
        websocket_error: "Erreur WebSocket.",
        connection_not_open: "La connexion n'est pas ouverte.",
        internal_game_error: "La partie s'est arrêtée à cause d'une erreur interne du serveur.",
        invalid_json_message: "Le serveur a reçu un message JSON invalide.",
        invalid_message_format: "Le serveur a reçu un format de message invalide.",
        creation_data_object: "Les données de création de partie doivent être un objet.",
        unknown_creation_fields: "Champs de création de partie inconnus : {fields}",
        invalid_game_configuration: "La configuration de partie sélectionnée est invalide.",
        unknown_message_type: "Type de message inconnu : {messageType}.",
        invalid_resume_token: "Ce navigateur ne possède pas d’identifiants valides pour ce joueur.",
        lobby_expired: "Ce salon a expiré après 15 minutes. Créez une nouvelle partie ou rejoignez-en une autre.",
        game_suspended: "Cette partie a été suspendue après une période d’inactivité. Vous pouvez la reprendre avec le même nom et le même identifiant.",
      },
    },
  };

  const FALLBACK_LANGUAGE = "en";
  const SUPPORTED_LANGUAGES = Object.keys(TRANSLATIONS);
  const LANGUAGE_STORAGE_KEY = "toc_language";

  function getStoredLanguage() {
    try {
      return window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    } catch (error) {
      return null;
    }
  }

  function detectLanguage() {
    const storedLanguage = getStoredLanguage();
    if (SUPPORTED_LANGUAGES.includes(storedLanguage)) return storedLanguage;

    const browserLanguages = [...(navigator.languages || []), navigator.language].filter(Boolean);

    for (const browserLanguage of browserLanguages) {
      const language = browserLanguage.toLowerCase().split("-")[0];
      if (SUPPORTED_LANGUAGES.includes(language)) return language;
    }

    return FALLBACK_LANGUAGE;
  }

  function getNestedTranslation(language, key) {
    return key.split(".").reduce((value, part) => value?.[part], TRANSLATIONS[language]);
  }

  let currentLanguage = detectLanguage();

  function t(key, parameters = {}) {
    const translatedValue = getNestedTranslation(currentLanguage, key) ?? getNestedTranslation(FALLBACK_LANGUAGE, key);
    if (typeof translatedValue !== "string") return key;

    return translatedValue.replace(/\{([a-zA-Z0-9_]+)\}/g, (match, parameterName) => {
      return Object.hasOwn(parameters, parameterName) ? String(parameters[parameterName]) : match;
    });
  }

  function setLanguage(language) {
    if (!SUPPORTED_LANGUAGES.includes(language)) return false;

    currentLanguage = language;
    document.documentElement.lang = language;

    try {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    } catch (error) {
      console.warn("Could not persist language preference.", error);
    }

    window.dispatchEvent(new CustomEvent("toc-language-change", {detail: {language}}));
    return true;
  }

  function getLanguage() {
    return currentLanguage;
  }

  function flattenTranslations(value, prefix = "", result = {}) {
    Object.entries(value).forEach(([key, nestedValue]) => {
      const fullKey = prefix ? `${prefix}.${key}` : key;

      if (typeof nestedValue === "string") {
        result[fullKey] = nestedValue;
        return;
      }

      if (nestedValue && typeof nestedValue === "object" && !Array.isArray(nestedValue)) {
        flattenTranslations(nestedValue, fullKey, result);
        return;
      }

      throw new Error(`Translation "${fullKey}" must be a string or an object.`);
    });

    return result;
  }

  function getTranslationParameters(translation) {
    const parameters = [...translation.matchAll(/\{([a-zA-Z0-9_]+)\}/g)].map(match => match[1]);
    return [...new Set(parameters)].sort();
  }

  function validateTranslationCatalogs() {
    const referenceCatalog = flattenTranslations(TRANSLATIONS[FALLBACK_LANGUAGE]);
    const referenceKeys = Object.keys(referenceCatalog);
    const errors = [];

    SUPPORTED_LANGUAGES.forEach(language => {
      const catalog = flattenTranslations(TRANSLATIONS[language]);
      const catalogKeys = Object.keys(catalog);
      const missingKeys = referenceKeys.filter(key => !(key in catalog));
      const unexpectedKeys = catalogKeys.filter(key => !(key in referenceCatalog));

      if (missingKeys.length) errors.push(`${language} is missing: ${missingKeys.join(", ")}`);
      if (unexpectedKeys.length) errors.push(`${language} has unexpected keys: ${unexpectedKeys.join(", ")}`);

      referenceKeys.forEach(key => {
        if (!(key in catalog)) return;

        const referenceParameters = getTranslationParameters(referenceCatalog[key]);
        const translatedParameters = getTranslationParameters(catalog[key]);

        if (referenceParameters.join(",") !== translatedParameters.join(",")) {
          errors.push(`${language}.${key} uses parameters {${translatedParameters.join(", ")}} instead of {${referenceParameters.join(", ")}}`);
        }
      });
    });

    if (errors.length) throw new Error(`Invalid translation catalog:\n${errors.join("\n")}`);
  }

  function getMissingTranslationKeys(keys) {
    const missingKeys = [];

    SUPPORTED_LANGUAGES.forEach(language => {
      keys.forEach(key => {
        if (typeof getNestedTranslation(language, key) !== "string") missingKeys.push(`${language}.${key}`);
      });
    });

    return missingKeys;
  }

  validateTranslationCatalogs();
  document.documentElement.lang = currentLanguage;

  window.tocI18n = Object.freeze({
    t,
    setLanguage,
    getLanguage,
    getMissingTranslationKeys,
    supportedLanguages: [...SUPPORTED_LANGUAGES],
  });


})();
# -*- coding: utf-8 -*-
import logging

from blackjack.errors import PlayerBustedException, GameAlreadyRunningException, GameNotRunningException, MaxPlayersReachedException, \
    PlayerAlreadyExistingException, NotEnoughPlayersException
from blackjack.game import Player, Dealer, Deck, GameType


class BlackJackGame(object):
    MAX_PLAYERS = 5

    def __init__(self, gametype=None, game_id=None, lang_id="en"):
        self.logger = logging.getLogger(__name__)
        self.__on_start_handlers = []
        self.__on_stop_handlers = []
        self._current_player = 0
        self.players = []
        self.running = False
        self.deck = Deck(lang_id)
        self.dealer = Dealer("Dealer")

        self.type = gametype or GameType.SINGLEPLAYER
        self.id = game_id
        self.lang_id = lang_id

    def register_on_start_handler(self, func):
        """
        Registers a callback function as on_start_handler.
        :param func: Function reference that will be called when the game is starting. It receives a reference to the game as parameter.
        :return:
        """
        self.__on_start_handlers.append(func)

    def register_on_stop_handler(self, func):
        """
        Registers a callback function as on_stop_handler.
        :param func: Function reference that will be called when the game is stopping. It receives a reference to the game as parameter.
        :return:
        """
        self.__on_stop_handlers.append(func)

    # noinspection PyBroadException
    def _run_handlers(self, handlers):
        """
        Call all handlers of the passed 'handlers' list
        :param handlers: List of handlers (e.g. __on_start_handlers, __on_stop_handlers)
        :return:
        """
        for handler in handlers:
            try:
                handler(self)
            except Exception as e:
                self.logger.error("Couldn't run handler '{}' - The following exception occurred: ''".format(handler, e))

    def start(self):
        """
        Sets up the player's and the dealer's hands
        :return:
        """
        if self.running:
            raise GameAlreadyRunningException

        if len(self.players) < 1:
            raise NotEnoughPlayersException

        self.running = True

        # Give every player and the dealer 2 cards
        for player in (self.players + [self.dealer]) * 2:
            card = self.deck.pick_one_card()
            player.give_card(card)

        self._run_handlers(self.__on_start_handlers)

    def stop(self, user_id):
        """
        Stops the game, if the user has sufficient permissions
        :param user_id: The user_id of the user requesting to stop the game
        :return:
        """
        if user_id != -1 and user_id != self.players[0].user_id:
            raise InsufficientPermissionsException
        self.running = False
        self._run_handlers(self.__on_stop_handlers)

    def get_current_player(self):
        return self.players[self._current_player]

    def add_player(self, user_id, first_name, message_id):
        """
        Add a new player to the game as long as it didn't start yet
        :param user_id: The user_id of the player
        :param first_name: The player's first_name
        :param message_id: The id of the message where the user joined
        :return:
        """
        if self.running:
            raise GameAlreadyRunningException("Not adding player, the game is already on!")

        if len(self.players) >= self.MAX_PLAYERS:
            raise MaxPlayersReachedException

        if user_id in [player.user_id for player in self.players]:
            raise PlayerAlreadyExistingException

        # TODO Check if join_id is still needed
        player = Player(user_id, first_name, join_id=message_id)
        self.logger.debug("Adding new player: {}!".format(player))
        self.players.append(player)

    def draw_card(self):
        """
        Draw one card and add it to the player's hand
        :return:
        """
        if not self.running:
            raise GameNotRunningException("The game must be started before you can draw cards")

        player = self.get_current_player()
        card = self.deck.pick_one_card()

        player.give_card(card)

        if player.cardvalue > 21:
            self.logger.debug("While giving user {} the card {}, they busted.".format(player.first_name, card))
            raise PlayerBustedException

    def next_player(self):
        """
        Marks the next player as active player. If all players are finished, go to dealer's turn
        :return:
        """
        if not self.running:
            raise GameNotRunningException("The game must be started before it's the next player's turn")

        if self._current_player != -1 and self._current_player < (len(self.players) - 1):
            self._current_player += 1
        else:
            self.logger.debug("Dealer's turn")
            self._current_player = -1
            self.dealers_turn()

    def dealers_turn(self):
        if not self.running:
            raise GameNotRunningException("The game must be started before it's the dealer's turn")

        while self.dealer.cardvalue <= 16:
            card = self.deck.pick_one_card()
            self.dealer.give_card(card)

    @staticmethod
    def _sort_list(player_list):
        return sorted(player_list, key=lambda x: x.cardvalue, reverse=True)

    def evaluation(self):
        """
        Check which player won and which lost. Also calculate profits if applicable
        :return:
        """
        list_busted = [player for player in self.players if player.busted]
        list_not_busted = [player for player in self.players if player.cardvalue <= 21]

        list_won = []
        list_tie = []
        list_lost = []

        if self.dealer.busted:
            for player in list_not_busted:
                # TODO set game won in statistics
                if player.has_blackjack():
                    # BlackJack pays 3:2 -> return bet + 1.5 x bet
                    player.pay(factor=2.5)
                else:
                    player.pay(factor=2)
                list_won.append(player)

        elif self.dealer.has_blackjack():
            # Dealer has a black jack
            for player in list_not_busted:
                if player.has_blackjack():
                    # TODO set game tie in statistics
                    player.pay(1)
                    list_tie.append(player)
                else:
                    list_lost.append(player)
        elif self.dealer.cardvalue <= 21:
            for player in list_not_busted:
                if player.cardvalue > self.dealer.cardvalue:
                    # TODO set game won in statistics
                    player.pay(2)
                    list_won.append(player)
                elif player.cardvalue == self.dealer.cardvalue:
                    # TODO set game tie in statistics
                    player.pay(1)
                    list_tie.append(player)
                elif player.cardvalue < self.dealer.cardvalue:
                    list_lost.append(player)

        list_lost.extend(list_busted)

        list_won = self._sort_list(list_won)
        list_tie = self._sort_list(list_tie)
        list_lost = self._sort_list(list_lost)

        return list_won, list_tie, list_lost

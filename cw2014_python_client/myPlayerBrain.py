"""
 * ----------------------------------------------------------------------------
 * "THE BEER-WARE LICENSE" 
 * As long as you retain this notice you can do whatever you want with this 
 * stuff. If you meet an employee from Windward some day, and you think this
 * stuff is worth it, you can buy them a beer in return. Windward Studios
 * ----------------------------------------------------------------------------
"""

import random as rand
import traceback
import simpleAStar
import sys
from framework import sendOrders, playerPowerSend

NAME = "Team Tonmai42"
SCHOOL = "Harvey Mudd College"

class MyPlayerBrain(object):
    """The Python AI class.  This class must have the methods setup and gameStatus."""
    def __init__(self, name=NAME):
        self.name = name #The name of the player.
        
        #The player's avatar (looks in the same directory that this module is in).
        #Must be a 32 x 32 PNG file.
        try:
            avatar = open("tree.png", "rb")
            avatar_str = b''
            for line in avatar:
                avatar_str += line
            avatar = avatar_str
        except IOError:
            avatar = None # avatar is optional
        self.avatar = avatar
    
    def setup(self, gMap, me, allPlayers, companies, passengers, client, stores, powerUpDeck, framework):
        """
        Called at the start of the game; initializes instance variables.

        gMap -- The game map.
        me -- Your Player object.
        allPlayers -- List of all Player objects (including you).
        companies -- The companies on the map.
        passengers -- The passengers that need a lift.
        client -- TcpClient to use to send orders to the server.
        stores -- All the coffee stores.
        powerUpDeck -- The powerups this player has in their hand (may have to wait before playing it).
        powerUpHand -- The powerups this player can draw.
        myPassenger -- The passenger currently in my limo, none to start.
        MAX_TRIPS_BEFORE_REFILL -- The maximum number of trips allowed before a refill is required.
        
        """
        self.framework = framework
        self.gameMap = gMap
        self.players = allPlayers
        self.me = me
        self.companies = companies
        self.passengers = passengers
        self.client = client
        self.stores = stores
        self.powerUpDeck = powerUpDeck
        self.powerUpHand = []
        self.myPassenger = None
        self.MAX_TRIPS_BEFORE_REFILL = 3

        self.pickup = pickup = self.allPickups(me, passengers)

        # get the path from where we are to the dest.

        path = self.calculatePathPlus1(me, pickup[0].lobby.busStop)
        sendOrders(self, "ready", path, pickup)

    def gameStatus(self, status, playerStatus):
        """
        Called to send an update message to this A.I.  We do NOT have to send a response.

        status -- The status message.
        playerStatus -- The player this status is about. THIS MAY NOT BE YOU.
        players -- The status of all players.
        passengers -- The status of all passengers.

        """

        # bugbug - Framework.cs updates the object's in this object's Players,
        # Passengers, and Companies lists. This works fine as long as this app
        # is single threaded. However, if you create worker thread(s) or
        # respond to multiple status messages simultaneously then you need to
        # split these out and synchronize access to the saved list objects.

        try:
            # bugbug - we return if not us because the below code is only for
            # when we need a new path or our limo hits a bus stop. If you want
            # to act on other players arriving at bus stops, you need to
            # remove this. But make sure you use self.me, not playerStatus for
            # the Player you are updating (particularly to determine what tile
            # to start your path from).
            if playerStatus != self.me:
                return

            ptDest = None
            pickup = []
            
            if status == "UPDATE":
                self.playPowerUp()
                return
                # return
            
            self.displayStatus(status, playerStatus)
            
            
            if (status == "PASSENGER_NO_ACTION" or status == "NO_PATH"):
                if self.me.limo.passenger is None:
                    pickup = self.allPickups(self.me, self.passengers)
                    ptDest = pickup[0].lobby.busStop
                else:
                    ptDest = self.me.limo.passenger.destination.busStop
            elif (status == "PASSENGER_DELIVERED" or
                  status == "PASSENGER_ABANDONED"):
                pickup = self.allPickups(self.me, self.passengers)
                ptDest = pickup[0].lobby.busStop
            elif  status == "PASSENGER_REFUSED_ENEMY":
                enemy = self._get_enemy_at_place(self.me.limo.passenger.destination)
                self.playPowerUp(action="MOVE_ENEMY", target=enemy)
                # If the enemy is sill there.
                if (enemy.lobby == self.me.limo.passenger.destination):
                    ptDest = self._find_the_closest_places(
                        filter(
                            lambda c: c not in [enemy.lobby for enemy in self.me.limo.passenger.enemies if enemy.lobby is not None],
                            self.companies
                            # filter(
                            #         lambda c: c != self.me.limo.passenger.destination,
                            #         self.companies)
                            # )
                        )
                    )
                else:
                    ptDest = self.me.limo.passenger.destination
            elif (status == "PASSENGER_DELIVERED_AND_PICKED_UP" or
                  status == "PASSENGER_PICKED_UP"):
                pickup = self.allPickups(self.me, self.passengers)
                ptDest = self.me.limo.passenger.destination.busStop

            if (self.me.limo.coffeeServings <= 0):
                ptDest = self._find_the_closest_places(self.stores)
            # coffee store override
            # elif(status == "PASSENGER_DELIVERED_AND_PICKED_UP" or status == "PASSENGER_DELIVERED" or status == "PASSENGER_ABANDONED"):
            #    pass
            #elif(status == "PASSENGER_REFUSED_NO_COFFEE" or status == "PASSENGER_DELIVERED_AND_PICK_UP_REFUSED"):
            #    ptDest = rand.choice(self.stores).busStop
            elif(status == "COFFEE_STORE_CAR_RESTOCKED"):
                pickup = self.allPickups(self.me, self.passengers)
                if len(pickup) != 0:
                    ptDest = pickup[0].lobby.busStop
            
            if(ptDest == None):
                return
            
            self.displayOrders(ptDest)
            
            # get the path from where we are to the dest.
            path = self.calculatePathPlus1(self.me, ptDest)

            sendOrders(self, "move", path, pickup)
        except Exception as e:
            print traceback.format_exc()
            raise e

    def _get_enemy_at_place(self, place):
        possible_enemies_list = filter(
            lambda e: e.lobby == place,
            self.me.limo.passenger.enemies
        )

        if len(possible_enemies_list) > 0:
            return possible_enemies_list[0]
        else:
            return None

    def _find_the_closest_places(self, places):
        min_closest_distance = sys.maxint;
        corresponding_busStop = None
        for place in places:
            path = self.calculatePathPlus1(self.me, place.busStop)
            if len(path) < min_closest_distance:
                min_closest_distance = len(path)
                corresponding_busStop = place.busStop
        print "busStop is"
        print corresponding_busStop
        return corresponding_busStop

    def displayOrders(self, ptDest):
        msg = None
        potentialStores = [s for s in self.stores if s.busStop == ptDest]
        store = None
        if len(potentialStores) > 0:
            store = potentialStores[0]
        if store is not None:
            storename = store.name
            if "Gloria Jean" in storename:
                storename = "Gloria Jean's Coffees"
            if "Peet" in storename:
                storename = "Peet's Coffee and Tea"
            if "Tully" in storename:
                storename = "Tully's Coffee"
            msg = "Heading toward {0} at {1}".format(storename, ptDest)
        else:
            potentialCompanies = [c for c in self.companies if c.busStop == ptDest]
            company = None
            if len(potentialCompanies) > 0:
                company = potentialCompanies[0]
            if company is not None:
                msg = "Heading toward {0} at {1}".format(company.name, ptDest)
        if msg is not None:
            print(msg)

    def calculatePathPlus1(self, me, ptDest):
        path = simpleAStar.calculatePath(self.gameMap, me.limo.tilePosition, ptDest)
        # add in leaving the bus stop so it has orders while we get the message
        # saying it got there and are deciding what to do next.
        if len(path) > 1:
            path.append(path[-2])
        return path
    
    def playPowerUp(self, action=None, target=None):

        if len(self.powerUpHand) is not 0 and rand.randint(0, 50) < 30:
            return
        # not enough, draw
        if len(self.powerUpHand) < self.me.maxCardsInHand and len(self.powerUpDeck) > 0:
            for card in self.powerUpDeck:
                if(len(self.powerUpHand) == self.me.maxCardsInHand):
                    break
                # select a card
                self.powerUpDeck.remove(card)
                self.powerUpHand.append(card)
                playerPowerSend(self, "DRAW", card)
            return
        
        # can we play one?
        okToPlayHand = filter(lambda p: p.okToPlay, self.powerUpHand)
        if len(okToPlayHand) == 0:
            return

        print [my_card.card for my_card in okToPlayHand]
        powerUp = okToPlayHand[0]

        power_up_cards = [power_up_card for power_up_card in okToPlayHand if power_up_card.card == "MOVE_PASSENGER"]
        if action == "MOVE_ENEMY" and target != None and len(power_up_cards) > 0:
            powerUp = power_up_cards[0]
            powerUp.passenger = target
            playerPowerSend(self, "PLAY", powerUp)
            print "*" * 70
            print "Playing powerup " + powerUp.card
            self.powerUpHand.remove(powerUp)
            return
        
        # 10% discard, 90% play
        if rand.randint(1, 10) == 1:
            playerPowerSend(self, "DISCARD", powerUp)
        else:
            if powerUp.card == "MOVE_PASSENGER":
                powerUp.passenger = rand.choice(filter(lambda p: p.car is None, self.passengers))
            if powerUp.card == "CHANGE_DESTINATION" or powerUp.card == "STOP_CAR":
                playersWithPassengers = filter(lambda p: p.guid != self.me.guid and p.limo.passenger is not None, self.players)
                if len(playersWithPassengers) == 0:
                    return
                powerUp.player = rand.choice(playersWithPassengers)

            playerPowerSend(self, "PLAY", powerUp)
            print "Playing powerup " + powerUp.card
        self.powerUpHand.remove(powerUp)
        
        return
    
    # A power-up was played. It may be an error message, or success.
    def powerUpStatus(self, status, playerPowerUp, cardPlayed):
        # redo the path if we got relocated
        if((status == "POWER_UP_PLAYED") and ((cardPlayed.card == "RELOCATE_ALL_CARS") or ((cardPlayed.card == "CHANGE_DESTINATION") and (cardPlayed.player.guid == self.me.guid)))):
            self.gameStatus("NO_PATH", self.me)
        return
    
    def displayStatus(self, status, plyrStatus):
        msg = ""
        # Sometimes, myPassenger or myPassenger.lobby is None. If you want to figure this
        # out on your own, have at it, but it really only affects the messages displayed below.
        if(status == "PASSENGER_DELIVERED"):
            if self.myPassenger.name is not None or self.myPassenger.lobby is not None:
                msg = "{0} delivered to {1}\n".format(self.myPassenger.name, self.myPassenger.lobby.name)
            self.myPassenger = None
        elif(status == "PASSENGER_ABANDONED"):
            if self.myPassenger is not None or self.myPassenger.lobby is not None:
                msg = "{0} abandoned at {1}\n".format(self.myPassenger.name, self.myPassenger.lobby.name)
            self.myPassenger = None
        elif(status == "PASSENGER_REFUSED_ENEMY"):
            msg = "{0} refused to exit at {1} - enemy there".format(plyrStatus.limo.passenger.name, plyrStatus.limo.passenger.destination.name)
        elif(status == "PASSENGER_DELIVERED_AND_PICKED_UP"):
            msg = "{0} delivered at {1} and {2} picked up".format(self.myPassenger.name, self.myPassenger.lobby.name, plyrStatus.limo.passenger.name)
            self.myPassenger = plyrStatus.limo.passenger
        elif(status == "PASSENGER_PICKED_UP"):
            msg = "{0} picked up".format(plyrStatus.limo.passenger.name)
            self.myPassenger = plyrStatus.limo.passenger
        elif(status == "PASSENGER_REFUSED_NO_COFFEE"):
            msg = "Passenger refused to board limo, no coffee"
        elif(status == "PASSENGER_DELIVERED_AND_PICK_UP_REFUSED"):
            msg = "{0} delivered at {1}, new passenger refused to board limo, no coffee".format(self.myPassenger.name, self.myPassenger.lobby.name)
        elif(status == "COFFEE_STORE_CAR_RESTOCKED"):
            msg = "Coffee restocked!"
        
        if(msg != ""):
            print (msg)
        return
    
    def allPickups (self, me, passengers):
            pickup = [p for p in passengers if
                (
                    not p in me.passengersDelivered and
                    p != me.limo.passenger and
                    p.car is None and
                    p.lobby is not None and p.destination is not None and
                    p.destination.busStop not in [enemy.lobby.busStop for enemy in p.enemies if enemy.lobby is not None]
                )
            ]
            #rand.shuffle(pickup)
            # Go to lobby of company that is closest and with the shortest route
            pickup.sort(key = lambda x:
                (1.0 + 1.0/x.pointsDelivered)*len(self.calculatePathPlus1(self.me, x.lobby.busStop))
                )
            return pickup
"""
  ----------------------------------------------------------------------------
  "THE BEER-WARE LICENSE"
  As long as you retain this notice you can do whatever you want with this
  stuff. If you meet an employee from Windward some day, and you think this
  stuff is worth it, you can buy them a beer in return. Windward Studios
  ----------------------------------------------------------------------------



  """

from xml.etree import ElementTree as ET
import debug

PSNGR_STATUS = ("lobby", "travelling", "done")
"""
Current status of the player:

UPDATE: Called ever N ticks to update the AI with the game status.
NO_PATH: The car has no path.
PASSENGER_ABANDONED: The passenger was abandoned, no passenger was picked up.
PASSENGER_DELIVERED: The passenger was delivered, no passenger was picked up.
PASSENGER_DELIVERED_AND_PICKED_UP: The passenger was delivered or abandoned, a new passenger was picked up.
PASSENGER_REFUSED: The passenger refused to exit at the bus stop because an enemy was there.
PASSENGER_PICKED_UP: A passenger was picked up. There was no passenger to deliver.
PASSENGER_NO_ACTION: At a bus stop, nothing happened (no drop off, no pick up).

"""

CARD = ("MOVE_PASSENGER", "CHANGE_DESTINATION", "MULT_DELIVERY_QUARTER_SPEED",
        "ALL_OTHER_CARS_QUARTER_SPEED", "STOP_CAR", "RELOCATE_ALL_CARS",
        "RELOCATE_ALL_PASSENGERS", "MULT_DELIVERING_PASSENGER",
        "MULT_DELIVER_AT_COMPANY")

"""
Card Descriptions:

MOVE_PASSENGER: Will move all passengers (not in a car) to a random bus stop (can play anytime).
CHANGE_DESTINATION: Change destination for a passenger in an opponentâs car to a random company (can play anytime).
MULT_DELIVERY_QUARTER_SPEED: Delivery is 1.5X points, but your car travels at 1/4 speed.
ALL_OTHER_CARS_QUARTER_SPEED: Drop all other cars to 1/4 speed for 30 seconds (can play anytime).
STOP_CAR: Can make a specific car stop for 30 seconds (tacks on road) - (can play anytime).
RELOCATE_ALL_CARS: Relocate all cars (including yours) to random locations (can play anytime).
RELOCATE_ALL_PASSENGERS: Relocate all passengers at bus stops to random locations (can play anytime).
MULT_DELIVERING_PASSENGERS: 1.2X multiplier for delivering a specific person (we have one card for each passenger).
MULT_DELIVER_AT_COMPANY: 1.2X multiplier for delivering at a specific company (we have one card for each company).

"""


class Player(object):
    """Class for representing a player in the game."""

    def __init__(self, element, pickup=[], passes=[], score=0, totalScore=0, maxCardsInHand=4):
        """Create a player instance from the given XML Element.

        Initialize the following instance variables:
        guid -- A unique string identifier for this player. This string will remain
            constant throughout the game (while the Player objects passed will change
            on every call).
        name -- The name of this player.
        school - The school this player is from
        language - The computer language this player's AI is written in
        pickup -- List of who to pick up at the next bus stop. Can be empty and
            can also only list people not at the next bus stop. This may be
            wrong after a pick-up occurs as all we get is a count. This is
            updated with the most recent list sent to the server.
        passengersDelivered -- The passengers delivered so far (this game).
        limo -- The player's limo.
        score  -- The score for this player (this game, not across all games so far).
        totalScore  -- The score for thie player across all games (so far)
        maxCardsInHand -- The maximum number of cards this player can have in their hand. Starts at 4
        powerUpNextBusStop -- The power up this player will play at the next bus stop.
        powerUpTransit -- The power up in effect for the transit this player is presently executing.

        """
        if isinstance(element, basestring):
            element = ET.XML(element)
        self.guid = element.get('guid')
        self.name = element.get('name')
        self.school = element.get('school')
        self.language = element.get('language')

        self.limo = Limo((int(element.get('limo-x')), int(element.get('limo-y'))),
                         int(element.get('limo-angle')))
        self.pickup = pickup if pickup else []
        self.passengersDelivered = passes if passes else []
        self.score = score
        self.totalScore = totalScore
        self.maxCardsInHand = maxCardsInHand
        self.powerUpNextBusStop = None
        self.powerUpTransit = None

    def __repr__(self):
        return ("Player('" +
                '<player guid="%s" name=%r limo-x="%r" limo-y="%r" limo-angle="%r">' %
                (self.guid, self.name, self.limo.tilePosition[0], self.limo.tilePosition[1], self.limo.angle) +
                "', pickup=%r, passes=%r, score=%r)" % (self.pickup, self.passengersDelivered, self.score))

    def __str__(self):
        return "Player %s; NumDelivered:%r" % (self.name, len(self.passengersDelivered))

    def __eq__(self, other):
        if isinstance(other, Player) and other.guid == self.guid:
            return True
        else:
            return False

    def __hash__(self):
        return hash(self.guid)


class PowerUp(object):
    """ The powers available to cars."""
    statusPowerUps = {}

    def __init__(self, element, card, company, passenger, player, src):
        """	passenger = The passenger affected for MOVE_PASSENGER, MULT_DELIVERING_PASSENGER.
			player = The player affected for CHANGE_DESTINATION, STOP_CAR
			name = The name of the power-up.
			card = The power-up card.
			company = The company affected for MULT_DELIVER_AT_COMPANY.
			OkToPlay = It's ok to play this card. This is false until a card is drawn and the limo then visits a stop.
        """
        if element is not None:
            self.name = element.get('name')
            self.card = element.get('card')
            self.player = None
            self.company = None
            self.okToPlay = None
            self.passenger = None
            assert self.card in CARD
        elif src is not None:
            self.passenger = src.passenger
            self.player = src.player
            self.name = src.name
            self.card = src.card
            self.company = src.company
            self.okToPlay = src.okToPlay
        else:
            self.card = card
            self.name = str(card)
            if company is not None:
                self.company = company
                self.name = self.name + " - " + company.name
            else:
                self.company = None
            if passenger is not None:
                if self.card == "CARD.CHANGE_DESTINATION":
                    raise Exception("set the Player for CHANGE_DESTINATION")
                self.passenger = passenger
                self.name = self.name + " - " + passenger.name
            else:
                self.passenger = None
            if player is not None:
                self.player = player
                self.name = self.name + " - " + player.name
            else:
                self.player = None
            self.okToPlay = None


    def __str__(self):
        return self.name


class Limo(object):
    """A player's limo - holds a single passenger."""

    def __init__(self, tilePosition, angle, path=[], passenger=None, coffeeServings=3):
        """tilePosition -- The location in tile units of the center of the vehicle.
        angle -- the angle this unit is facing (an int from 0 to 359; 0 is
            North and 90 is East.
        path -- Only set for the AI's own limo - the number of tiles
            remaining in the limo's path. This may be wrong after movement
            as all we get is a count. This is updated witht the most recent
            list sent to the server.
        passenger -- The passenger in this limo. None if there is no passenger.
        coffeeServings -- The coffee servings in this car. The coffee is reduced when the passenger exits the limo. It is
	        reduced by 2 if the trip used a power-up multiplier for the points.

        """
        self.tilePosition = tilePosition
        self.angle = angle
        self.path = path if path else []
        self.passenger = passenger
        self.coffeeServings = coffeeServings

    def __str__(self):
        if self.passenger is not None:
            return ("%s:%s; Passenger:%s; Dest:%s; PathLength:%s" %
                    (self.tilePosition, self.angle, self.passenger.name,
                     self.passenger.destination, len(self.path)))
        else:
            return "%s:%s; Passenger:{none}" % (self.tilePosition, self.angle)


class Passenger(object):
    """A company CEO."""

    def __init__(self, element, companies):
        """Create a passenger from XML and a list of Company objects.

        name -- The name of this passenger.
        pointsDelivered -- The number of points a player get for delivering this passenger.
        car -- The limo the passenger is currently in. None if they are not in a limo.
        lobby -- The bus stop the passenger is currently waiting in. None if they
            are in a limo or if they have arrived at their final destination.
        destination -- The company the passenger wishes to go to next. This is
            valid both at a bus stop and in a car. It is None of they have been
            delivered to their final destination.
        route -- The remaining companies the passenger wishes to go to after
            destination, in order. This does not include their current destination.
        enemies -- List of other Passenger objects. If any of them are at a bus
            stop, this passenger will not exit the limo at that stop. If a
            passenger at the bus stop has this passenger as an enemy, this
            passenger can still exit the car.

        """
        self.name = element.get('name')
        self.pointsDelivered = int(element.get('points-delivered'))
        lobby = element.get('lobby')
        self.lobby = ([c for c in companies if c.name == lobby][0]
                      if lobby is not None else None)
        dest = element.get('destination')
        self.destination = ([c for c in companies if c.name == dest][0]
                            if dest is not None else None)
        route = []
        for routeElement in element.findall('route'):
            debug.trap()
            route.append([c for c in companies if c.name == routeElement.text][0])
        self.route = route
        self.enemies = []
        self.car = None

    def __repr__(self):
        return self.name


def playersFromXml(element):
    """Called on setup to create initial list of players."""
    return [Player(p) for p in element.findall('player')]


def updatePlayersFromXml(companies, players, passengers, element):
    """Update a list of Player objects with passengers from the given XML."""
    for playerElement in element.findall('player'):
        player = [p for p in players if p.guid == playerElement.get('guid')][0]
        # player score (this round)
        player.score = float(playerElement.get('score'))
        # player total score
        player.totalScore = float(playerElement.get('total-score'))
        # max cards in hand
        player.maxCardsInHand = int(playerElement.get('cards-max'))
        # coffee servings
        player.limo.coffeeServings = int(playerElement.get('coffee-servings'))
        # car location
        player.limo.tilePosition = ( int(playerElement.get('limo-x')),
                                     int(playerElement.get('limo-y')) )
        player.limo.angle = int(playerElement.get('limo-angle'))
        # see if we now have a passenger
        psgrName = playerElement.get('passenger')
        if psgrName is not None:
            passenger = [p for p in passengers if p.name == psgrName][0]
            player.limo.passenger = passenger
            passenger.car = player.limo
        else:
            player.limo.passenger = None
            # add most recent delivery if this is the first time we're told.
        psgrName = playerElement.get('last-delivered')
        if psgrName is not None:
            passenger = [p for p in passengers if p.name == psgrName][0]
            if passenger not in player.passengersDelivered:
                player.passengersDelivered.append(passenger)
            # power ups in action
        elemCards = playerElement.get("next-bus-stop")
        if elemCards is not None:
            player.powerUpNextBusStop = powerUpGenerateFlyweight(elemCards, companies, passengers, players)
        elemCards = playerElement.get("transit")
        if elemCards is not None:
            player.powerUpTransit = powerUpGenerateFlyweight(elemCards, companies, passengers, players)


def passengersFromXml(element, companies):
    elements = element.findall('passenger')
    passengers = [Passenger(psgr, companies) for psgr in elements]
    # need to now assign enemies - needed all Passenger objects created first
    for elemOn in elements:
        psgr = [p for p in passengers if p.name == elemOn.get('name')][0]
        psgr.enemies = [filter(lambda p: p.name == e.text, passengers)[0]
                        for e in elemOn.findall('enemy')]
        # set if they're in a lobby
    for psgr in passengers:
        if psgr.lobby is not None:
            company = [c for c in companies if c == psgr.lobby][0]
            company.passengers.append(psgr)
    return passengers


def updatePassengersFromXml(passengers, players, companies, element):
    for psgrElement in element.findall('passenger'):
        #debug.bugprint('updatePassengers XML:', ET.tostring(psgrElement))
        #debug.bugprint('  passengers: ' + str(passengers))
        passenger = [p for p in passengers if p.name == psgrElement.get('name')][0]
        dest = psgrElement.get('destination')
        if dest is not None:
            passenger.destination = [c for c in companies if c.name == dest][0]
            # remove from the route
            if passenger.destination in passenger.route:
                passenger.route.remove(passenger.destination)
        passenger.route = []
        dest = psgrElement.get("route")
        if dest is not None:
            companyNames = dest.split(";")
            companyNames = [x for x in companyNames if x]
            for nameOn in companyNames:
                passenger.route.append([c for c in companies if c.name == nameOn])

        # set props based on waiting, travelling, done
        switch = psgrElement.get('status')
        assert switch in PSNGR_STATUS

        if switch == "lobby":
            cmpny = [c for c in companies if c.name == psgrElement.get('lobby')][0]
            passenger.lobby = cmpny
            passenger.car = None

            if not (passenger in cmpny.passengers):
                cmpny.passengers.append(passenger)
            for plyrOn in players:
                if plyrOn.limo.passenger == passenger:
                    plyrOn.limo.passenger = None
            for cmpyOn in companies:
                if cmpyOn != cmpny:
                    if passenger in cmpyOn.passengers:
                        cmpyOn.passengers.remove(passenger)

        elif switch == "travelling":
            plyr = [p for p in players if p.name == psgrElement.get('limo-driver')][0]
            passenger.car = plyr.limo
            passenger.lobby = None

            for plyrOn in players:
                if (plyrOn != plyr and plyrOn.limo.passenger == passenger):
                    plyrOn.limo.passenger = None
            for cmpyOn in companies:
                if passenger in cmpyOn.passengers:
                    cmpyOn.passengers.remove(passenger)
                    # passenger.car set in Player update
        elif switch == "done":
            debug.trap()
            passenger.destination = None
            passenger.lobby = None
            passenger.car = None
        else:
            raise TypeError("Invalid passenger status in XML: %r" % switch)


def powerUpFromXml(elemPowerUps, companies, passengers):
    powerUps = []
    for elemPuOn in elemPowerUps.findall('powerup'):
        pu = PowerUp(elemPuOn, None, None, None, None, None)
        if (pu.card == "MULT_DELIVERING_PASSENGER"):
            passName = elemPuOn.get('passenger')
            passengerToSet = None
            for p in passengers:
                if (p.name == passName):
                    passengerToSet = p
                    break

            pu.passenger = passengerToSet
        elif (pu.card == "MULT_DELIVER_AT_COMPANY"):
            compName = elemPuOn.get('company')
            compToSet = None
            for c in companies:
                if (c.name == compName):
                    compToSet = c
                    break

            pu.company = compToSet
        powerUps.append(pu)
    return powerUps


""" We only create one of each type to avoid memory allocations every time we get an update. """


def powerUpGenerateFlyweight(element, companies, passengers, players):
    card = element.get("card") if element.get("card") is not None else ""
    companyName = element.get("company") if element.get("company") is not None else ""
    passengerName = element.get("passenger") if element.get("passenger") is not None else ""
    playerName = element.get("player") if element.get("player") is not None else ""

    key = card + ":" + companyName + ":" + passengerName + ":" + playerName

    OkToPlay = element.get("ok-to-play")

    if (key in PowerUp.statusPowerUps):
        PowerUp.statusPowerUps[key].okToPlay = (OkToPlay == "true")
        return PowerUp.statusPowerUps[key]

    company = get_first(companies)
    passenger = get_first(passengers)
    player = get_first(players)
    pu = PowerUp(None, card, company, passenger, player, None)

    PowerUp.statusPowerUps[key] = pu

    pu.okToPlay = (OkToPlay == "true")
    return pu


def get_first(iterable, default=None):
    if iterable:
        for item in iterable:
            return item
    return default
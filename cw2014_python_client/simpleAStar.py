"""
  ----------------------------------------------------------------------------
  "THE BEER-WARE LICENSE"
  As long as you retain this notice you can do whatever you want with this
  stuff. If you meet an employee from Windward some day, and you think this
  stuff is worth it, you can buy them a beer in return. Windward Studios
  ----------------------------------------------------------------------------
  """

from debug import trap, printrap

# CACHEPATHS dictionary contains a number and a list of points associated with that number
CACHEPATHS = {}
OFFSETS = ( (-1, 0), (1, 0), (0, -1), (0, 1) )
DEAD_END = 10000
POINT_OFF_MAP = (-1, -1)

def calculatePath(gmap, start, end):
    """Calculate and return a path from start to end.

    This implementation is intentionally stupid and is NOT guaranteed in any
    way. Specifically, although it may, it is not guaranteed to:
        ->Return the shortest possible path
        ->Return a legal path
        ->Return in a reasonable amount of time
        ->Be free of bugs

    Use unmodified at your own risk.

    map -- The game map.
    start -- The tile units of the start point (inclusive).
    end -- The tile units of the end point (inclusive).

    """
    # should never happen but just to be sure
    if start == end:
        return [start]

    #startEnd = {start.x: None, start.y: None, end.x: None, end.y: None}
    #savedPath = []
    #if CACHEPATHS.get(start) is not None:   # TODO, this is wrong
        #return savedPath

    # nodes are points we have walked to
    nodes = {}
    # points we have in a trailPoint, but not yet evaluated
    notEvaluated = {}

    tpOn = TrailPoint(start, end, 0)
    while True:
        nodes[tpOn.mapTile] = tpOn

        # get the neighbors
        tpClosest = None
        for ptOffset in OFFSETS:
            pointNeighbor = (tpOn.mapTile[0] + ptOffset[0], tpOn.mapTile[1] + ptOffset[1])
            square = gmap.squareOrDefault(pointNeighbor)
            # off the map or not a road/bus stop
            if square is None or (not square.isDriveable()):
                continue
            # already evaluated - add it in
            if pointNeighbor in nodes:
                tpAlreadyEvaluated = nodes[pointNeighbor]
                
                tpRecalc = None
                ptIgnore = None

                if (tpAlreadyEvaluated.costFromStart + 1 < tpOn.costFromStart):
                    tpRecalc = tpOn
                    ptIgnore = tpAlreadyEvaluated.mapTile
                elif(tpOn.costFromStart + 1 < tpAlreadyEvaluated.costFromStart):
                    tpRecalc = tpAlreadyEvaluated
                    ptIgnore = tpOn.mapTile
                else:
                    tpRecalc = None
                    ptIgnore = POINT_OFF_MAP

                tpOn.costFromStart = min(tpOn.costFromStart, tpAlreadyEvaluated.costFromStart + 1)
                tpAlreadyEvaluated.costFromStart = min(tpAlreadyEvaluated.costFromStart, tpOn.costFromStart + 1)
                tpOn.neighbors.append(tpAlreadyEvaluated)
                if tpRecalc is not None:
                    tpRecalc.recalculateFromStart(ptIgnore, (gmap.width * gmap.height) / 4)
                continue

            # add this one in
            tpNeighbor = TrailPoint(pointNeighbor, end, tpOn.costFromStart+1)
            tpOn.neighbors.append(tpNeighbor)
            # may already be in notEvaluated. If so remove it as this is a more
            # recent cost estimate.
            if tpNeighbor in notEvaluated:
                del notEvaluated[tpNeighbor.mapTile]

            # we only assign to tpClosest if it is closer to the destination.
            # If it's further away, then we use notEvaluated below to find the
            # one closest to the dest that we ahve not walked yet.
            if tpClosest is None:
                if tpNeighbor.costCompletePath() < tpOn.costCompletePath():
                    # new neighbor is closer - work from this next
                    tpClosest = tpNeighbor
                else:
                    # this is further away - put in the list to try if a
                    # better route is not found
                    notEvaluated[tpNeighbor.mapTile] = tpNeighbor
            elif tpClosest.costCompletePath() <= tpNeighbor.costCompletePath():
                # this is further away - put in the list to try if a
                # better route is not found
                notEvaluated[tpNeighbor.mapTile] = tpNeighbor
            else:
                # this is closer than tpOn and another neighbor - use it next.
                notEvaluated[tpClosest.mapTile] = tpClosest
                tpClosest = tpNeighbor
        # re-calc based on neighbors
        tpOn.recalculateDistance(POINT_OFF_MAP, gmap.width + gmap.height)

        # if no closest, then get from notEvaluated. This is where it
        # guarantees that we are getting the shortest route - we go in here
        # if the above did not move a step closer. This may not either as
        # the best choice may be the neighbor we didn't go with above - but
        # we drop into this to find the closest based on what we know.
        if tpClosest is None:
            # we need the closest one as that's how we find the shortest path
            tpClosest = None
            for i in notEvaluated.keys():
                if(tpClosest is None):
                    tpClosest = notEvaluated[i]
                elif(tpClosest.costCompletePath() > notEvaluated[i].costCompletePath()):
                    tpClosest = notEvaluated[i]

            if tpClosest is None:
                break
            del notEvaluated[tpClosest.mapTile]

        # if we're at the end - we're done!
        if tpClosest.mapTile == end:
            tpClosest.neighbors.append(tpOn)
            nodes[tpClosest.mapTile] = tpClosest
            break

        # try this one next
        tpOn = tpClosest

    path = []
    if not (end in nodes):
        return

    # create the return path - from end back to beginning
    tpOn = nodes[end]
    path.append(tpOn.mapTile)
    while tpOn.mapTile != start:
        neighbors = tpOn.neighbors
        cost = tpOn.costFromStart

        tpOn = sorted(neighbors, key=lambda x: x.costFromStart)[0]    # TODO make sure this is ok

        # we didn't get to the start.
        if tpOn.costFromStart >= cost:
            return path
        else:
            path.insert(0, tpOn.mapTile)

    # TODO add to cache
    return path

class TrailPoint(object):
    def __init__(self, point, end, costFromStart):
        """A point in a car's path.

        mapTile -- The map tile (a 2-tuple) for this point in the trail.
        neighbors -- A list of the neighboring tiles (up to 4). If 0 then this
            point has been added as a neighbor but is in the notEvaluated list
            because it has not yet been tried.
        costToEnd -- Estimate of the distance from mapTile to the end. Manhattan
            distance if have no neighbors, best neighbor.distance + 1 otherwise.
            This value is bad if it's along a trail that failed.
        costFromStart -- The number of steps from the start to this tile
        costCompletePath -- The cost from beginning to end if using this tile in the final path

        """
        self.mapTile = point
        self.neighbors = []
        self.costToEnd = abs(point[0] - end[0]) + abs(point[1] - end[1])
        self.costFromStart = costFromStart

    def costCompletePath(self):
        return self.costFromStart + self.costToEnd

    def recalculateFromStart(self, ptIgnore, remainingSteps):
        if self.costFromStart == 0:
            return
        if ((remainingSteps - 1) < 0):
            return
        for neighborOn in self.neighbors:
            if neighborOn.mapTile is not ptIgnore:
                continue
            if neighborOn.costFromStart <= self.costFromStart + 1:
                continue
            neighborOn.costFromStart = self.costFromStart + 1
            neighborOn.recalculateFromStart(self.mapTile, remainingSteps)

    def recalculateDistance(self, mapTileCaller, remainingSteps):
        neighbors = self.neighbors
        trap(self.costToEnd == 0)
        # if no neighbors then this is in notEvaluated and so can't recalculate.
        if len(neighbors) == 0:
            return

        shortestDistance = None
        # if just one neighbor, then it's a dead end
        if len(neighbors) == 1:
            shortestDistance = DEAD_END
        else:
            shortestDistance = min(neighbors, key=lambda n: n.costToEnd).costToEnd
            # it's 1+ lowest neighbor value (unless a dead end)
            if shortestDistance != DEAD_END:
                shortestDistance += 1

        # no change, no need to recalc neighbors
        if shortestDistance == self.costToEnd:
            return
        # new value (could be shorter or longer)
        self.costToEnd = shortestDistance
        # if gone too far, no more recalculate
        if remainingSteps < 0:
            return
        remainingSteps -= 1
        # need to tell our neighbors - except the one that called us
        newNeighbors = [n for n in neighbors if n.mapTile != mapTileCaller]
        for neighborOn in newNeighbors:
            neighborOn.recalculateDistance(self.mapTile, remainingSteps)
        # and we re-calc again because that could have changed our neighbors' values
        shortestDistance = min(neighbors, key=lambda n: n.costToEnd).costToEnd
        # it's 1+ lowest neighbor value (unless a dead end)
        if shortestDistance != DEAD_END:
            shortestDistance += 1
        self.costToEnd = shortestDistance

    def __repr__(self):
        return ("TrailPoint<Map=%s, Cost=%s, Distance=%s, Neighbors=%s>" %
               (self.mapTile, self.costFromStart, self.costToEnd, len(self.neighbors)))

    def __hash__(self):
        return hash("TrailPoint at {0}".format(self.mapTile))

    def __eq__(self, other):
        if isinstance(other, TrailPoint) and other.mapTile == self.mapTile:
            return True
        else:
            return False
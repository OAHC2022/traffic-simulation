import random
import networkx as nx
import numpy as np
from typing import *


class Car:
    def __init__(self, init_dist: Union[int, float], init_dest: list, actions: list, id=0):
        """
        The Cars contain attributes: its own time, its previous cross road node,
                                     its current crossroad queue, the length of the edge it is on
                                     a sequence of the nodes it has to reach,
                                     whether it is in the waiting queue/pass in progress queue,
                                     the time it passes through a cross road, whether it has arrived.
        :param init_dist: The length of the edge it is on
        :param init_dest: The current cross road queue
        :param actions: A list containing the reference to cross roads that this car will pass (that is, a representation of the car path)
        """
        self.wait_time: Union[int, float] = 0  # Its own time
        # the reference to the next cross road's queue
        self.dest: List[Car] = init_dest
        # Reference to the previous cross road
        self.previous_cross: Optional[object] = None
        self.dist_to_cross = init_dist  # Car's distance to the next cross road
        self.actions = actions
        self.cross_time = 2  # The time required for it to pass through a cross road
        # whether the car's status is already updated by the update_cross_roads method.
        self.updated = False
        self.arrived = False  # whether it has arrived at its destination
        self.id = id


class CrossRoad:
    def __init__(self, ns_state: bool, we_state: bool, id=0):
        """
        The cross road contain attributes: waiting queue, pass in progress queue, light signal boolean
        :param ns_state: A boolean which determine if it is green light for the north-south direction
        :param we_state: A boolean which determine if it is green light for the west-east direction
        """
        self.west: List[Car] = []  # queue on the west side
        self.east: List[Car] = []  # queue on the east side
        self.north: List[Car] = []  # queue on the north side
        self.south: List[Car] = []  # queue on the south side
        self.all = [self.north, self.south,
                    self.west, self.east]  # all the queues
        # the pass in progress queue
        self.pass_in_prog: Dict[Car, Union[int, float]] = {}
        self.ns_state = ns_state
        self.we_state = we_state
        self.id = id


class World:
    def __init__(self, G: nx.DiGraph, all_cross_roads: List[CrossRoad], all_cars: List[Car],
                 policy: Callable[[nx.DiGraph, List[CrossRoad], List[Car], int], None]):
        self.G = G
        self.all_cross_roads = all_cross_roads
        self.all_cars = all_cars
        self.__all_cars__ = all_cars[:]
        self.time: Union[int, float] = 0
        self.policy = policy

    def update_cross_roads(self, time: Union[int, float]):
        """
        :param time: the global time step
        :return: None
        """
        for cross_road in self.all_cross_roads:
            # update pass_in_progress
            # assuming pass_in_prog has unlimited capacity
            for car in list(cross_road.pass_in_prog.keys()):

                # increase the time that each car has spent passing the cross road
                cross_road.pass_in_prog[car] += time
                car.updated = True

                # if the time spent is greater than the predefined cross time,
                # then the car has already passed the cross road.
                if cross_road.pass_in_prog[car] >= car.cross_time:
                    # remove the car from the pass in progress dictionary
                    time_at_cross = cross_road.pass_in_prog.pop(car)

                    # if the car has not yet arrived at its final destination,
                    # place the car on the way to the next cross road
                    # assign the cross road that this car has just passes to this car's current cross
                    car.previous_cross = car.actions.pop(0)
                    if len(car.actions) > 0:

                        # get the edge from the past cross road to the next cross road
                        edge = self.G[cross_road][car.actions[0]]

                        # update the car's distance to the next cross road
                        car.dist_to_cross = edge['length'] - \
                            time_at_cross + car.cross_time

                        # update car's reference to the next cross road's queue
                        car.dest = edge['dest']
                    else:
                        car.arrived = True

            # then, update the queue of cars waiting to pass
            # if the cars are in the queues of north-south direction and the traffic light is green,
            if cross_road.ns_state:
                for queue in cross_road.all[:2]:
                    if len(queue) == 0:
                        continue

                    # compute each car's distance to the cross road
                    for car in queue:
                        car.dist_to_cross -= time
                        car.updated = True

                        # negative distance means it has arrived at this cross road
                        if car.dist_to_cross <= 0:
                            # add this car to the pass_in_prog dictionary
                            cross_road.pass_in_prog[car] = -car.dist_to_cross
                            car.dist_to_cross = 0

                    # remove cars that are already in pass_in_prog
                    queue[:] = [car for car in queue if car.dist_to_cross > 0]

            # if the traffic light is not green, we need to make sure that cars will not
            # acquire negative dist_to_cross values (i.e. we won't let then go through the sto line!)
            else:
                
                for queue in cross_road.all[:2]:
                    if len(queue) == 0:
                        continue

                    dist_move_back: Union[int, float] = 0
                    front_car = queue[-1]

                    # if the front car passes the stop line
                    if front_car.dist_to_cross < 0:
                        dist_move_back = -front_car.dist_to_cross

                        # move it back
                        front_car.dist_to_cross = 0
                    
                    # also shift subsequent cars by dist_move_back
                    for car in queue[:len(queue) - 1]:
                        car.dist_to_cross += dist_move_back

            # if the cars are in the queues of west-east direction
            if cross_road.we_state:
                for queue in cross_road.all[2:]:
                    if len(queue) == 0:
                        continue

                    for car in queue:
                        car.dist_to_cross -= time
                        car.updated = True

                        if car.dist_to_cross <= 0:
                            cross_road.pass_in_prog[car] = -car.dist_to_cross
                            car.dist_to_cross = 0

                    queue[:] = [car for car in queue if car.dist_to_cross > 0]
                
            else:
                for queue in cross_road.all[2:]:
                    if len(queue) == 0:
                        continue
                    dist_move_back = 0
                    front_car = queue[-1]
                    if front_car.dist_to_cross < 0:
                        dist_move_back = -front_car.dist_to_cross
                        front_car.dist_to_cross = 0
                    for car in queue[:len(queue) - 1]:
                        car.dist_to_cross -= dist_move_back

            for queue in cross_road.all:
                for car in queue:
                    car.updated = True

    def update_cars(self, time: Union[int, float]) -> bool:
        """
        :param time: the global time step
        :return:
        Assumption: All cars' velocities are 1
                    The length of each car is 1
                    The length of the street is measured using car length
        Warning: Must be executed after update_cross_roads
        """
        all_arrived = True
        for car in self.all_cars:

            if car.arrived:
                continue

            all_arrived = False
            # if the car has not been updated by the update_cross_roads method
            # namely, the car is not in the waiting queue or the pass in progress dict
            if not car.updated:
                # that means the car is on the way to the next queue
                # update the distance by the amount of time
                car.dist_to_cross -= time

                # if the car's distance to the next cross road is smaller than the length of the queue,
                # that means the car has reached the tail of the queue,
                # and therefore we append the car to the queue
                if car.dist_to_cross <= len(car.dest) and car not in car.dest:
                    car.dest.append(car)

            # clear the flag for the next update
            car.updated = False

            car.wait_time += time

        return all_arrived

    def update_all(self, time: Union[int, float]) -> bool:
        all_arrived = self.update_cars(time)
        self.update_cross_roads(time)
        self.time += time
        self.exec_policy()
        return all_arrived

    def exec_policy(self):
        self.policy(self.G, self.all_cross_roads, self.all_cars, self.time)

    def stats(self):
        wait_times = [car.wait_time for car in self.__all_cars__]
        total_wait_time = sum(wait_times)
        avg_wait_time = total_wait_time / len(self.__all_cars__)
        std_wait_time = np.std(wait_times)
        max_wait_time = max(wait_times)

        stat_str = "Total waiting time {}\nAverage waiting time {}\nMaximum waiting time {}\nstd. of waiting time {}\n".format(total_wait_time, avg_wait_time,
                                                                                                                               max_wait_time, std_wait_time)
        print(stat_str)


if __name__ == "__main__":
    G = nx.DiGraph()
    cross_roads = [CrossRoad(True, True, id=i) for i in range(4)]
    all_cars = [
        Car(
            2, cross_roads[0].north, [cross_roads[0], cross_roads[2], cross_roads[3]], id=0
        ),
        Car(
            3, cross_roads[3].south, [cross_roads[3], cross_roads[1], cross_roads[0]], id=1
        )
    ]
    # the edges contain two important info: the length, and the direction
    G.add_edge(cross_roads[0], cross_roads[1],
               length=10, dest=cross_roads[1].west)
    G.add_edge(cross_roads[1], cross_roads[0],
               length=10, dest=cross_roads[0].east)
    G.add_edge(cross_roads[0], cross_roads[2],
               length=10, dest=cross_roads[2].north)
    G.add_edge(cross_roads[2], cross_roads[0],
               length=10, dest=cross_roads[0].south)
    G.add_edge(cross_roads[1], cross_roads[3],
               length=10, dest=cross_roads[3].north)
    G.add_edge(cross_roads[3], cross_roads[1],
               length=10, dest=cross_roads[1].south)
    G.add_edge(cross_roads[3], cross_roads[2],
               length=10, dest=cross_roads[2].east)
    G.add_edge(cross_roads[2], cross_roads[3],
               length=10, dest=cross_roads[3].west)

    w = World(G, cross_roads, all_cars, lambda a, b, c, d: None)

    for i in range(40):
        print(i)
        if w.update_all(1):
            break

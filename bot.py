# SPDX-License-Identifier: BSD-3-Clause

# flake8: noqa F401
from collections.abc import Callable
from typing import Optional, Any

import random

import numpy as np

from vendeeglobe import Heading, Instructions, Location

from enum import Enum


NAV_LOCATIONS = [
    Location(-80.0, 9.6),
    Location(-79.4, 8.7),
    Location(-79.4, 6.5),
    190.0,
    Location(80.0, -22.5),
    120.0,
    Location(55.0, 14.0),
    Location(43.7, 12.2),
    116.0,
    Location(33.9, 27.6),
    120.0,
    Location(-5.3, 36.0),
    190.0,
    Location(-1.8, 46.5),
    None,
]


class NavLatitudes(float, Enum):
    AMERICAS = -22.0
    CENTRAL_AMERICA = -65.8
    OCEANIA_ONE = -160.2
    SOUTH_AUSTRALIA = 180.0
    SOUTH_WEST_AUSTRALIA = 133.0
    INDIAN_OCEAN = 100.0
    INDIAN_OCEAN_TWO = 90.0
    ARABIAN_SEA = 60.0
    RED_SEA = 40.0
    RED_SEA_TWO = 35.0
    MEDITTERANEAN = 31.4
    MEDITTERANEAN_TWO = 12.7
    MEDITTERANEAN_THREE = 11.0
    MEDITTERANEAN_FOUR = -3.9
    GIBRALTAR = -6.2
    PORTUGAL = -10.2
    FRANCE = -9.9


class Turn(Enum):
    NO = 0
    RIGHT = 1
    LEFT = 2


class Bot:
    """
    This is the ship-controlling bot that will be instantiated for the competition.
    """

    intended_heading: float
    tack_within_degrees: float
    time_adjusted: Optional[float]
    last_turn: Turn
    course_plan: dict[Any, Any]
    actual_course: dict[Any, Any]
    tack: bool
    coord_navigation: bool
    current_nav_location: int
    nav_location_reached: bool
    previous_lat: float
    previous_long: float
    unstick_mode: dict[Any, Any]

    def __init__(self):
        self.team = "Big Brain Boat"  # This is your team name
        self.intended_heading = 180.0
        self.tack_within_degrees = 45.0
        self.tack_time_hours = 6.0
        self.time_adjusted = None
        self.last_turn = Turn.NO
        self.course_plan = {NavLatitudes.AMERICAS: {"N": 90.0, "S": 250.0}}
        self.actual_course = {NavLatitudes.AMERICAS: {}}
        self.tack = True
        self.coord_navigation = False
        self.current_nav_location = 0
        self.nav_location_reached = False
        self.previous_lat = 0.0
        self.previous_long = 0.0
        self.unstick_mode = {}

    def run(
        self,
        t: float,
        dt: float,
        longitude: float,
        latitude: float,
        heading: float,
        speed: float,
        vector: np.ndarray,
        forecast: Callable,
        world_map: Callable,
    ) -> Instructions:
        """
        This is the method that will be called at every time step to get the
        instructions for the ship.

        Parameters
        ----------
        t:
            The current time in hours.
        dt:
            The time step in hours.
        longitude:
            The current longitude of the ship.
        latitude:
            The current latitude of the ship.
        heading:
            The current heading of the ship.
        speed:
            The current speed of the ship.
        vector:
            The current heading of the ship, expressed as a vector.
        forecast:
            Method to query the weather forecast for the next 5 days.
            Example:
            current_position_forecast = forecast(
                latitudes=latitude, longitudes=longitude, times=0
            )
        world_map:
            Method to query map of the world: 1 for sea, 0 for land.
            Example:
            current_position_terrain = world_map(
                latitudes=latitude, longitudes=longitude
            )

        Returns
        -------
        instructions:
            A set of instructions for the ship. This can be:
            - a Location to go to
            - a Heading to point to
            - a Vector to follow
            - a number of degrees to turn Left
            - a number of degrees to turn Right

            Optionally, a sail value between 0 and 1 can be set.
        """

        if NAV_LOCATIONS[self.current_nav_location] is None:
            instructions = Instructions(sail=0)
            return instructions
        current_position_forecast = forecast(
            latitudes=latitude, longitudes=longitude, times=0
        )

        wind_heading = self.wind_heading(*current_position_forecast)

        print(
            f"{np.round(t, 2)} :: long: {np.round(longitude, 1)}, lat: {np.round(latitude, 1)}. Tack: {self.tack}"
        )
        # Initialize the instructions
        instructions = Instructions()
        instructions.heading = Heading(self.intended_heading)
        instructions.sail = 1
        if latitude == self.previous_lat and longitude == self.previous_long:
            print("Trying to unstick")
            self.unstick(heading, np.round(t, 1))
            if t > self.unstick_mode["time"] and t < self.unstick_mode["time"] + 2.0:
                print(f"Sailing back to {self.unstick_mode['back']}")
                instructions.heading = Heading(self.unstick_mode["back"])
                print(f"Instructions: {instructions}")
                return instructions
            elif (
                t > self.unstick_mode["time"] + 2.0
                and t < self.unstick_mode["time"] + 4.0
            ):
                print(f"Sailing angled to {self.unstick_mode['turn']}")
                instructions.heading = Heading(self.unstick_mode["turn"])
                return instructions
            else:
                print("Are we unstuck yet?")
                self.unstick_mode = {}
                self.tack = True

        self.previous_long = longitude
        self.previous_lat = latitude

        if self.coord_navigation:
            if self.coord_navigate(instructions, longitude, latitude):
                print(f"Navigating to {instructions}")
                return instructions

        if self.tack:
            if correction := self.catch_wind(heading, wind_heading, t):
                instructions.heading = correction

        # if np.round(longitude, 1) == -20.0 and self.intended_heading != 90.0:
        #     print("Turning north")
        #     self.intended_heading = 90.0
        self.navigate(np.round(latitude, 1), np.round(longitude, 1), wind_heading)
        print(f"Instructions: {instructions}")
        return instructions

    def unstick(self, current_heading: float, time: float):
        if self.unstick_mode:
            print("unstick already set")
            return
        self.tack = False
        self.unstick_mode["back"] = self.minus_wrap(
            current_heading, random.choice([135.0, 225.0])
        )
        self.unstick_mode["turn"] = self.plus_wrap(
            self.minus_wrap(current_heading, 180.0), 90.0
        )
        self.unstick_mode["time"] = time

    def coord_navigate(
        self, instructions: Instructions, longitude: float, latitude: float
    ) -> bool:
        """returns True to continue coord_navigating, False to resume heading navigation"""
        instructions.heading = None

        if not isinstance(NAV_LOCATIONS[self.current_nav_location], float):
            print(f"Not a float: {NAV_LOCATIONS[self.current_nav_location]}")
            instructions.location = NAV_LOCATIONS[self.current_nav_location]
        else:
            print(f"Float: {NAV_LOCATIONS[self.current_nav_location]}")
            self.nav_location_reached = False
            instructions.location = None
            self.coord_navigation = False
            self.intended_heading = NAV_LOCATIONS[self.current_nav_location]
            instructions.heading = Heading(self.intended_heading)
            return False
        if self.nav_location_reached:
            print(f"Reached {Location(np.round(longitude, 1), np.round(latitude, 1))}")
            self.current_nav_location += 1
            self.nav_location_reached = False
        else:
            self.nav_location_reached = (
                Location(np.round(longitude, 1), np.round(latitude, 1))
                == NAV_LOCATIONS[self.current_nav_location]
            )
        return True

    def navigate(self, lat: float, long: float, wind_heading: float) -> None:
        if long == NavLatitudes.AMERICAS and self.intended_heading == 180.0:
            print("Checking prevailing wind direction")
            self.intended_heading = 220.0
        # elif (
        #     long == NavLatitudes.CENTRAL_AMERICA_ONE and self.intended_heading == 200.0
        # ):
        #     self.intended_heading = 180.0
        elif long == NavLatitudes.CENTRAL_AMERICA and self.intended_heading == 220.0:
            self.intended_heading = 180.0
            self.coord_navigation = True
        elif long == NavLatitudes.OCEANIA_ONE and self.intended_heading == 190.0:
            self.intended_heading = 250.0
        elif long == NavLatitudes.SOUTH_AUSTRALIA and self.intended_heading == 250.0:
            self.intended_heading = 180.0
        elif (
            long == NavLatitudes.SOUTH_WEST_AUSTRALIA and self.intended_heading == 180.0
        ):
            self.intended_heading = 130.0
        elif long == NavLatitudes.INDIAN_OCEAN and self.intended_heading == 130.0:
            self.intended_heading = 180.0
        elif long == NavLatitudes.INDIAN_OCEAN_TWO and self.intended_heading == 180.0:
            self.coord_navigation = True
            self.current_nav_location = 4
        elif long == NavLatitudes.ARABIAN_SEA and self.intended_heading == 120.0:
            self.coord_navigation = True
            self.current_nav_location = 6
        elif long == NavLatitudes.RED_SEA and self.intended_heading == 116.0:
            self.intended_heading = 120.0
        elif long == NavLatitudes.RED_SEA_TWO and self.intended_heading == 120.0:
            self.coord_navigation = True
            self.current_nav_location = 9
        elif long == NavLatitudes.MEDITTERANEAN and self.intended_heading == 120.0:
            self.intended_heading = 170.0
        elif long == NavLatitudes.MEDITTERANEAN_TWO and self.intended_heading == 170.0:
            self.intended_heading = 117.0
        elif (
            long == NavLatitudes.MEDITTERANEAN_THREE and self.intended_heading == 117.0
        ):
            self.intended_heading = 187.0
        elif long == NavLatitudes.MEDITTERANEAN_FOUR and self.intended_heading == 187.0:
            self.coord_navigation = True
            self.current_nav_location = 11
        elif long == NavLatitudes.GIBRALTAR and self.intended_heading == 190.0:
            self.intended_heading = 170.0
        elif long == NavLatitudes.PORTUGAL and self.intended_heading == 170.0:
            self.intended_heading = 89.0
        elif long == NavLatitudes.FRANCE and self.intended_heading == 89.0:
            self.coord_navigation = True
            self.current_nav_location = 13

    def should_turn(
        self,
        wind_heading: float,
        turn_above_heading: float,
        turn_below_heading: float,
        current_heading: float,
    ) -> Turn:
        if (
            wind_heading > turn_above_heading
            and wind_heading < turn_below_heading
            and self.within_acceptable_deviation(current_heading)
        ):
            print(
                f"Should turn left or tack right: {wind_heading} > {turn_above_heading} and {wind_heading} < {turn_below_heading} and {current_heading} <=> {self.intended_heading}"
            )
            return Turn.LEFT
        elif (
            wind_heading < turn_above_heading
            and wind_heading > turn_below_heading
            and current_heading != self.intended_heading
        ):
            print(
                f"Should turn right or tack left: {wind_heading} < {turn_above_heading} and {wind_heading} > {turn_below_heading} and {current_heading} <=> {self.intended_heading}"
            )
            return Turn.RIGHT

        # print(
        #     f"Should not turn: Wind: {wind_heading} Turn above: {turn_above_heading} Turn below: {turn_below_heading} Current: {current_heading} Intended: {self.intended_heading}"
        # )
        return Turn.NO

    def catch_wind(
        self,
        current_heading: float,
        wind_heading: float,
        timestamp: float,
    ) -> Optional[Heading]:
        """
        Turn to catch the wind if we're sailing too much against it

        Returns the new Heading to follow (max within 30 degrees of current)
        """

        turn_below_heading = self.plus_wrap(
            self.plus_wrap(180.0, self.intended_heading), self.tack_within_degrees
        )
        turn_above_heading = self.minus_wrap(
            self.plus_wrap(180.0, self.intended_heading), self.tack_within_degrees
        )
        if turn_below_heading < turn_above_heading:
            turn_below_heading = 360.0

        should_turn = self.should_turn(
            wind_heading, turn_above_heading, turn_below_heading, current_heading
        )

        if should_turn == Turn.LEFT and (
            not self.time_adjusted
            or (timestamp - self.tack_time_hours) > self.time_adjusted
        ):
            print(
                f"Adjusting: turning left ({wind_heading} > {turn_above_heading} and {current_heading} within acceptable deviation of {self.intended_heading})"
            )
            adjustment = 45.0
            new_heading = self.plus_wrap(self.intended_heading, adjustment)
            # adjustment = wind_heading - turn_above_heading + 40.0
            # new_heading = self.plus_wrap(current_heading, adjustment)
            print(f"Adjusting {current_heading} by {adjustment} for {new_heading}")
            # new_heading = self.plus_wrap(
            #     current_heading,
            #     self.plus_wrap(
            #         wind_heading,
            #         self.plus_wrap(self.intended_heading, 180.0),
            #     ),
            # )
            print(f"New heading: {new_heading}")
            if self.last_turn == Turn.LEFT:
                self.last_turn = Turn.RIGHT
                new_heading = self.minus_wrap(new_heading, 90.0)
                print(f"Tacking to {new_heading}")
            else:
                self.last_turn = Turn.LEFT
                print("Not tacking - last turn was left")
            self.time_adjusted = timestamp
            return Heading(new_heading)
        elif should_turn == Turn.RIGHT and (
            not self.time_adjusted
            or (timestamp - self.tack_time_hours) > self.time_adjusted
        ):
            print(
                f"Adjusting: turning right ({wind_heading} < {turn_above_heading} and {current_heading} within acceptable deviation of {self.intended_heading})"
            )
            adjustment = 45.0
            new_heading = self.minus_wrap(self.intended_heading, adjustment)
            # adjustment = turn_below_heading - wind_heading + 40.0
            # new_heading = self.minus_wrap(current_heading, adjustment)
            print(f"Adjusting {current_heading} by {adjustment} for {new_heading}")
            # new_heading = self.minus_wrap(
            #     current_heading,
            #     self.minus_wrap(
            #         wind_heading,
            #         self.plus_wrap(self.intended_heading, 180.0),
            #     ),
            # )
            print(f"New heading: {new_heading}")
            if self.last_turn == Turn.RIGHT:
                self.last_turn = Turn.LEFT
                new_heading = self.plus_wrap(new_heading, 90.0)
                print(f"Tacking to {new_heading}")
            else:
                self.last_turn = Turn.RIGHT
                print("Not tacking - last turn was right")
            self.time_adjusted = timestamp
            return Heading(new_heading)
        else:
            self.time_adjusted = None
            print(
                f"Should not turn: {wind_heading} !> {turn_above_heading} and {wind_heading} !< {turn_below_heading} and {current_heading} <=> {self.intended_heading}"
            )
            return Heading(self.intended_heading)

    def minus_wrap(self, a: float, b: float) -> float:
        """a - b, wrapped around to 360.0 at 0.0"""
        res = a - b
        if res < 0.0:
            return res + 360.0
        else:
            return res

    def plus_wrap(self, a: float, b: float) -> float:
        """a + b, wrapped around at 360.0"""
        res = a + b
        if res > 360.0:
            return res - 360.0
        else:
            return res

    def within_acceptable_deviation(self, current_heading: float) -> bool:
        if current_heading > self.minus_wrap(
            self.intended_heading, 45.0
        ) and current_heading < self.plus_wrap(self.intended_heading, 45.0):
            return True
        else:
            return False

    def wind_heading(self, horizontal: float, vertical: float) -> float:
        # r = np.sqrt(pow(horizontal, 2) + pow(vertical, 2))
        phi = np.rad2deg(np.arctan2(vertical, horizontal))
        # print(f"Wind r: {r}, wind phi: {phi}")
        if phi < 0:
            phi = -phi
        else:
            phi = phi + 180.0

        if phi == 0.0:
            return phi
        else:
            return 360.0 - phi

# SPDX-License-Identifier: BSD-3-Clause

# flake8: noqa F401
from collections.abc import Callable
from typing import Optional

import numpy as np

from vendeeglobe import Heading, Instructions

from enum import Enum


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

    def __init__(self):
        self.team = "Venefyxatu"  # This is your team name
        self.intended_heading = 180.0
        self.tack_within_degrees = 45.0
        self.tack_time_hours = 4.0
        self.time_adjusted = None
        self.last_turn = Turn.NO

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
        # Initialize the instructions
        instructions = Instructions()
        instructions.heading = Heading(self.intended_heading)
        instructions.sail = 1

        current_position_forecast = forecast(
            latitudes=latitude, longitudes=longitude, times=0
        )

        if correction := self.catch_wind(heading, current_position_forecast, t):
            instructions.heading = correction

        # print(f"long: {np.round(longitude, 1)}, lat: {np.round(latitude, 1)}")
        if np.round(longitude, 1) == -20.0 and self.intended_heading != 90.0:
            print("Turning north")
            self.intended_heading = 90.0
        return instructions

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

        return Turn.NO

    def catch_wind(
        self,
        current_heading: float,
        current_position_forecast: tuple[float, float],
        timestamp: float,
    ) -> Optional[Heading]:
        """
        Turn to catch the wind if we're sailing too much against it

        Returns the new Heading to follow (max within 30 degrees of current)
        """

        wind_heading = self.wind_heading(*current_position_forecast)
        # turn_below_heading = 30.0  # for an intended_heading of 180.0
        # turn_above_heading = 330.0  # for an intended_heading of 180.0
        turn_below_heading = self.plus_wrap(
            self.plus_wrap(180.0, self.intended_heading), self.tack_within_degrees
        )
        turn_above_heading = self.minus_wrap(
            self.plus_wrap(180.0, self.intended_heading), self.tack_within_degrees
        )

        should_turn = self.should_turn(
            wind_heading, turn_above_heading, turn_below_heading, current_heading
        )

        if should_turn == Turn.LEFT and (
            not self.time_adjusted
            or (timestamp - self.tack_time_hours) > self.time_adjusted
        ):
            if turn_above_heading < wind_heading < self.intended_heading:
                # print(
                #     f"Adjusting: turning left ({wind_heading} > {turn_above_heading} and {current_heading} within acceptable deviation of {self.intended_heading})"
                # )
                new_heading = self.plus_wrap(
                    current_heading,
                    self.plus_wrap(
                        wind_heading,
                        self.plus_wrap(self.intended_heading, 180.0),
                    ),
                )
                print(
                    f"New heading: {self.plus_wrap(self.intended_heading, 180.0)} - {self.minus_wrap(wind_heading, self.plus_wrap(self.intended_heading, 180.0))} = {new_heading}"
                )
                if self.last_turn == Turn.LEFT:
                    self.last_turn = Turn.RIGHT
                    new_heading = self.minus_wrap(new_heading, 90.0)
                    print(f"Tacking to {new_heading}")
                else:
                    self.last_turn = Turn.LEFT
                self.time_adjusted = timestamp
                return Heading(new_heading)
            elif self.intended_heading < wind_heading < turn_below_heading:
                # print(
                #     f"Adjusting: turning right ({wind_heading} < {turn_above_heading} and {current_heading} within acceptable deviation of {self.intended_heading})"
                # )
                new_heading = self.minus_wrap(
                    current_heading,
                    self.minus_wrap(
                        wind_heading,
                        self.plus_wrap(self.intended_heading, 180.0),
                    ),
                )
                print(
                    f"New heading: {self.plus_wrap(self.intended_heading, 180.0)} - {self.plus_wrap(wind_heading, self.plus_wrap(self.intended_heading, 180.0))} = {new_heading}"
                )
                print(f"New heading: {new_heading}")
                if self.last_turn == Turn.RIGHT:
                    self.last_turn = Turn.LEFT
                    new_heading = self.plus_wrap(new_heading, 90.0)
                    print(f"Tacking to {new_heading}")
                else:
                    self.last_turn = Turn.RIGHT
                self.time_adjusted = timestamp
                return Heading(new_heading)
        elif should_turn == Turn.RIGHT:
            print(
                f"{wind_heading} < {turn_above_heading} and {wind_heading} > {turn_below_heading}: resuming intended heading"
            )
            self.time_adjusted = None
            return Heading(self.intended_heading)
        else:
            print(
                f"Should not turn: {wind_heading} !> {turn_above_heading} and {wind_heading} !< {turn_below_heading} and {current_heading} <=> {self.intended_heading}"
            )
        # elif (
        #     wind_heading < self.minus_wrap(current_heading, 90.0)
        #     and current_heading != self.intended_heading
        # ):
        #     print("Resuming original heading")
        #     return Heading(self.intended_heading)
        # elif (
        #     wind_heading > self.plus_wrap(current_heading, 90.0)
        #     and current_heading != self.intended_heading
        # ):
        #     print("Resuming original heading")
        #     return Heading(self.intended_heading)

    def minus_wrap(self, a: float, b: float, log: bool = False) -> float:
        """a - b, wrapped around to 360.0 at 0.0"""
        res = a - b
        if log:
            print(f"minus_wrap: {a} - {b} = {res}")
        if res < 0.0:
            if log:
                print(f"minus_wrap: {res} + 360.0 = {res + 360.0}")
            return res + 360.0
        else:
            return res

    def plus_wrap(self, a: float, b: float, log: bool = False) -> float:
        """a + b, wrapped around at 360.0"""
        res = a + b
        if log:
            print(f"plus_wrap: {a} + {b} = {res}")
        if res > 360.0:
            if log:
                print(f"plus_wrap: {res} - 360.0 = {res - 360.0}")
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

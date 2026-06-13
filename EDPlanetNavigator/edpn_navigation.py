# -*- coding: utf-8 -*-
"""
Pure navigation maths for EDPlanetNavigator.

These functions have no dependency on EDMC, tkinter or the overlay, so they can
be unit-tested in isolation (run this file directly to execute the self-test).

A planet in Elite Dangerous is treated as a sphere of radius ``radius_m``.
Latitude/longitude are in degrees, as reported by ``Status.json``.
"""

from __future__ import annotations

import math


def initial_bearing(cur_lat: float, cur_lon: float,
                    tgt_lat: float, tgt_lon: float) -> float:
    """Great-circle initial bearing (forward azimuth) from current to target.

    Returns degrees in ``[0, 360)`` where 0 = north. Because the shortest path
    over a sphere curves, this bearing changes as you travel; it is recomputed
    on every dashboard update so it self-corrects on the way in.
    """
    phi1 = math.radians(cur_lat)
    phi2 = math.radians(tgt_lat)
    d_lon = math.radians(tgt_lon - cur_lon)

    y = math.sin(d_lon) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lon)

    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360.0) % 360.0


def relative_turn(heading: float, bearing: float) -> float:
    """Signed turn from current ``heading`` onto ``bearing``.

    Result is in ``(-180, 180]``: positive means turn right (clockwise),
    negative means turn left (counter-clockwise). Magnitude is the number of
    degrees to turn.
    """
    return (bearing - heading + 180.0) % 360.0 - 180.0


def surface_distance(cur_lat: float, cur_lon: float,
                    tgt_lat: float, tgt_lon: float,
                    radius_m: float) -> float:
    """Great-circle (haversine) distance over the surface, in metres.

    This replaces the original plugin's Euclidean chord calculation, which used
    an inconsistent spherical convention and produced wrong distances.
    """
    phi1 = math.radians(cur_lat)
    phi2 = math.radians(tgt_lat)
    d_phi = math.radians(tgt_lat - cur_lat)
    d_lon = math.radians(tgt_lon - cur_lon)

    a = (math.sin(d_phi / 2.0) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius_m * c


def format_distance(distance_m: float) -> str:
    """Format a distance in metres as m / km / Mm, like the original plugin."""
    distance = float(distance_m)
    unit = "m"

    if distance > 1000.0:
        distance /= 1000.0
        unit = "km"

    if distance > 1000.0:
        distance /= 1000.0
        unit = "Mm"

    if unit == "m":
        return f"{round(distance)} {unit}"
    return f"{distance:.2f} {unit}"


# Eight-way compass glyphs, indexed clockwise from "straight ahead" (up).
# All from the U+2190-2199 Arrows block for broad font coverage.
_ARROW_GLYPHS = ["↑", "↗", "→", "↘",
                 "↓", "↙", "←", "↖"]


def turn_glyph(turn: float) -> str:
    """Pick an 8-way arrow glyph for a signed ``turn`` angle (degrees).

    ``turn`` is interpreted as in :func:`relative_turn` (positive = right).
    Used as the overlay fallback when vector arrows are unavailable.
    """
    idx = int(round((turn % 360.0) / 45.0)) % 8
    return _ARROW_GLYPHS[idx]


def turn_text(turn: float, deadband: float = 2.0) -> str:
    """Human-readable turn guidance, e.g. ``"turn right 23°"``."""
    if abs(turn) <= deadband:
        return "on heading"
    direction = "right" if turn > 0 else "left"
    return f"turn {direction} {abs(round(turn))}°"


def _selftest() -> None:
    """Assert known values. Run via ``python navigation.py``."""
    def approx(a: float, b: float, tol: float = 1e-6) -> bool:
        return abs(a - b) <= tol

    # Bearing due east along the equator is 90 degrees.
    assert approx(initial_bearing(0, 0, 0, 90), 90.0), initial_bearing(0, 0, 0, 90)
    # Bearing due north is 0 degrees.
    assert approx(initial_bearing(0, 0, 90, 0), 0.0), initial_bearing(0, 0, 90, 0)
    # Bearing due west is 270 degrees.
    assert approx(initial_bearing(0, 0, 0, -90), 270.0), initial_bearing(0, 0, 0, -90)

    # Turn maths: from heading 350 onto bearing 10 is +20 (right).
    assert approx(relative_turn(350, 10), 20.0), relative_turn(350, 10)
    # From heading 10 onto bearing 350 is -20 (left).
    assert approx(relative_turn(10, 350), -20.0), relative_turn(10, 350)

    # Halfway around a unit-radius sphere is pi.
    assert approx(surface_distance(0, 0, 0, 180, 1.0), math.pi), \
        surface_distance(0, 0, 0, 180, 1.0)
    # Quarter circumference of a 1000 m radius sphere.
    assert approx(surface_distance(0, 0, 0, 90, 1000.0), 1000.0 * math.pi / 2.0), \
        surface_distance(0, 0, 0, 90, 1000.0)

    # Same point => zero distance, on heading.
    assert approx(surface_distance(12.34, -56.78, 12.34, -56.78, 6e6), 0.0)

    # Formatting tiers.
    assert format_distance(500) == "500 m", format_distance(500)
    assert format_distance(1500) == "1.50 km", format_distance(1500)
    assert format_distance(2_500_000) == "2.50 Mm", format_distance(2_500_000)

    # Glyphs: straight ahead -> up, hard right -> right.
    assert turn_glyph(0) == "↑"
    assert turn_glyph(90) == "→"
    assert turn_glyph(-90) == "←"

    print("navigation.py self-test: OK")


if __name__ == "__main__":
    _selftest()

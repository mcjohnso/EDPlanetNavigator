# -*- coding: utf-8 -*-
"""
Overlay handling for EDPlanetNavigator.

Wraps the optional ``edmcoverlay`` module (provided at runtime by the
EDMCOverlay or EDMCModernOverlay plugin). Unlike the original EliteHIS, nothing
here is done at import time and the absence of the overlay never raises: if the
overlay is missing or the connection drops, :attr:`OverlayManager.available`
stays ``False`` and the caller falls back to the in-app status line.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any, List, Optional

from config import appname

_plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{_plugin_name}")

# Overlay message ids (kept stable so each update overwrites the previous one).
_ID_BODY = "edpn_body"
_ID_LINE1 = "edpn_line1"
_ID_LINE2 = "edpn_line2"
_ID_ARROW = "edpn_arrow"
_ALL_IDS = (_ID_BODY, _ID_LINE1, _ID_LINE2, _ID_ARROW)

# How long (seconds) each message lives. Refreshed on every dashboard update;
# long enough to survive the gaps between sparse Status.json updates.
_TTL = 8

_ARROW_SIZE = 26  # half-height of the directional arrow, in overlay pixels


class OverlayManager:
    """Thin, resilient client around ``edmcoverlay.Overlay``."""

    def __init__(self, color: str = "#ff7100",
                 anchor_x: int = 40, anchor_y: int = 80) -> None:
        self.color = color
        self.anchor_x = anchor_x
        self.anchor_y = anchor_y

        self._overlay: Optional[Any] = None
        self.available = False
        # Whether vector shapes work on the installed overlay; falls back to a
        # text glyph if the first attempt fails.
        self._vector_ok = True

    # ------------------------------------------------------------------ config
    def set_style(self, color: str, anchor_x: int, anchor_y: int) -> None:
        """Update appearance from preferences."""
        self.color = color
        self.anchor_x = anchor_x
        self.anchor_y = anchor_y

    # -------------------------------------------------------------- connection
    def _ensure_connected(self) -> bool:
        """Lazily import and connect. Returns True if usable."""
        if self._overlay is not None:
            return True
        try:
            from edmcoverlay import Overlay  # provided by the overlay plugin
        except Exception:
            # Not installed / not importable. Stay silent at debug level so we
            # don't spam logs every second.
            logger.debug("edmcoverlay not available; using in-app fallback")
            self.available = False
            return False

        try:
            overlay = Overlay()
            overlay.connect()
        except Exception as exc:
            logger.debug("Could not connect to EDMCOverlay: %s", exc)
            self._overlay = None
            self.available = False
            return False

        self._overlay = overlay
        self.available = True
        logger.info("Connected to EDMCOverlay")
        return True

    def _drop(self) -> None:
        """Forget the current connection so the next call reconnects."""
        self._overlay = None
        self.available = False

    # ----------------------------------------------------------------- drawing
    def show_navigation(self, bearing: float, turn: float,
                        distance_str: str, glyph: str,
                        turn_label: str, body_name: str = "") -> None:
        """Draw the current navigation guidance on the overlay.

        ``glyph`` and ``turn_label`` come from ``navigation`` and are always
        shown as text (reliable on every overlay version). A rotated vector
        arrow is drawn additionally when supported.
        """
        if not self._ensure_connected():
            return

        ax, ay = self.anchor_x, self.anchor_y
        header = body_name or "EDPlanetNavigator"
        line1 = f"{glyph}  {turn_label}"
        line2 = f"Dist {distance_str}    Brng {round(bearing)}°"

        try:
            self._overlay.send_message(_ID_BODY, header, self.color,
                                       ax, ay, ttl=_TTL, size="normal")
            self._overlay.send_message(_ID_LINE1, line1, self.color,
                                       ax + 70, ay + 30, ttl=_TTL, size="large")
            self._overlay.send_message(_ID_LINE2, line2, self.color,
                                       ax + 70, ay + 62, ttl=_TTL, size="normal")
        except Exception as exc:
            logger.debug("Overlay send_message failed, will reconnect: %s", exc)
            self._drop()
            return

        self._draw_arrow(ax + 20, ay + 52, turn)

    def _draw_arrow(self, cx: int, cy: int, turn: float) -> None:
        """Draw a rotated arrow pointing toward the target relative to heading.

        Best-effort: if the installed overlay can't render vector shapes we
        give up quietly (the text glyph already conveys the direction).
        """
        if not self._vector_ok or self._overlay is None:
            return
        try:
            self._overlay.send_raw({
                "id": _ID_ARROW,
                "shape": "vect",
                "color": self.color,
                "ttl": _TTL,
                "vector": _arrow_points(cx, cy, _ARROW_SIZE, turn),
            })
        except Exception as exc:
            # Either send_raw is unavailable or "vect" isn't supported here.
            logger.debug("Vector arrow unavailable, falling back to glyph: %s", exc)
            self._vector_ok = False

    # ------------------------------------------------------------------- clear
    def clear(self) -> None:
        """Remove our overlay messages (e.g. on leaving a planet surface)."""
        if self._overlay is None:
            return
        try:
            for msg_id in (_ID_BODY, _ID_LINE1, _ID_LINE2):
                self._overlay.send_message(msg_id, "", self.color, 0, 0, ttl=1)
            if self._vector_ok:
                self._overlay.send_raw({
                    "id": _ID_ARROW, "shape": "vect", "color": self.color,
                    "ttl": 1, "vector": [],
                })
        except Exception as exc:
            logger.debug("Overlay clear failed: %s", exc)
            self._drop()

    def close(self) -> None:
        """Clear messages and drop the connection on shutdown."""
        self.clear()
        self._drop()


def _arrow_points(cx: int, cy: int, size: float, turn_deg: float) -> List[dict]:
    """Vertices for an arrow centred at ``(cx, cy)`` pointing along ``turn_deg``.

    ``turn_deg`` is the signed turn angle (0 = straight ahead/up, positive =
    right). The returned polyline is ``tail -> tip -> left wing -> tip ->
    right wing`` in overlay pixel coordinates (origin top-left, y downward).
    """
    ang = math.radians(turn_deg)
    cos_a, sin_a = math.cos(ang), math.sin(ang)

    def rot(px: float, py: float) -> dict:
        # Standard rotation; with screen y pointing down a positive angle
        # rotates clockwise, matching "positive turn = to the right".
        rx = px * cos_a - py * sin_a
        ry = px * sin_a + py * cos_a
        return {"x": int(round(cx + rx)), "y": int(round(cy + ry))}

    head = size
    wing = size * 0.55
    tail = size * 0.85

    tip = rot(0.0, -head)
    left = rot(-wing, -head + wing)
    right = rot(wing, -head + wing)
    back = rot(0.0, tail)
    return [back, tip, left, tip, right]

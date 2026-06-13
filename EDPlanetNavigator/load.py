# -*- coding: utf-8 -*-
"""
EDPlanetNavigator — an EDMarketConnector plugin.

Shows live navigation guidance (bearing, which way to turn, and distance) toward
a target latitude/longitude while flying near a planet, both as an on-screen
overlay and in the EDMC window. A modern, maintained replacement for the
unmaintained EliteHIS plugin by CMDR fiinnnn.

EDMC calls the module-level callbacks below (plugin_start3, plugin_app, etc.).
All of them run on the main Tk thread, so updating tk variables and sending to
the overlay socket from here is safe.
"""

from __future__ import annotations

import logging
import os
import sys
import tkinter as tk
from typing import Any, Optional

import myNotebook as nb  # type: ignore  # provided by EDMC
from config import appname, config  # type: ignore  # provided by EDMC
from theme import theme  # type: ignore  # provided by EDMC

import edpn_navigation as nav
from edpn_overlay import OverlayManager

__version__ = "1.0.0"

# Module is its own state container, per EDMC convention.
this: Any = sys.modules[__name__]

_PLUGIN_NAME = "EDPlanetNavigator"
_plugin_dir_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{_plugin_dir_name}")

# Config keys (prefixed to avoid clashing with other plugins).
_CFG_LAT = "edpn_target_lat"
_CFG_LON = "edpn_target_lon"
_CFG_HAS_TARGET = "edpn_has_target"
_CFG_AUTO_RADIUS = "edpn_auto_radius"
_CFG_RADIUS_KM = "edpn_manual_radius_km"
_CFG_COLOR = "edpn_overlay_color"
_CFG_ANCHOR_X = "edpn_anchor_x"
_CFG_ANCHOR_Y = "edpn_anchor_y"


# --------------------------------------------------------------------- helpers
def _parse_float(text: str) -> Optional[float]:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


def _get_float_setting(key: str, fallback: Optional[float]) -> Optional[float]:
    raw = config.get_str(key, default="")
    value = _parse_float(raw) if raw else None
    return fallback if value is None else value


def _coord_str(value: Optional[float]) -> str:
    return "" if value is None else f"{value:g}"


def _load_settings() -> None:
    """Populate runtime state from persisted config and reset session state."""
    this.target_lat = _get_float_setting(_CFG_LAT, None)
    this.target_lon = _get_float_setting(_CFG_LON, None)
    this.has_target = bool(
        config.get_bool(_CFG_HAS_TARGET, default=False)
        and this.target_lat is not None
        and this.target_lon is not None
    )

    this.auto_radius = bool(config.get_bool(_CFG_AUTO_RADIUS, default=True))
    radius_km = _get_float_setting(_CFG_RADIUS_KM, 0.0) or 0.0
    this.manual_radius_m = max(0.0, radius_km) * 1000.0

    this.overlay_color = config.get_str(_CFG_COLOR, default="#ff7100") or "#ff7100"
    this.anchor_x = config.get_int(_CFG_ANCHOR_X, default=40)
    this.anchor_y = config.get_int(_CFG_ANCHOR_Y, default=80)

    # Session state (last dashboard reading).
    this.cur_lat = 0.0
    this.cur_lon = 0.0
    this.cur_alt = 0.0
    this.cur_heading = -1.0
    this.cur_radius = 0.0
    this.on_surface = False
    this.body_name = ""

    # UI variables, created lazily in plugin_app.
    this.ui_status = None
    this.ui_lat = None
    this.ui_lon = None


def _current_radius() -> float:
    """Planet radius to use: auto-detected when available, else manual."""
    if this.auto_radius and this.cur_radius and this.cur_radius > 0:
        return this.cur_radius
    return this.manual_radius_m


def _persist_target() -> None:
    if this.has_target and this.target_lat is not None and this.target_lon is not None:
        config.set(_CFG_LAT, str(this.target_lat))
        config.set(_CFG_LON, str(this.target_lon))
        config.set(_CFG_HAS_TARGET, True)
    else:
        config.set(_CFG_HAS_TARGET, False)


def _persist_all() -> None:
    _persist_target()
    config.set(_CFG_AUTO_RADIUS, bool(this.auto_radius))
    config.set(_CFG_RADIUS_KM, str(this.manual_radius_m / 1000.0))
    config.set(_CFG_COLOR, this.overlay_color)
    config.set(_CFG_ANCHOR_X, int(this.anchor_x))
    config.set(_CFG_ANCHOR_Y, int(this.anchor_y))


def _set_status(text: str) -> None:
    if this.ui_status is not None:
        this.ui_status.set(text)


def _refresh(_reason: str = "") -> None:
    """Recompute guidance from the latest position and target, then display it."""
    if not this.has_target or this.target_lat is None or this.target_lon is None:
        _set_status("No target set — enter a latitude and longitude above.")
        return

    if not this.on_surface:
        _set_status(
            f"Target {this.target_lat:g}, {this.target_lon:g} — "
            "fly close to a planet surface to navigate."
        )
        return

    bearing = nav.initial_bearing(
        this.cur_lat, this.cur_lon, this.target_lat, this.target_lon
    )

    radius = _current_radius()
    if radius > 0:
        dist_m = nav.surface_distance(
            this.cur_lat, this.cur_lon, this.target_lat, this.target_lon, radius
        )
        distance_str = nav.format_distance(dist_m)
    else:
        distance_str = "n/a (set planet radius)"

    heading = this.cur_heading
    if heading is not None and heading >= 0:
        turn = nav.relative_turn(heading, bearing)
        glyph = nav.turn_glyph(turn)
        turn_label = nav.turn_text(turn)
    else:
        turn = 0.0
        glyph = "•"
        turn_label = "heading n/a"

    _set_status(
        f"{glyph} {turn_label}  |  Dist {distance_str}  |  "
        f"Brng {round(bearing)}°  →  {this.target_lat:g}, {this.target_lon:g}"
    )

    if this.overlay_mgr is not None:
        this.overlay_mgr.show_navigation(
            bearing, turn, distance_str, glyph, turn_label, this.body_name
        )


# ----------------------------------------------------------------- UI handlers
def _on_set() -> None:
    lat = _parse_float(this.ui_lat.get())
    lon = _parse_float(this.ui_lon.get())
    if lat is None or lon is None:
        _set_status("Invalid coordinates — enter numbers, e.g. 12.34 and -56.78.")
        return
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        _set_status("Latitude must be -90..90 and longitude -180..180.")
        return

    this.target_lat, this.target_lon, this.has_target = lat, lon, True
    this.ui_lat.set(_coord_str(lat))
    this.ui_lon.set(_coord_str(lon))
    _persist_target()
    _refresh("set")


def _on_clear() -> None:
    this.target_lat = None
    this.target_lon = None
    this.has_target = False
    if this.ui_lat is not None:
        this.ui_lat.set("")
        this.ui_lon.set("")
    _persist_target()
    if this.overlay_mgr is not None:
        this.overlay_mgr.clear()
    _refresh("clear")


# ------------------------------------------------------------- EDMC entrypoints
def plugin_start3(plugin_dir: str) -> str:
    """Load the plugin. Returns the internal/display name."""
    _load_settings()
    this.overlay_mgr = OverlayManager(
        this.overlay_color, this.anchor_x, this.anchor_y
    )
    logger.info("%s %s loaded", _PLUGIN_NAME, __version__)
    return _PLUGIN_NAME


def plugin_stop() -> None:
    """Tear down on application exit."""
    if getattr(this, "overlay_mgr", None) is not None:
        this.overlay_mgr.close()
    logger.info("%s stopped", _PLUGIN_NAME)


def plugin_app(parent: tk.Frame) -> tk.Frame:
    """Build the row shown in the main EDMC window."""
    this.ui_status = tk.StringVar(value="No target set")
    this.ui_lat = tk.StringVar(value=_coord_str(this.target_lat))
    this.ui_lon = tk.StringVar(value=_coord_str(this.target_lon))

    frame = tk.Frame(parent)
    frame.columnconfigure(2, weight=1)

    tk.Label(
        frame, textvariable=this.ui_status, anchor=tk.W, justify=tk.LEFT
    ).grid(row=0, column=0, columnspan=5, sticky=tk.EW)

    tk.Label(frame, text="Target:").grid(row=1, column=0, sticky=tk.W, padx=(0, 4))
    tk.Entry(frame, textvariable=this.ui_lat, width=9).grid(row=1, column=1, sticky=tk.W)
    tk.Entry(frame, textvariable=this.ui_lon, width=9).grid(
        row=1, column=2, sticky=tk.W, padx=(4, 4)
    )
    tk.Button(frame, text="Set", command=_on_set).grid(row=1, column=3, sticky=tk.W)
    tk.Button(frame, text="Clear", command=_on_clear).grid(row=1, column=4, sticky=tk.W)

    theme.update(frame)
    _refresh("app_start")
    return frame


def plugin_prefs(parent: nb.Notebook, cmdr: str, is_beta: bool) -> tk.Frame:
    """Build the settings tab."""
    pad = 8
    this.pref_lat = tk.StringVar(value=_coord_str(this.target_lat))
    this.pref_lon = tk.StringVar(value=_coord_str(this.target_lon))
    this.pref_auto = tk.BooleanVar(value=this.auto_radius)
    this.pref_radius_km = tk.StringVar(
        value="" if this.manual_radius_m <= 0 else f"{this.manual_radius_m / 1000.0:g}"
    )
    this.pref_color = tk.StringVar(value=this.overlay_color)
    this.pref_ax = tk.StringVar(value=str(this.anchor_x))
    this.pref_ay = tk.StringVar(value=str(this.anchor_y))

    frame = nb.Frame(parent)
    frame.columnconfigure(1, weight=1)
    row = 0

    nb.Label(frame, text=f"{_PLUGIN_NAME} {__version__}").grid(
        row=row, column=0, columnspan=2, padx=pad, pady=(pad, 0), sticky=tk.W
    )
    row += 1
    nb.Label(
        frame, text="Default target coordinates (degrees)"
    ).grid(row=row, column=0, columnspan=2, padx=pad, pady=(pad, 0), sticky=tk.W)
    row += 1
    nb.Label(frame, text="Latitude").grid(row=row, column=0, padx=pad, sticky=tk.W)
    nb.Entry(frame, textvariable=this.pref_lat).grid(
        row=row, column=1, padx=pad, sticky=tk.EW
    )
    row += 1
    nb.Label(frame, text="Longitude").grid(row=row, column=0, padx=pad, sticky=tk.W)
    nb.Entry(frame, textvariable=this.pref_lon).grid(
        row=row, column=1, padx=pad, sticky=tk.EW
    )
    row += 1

    nb.Checkbutton(
        frame,
        text="Detect planet radius automatically (recommended)",
        variable=this.pref_auto,
    ).grid(row=row, column=0, columnspan=2, padx=pad, pady=(pad, 0), sticky=tk.W)
    row += 1
    nb.Label(frame, text="Manual planet radius (km, used when auto is off)").grid(
        row=row, column=0, padx=pad, sticky=tk.W
    )
    nb.Entry(frame, textvariable=this.pref_radius_km).grid(
        row=row, column=1, padx=pad, sticky=tk.EW
    )
    row += 1

    nb.Label(frame, text="Overlay colour (name or #rrggbb)").grid(
        row=row, column=0, padx=pad, pady=(pad, 0), sticky=tk.W
    )
    nb.Entry(frame, textvariable=this.pref_color).grid(
        row=row, column=1, padx=pad, pady=(pad, 0), sticky=tk.EW
    )
    row += 1
    nb.Label(frame, text="Overlay position X / Y (pixels)").grid(
        row=row, column=0, padx=pad, sticky=tk.W
    )
    pos = nb.Frame(frame)
    nb.Entry(pos, textvariable=this.pref_ax, width=6).grid(row=0, column=0)
    nb.Entry(pos, textvariable=this.pref_ay, width=6).grid(row=0, column=1, padx=(4, 0))
    pos.grid(row=row, column=1, padx=pad, sticky=tk.W)
    row += 1

    nb.Label(
        frame,
        text="Requires the EDMCOverlay (or EDMCModernOverlay) plugin for the\n"
        "in-game overlay. Without it, guidance still shows in this window.",
    ).grid(row=row, column=0, columnspan=2, padx=pad, pady=(pad, 0), sticky=tk.W)

    return frame


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """Persist and apply settings when the dialog closes."""
    lat = _parse_float(this.pref_lat.get())
    lon = _parse_float(this.pref_lon.get())
    lat_blank = this.pref_lat.get().strip() == ""
    lon_blank = this.pref_lon.get().strip() == ""

    if lat_blank and lon_blank:
        this.target_lat = this.target_lon = None
        this.has_target = False
    elif (
        lat is not None
        and lon is not None
        and -90.0 <= lat <= 90.0
        and -180.0 <= lon <= 180.0
    ):
        this.target_lat, this.target_lon, this.has_target = lat, lon, True
    # Otherwise keep the previous target (invalid input ignored).

    this.auto_radius = bool(this.pref_auto.get())
    km = _parse_float(this.pref_radius_km.get()) or 0.0
    this.manual_radius_m = max(0.0, km) * 1000.0
    this.overlay_color = (this.pref_color.get().strip() or "#ff7100")
    this.anchor_x = int(_parse_float(this.pref_ax.get()) or 40)
    this.anchor_y = int(_parse_float(this.pref_ay.get()) or 80)

    _persist_all()

    if this.ui_lat is not None:
        this.ui_lat.set(_coord_str(this.target_lat))
        this.ui_lon.set(_coord_str(this.target_lon))
    if this.overlay_mgr is not None:
        this.overlay_mgr.set_style(this.overlay_color, this.anchor_x, this.anchor_y)
    _refresh("prefs")


def dashboard_entry(cmdr: str, is_beta: bool, entry: dict) -> None:
    """Handle a Status.json update (~1/s while playing)."""
    if "Latitude" not in entry or "Longitude" not in entry:
        # No surface coordinates -> not near a planet. Clear once.
        if this.on_surface:
            this.on_surface = False
            if this.overlay_mgr is not None:
                this.overlay_mgr.clear()
            _refresh("left_surface")
        return

    this.on_surface = True
    this.cur_lat = entry["Latitude"]
    this.cur_lon = entry["Longitude"]
    this.cur_alt = entry.get("Altitude", 0.0)
    this.cur_heading = entry.get("Heading", -1.0)
    radius = entry.get("PlanetRadius")
    if radius:
        this.cur_radius = radius
    body = entry.get("BodyName")
    if body:
        this.body_name = body

    _refresh("dashboard")


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: Optional[str],
    station: Optional[str],
    entry: dict,
    state: dict,
) -> Optional[str]:
    """Track the current body name and clear the overlay when leaving."""
    event = entry.get("event")

    if event in ("ApproachBody", "Touchdown", "Liftoff"):
        this.body_name = entry.get("Body") or state.get("BodyName") or this.body_name
    elif event in ("LeaveBody", "SupercruiseEntry", "StartJump", "FSDJump"):
        this.body_name = ""
        this.on_surface = False
        if getattr(this, "overlay_mgr", None) is not None:
            this.overlay_mgr.clear()
        _refresh("journal_leave")

    return None

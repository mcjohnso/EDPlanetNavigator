# EDPlanetNavigator

An [EDMarketConnector](https://github.com/EDCD/EDMarketConnector) (EDMC) plugin that helps you
fly to a target latitude/longitude on a planet in **Elite Dangerous**. It shows, live, which way
to turn, the bearing to the target, and the remaining distance — both as an in‑game overlay and in
the EDMC window.

It is a modern, maintained replacement for the unmaintained
[EliteHIS](https://github.com/fiinnnn/EliteHIS) plugin.

## Features

- **Turn guidance** — uses your ship's current heading to tell you to *turn left/right by N°*,
  with an on‑screen directional arrow, not just a raw compass bearing.
- **Automatic planet radius** — reads `PlanetRadius` from the game's `Status.json`, so distances
  are correct without you typing anything (manual override available).
- **Accurate distance** — great‑circle (haversine) surface distance, shown in m / km / Mm.
- **Set a target anywhere** — type coordinates directly in the EDMC window *or* in the settings
  tab; your target is remembered between sessions.
- **Works without the overlay** — if EDMCOverlay isn't installed, guidance still appears in the
  EDMC window instead of crashing.

## Requirements

- **EDMarketConnector** (current version; Python 3.11 build).
- For the in‑game overlay: the **[EDMCOverlay](https://github.com/inorton/EDMCOverlay)** plugin, or
  the compatible **EDMCModernOverlay** fork. The overlay is optional — without it the plugin falls
  back to showing the same information in the EDMC window.

## Installation

1. Download/clone this plugin and copy the **`EDPlanetNavigator`** folder into your EDMC plugins
   directory. You can open it from EDMC via *File → Settings → Plugins → “Open”*. The path is:
   - **Windows:** `%LOCALAPPDATA%\EDMarketConnector\plugins`
   - **macOS:** `~/Library/Application Support/EDMarketConnector/plugins`
   - **Linux:** `~/.local/share/EDMarketConnector/plugins`
2. (Optional, for the overlay) install EDMCOverlay or EDMCModernOverlay the same way.
3. Restart EDMC.

## Usage

1. Find your target coordinates (e.g. from a system map, a guide, or the
   [Touchdown]/[Scan] entries in your journal).
2. In the EDMC main window, type the **latitude** and **longitude** and click **Set**
   (or set defaults in *Settings → EDPlanetNavigator*).
3. Approach the planet. Once the game reports surface coordinates, the overlay and the EDMC window
   show the turn arrow, bearing, and distance, updating about once per second as you fly.
4. Click **Clear** to stop navigating.

## Settings (Settings → EDPlanetNavigator)

| Setting | Description |
| --- | --- |
| Latitude / Longitude | Default target, remembered between sessions. |
| Detect planet radius automatically | Use `PlanetRadius` from the game (recommended). |
| Manual planet radius (km) | Used only when auto‑detect is off. |
| Overlay colour | A colour name (`red`, `yellow`, …) or `#rrggbb`. |
| Overlay position X / Y | Top‑left anchor of the overlay, in overlay pixels. |

## How it works

On every `Status.json` update EDMC passes the data to `dashboard_entry`. The plugin reads your
`Latitude`, `Longitude`, `Heading`, `Altitude` and `PlanetRadius`, then computes:

- the **great‑circle initial bearing** to the target (recomputed each tick so it self‑corrects),
- the **signed turn** from your current heading onto that bearing, and
- the **haversine surface distance** using the planet radius.

These are drawn via EDMCOverlay (`send_message` text plus a rotated `vect` arrow) and mirrored into
the EDMC window.

## Credits

- Original **EliteHIS** plugin by **CMDR fiinnnn**; the name "Help I'm Stuck" was coined by
  **CMDR Hersilia**.
- Built on **EDMarketConnector** and **EDMCOverlay**.

## License

MIT — see [LICENSE](LICENSE).

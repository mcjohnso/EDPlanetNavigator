# Changelog

All notable changes to this project are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## v1.0.0 — 2026-06-13

First release: a maintained rewrite of [EliteHIS](https://github.com/fiinnnn/EliteHIS) for the
current version of EDMarketConnector (Python 3.11).

### Added
- Live **turn guidance** — uses the ship's heading to show "turn left/right by N°" plus an
  on-screen directional arrow, instead of only an absolute bearing.
- **Automatic planet radius** detection from `Status.json` (`PlanetRadius`), with a manual override.
- **Great-circle (haversine) surface distance**, shown in m / km / Mm.
- Set/clear the target directly in the **EDMC main window**, and via the **settings tab**; the
  target is persisted between sessions.
- **Graceful fallback**: navigation data still shows in the EDMC window when EDMCOverlay isn't
  installed, instead of crashing.

### Changed (vs. EliteHIS)
- Fixed the distance calculation (the original used an inconsistent spherical convention).
- Modern EDMC entry points, `logging` instead of `print`, `__version__`, and resilient overlay
  connection handling.

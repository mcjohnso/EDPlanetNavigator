# EDPlanetNavigator

An [EDMarketConnector](https://github.com/EDCD/EDMarketConnector) (EDMC) plugin that overlays live
navigation guidance — turn arrow, bearing, and distance — for flying to a target latitude/longitude
on a planet in **Elite Dangerous**. A maintained rewrite of the unmaintained
[EliteHIS](https://github.com/fiinnnn/EliteHIS).

Repo: https://github.com/mcjohnso/EDPlanetNavigator

## Layout

- **`EDPlanetNavigator/`** — the shippable plugin. This whole folder is what gets zipped and dropped
  into EDMC's `plugins/` directory.
  - `load.py` — EDMC entry points (`plugin_start3`, `plugin_app`, `plugin_prefs`, `prefs_changed`,
    `dashboard_entry`, `journal_entry`), the UI, state, and settings persistence. Holds
    **`__version__`** — the single source of truth for the release version.
  - `edpn_navigation.py` — pure math: great-circle bearing, signed turn, haversine distance,
    formatting. No EDMC dependencies; has a runnable self-test (`python edpn_navigation.py`).
  - `edpn_overlay.py` — resilient EDMCOverlay client (lazy connect, reconnect, text + vector arrow,
    graceful absence).
  - `README.md`, `LICENSE` — ship inside the zip.
- `package.py` — builds `dist/EDPlanetNavigator-v<version>.zip`.
- `.github/workflows/` — `test.yml` (CI on push/PR) and `release.yml` (publishes a release on `v*`
  tags).
- `README.md`, `CHANGELOG.md` — repo-level docs.

## Conventions & gotchas

- **Do not rename the `edpn_`-prefixed helper modules.** EDMC adds every plugin's folder to a shared
  `sys.path`, so a generic name like `overlay.py` / `navigation.py` would collide with another
  installed plugin's same-named module (first import wins). The prefix is deliberate.
- **Helpers are imported as top-level modules** (`import edpn_navigation`,
  `from edpn_overlay import OverlayManager`), not as a package — EDMC loads `load.py` directly, so
  relative imports (`from .` ) won't work.
- **`edmcoverlay` is NOT bundled.** It's provided at runtime by the user's EDMCOverlay /
  EDMCModernOverlay plugin. The overlay is optional; without it the plugin falls back to showing
  guidance in the EDMC window.
- **Target Python 3.11** (what current EDMC bundles). Stick to the stdlib plus the EDMC-provided
  modules (`config`, `myNotebook`, `theme`).
- EDMC calls the plugin callbacks on the main Tk thread, so updating tk variables and sending to the
  overlay socket from them is safe.

## Development

EDMC's runtime modules (`config`, `myNotebook`, `theme`, `edmcoverlay`) aren't installed locally, so
`load.py` can't be imported outside EDMC. What you *can* run locally:

```sh
# Pure-math self-test (asserts known bearings / turns / distances)
python EDPlanetNavigator/edpn_navigation.py

# Syntax / compile check of all three modules
python -m py_compile EDPlanetNavigator/load.py EDPlanetNavigator/edpn_navigation.py EDPlanetNavigator/edpn_overlay.py

# Build the distributable zip
python package.py            # -> dist/EDPlanetNavigator-v<version>.zip
```

To test in the real app, copy (or symlink) the `EDPlanetNavigator/` folder into the EDMC plugins
dir and restart EDMC:
- **Windows:** `%LOCALAPPDATA%\EDMarketConnector\plugins`
- **macOS:** `~/Library/Application Support/EDMarketConnector/plugins`
- **Linux:** `~/.local/share/EDMarketConnector/plugins`

## Cutting a release

Releases are automated by `.github/workflows/release.yml`: **pushing a `v*` tag** builds the zip
(via `package.py`) and publishes a GitHub Release with it attached. Steps:

1. **Bump the version** in `EDPlanetNavigator/load.py`:
   ```python
   __version__ = "1.1.0"
   ```
   `package.py` reads this, so the zip is named to match. ⚠️ **The tag must match this version**
   (tag `v1.1.0` ↔ `__version__ = "1.1.0"`), or the zip name won't line up with the release tag.
2. **Update `CHANGELOG.md`** — add a section for the new version.
3. **Commit** the bump + changelog:
   ```sh
   git add -A && git commit -m "Release v1.1.0"
   ```
4. **Tag and push** (this is what triggers the release workflow):
   ```sh
   git tag v1.1.0
   git push origin main --tags
   ```
5. **Confirm it published:**
   ```sh
   gh run watch --exit-status   # or watch the Actions tab
   gh release view v1.1.0       # check the zip asset is attached
   ```

If the workflow ever fails, publish manually with the locally built zip:
```sh
python package.py
gh release create v1.1.0 dist/EDPlanetNavigator-v1.1.0.zip --generate-notes
```

Versioning follows [SemVer](https://semver.org/) (MAJOR.MINOR.PATCH).

# Ocolyx Architecture

High-level overview:

- src/ocolyx/
  - `app.py` - ApplicationController and orchestration
  - `blink_detector.py` - CV pipeline and webcam manager
  - `blink_rate_analysis.py` - Rolling blink-rate analytics
  - `alerts.py` - Alert management and escalation
  - `overlay.py` - Screen dimming overlay
  - `services/` - background services, settings persistence
  - `ui/` - CustomTkinter dashboard and controllers
  - `utils/` - helpers and thread-safe utilities

Design goals

- Thread-safe architecture: all background threads publish events to `EventBus`.
- Config-driven: `config/default_config.json` provides defaults and runtime overrides.
- Resilient: missing models or devices fall back to safe no-op components.
- Cross-platform: UI and tray abstractions to support Windows/macOS/Linux.

Operational notes

- Logs are written to `logs/` with rotation.
- Place ML models under `assets/models/`.
- Icons and assets under `assets/icons/` and `assets/themes/`.

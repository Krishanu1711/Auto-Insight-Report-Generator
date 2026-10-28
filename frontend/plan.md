# Frontend implementation plan

## Direction

Build a restrained editorial analytics workspace, not a generic AI dashboard. Use a dark graphite canvas, subtly layered charcoal surfaces, warm-white primary text, readable cool-gray secondary text, thin low-contrast separators, and a selective muted ice-blue accent. Keep the serif page headings, system sans-serif interface, compact legible tables, quiet status cues, and ample whitespace. The visual hierarchy favors data shape and analysis over decorative cards. Use the same tokenized, transparent chart treatment across Bklit and Plotly: muted ice, sage, ochre, clay, and slate series with readable axes, subtle grids, and graphite tooltips. Mobile navigation becomes a horizontal, touch-friendly rail; chart surfaces and wide tables remain readable at narrow widths. Animations are limited to short state transitions and respect reduced-motion preferences.

## Architecture

- Keep the primary application vanilla HTML/CSS/JavaScript.
- Use Vite for local serving and production bundling.
- Isolate React to two chart mount modules that use official Bklit registry components for compatible bar and time-series line specs.
- Lazy-load Plotly.js for figure types whose richer semantics (box/histogram, scatter/heatmap, decomposition, forecast intervals) are not covered by those adapters.
- Keep all synthetic data in one explicit demo module; only load it after the user selects “Open demo workspace” and label every demo page.
- Implement only the frontend HTTP client and API documentation here. Do not add or modify the Python API/backend in this deliverable.

## Project structure

`index.html`, `vite.config.js`, `package.json`/lock, `.env.example`, and `public/` form the Vite shell. `src/main.js`, `src/styles.css`, and `src/api.js` contain the vanilla application and its API client. `src/charts/` contains the Bklit adapters and chart lifecycle bridge; `src/components/charts/` is official Bklit registry source. `src/demo/` contains synthetic-only data. Root docs include `README.md`, `API_CONTRACT.md`, and `INTEGRATION_GUIDE.md`.

## Explicit boundary

The supplied Python repository exposes a Streamlit UI rather than the API routes expected by the frontend. Therefore the UI is built as an isolated deliverable, with a documented contract for the user to implement through Antigravity. No backend functionality is represented as connected or tested.

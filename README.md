# 🃏 Card Game Score Tracker

A lightweight, secure web app for tracking scores and leaderboards in multiplayer card games where point totals vary per match and player attendance is uneven.

Built with **FastAPI**, **Jinja2**, **Tailwind CSS**, and **Alpine.js**, shipped as a **Docker** container (or image on GitHub Container Registry), and configured with Dev Container support.

---

## ✨ Key Features

1. **Official Bayesian Leaderboard (Default View):**
   * Solves the "one-game wonder" problem where a single win skews raw averages.
   * Calculates a **Bayesian Average** using global statistics with dynamic regularisation ($C = 30\%$ of the maximum number of matches played).
   * Sorted in ascending order (ideal for penalty-point card games where lower scores are better).

2. **Badges & Explanatory Modals:**
   * 👑 **Crown** for the #1 player on the Bayesian leaderboard.
   * 💀 **Skull** for the bottom player (when >1 player exists).
   * Interactive click-to-open modals detailing badge criteria.

3. **Match History & Trend Analysis (`/history`):**
   * Detailed match-by-match score logs for each participant with timeline alignment (absent matches represented with `-`).
   * Interactive **Chart.js** line graph showing performance trends across matches.
   * **Dedicated Unique Player Colors:** Dynamically computes distinct, deterministic HSL colors for each player across the color spectrum using the golden angle ($137.5^\circ$), eliminating color collisions.

4. **Collapsible Raw-Average Table:**
   * Access the unweighted raw average rankings anytime via the bottom toggle link (*"Mostra la classifica a media reale"*).

5. **Secure Match Submission & Score Rules (`POST /update`):**
   * Protected with `ADMIN_PASSWORD` (timing-safe check with `hmac.compare_digest`).
   * **Searchable combobox:** Select existing players or add new players directly from the dropdown.
   * **Duplicate & minimum player validation:** Prevents duplicate player rows in a single match and requires at least 2 players.
   * **Match winner scoring:** Toggle winner(s) with 🏆. A single winner scores `-10` points; multiple tied winners score `0` points; other players submit whole number penalty points ($> 0$).

6. **Alfredo Card Game Simulator (`/alfredo`):**
   * Full bot-vs-bot simulation engine driven by the complete rule set in [`alfredoRuleSet.md`](alfredoRuleSet.md).
   * Configurable player counts, round numbers, bot personality styles (`conservative`, `aggressive`, `mixed`, etc.), and repeatable random seeds.
   * Comprehensive round-by-round point breakdown and interactive turn logs.

7. **Resilient Data Storage (`scores.json`):**
   * Atomic file writes (temporary write + `fsync` + atomic `os.replace`) to ensure data cannot be corrupted mid-write.
   * Automatic backward-compatibility for legacy data files.

8. **Mobile-First Responsive UI:**
   * Responsive layout with Tailwind CSS and horizontal table scrolling for phones and tablets.

---

## 🛠️ Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Python 3.13, FastAPI, Starlette, Uvicorn |
| **Frontend** | Jinja2, Tailwind CSS (CDN), Alpine.js, Chart.js |
| **Storage** | Atomic JSON file persistence (`data/scores.json`), mapped via Docker volume |
| **Testing** | pytest, httpx / FastAPI TestClient |
| **Container & CI** | Docker, Docker Compose, GitHub Actions (`ghcr.io`) |
| **Dev Environment** | VS Code Dev Containers |

### Repository Structure

```
.
├── app/
│   ├── app.py                     # Application entrypoint (uvicorn on port 5000)
│   ├── cardgame/                  # Core package
│   │   ├── alfredo/               # Alfredo rules engine, bots, and simulation
│   │   │   ├── bots.py            # Bot memory and decision policies
│   │   │   ├── cards.py           # Deck definition, cards, and values
│   │   │   ├── engine.py          # State machine and rules engine
│   │   │   ├── report.py          # Match reports and terminal standings
│   │   │   ├── simulate.py        # Match simulator
│   │   │   ├── state.py           # Hand slots, player state, and event logs
│   │   │   └── views.py           # Memory views visible to bot policies
│   │   ├── static/js/             # Client-side scripts (match-form.js, trend-chart.js)
│   │   ├── templates/             # Jinja2 templates (index.html, history.html, alfredo.html)
│   │   ├── alfredo_routes.py      # Simulator route (/alfredo)
│   │   ├── config.py              # Environment configuration
│   │   ├── const.py               # Constants (DEV mode detection)
│   │   ├── models.py              # Domain dataclasses (ScoreData, PlayerRow, etc.)
│   │   ├── routes.py              # Main routes (/, /history, /update)
│   │   ├── stats.py               # Bayesian average & leaderboard calculations
│   │   └── storage.py             # JSON persistence & atomic writes
│   ├── tests/                     # Unit and integration test suite
│   ├── Dockerfile                 # Docker build definition
│   └── requirements*.txt          # Python dependencies
├── data/scores.json               # Persistent score storage (bind-mounted, gitignored)
├── data.example/scores.json       # Example scores structure
├── docker-compose.example.yaml    # Docker Compose example template
├── deploy.sh                      # Tag/release-based VPS deployment script
├── alfredoRuleSet.md              # Complete rulebook for the Alfredo game
├── .devcontainer/                 # Dev Container configuration
└── .github/workflows/deploy.yml   # CI workflow pushing Docker image to ghcr.io
```

---

## 📦 Configuration & Environment Variables

Environment variables can be defined in a `.env` file at the repository root (see [`.env.example`](.env.example)):

| Variable | Description | Default |
| :--- | :--- | :--- |
| `ADMIN_PASSWORD` | Password required to record matches on `/update`. | `yourPassword` |
| `SECRET_KEY` | Secret key used to sign session cookies for flash messages. | `secret_key` |
| `DEV` | When set to `true`, enables uvicorn auto-reload and bypasses admin password check in development. | `""` |
| `UID` / `GID` | User and group ID to run container processes as, avoiding root-owned files in `./data`. | Host user UID/GID |

---

## 🚀 Running the Application

### Option A: Running with Docker Compose (Recommended)

1. Copy and configure your environment:
   ```bash
   cp .env.example .env
   # Edit .env and set your ADMIN_PASSWORD and SECRET_KEY
   ```

2. Start the service:
   ```bash
   docker compose up -d --build
   ```
   The application will be live at `http://localhost:5000`.

### Option B: Automated VPS Deployment (`deploy.sh`)

If running on a VPS using Git tags / releases:
1. Ensure `deploy.sh` is executable:
   ```bash
   chmod +x deploy.sh
   ```
2. Run `./deploy.sh` or configure a cron job to check for updates periodically:
   ```cron
   0 * * * * /bin/bash /path/to/game_scoreboard/deploy.sh >> /path/to/game_scoreboard/deploy.log 2>&1
   ```

### Option C: Development via Dev Container

1. Open the project folder in **VS Code** with the **Dev Containers** extension installed.
2. Select **"Dev Containers: Reopen in Container"** when prompted.
3. The environment sets `DEV=true` automatically with hot-reload enabled. Start or test:
   ```bash
   # Run app
   python app/app.py

   # Run tests
   cd app && pytest -q
   ```

---

## 🧪 Testing

Run the test suite using `pytest`:

```bash
cd app
python -m pytest
```

The test suite covers:
* Player score updates, duplicate rejection, and winner point assignments (`test_update_route.py`)
* Alfredo card rules, special abilities, and game state transitions (`test_alfredo_rules.py`)
* Bot decision policies and simulations (`test_alfredo_bots.py`)
* Web route rendering and query handling (`test_alfredo_routes.py`)

---

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).

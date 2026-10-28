# 🃏 Card Game Score Tracker

A lightweight, secure web app for tracking scores and leaderboards in multiplayer
games where point totals vary per match and player attendance is uneven.

Built with **FastAPI**, **Jinja2**, **Tailwind CSS** and **Alpine.js**, shipped as a
**Docker** image on GitHub Container Registry, and developed inside a **Dev Container**.

---

## ✨ Key Features

1. **Official Bayesian Leaderboard (default view)**
   * Fixes the "one-game wonder" problem — a player who plays a single match and wins
     should not top a raw average.
   * Bayesian average using global game statistics with a dynamic regularisation weight
     ($C = 30\%$ of the maximum number of matches played).
   * Sorted ascending, so it also works for penalty-point scoring (lower is better).

2. **Badges & explanation pop-ups**
   * 👑 **Crown** for the #1 player and 💀 **Skull** for the last one, each opening a
     modal that explains why.

3. **Match history & trend analysis (`/history`)**
   * Per-match point log for every participant.
   * Interactive **Chart.js** line chart of each player's trend across matches.

4. **Collapsible raw-average table**
   * The traditional raw average stays available at the bottom of the home page
     (*"Mostra la classifica a media reale"*).

5. **Password-protected score entry (`POST /update`)**
   * No anonymous tampering with game statistics. Set `ADMIN_PASSWORD`; in dev,
     `DEV=true` bypasses it.

6. **Rules engine & bot simulation (`/alfredo`)**
   * Simulated matches driven by the rule set in [`alfredoRuleSet.md`](alfredoRuleSet.md),
     with bot opponents and match reports.

7. **Mobile-first responsive UI** — Tailwind + Alpine, horizontal table scrolling on phones.

---

## 🛠️ Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.13, FastAPI, uvicorn |
| Templates | Jinja2 + Tailwind CSS (CDN), Alpine.js, Chart.js |
| Storage | JSON file (`data/scores.json`), atomic writes, mounted as a Docker volume |
| Tests | pytest |
| Dev environment | Dev Container (VS Code / any devcontainer-compatible editor) |
| CI/CD | GitHub Actions → image published to `ghcr.io` |
| Deployment | Docker Compose, pulling the published image |

### Repository layout

```
.
├── app/
│   ├── app.py                # entrypoint (uvicorn on :5000)
│   ├── cardgame/             # app package: routes, stats, storage, simulation engine
│   ├── templates/  static/   # Jinja2 templates, JS
│   ├── tests/                # pytest suite
│   ├── Dockerfile            # built from ./app
│   └── requirements*.txt
├── data/scores.json          # persistent data (volume)
├── docker-compose.yaml       # production / devcontainer compose file
├── .devcontainer/            # dev container config
└── .github/workflows/deploy.yml
```

---

## 💻 Development (Dev Container)

Development happens inside the dev container — no local Python install needed.

1. Install **Docker** and **VS Code** with the **Dev Containers** extension.
2. Open this folder in VS Code and run **"Dev Containers: Reopen in Container"**
   (or let VS Code prompt you). The container is built from `app/Dockerfile` via
   `docker-compose.yaml` + `.devcontainer/docker-compose.devcontainer.yaml`, with the
   repo bind-mounted at `/app`.
3. Inside the container, `DEV=true` is already set, so the app runs with auto-reload:

   ```bash
   python app/app.py            # → http://localhost:5000
   ```

4. Run the tests:

   ```bash
   cd app && python -m pytest -q
   ```

Environment variables live in `.env` at the repo root (copy `.env.example`):

| Variable | Purpose |
| --- | --- |
| `ADMIN_PASSWORD` | password required by `POST /update` |
| `SECRET_KEY` | signing key for the admin session cookie |
| `DEV` | `true` disables the admin password and enables uvicorn reload (dev container only) |
| `UID` / `GID` | run the container as your host user (avoids root-owned `data/`) |

VS Code settings in the dev container enable Python type checking in `strict` mode.

### Running without the dev container

```bash
cp .env.example .env      # then edit ADMIN_PASSWORD
docker compose up --build # → http://localhost:5000
```

---

## 🚢 Continuous Integration

`.github/workflows/deploy.yml` builds `app/Dockerfile` and pushes it to
`ghcr.io/<owner>/<repo>`:

| Event | Image tags pushed |
| --- | --- |
| Push to `main` | `latest`, `main`, `sha-<commit>` |
| Push a `v*` tag | `v1.2.3`, `sha-<commit>` |
| Publish a GitHub Release | `v1.2.3`, `sha-<commit>` |
| Manual run (Actions tab) | `sha-<commit>` |

---

## 🏷️ Publishing a release

```bash
git add .
git commit -m "feat: ..."
git push origin main

git tag v1.0.0 && git push origin v1.0.0   # → image tagged v1.0.0
# or create a Release in the GitHub UI → same image tag
```

Pushing the tag (or publishing the release) triggers the workflow, which builds and
pushes the versioned image.

---

## 🚀 Running with Docker Compose

Create a `docker-compose.yaml` next to a `.env` file holding the real secrets (never
commit them), then `docker compose up -d`:

```yaml
services:
  card-game-tracker:
    image: <registry>/<owner>/<repo>:<tag>   # e.g. ghcr.io/<owner>/<repo>:v1.0.0
    container_name: card_game_server
    restart: always
    user: "${UID}:${GID}"
    ports:
      - "5000:5000"
    environment:
      - SECRET_KEY=your-super-secret-key
      - ADMIN_PASSWORD="${ADMIN_PASSWORD:-yourPassword}"
    volumes:
      - ./data:/app/data
```

Replace the `image:` placeholder with the image published by the CI workflow, e.g.
`ghcr.io/<owner>/<repo>:latest` or a released version tag. If the registry is private,
log in first (`docker login ghcr.io`).

The `./data` directory holds `scores.json` and survives container recreation — back it
up if you care about the history.

---

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).

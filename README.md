# 🃏 Card Game Score Tracker

A modern, lightweight, and secure web application built with **Flask** and **Tailwind CSS** designed to track scores and leaderboards for multiplayer card games (such as Rummy, Hearts, or Uno) where point totals vary per match and player attendance is uneven.

---

## ✨ Key Features

1. **Official Bayesian Leaderboard (Default):**
   * Solves the problem of "one-game wonders" (players who play a single match and win, artificially skewing raw averages).
   * Automatically calculates a **Bayesian Average** using global game statistics and a dynamic regularization weight ($C = 30\% \text{ of max matches played}$).
   * Sorts players automatically (ascending order, ideal for penalty-point card games).

2. **Badges & Interactive Pop-ups:**
   * **Crown (👑):** Awarded to the #1 player on the official Bayesian leaderboard (with an interactive click-to-open explanation modal).
   * **Skull (💀):** Highlights the bottom player on the Bayesian leaderboard (with an interactive click-to-open explanation modal).

3. **Match History & Trend Analysis (`/history`):**
   * View point logs match-by-match for every participant.
   * Interactive **Chart.js** line graph tracking each player's performance trend across matches.

4. **Collapsible Raw Average Table:**
   * The traditional raw average table is safely tucked away at the bottom of the home page via an interactive hyperlink toggle (*"Mostra la classifica a media reale"*).

5. **Secure Admin Panel:**
   * Password-protected score submission (`/update`).
   * Prevents unauthorized tampering with game statistics.

6. **Mobile-First & Responsive UI:**
   * Styled with **Tailwind CSS** and **Alpine.js**.
   * Features horizontal table scrolling for seamless viewing on smartphones.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.11, Flask
* **Data Storage:** JSON-based persistent storage (`scores.json`) secured via Docker volumes
* **Frontend:** Tailwind CSS, Alpine.js, Chart.js
* **Containerization & Automation:** Docker, Docker Compose, Git Tags / Releases, Cron Jobs

---

## 🚀 Complete Configuration & Deployment Guide (VPS)

### 1. Project Structure on your VPS
Ensure your project directory on the host (e.g., `/home/debian/game_scoreboard`) contains:
* `app.py`
* `requirements.txt`
* `Dockerfile`
* `docker-compose.yml`
* `deploy.sh`

### 2. Environment Variables (`docker-compose.yml`)
Configure your secure password and secrets:
```yaml
version: '3.8'

services:
  scoretracker:
    build: .
    container_name: card_game_server
    restart: always
    ports:
      - "5000:5000"
    environment:
      - SECRET_KEY=your-super-secret-flask-key
      - ADMIN_PASSWORD=your_secure_admin_password
    volumes:
      - ./data:/app/data
```

### 3. Automated Release-Based Deployment Script (`deploy.sh`)
Create or update `/home/debian/game_scoreboard/deploy.sh`:
```bash
#!/bin/bash

GIT="/usr/bin/git"
DOCKER="/usr/bin/docker"

cd /home/debian/game_scoreboard || { echo "Error: Directory not found!"; exit 1; }

$GIT fetch --tags origin

LATEST_TAG=$($GIT describe --tags $($GIT rev-list --tags --max-count=1) 2>/dev/null)

if [ -z "$LATEST_TAG" ]; then
        echo "Error: no release (tag Git) found."
        exit 1
fi

CURRENT_TAG=$($GIT describe --tags --exact-match 2>/dev/null || echo "none")

echo "Last release available on github: $LATEST_TAG"
echo "Current running version: $CURRENT_TAG"

if [ "$CURRENT_TAG" != "$LATEST_TAG" ]; then
        echo "Updating to release on server: $LATEST_TAG"

        $GIT reset --hard "$LATEST_TAG"

        $DOCKER compose down
        $DOCKER compose build --no-cache
        $DOCKER compose up -d

        echo "Deployment to release $LATEST_TAG completed"
else
        echo "Server already updated"
fi
```

Make it executable:
```bash
chmod +x /home/debian/game_scoreboard/deploy.sh
```

### 4. Setting up the Cron Job (Automatic Updates)
Configure root crontab to check for new releases automatically (e.g., every hour):
```bash
sudo crontab -e
```
Add this line at the bottom:
```cron
* */1 * * * /bin/bash /home/debian/game_scoreboard/deploy.sh >> /home/debian/game_scoreboard/deploy.log 2>&1
```

---

## 🏷️ How to Publish Your First Release

1. **Commit and Push your code from your development environment:**
   ```bash
   git add .
   git commit -m "Complete stable release configuration"
   git push origin main
   ```
2. **Create and push your first Git Tag:**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. Your host cron job will automatically detect the new release (`v1.0.0`), pull it, rebuild the Docker container, and deploy it smoothly!

---

## 📜 License
This project is open-source and available under the [MIT License](LICENSE).

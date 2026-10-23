# 🃏 Card Game Score Tracker

A modern, lightweight, and secure web application built with **Flask** and **Tailwind CSS** designed specifically to track scores and leaderboards for multiplayer card games (such as Rummy, Hearts, or Uno) where point totals vary per match and player attendance is uneven.

---

## ✨ Key Features

1. **Fair Leaderboard with Bayesian Average:**
   * Solves the problem of "one-game wonders" (players who play a single match and win, artificially skewing raw averages).
   * Automatically calculates a **Bayesian Average** using global game statistics and a dynamic regularization weight ($C = 30\% \text{ of max matches played}$).
   * Provides a toggleable view for the raw average table.

2. **Attendance & Performance Badges:**
   * **Crown (👑):** Awarded to the #1 player on the official Bayesian leaderboard.
   * **Skull (💀):** Highlights the bottom player on the leaderboard.
   * Interactive pop-ups explain the meaning of each stemma when clicked.

3. **Match History & Trend Analysis (`/history`):**
   * View point logs match-by-match for every participant.
   * Interactive **Chart.js** line graph tracking each player's performance trend across matches.

4. **Secure Admin Panel:**
   * Password-protected score submission (`/update`).
   * Prevents unauthorized tampering with game statistics.

5. **Mobile-First & Responsive UI:**
   * Styled with **Tailwind CSS** and **Alpine.js**.
   * Features horizontal table scrolling for seamless viewing on smartphones.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.11, Flask
* **Data Storage:** JSON-based persistent storage (`scores.json`) secured via Docker volumes
* **Frontend:** Tailwind CSS, Alpine.js, Chart.js
* **Containerization:** Docker & Docker Compose

---

## 🚀 Deployment Guide (via Docker)

### 1. Prerequisites
Ensure your host has **Docker** and **Docker Compose** installed.

### 2. Project Structure
Make sure your project folder contains:
* `app.py`
* `requirements.txt`
* `Dockerfile`
* `docker-compose.yml`

### 3. Configure Environment Variables
In your `docker-compose.yml`, configure your secure password:
```yaml
environment:
  - SECRET_KEY=your-super-secret-flask-key
  - ADMIN_PASSWORD=your_secure_admin_password
```

### 4. Build and Run
Run the following command in your project directory on the VPS:
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

The application will be accessible on port `5000` (`http://<YOUR_VPS_IP>:5000`).

---

## 🔒 Security & Firewall (Oracle Cloud / VPS Note)
If you are hosting on a machine with strict firewall defaults, remember to allow port `5000` in your server firewall (`iptables` / `ufw`).

---

## 📜 License
This project is open-source and available under the [MIT License](LICENSE).

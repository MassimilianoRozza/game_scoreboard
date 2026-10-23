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

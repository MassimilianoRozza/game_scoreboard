// Chart.js trend chart for the history page.
(function () {
    "use strict";

    const dataEl = document.getElementById("trend-data");
    const canvas = document.getElementById("trendChart");
    if (!dataEl || !canvas) {
        return;
    }

    /**
     * Compute a unique, pleasant, and deterministic color for a player name.
     * Uses djb2 hashing mapped across HSL space with calibrated saturation
     * and lightness to ensure contrast and readability on light backgrounds.
     *
     * @param {string} name - Unique player name.
     * @returns {string} CSS hsl(...) color string.
     */
    function getPlayerColor(name) {
        const cleanName = (name || "").trim().toLowerCase();
        let hash = 0;
        for (let i = 0; i < cleanName.length; i++) {
            hash = cleanName.charCodeAt(i) + ((hash << 5) - hash);
            hash |= 0;
        }

        // Map hash to hue (0-359 deg), vary saturation and lightness slightly to avoid collisions
        const hue = Math.abs(hash) % 360;
        const sat = 65 + (Math.abs(hash >> 8) % 20); // 65% - 84%
        const lit = 45 + (Math.abs(hash >> 16) % 15); // 45% - 59%

        return `hsl(${hue}, ${sat}%, ${lit}%)`;
    }

    /**
     * Build a color map allocating distinct, evenly spaced hues using the
     * golden ratio angle (137.5 deg) so all players present on the chart
     * have maximally distinct, dedicated colors without any duplicates.
     *
     * @param {Array<string>} names - Array of player names.
     * @returns {Map<string, string>} Mapping from player name to CSS color.
     */
    function createPlayerColorPalette(names) {
        const uniqueNames = Array.from(new Set(names)).sort((a, b) =>
            a.localeCompare(b, undefined, { sensitivity: "base" })
        );
        const colorMap = new Map();
        const GOLDEN_ANGLE = 137.507764; // degrees

        uniqueNames.forEach((name, index) => {
            const hue = Math.round((index * GOLDEN_ANGLE) % 360);
            const sat = index % 2 === 0 ? 75 : 68;
            const lit = index % 2 === 0 ? 46 : 52;
            colorMap.set(name, `hsl(${hue}, ${sat}%, ${lit}%)`);
        });

        return colorMap;
    }

    const rawData = JSON.parse(dataEl.textContent);
    const maxLen = Math.max(...rawData.map((p) => p.history.length), 0);
    const labels = Array.from({ length: maxLen }, (_, i) => "Partita " + (i + 1));

    // Allocate dedicated unique colors for all players on the chart
    const playerPalette = createPlayerColorPalette(rawData.map((p) => p.name));

    const datasets = rawData.map((player) => {
        const color = playerPalette.get(player.name) || getPlayerColor(player.name);
        return {
            label: player.name,
            data: player.history,
            borderColor: color,
            backgroundColor: color,
            tension: 0.1,
            fill: false,
            spanGaps: true
        };
    });

    new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    title: {
                        display: true,
                        text: "Punti"
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: "Partite"
                    }
                }
            }
        }
    });
})();

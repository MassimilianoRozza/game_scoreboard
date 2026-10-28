// Chart.js trend chart for the history page.
(function () {
    "use strict";

    const dataEl = document.getElementById("trend-data");
    const canvas = document.getElementById("trendChart");
    if (!dataEl || !canvas) {
        return;
    }

    const rawData = JSON.parse(dataEl.textContent);
    const maxLen = Math.max(...rawData.map((p) => p.history.length), 0);
    const labels = Array.from({ length: maxLen }, (_, i) => "Partita " + (i + 1));

    const colors = [
        "#2563eb", "#dc2626", "#16a34a", "#9333ea",
        "#ca8a04", "#0d9488", "#db2777", "#4f46e5"
    ];

    const datasets = rawData.map((player, index) => ({
        label: player.name,
        data: player.history,
        borderColor: colors[index % colors.length],
        backgroundColor: colors[index % colors.length],
        tension: 0.1,
        fill: false
    }));

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

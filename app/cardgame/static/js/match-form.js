// Dynamic player rows for the match registration form:
// searchable combobox dropdown (existing players + create new) and duplicate guard.
(function () {
    "use strict";

    const container = document.getElementById("player-inputs");
    const template = document.getElementById("player-row-template");
    const addButton = document.getElementById("add-player");
    const form = document.getElementById("match-form");
    const knownData = document.getElementById("known-players-data");
    const submitButton = document.getElementById("submit-match");

    // A match needs at least two players to be meaningful.
    const MIN_PLAYERS = 2;

    if (!container || !template || !addButton) {
        return;
    }

    const knownPlayers = knownData ? JSON.parse(knownData.textContent) : [];

    // A match may have several winners: a lone winner takes the fixed winning
    // score, but when more than one player wins nobody gains, so they all score
    // 0 (mirrors the server-side rule in routes.py).
    const initialBadge = container.querySelector(".win-badge");
    const WIN_POINTS_LABEL = initialBadge ? initialBadge.textContent.trim() : "";
    const TIE_POINTS_LABEL = "0";

    function nameInOtherRows(name, exceptInput) {
        const target = name.trim().toLowerCase();
        if (!target) {
            return false;
        }
        for (const input of container.querySelectorAll("input[name='player_name[]']")) {
            if (input !== exceptInput && input.value.trim().toLowerCase() === target) {
                return true;
            }
        }
        return false;
    }

    function matchesFor(query) {
        const q = query.trim().toLowerCase();
        if (!q) {
            return knownPlayers.slice();
        }
        return knownPlayers.filter((name) => name.toLowerCase().includes(q));
    }

    function closeAllDropdowns(except) {
        for (const picker of container.querySelectorAll(".player-picker")) {
            if (picker !== except) {
                picker.querySelector(".player-dropdown").classList.add("hidden");
            }
        }
    }

    function renderDropdown(picker) {
        const input = picker.querySelector(".player-search");
        const dropdown = picker.querySelector(".player-dropdown");
        const query = input.value;
        const matches = matchesFor(query);

        dropdown.innerHTML = "";

        for (const name of matches) {
            const li = document.createElement("li");
            const taken = nameInOtherRows(name, input);
            li.textContent = name;
            li.dataset.name = name;
            li.className = "px-3 py-2 text-sm cursor-pointer hover:bg-blue-50" +
                (taken ? " text-gray-400 line-through" : "");
            if (taken) {
                li.title = "Già presente nella partita";
            }
            dropdown.appendChild(li);
        }

        const trimmed = query.trim();
        const exact = knownPlayers.some((n) => n.toLowerCase() === trimmed.toLowerCase());
        if (trimmed && !exact) {
            const li = document.createElement("li");
            li.textContent = "+ Nuovo giocatore: " + trimmed;
            li.dataset.name = trimmed;
            li.className = "px-3 py-2 text-sm font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 cursor-pointer border-t border-gray-100";
            dropdown.appendChild(li);
        }

        if (!dropdown.children.length) {
            const li = document.createElement("li");
            li.textContent = "Nessun giocatore: scrivi un nome per crearne uno";
            li.className = "px-3 py-2 text-sm text-gray-500";
            dropdown.appendChild(li);
        }

        dropdown.classList.remove("hidden");
    }

    function filledPlayerCount() {
        let count = 0;
        for (const input of container.querySelectorAll("input[name='player_name[]']")) {
            if (input.value.trim()) {
                count += 1;
            }
        }
        return count;
    }

    function updateSubmitState() {
        if (!submitButton) {
            return;
        }
        const count = filledPlayerCount();
        const enabled = count >= MIN_PLAYERS;
        submitButton.disabled = !enabled;
        submitButton.classList.toggle("opacity-50", !enabled);
        submitButton.classList.toggle("cursor-not-allowed", !enabled);
        submitButton.title = enabled
            ? ""
            : "Servono almeno " + MIN_PLAYERS + " giocatori per registrare una partita";
    }

    function winnerCount() {
        let count = 0;
        for (const flag of container.querySelectorAll("input[name='player_winner[]']")) {
            if (flag.value === "1") {
                count += 1;
            }
        }
        return count;
    }

    // Keep every winner badge showing the score that will actually be recorded.
    function updateWinBadges() {
        const label = winnerCount() === 1 ? WIN_POINTS_LABEL : TIE_POINTS_LABEL;
        for (const badge of container.querySelectorAll(".win-badge")) {
            badge.textContent = label;
        }
    }

    function applyWinner(row, isWinner) {
        const button = row.querySelector(".winner-toggle");
        const flag = row.querySelector("input[name='player_winner[]']");
        const points = row.querySelector("input[name='player_points[]']");
        const badge = row.querySelector(".win-badge");

        flag.value = isWinner ? "1" : "0";
        button.setAttribute("aria-pressed", isWinner ? "true" : "false");
        button.classList.toggle("bg-yellow-100", isWinner);
        button.classList.toggle("opacity-40", !isWinner);
        // Hidden inputs still submit, so the parallel arrays stay aligned.
        points.classList.toggle("hidden", isWinner);
        points.required = !isWinner;
        badge.classList.toggle("hidden", !isWinner);
    }

    function toggleWinner(row) {
        const wasWinner = row.querySelector("input[name='player_winner[]']").value === "1";
        // Any number of players may win the same match; clicking again clears
        // that row's flag without touching the others.
        applyWinner(row, !wasWinner);
        updateWinBadges();
    }

    function focusPoints(row) {
        const points = row.querySelector("input[name='player_points[]']");
        if (!points.classList.contains("hidden")) {
            points.focus();
        }
    }

    function selectName(picker, name) {
        const input = picker.querySelector(".player-search");
        input.value = name;
        picker.querySelector(".player-dropdown").classList.add("hidden");
        updateSubmitState();
        focusPoints(input.closest(".player-row"));
    }

    function createRow(name) {
        const fragment = template.content.cloneNode(true);
        const row = fragment.querySelector(".player-row");
        const nameInput = row.querySelector("input[name='player_name[]']");
        if (name) {
            nameInput.value = name;
        }
        container.appendChild(fragment);
        applyWinner(row, false);
        updateWinBadges();
        updateSubmitState();
        (name ? row.querySelector("input[name='player_points[]']") : nameInput).focus();
        if (!name) {
            renderDropdown(row.querySelector(".player-picker"));
        }
        return row;
    }

    addButton.addEventListener("click", function () {
        createRow("");
    });

    // Reflect the initial state (the first empty row means the button starts off).
    updateSubmitState();

    // Dropdown interactions (delegated on the container).
    container.addEventListener("click", function (event) {
        const winnerBtn = event.target.closest(".winner-toggle");
        if (winnerBtn) {
            toggleWinner(winnerBtn.closest(".player-row"));
            return;
        }

        const removeBtn = event.target.closest(".remove-row");
        if (removeBtn) {
            if (container.getElementsByClassName("player-row").length > 1) {
                removeBtn.closest(".player-row").remove();
                updateWinBadges();
                updateSubmitState();
            } else {
                alert("Devi includere almeno un giocatore.");
            }
            return;
        }

        const toggle = event.target.closest(".picker-toggle");
        if (toggle) {
            const picker = toggle.closest(".player-picker");
            const dropdown = picker.querySelector(".player-dropdown");
            if (dropdown.classList.contains("hidden")) {
                renderDropdown(picker);
                picker.querySelector(".player-search").focus();
            } else {
                dropdown.classList.add("hidden");
            }
            return;
        }

        const option = event.target.closest("li[data-name]");
        if (option) {
            if (option.classList.contains("line-through")) {
                return;
            }
            selectName(option.closest(".player-picker"), option.dataset.name);
            return;
        }

        if (!event.target.closest(".player-picker")) {
            closeAllDropdowns();
        }
    });

    container.addEventListener("input", function (event) {
        if (event.target.matches(".player-search")) {
            renderDropdown(event.target.closest(".player-picker"));
            updateSubmitState();
        }
    });

    container.addEventListener("focusin", function (event) {
        if (event.target.matches(".player-search")) {
            renderDropdown(event.target.closest(".player-picker"));
        }
    });

    container.addEventListener("keydown", function (event) {
        if (!event.target.matches(".player-search")) {
            return;
        }
        const picker = event.target.closest(".player-picker");
        const dropdown = picker.querySelector(".player-dropdown");
        const open = !dropdown.classList.contains("hidden");
        const items = Array.from(dropdown.querySelectorAll("li[data-name]"));
        const active = dropdown.querySelector("li.bg-blue-200");

        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            if (!open) {
                renderDropdown(picker);
                return;
            }
            if (!items.length) {
                return;
            }
            let index = active ? items.indexOf(active) : -1;
            if (active) {
                active.classList.remove("bg-blue-200");
            }
            index = event.key === "ArrowDown"
                ? (index + 1) % items.length
                : (index - 1 + items.length) % items.length;
            items[index].classList.add("bg-blue-200");
            items[index].scrollIntoView({ block: "nearest" });
        } else if (event.key === "Enter") {
            if (open && active) {
                event.preventDefault();
                if (!active.classList.contains("line-through")) {
                    selectName(picker, active.dataset.name);
                }
            } else if (open) {
                event.preventDefault();
                const trimmed = event.target.value.trim();
                if (trimmed) {
                    selectName(picker, trimmed);
                }
            }
        } else if (event.key === "Escape") {
            dropdown.classList.add("hidden");
        }
    });

    document.addEventListener("click", function (event) {
        if (!event.target.closest(".player-picker") && !event.target.closest("#add-player")) {
            closeAllDropdowns();
        }
    });

    if (form) {
        form.addEventListener("submit", function (event) {
            const seen = new Set();
            for (const row of container.querySelectorAll(".player-row")) {
                const name = row.querySelector("input[name='player_name[]']").value.trim();
                if (!name) {
                    continue;
                }
                const key = name.toLowerCase();
                if (seen.has(key)) {
                    event.preventDefault();
                    alert("Giocatore duplicato nella stessa partita: " + name);
                    return;
                }
                seen.add(key);
            }
        });
    }
})();

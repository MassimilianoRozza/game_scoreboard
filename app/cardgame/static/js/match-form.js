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

    // The server sends players ordered by official rank; the dropdown shows them
    // alphabetically instead (case-insensitive, locale-aware).
    const knownPlayers = (knownData ? JSON.parse(knownData.textContent) : [])
        .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));

    // Crown states per row (mirrors the server-side rules in routes.py):
    // none -> gold -> silver -> black -> gold ... (the cycle skips gold when it
    // is not assignable). Gold = the player who called Alfredo and won
    // (WIN_POINTS, points not applicable); silver = 0 points (points not
    // applicable, or user-entered after a gold collision); black = the failed
    // Alfredo call (editable penalty points). Gold is assignable only while no
    // silver or black crown is on the board; black only while no gold is.
    // A match needs exactly one black crown unless exactly one gold is assigned.
    const CROWN_NONE = "none";
    const CROWN_GOLD = "gold";
    const CROWN_SILVER = "silver";
    const CROWN_BLACK = "black";

    const crownButtonTemplate = container.querySelector(".crown-toggle");
    const WIN_POINTS_LABEL = crownButtonTemplate && crownButtonTemplate.dataset.winPoints
        ? crownButtonTemplate.dataset.winPoints
        : "";
    const PENALTY_POINTS_LABEL = crownButtonTemplate && crownButtonTemplate.dataset.penaltyPoints
        ? crownButtonTemplate.dataset.penaltyPoints
        : "10";
    const SILVER_POINTS_LABEL = "0";

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

    // A match is valid when it has exactly one black crown (the failed Alfredo
    // call), except when exactly one gold crown is assigned: the player who
    // called Alfredo and won, so there is no failed call to penalise (mirrors
    // the server-side check in routes.py). Crowns on unnamed rows are ignored.
    function crownsValid() {
        const gold = crownCount(CROWN_GOLD);
        const black = crownCount(CROWN_BLACK);
        if (gold === 1) {
            return black === 0;
        }
        return gold === 0 && black === 1;
    }

    function updateSubmitState() {
        if (!submitButton) {
            return;
        }
        const count = filledPlayerCount();
        let reason = "";
        if (count < MIN_PLAYERS) {
            reason = "Servono almeno " + MIN_PLAYERS + " giocatori per registrare una partita";
        } else if (!crownsValid()) {
            reason = "Serve esattamente una corona nera (chiamata Alfredo fallita), "
                + "a meno che non ci sia un solo vincitore con la corona oro";
        }
        const enabled = reason === "";
        submitButton.disabled = !enabled;
        submitButton.classList.toggle("opacity-50", !enabled);
        submitButton.classList.toggle("cursor-not-allowed", !enabled);
        submitButton.title = reason;
    }

    function crownFlag(row) {
        return row.querySelector("input[name='player_crown[]']");
    }

    function crownOf(row) {
        return crownFlag(row).value || CROWN_NONE;
    }

    // Count crowns over rows that actually carry a player name: unnamed rows
    // are skipped by the server, so they must not lock crowns either.
    function crownCount(crown) {
        let count = 0;
        for (const row of container.querySelectorAll(".player-row")) {
            const name = row.querySelector("input[name='player_name[]']").value.trim();
            if (name && crownOf(row) === crown) {
                count += 1;
            }
        }
        return count;
    }

    // Gold is assignable only while no silver or black crown is on the board;
    // black only while no gold crown is. Silver is always assignable.
    function crownAssignable(crown) {
        if (crown === CROWN_GOLD) {
            return crownCount(CROWN_SILVER) === 0 && crownCount(CROWN_BLACK) === 0;
        }
        if (crown === CROWN_BLACK) {
            return crownCount(CROWN_GOLD) === 0;
        }
        return true;
    }

    // The next crown in the cycle for a row, skipping states it cannot take.
    function nextCrown(row, current) {
        const order = [CROWN_GOLD, CROWN_SILVER, CROWN_BLACK].filter(crownAssignable);
        const index = order.indexOf(current);
        // If the row's current crown is no longer assignable (e.g. it holds
        // gold while another crown now blocks it), restart from the first
        // assignable crown instead of wrapping around.
        return index === -1 ? order[0] : order[(index + 1) % order.length];
    }

    // Paint one row to match its crown flag: button glyph/colour, badge, and
    // the points field (hidden for gold and plain silver, shown for black and
    // for silvers born from a gold collision).
    function applyCrown(row) {
        const crown = crownOf(row);
        const button = row.querySelector(".crown-toggle");
        const points = row.querySelector("input[name='player_points[]']");
        const badge = row.querySelector(".crown-badge");
        const collision = row.dataset.crownCollision === "1";

        button.textContent = crown === CROWN_GOLD ? "🥇"
            : crown === CROWN_SILVER ? "🥈"
            : crown === CROWN_BLACK ? "⚫" : "🏆";
        button.setAttribute("aria-pressed", crown === CROWN_NONE ? "false" : "true");
        button.classList.toggle("opacity-40", crown === CROWN_NONE);
        button.classList.toggle("bg-yellow-100", crown === CROWN_GOLD);
        button.classList.toggle("bg-gray-200", crown === CROWN_SILVER);
        button.classList.toggle("bg-gray-800", crown === CROWN_BLACK);

        // The points field applies to: no crown (plain loser), black (editable
        // penalty) and silvers born from a gold collision. Gold and plain
        // silver have fixed scores, so the field is hidden (but still submits).
        const pointsApplicable = crown === CROWN_NONE || crown === CROWN_BLACK
            || (crown === CROWN_SILVER && collision);
        // Hidden inputs still submit, so the parallel arrays stay aligned.
        points.classList.toggle("hidden", !pointsApplicable);
        points.required = pointsApplicable;

        if (crown === CROWN_GOLD) {
            badge.textContent = WIN_POINTS_LABEL;
            badge.classList.remove("hidden");
        } else if (crown === CROWN_SILVER && !collision) {
            badge.textContent = SILVER_POINTS_LABEL;
            badge.classList.remove("hidden");
        } else if (crown === CROWN_BLACK) {
            badge.textContent = points.value || PENALTY_POINTS_LABEL;
            badge.classList.remove("hidden");
        } else {
            badge.textContent = "";
            badge.classList.add("hidden");
        }
    }

    // Repaint every row and refresh the submit gate after any crown change.
    function refreshCrowns() {
        for (const row of container.querySelectorAll(".player-row")) {
            applyCrown(row);
        }
        updateSubmitState();
    }

    function cycleCrown(row) {
        const current = crownOf(row);
        const next = nextCrown(row, current);
        if (next === CROWN_GOLD && crownCount(CROWN_GOLD) >= 1) {
            // Assigning a second gold collides: every gold crown (this row
            // included) flips to silver and its points field becomes
            // applicable, empty and required.
            for (const other of container.querySelectorAll(".player-row")) {
                if (other === row || crownOf(other) === CROWN_GOLD) {
                    crownFlag(other).value = CROWN_SILVER;
                    other.dataset.crownCollision = "1";
                    other.querySelector("input[name='player_points[]']").value = "";
                }
            }
        } else {
            crownFlag(row).value = next;
            delete row.dataset.crownCollision;
            if (next === CROWN_BLACK) {
                const points = row.querySelector("input[name='player_points[]']");
                if (!points.value) {
                    points.value = PENALTY_POINTS_LABEL;
                }
            }
        }
        refreshCrowns();
        const crown = crownOf(row);
        if (crown === CROWN_BLACK || row.dataset.crownCollision === "1") {
            row.querySelector("input[name='player_points[]']").focus();
        }
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
        applyCrown(row);
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
    refreshCrowns();

    // Dropdown interactions (delegated on the container).
    container.addEventListener("click", function (event) {
        const crownBtn = event.target.closest(".crown-toggle");
        if (crownBtn) {
            cycleCrown(crownBtn.closest(".player-row"));
            return;
        }

        const removeBtn = event.target.closest(".remove-row");
        if (removeBtn) {
            if (container.getElementsByClassName("player-row").length > 1) {
                removeBtn.closest(".player-row").remove();
                refreshCrowns();
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
            return;
        }
        if (event.target.matches("input[name='player_points[]']")) {
            // Keep the black crown badge in sync with the edited penalty.
            const row = event.target.closest(".player-row");
            if (row && crownOf(row) === CROWN_BLACK) {
                const badge = row.querySelector(".crown-badge");
                badge.textContent = event.target.value || PENALTY_POINTS_LABEL;
            }
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

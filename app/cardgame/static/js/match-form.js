// Dynamic player rows for the match registration form:
// searchable combobox dropdown (existing players + create new) and duplicate guard.
(function () {
    "use strict";

    const container = document.getElementById("player-inputs");
    const template = document.getElementById("player-row-template");
    const addButton = document.getElementById("add-player");
    const form = document.getElementById("match-form");
    const knownData = document.getElementById("known-players-data");

    if (!container || !template || !addButton) {
        return;
    }

    const knownPlayers = knownData ? JSON.parse(knownData.textContent) : [];

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

    function selectName(picker, name) {
        const input = picker.querySelector(".player-search");
        input.value = name;
        picker.querySelector(".player-dropdown").classList.add("hidden");
        const points = input.closest(".player-row").querySelector("input[name='player_points[]']");
        points.focus();
    }

    function createRow(name) {
        const fragment = template.content.cloneNode(true);
        const row = fragment.querySelector(".player-row");
        const nameInput = row.querySelector("input[name='player_name[]']");
        if (name) {
            nameInput.value = name;
        }
        container.appendChild(fragment);
        (name ? row.querySelector("input[name='player_points[]']") : nameInput).focus();
        if (!name) {
            renderDropdown(row.querySelector(".player-picker"));
        }
        return row;
    }

    addButton.addEventListener("click", function () {
        createRow("");
    });

    // Dropdown interactions (delegated on the container).
    container.addEventListener("click", function (event) {
        const removeBtn = event.target.closest(".remove-row");
        if (removeBtn) {
            if (container.getElementsByClassName("player-row").length > 1) {
                removeBtn.closest(".player-row").remove();
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

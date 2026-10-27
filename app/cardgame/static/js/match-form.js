// Dynamic player rows for the match registration form.
(function () {
    "use strict";

    const container = document.getElementById("player-inputs");
    const template = document.getElementById("player-row-template");
    const addButton = document.getElementById("add-player");

    if (!container || !template || !addButton) {
        return;
    }

    addButton.addEventListener("click", function () {
        const fragment = template.content.cloneNode(true);
        container.appendChild(fragment);
    });

    container.addEventListener("click", function (event) {
        const button = event.target.closest(".remove-row");
        if (!button) {
            return;
        }
        if (container.getElementsByClassName("player-row").length > 1) {
            button.closest(".player-row").remove();
        } else {
            alert("Devi includere almeno un giocatore.");
        }
    });
})();

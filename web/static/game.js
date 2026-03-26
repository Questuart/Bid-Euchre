/**
 * Bid Euchre Browser Game — Client-side JavaScript
 *
 * - Decision timer logging
 * - Card tap-select + confirm for human hand play
 * - AI pacing controls + adjustable delay profiles
 * - Optional pacing indicator during delayed AI response simulation
 */

(function () {
    "use strict";

    // -----------------------------------------------------------------------
    // Configuration
    // -----------------------------------------------------------------------

    /** Storage key for AI pacing profile preference. */
    var STORAGE_KEY = "bid_euchre_ai_pace";

    /** Delay presets (milliseconds, before card resolution request is sent). */
    var PACING_PRESETS = {
        instant: { multiplier: 0, regularMinMs: 0, regularMaxMs: 0, moonMinMs: 0, moonMaxMs: 0, lonerMinMs: 0, lonerMaxMs: 0 },
        fast: { multiplier: 0.6, regularMinMs: 200, regularMaxMs: 450, moonMinMs: 450, moonMaxMs: 800, lonerMinMs: 550, lonerMaxMs: 1100 },
        normal: { multiplier: 1.0, regularMinMs: 300, regularMaxMs: 600, moonMinMs: 800, moonMaxMs: 1500, lonerMinMs: 1000, lonerMaxMs: 2000 },
        slow: { multiplier: 1.5, regularMinMs: 500, regularMaxMs: 950, moonMinMs: 1200, moonMaxMs: 2200, lonerMinMs: 1400, lonerMaxMs: 2800 },
    };

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------

    var decisionStart = Date.now();

    // -----------------------------------------------------------------------
    // Decision Timer
    // -----------------------------------------------------------------------

    function resetTimer() {
        decisionStart = Date.now();
    }

    function injectDecisionTime(evt) {
        var form = evt.target.closest("form");
        if (!form) {
            return;
        }
        var elapsed = Date.now() - decisionStart;
        var existing = form.querySelector('input[name="decision_time_ms"]');
        if (existing) {
            existing.value = elapsed;
        } else {
            var input = document.createElement("input");
            input.type = "hidden";
            input.name = "decision_time_ms";
            input.value = elapsed;
            form.appendChild(input);
        }
    }

    // -----------------------------------------------------------------------
    // Pace controls
    // -----------------------------------------------------------------------

    function getPaceMode() {
        var select = document.getElementById("ai-pace-control");
        if (select && select.value in PACING_PRESETS) {
            return select.value;
        }
        return "normal";
    }

    function initPaceControl() {
        var select = document.getElementById("ai-pace-control");
        if (!select) {
            return;
        }
        var saved = "normal";
        try {
            saved = window.localStorage.getItem(STORAGE_KEY) || "normal";
        } catch (err) {
            // localStorage may be unavailable in privacy modes.
            saved = "normal";
        }
        if (saved in PACING_PRESETS) {
            select.value = saved;
        }
    }

    function getPacingDelay(form) {
        if (!(form && form.dataset && form.dataset.paced === "true")) {
            return 0;
        }
        var mode = getPaceMode();
        var preset = PACING_PRESETS[mode] || PACING_PRESETS.normal;
        if (preset.multiplier === 0) {
            return 0;
        }

        var bidTypeSelect = form.querySelector('[name="bid_type"]');
        var bidType = bidTypeSelect ? bidTypeSelect.value : "regular";
        var minMs = preset.regularMinMs;
        var maxMs = preset.regularMaxMs;
        if (bidType === "moon") {
            minMs = preset.moonMinMs;
            maxMs = preset.moonMaxMs;
        } else if (bidType === "loner") {
            minMs = preset.lonerMinMs;
            maxMs = preset.lonerMaxMs;
        }

        var scaledMin = Math.max(0, Math.round(minMs * preset.multiplier));
        var scaledMax = Math.max(scaledMin, Math.round(maxMs * preset.multiplier));
        return Math.floor(Math.random() * (scaledMax - scaledMin + 1)) + scaledMin;
    }

    function showPacingIndicator() {
        var existing = document.getElementById("pacing-indicator");
        if (existing) {
            existing.classList.add("active");
            return existing;
        }
        var control = document.querySelector(".pacing-controls");
        var indicator = document.createElement("div");
        indicator.id = "pacing-indicator";
        indicator.className = "pacing-indicator active";
        indicator.innerHTML = 'AI is considering<span class="pacing-dots"></span>';
        if (control) {
            control.appendChild(indicator);
            return indicator;
        }
        document.body.appendChild(indicator);
        return indicator;
    }

    function hidePacingIndicator() {
        var indicator = document.getElementById("pacing-indicator");
        if (indicator) {
            indicator.classList.remove("active");
        }
    }

    function clearPacingState(form) {
        if (!form) {
            return;
        }
        if (form.dataset && form.dataset.queued === "1") {
            form.dataset.queued = "0";
            delete form.dataset.queued;
        }
    }

    function onPaceModeChange(evt) {
        var select = evt.target;
        if (!select || !select.value) {
            return;
        }
        if (!(select.value in PACING_PRESETS)) {
            select.value = "normal";
        }
        try {
            window.localStorage.setItem(STORAGE_KEY, select.value);
        } catch (err) {
            // Ignore — privacy mode might block storage writes.
        }
    }

    function queuePacedSubmit(form) {
        if (!form || form.dataset.queued === "1") {
            return;
        }
        var delay = getPacingDelay(form);
        if (delay <= 0) {
            form.dataset.queued = "1";
            htmx.trigger(form, "submit");
            return;
        }

        form.dataset.queued = "1";
        showPacingIndicator();
        setTimeout(function () {
            htmx.trigger(form, "submit");
        }, delay);
    }

    // -----------------------------------------------------------------------
    // Card selection / play panel
    // -----------------------------------------------------------------------

    function isPlayCardForm(form) {
        return form && form.id === "play-card-form";
    }

    function selectedCardLabel(form, value) {
        if (!form) {
            return null;
        }
        var buttons = form.querySelectorAll(".card--playable");
        for (var i = 0; i < buttons.length; i += 1) {
            if (buttons[i].getAttribute("data-card-index") === value) {
                return buttons[i].getAttribute("data-card-text") || null;
            }
        }
        return null;
    }

    function updatePlayState(form) {
        if (!form) {
            return;
        }
        var selected = form.querySelector("#selected-card-index");
        var submit = form.querySelector("#play-card-submit");
        var help = form.querySelector("#card-selection-help");
        var idx = selected ? selected.value : "";
        var hasSelection = idx !== "";

        if (submit) {
            submit.disabled = !hasSelection;
        }

        if (help) {
            if (hasSelection) {
                var label = selectedCardLabel(form, idx);
                if (label) {
                    help.textContent = "Selected: " + label + ".";
                }
            } else {
                help.textContent = "Tap a legal card to select, then confirm.";
            }
        }
    }

    function clearSelectedCard(form) {
        if (!form) {
            return;
        }
        var cards = form.querySelectorAll(".card--playable");
        for (var i = 0; i < cards.length; i += 1) {
            cards[i].classList.remove("card--selected");
        }
        var selected = form.querySelector("#selected-card-index");
        if (selected) {
            selected.value = "";
        }
        updatePlayState(form);
    }

    function setSelectedCard(form, button, cardIndex) {
        if (!form) {
            return;
        }
        var selected = form.querySelector("#selected-card-index");
        if (!selected) {
            return;
        }

        var currentIdx = selected.value;
        if (currentIdx) {
            var prev = form.querySelector('[data-card-index="' + currentIdx + '"]');
            if (prev) {
                prev.classList.remove("card--selected");
            }
        }

        button.classList.add("card--selected");
        selected.value = cardIndex;
        updatePlayState(form);
    }

    function onCardPlayableClick(evt) {
        var target = evt.target.closest(".card--playable");
        if (!target) {
            return;
        }
        var form = document.getElementById("play-card-form");
        var idx = target.getAttribute("data-card-index");
        if (!form || !idx) {
            return;
        }
        evt.preventDefault();
        setSelectedCard(form, target, idx);
    }

    // -----------------------------------------------------------------------
    // Event binding
    // -----------------------------------------------------------------------

    function bindCardControls() {
        var cards = document.querySelectorAll(".card--playable");
        for (var i = 0; i < cards.length; i += 1) {
            cards[i].addEventListener("click", onCardPlayableClick);
        }
        var playForm = document.getElementById("play-card-form");
        if (playForm) {
            var selected = playForm.querySelector("#selected-card-index");
            if (selected && selected.value === "") {
                clearSelectedCard(playForm);
            } else {
                updatePlayState(playForm);
            }
        }
    }

    // -----------------------------------------------------------------------
    // HTMX lifecycle events
    // -----------------------------------------------------------------------

    // Delay paced forms (currently bid form) to simulate AI thought time.
    document.body.addEventListener("submit", function (evt) {
        var form = evt.target.closest("form");
        if (!form || form.dataset.paced !== "true" || form.dataset.queued === "1") {
            return;
        }
        evt.preventDefault();
        queuePacedSubmit(form);
    });

    // Inject decision timings and clear pacing state before the request fires.
    document.body.addEventListener("htmx:beforeRequest", function (evt) {
        injectDecisionTime(evt);
        var form = evt.target.closest("form");
        if (form && form.dataset && form.dataset.queued === "1") {
            clearPacingState(form);
            hidePacingIndicator();
        }
    });

    // Reset UI and timing after board swaps.
    document.body.addEventListener("htmx:afterSwap", function () {
        hidePacingIndicator();
        resetTimer();
        clearSelectedCard(document.getElementById("play-card-form"));
        initPaceControl();
        bindCardControls();
        var paceSelect = document.getElementById("ai-pace-control");
        if (paceSelect) {
            paceSelect.addEventListener("change", onPaceModeChange);
        }
    });

    // Hide indicator and clear any queued state if request errors.
    document.body.addEventListener("htmx:responseError", function (evt) {
        hidePacingIndicator();
        clearPacingState(evt.target.closest("form"));
    });

    // Initial boot.
    initPaceControl();
    if (!document.getElementById("play-card-form")) {
        var placeholderSubmit = document.getElementById("play-card-submit");
        if (placeholderSubmit) {
            placeholderSubmit.disabled = true;
        }
    }
    var paceSelect = document.getElementById("ai-pace-control");
    if (paceSelect) {
        paceSelect.addEventListener("change", onPaceModeChange);
    }
    resetTimer();
    bindCardControls();

    // Ensure submit helper remains global for existing onclick handlers in templates.
    window.__bidEuchreSubmitPass = function (btn) {
        var form = btn.closest("form");
        if (form) {
            htmx.trigger(form, "submit");
        }
    };
})();

/**
 * Bid Euchre Browser Game — Client-side JavaScript
 *
 * Minimal vanilla JS (no build tooling):
 * 1. Decision timer — records how long the human takes to act
 * 2. HTMX swap hooks — resets timer on new decision prompts
 * 3. Card click handler — visual feedback on interaction
 * 4. AI response pacing — configurable delay for moon/loner bids
 *
 * The decision_time_ms hidden input is injected into every bid/play form
 * submission so the server can record human decision latency.
 */

(function () {
    "use strict";

    // -----------------------------------------------------------------------
    // Configuration
    // -----------------------------------------------------------------------

    /**
     * AI pacing delay range in milliseconds.
     * After a human submits a moon or loner bid, a brief delay is added
     * before the HTMX response is processed to give a sense of AI
     * deliberation.  Regular bids get a shorter delay.
     */
    var PACING = {
        moonMinMs: 800,
        moonMaxMs: 1500,
        lonerMinMs: 1000,
        lonerMaxMs: 2000,
        regularMinMs: 300,
        regularMaxMs: 600
    };

    // -----------------------------------------------------------------------
    // Decision Timer
    // -----------------------------------------------------------------------

    /** Timestamp (ms) when the current decision prompt was loaded. */
    var decisionStart = Date.now();

    /**
     * Reset the decision timer.  Called on page load and after each HTMX swap
     * that delivers a new decision prompt.
     */
    function resetTimer() {
        decisionStart = Date.now();
    }

    /**
     * Inject a hidden `decision_time_ms` input into the form that is about to
     * submit.  HTMX fires `htmx:beforeRequest` on the element with the
     * `hx-post` attribute — which may be a <form> or a child <button>.
     *
     * We walk up to the enclosing <form> to ensure the input is added in the
     * right place.  If a previous hidden input already exists (e.g. from a
     * duplicate event), we update its value rather than creating a second one.
     *
     * @param {CustomEvent} evt — htmx:beforeRequest event
     */
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
    // AI Response Pacing
    // -----------------------------------------------------------------------

    /**
     * Return a random integer in [min, max].
     */
    function randInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    /**
     * Get the pacing delay for the current bid type.
     * Reads the bid_type select value from the bid form if present.
     *
     * @param {Element} form — the form being submitted
     * @returns {number} delay in milliseconds (0 for card plays)
     */
    function getPacingDelay(form) {
        var action = form.getAttribute("action") || "";

        // Only pace bid submissions, not card plays
        if (action.indexOf("/bid") === -1) {
            return 0;
        }

        var bidTypeSelect = form.querySelector('[name="bid_type"]');
        if (!bidTypeSelect) {
            return randInt(PACING.regularMinMs, PACING.regularMaxMs);
        }

        var bidType = bidTypeSelect.value;
        if (bidType === "moon") {
            return randInt(PACING.moonMinMs, PACING.moonMaxMs);
        } else if (bidType === "loner") {
            return randInt(PACING.lonerMinMs, PACING.lonerMaxMs);
        }
        return randInt(PACING.regularMinMs, PACING.regularMaxMs);
    }

    /**
     * Show a pacing indicator during the AI delay.
     * Creates a temporary element that displays "AI is thinking..." style
     * text while the delayed response is pending.
     */
    function showPacingIndicator() {
        var existing = document.getElementById("pacing-indicator");
        if (existing) {
            existing.classList.add("active");
            return existing;
        }

        var indicator = document.createElement("div");
        indicator.id = "pacing-indicator";
        indicator.className = "pacing-indicator active";
        indicator.innerHTML = 'AI is considering<span class="pacing-dots"></span>';

        var bidPanel = document.getElementById("bid-panel");
        if (bidPanel) {
            bidPanel.appendChild(indicator);
        }
        return indicator;
    }

    /**
     * Hide and remove the pacing indicator.
     */
    function hidePacingIndicator() {
        var indicator = document.getElementById("pacing-indicator");
        if (indicator) {
            indicator.classList.remove("active");
        }
    }

    /**
     * Handle HTMX beforeSwap to apply pacing delay for bid submissions.
     * This delays the DOM swap to create a deliberation effect.
     *
     * @param {CustomEvent} evt — htmx:beforeSwap event
     */
    function handlePacingBeforeRequest(evt) {
        var form = evt.target.closest("form");
        if (!form) {
            return;
        }

        var delay = getPacingDelay(form);
        if (delay > 0) {
            showPacingIndicator();
        }
    }

    // -----------------------------------------------------------------------
    // Card Click Feedback
    // -----------------------------------------------------------------------

    /**
     * Add a brief pressed effect when a legal card button is clicked.
     * The actual form submission is handled by HTMX — this is purely visual.
     *
     * @param {Event} evt — click event on a .card--legal button
     */
    function onCardClick(evt) {
        var card = evt.currentTarget;
        card.style.transform = "translateY(-4px) scale(0.95)";
        // Let HTMX handle the rest; the card will be replaced on swap.
    }

    // -----------------------------------------------------------------------
    // Event Binding
    // -----------------------------------------------------------------------

    /**
     * Bind click handlers to all legal card buttons currently in the DOM.
     * Called on page load and after each HTMX swap.
     */
    function bindCardHandlers() {
        var cards = document.querySelectorAll("button.card--legal");
        for (var i = 0; i < cards.length; i++) {
            cards[i].addEventListener("click", onCardClick);
        }
    }

    // Listen for HTMX events on the document body (delegated).
    // htmx:beforeRequest fires before any HTMX request — inject timer value
    // and show pacing indicator.
    document.body.addEventListener("htmx:beforeRequest", function (evt) {
        injectDecisionTime(evt);
        handlePacingBeforeRequest(evt);
    });

    // htmx:afterSwap fires after HTMX replaces content — reset timer,
    // hide pacing indicator, and rebind card handlers for the new DOM content.
    document.body.addEventListener("htmx:afterSwap", function () {
        hidePacingIndicator();
        resetTimer();
        bindCardHandlers();
    });

    // Initial binding on page load.
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bindCardHandlers);
    } else {
        bindCardHandlers();
    }
})();

/**
 * Bid Euchre Browser Game — Client-side JavaScript
 *
 * Minimal vanilla JS (no build tooling):
 * 1. Decision timer — records how long the human takes to act
 * 2. HTMX swap hooks — resets timer on new decision prompts
 * 3. Card click handler — visual feedback on interaction
 *
 * The decision_time_ms hidden input is injected into every bid/play form
 * submission so the server can record human decision latency.
 */

(function () {
    "use strict";

    // -----------------------------------------------------------------------
    // Decision Timer
    // -----------------------------------------------------------------------

    /** Timestamp (ms) when the current decision prompt was loaded. */
    let decisionStart = Date.now();

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
    // htmx:beforeRequest fires before any HTMX request — inject timer value.
    document.body.addEventListener("htmx:beforeRequest", injectDecisionTime);

    // htmx:afterSwap fires after HTMX replaces content — reset timer and
    // rebind card handlers for the new DOM content.
    document.body.addEventListener("htmx:afterSwap", function () {
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

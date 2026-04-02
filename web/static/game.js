/**
 * Browser game interactions.
 *
 * Responsibilities:
 * - tap a legal card to play it immediately (all devices)
 * - keep card selection state in sync across HTMX swaps
 */
(function () {
    if (typeof window === 'undefined' || typeof document === 'undefined') {
        return;
    }

    if (typeof htmx === 'undefined') {
        return;
    }

    function getCardPlayForm() {
        return document.getElementById('card-play-form');
    }

    function getSelectedCardInput(form) {
        if (form === null) {
            return null;
        }
        return form.querySelector('#selected-card-index');
    }

    function clearCardSelection(form) {
        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        var selectedCards = document.querySelectorAll('#card-play-form .card--legal.card--selected');
        Array.prototype.forEach.call(selectedCards, function (card) {
            card.classList.remove('card--selected');
        });

        var help = form.querySelector('#card-play-help');
        var input = getSelectedCardInput(form);
        if (input !== null) {
            input.value = '';
        }

        var submitButton = form.querySelector('#card-play-submit');
        if (submitButton instanceof HTMLElement) {
            submitButton.disabled = true;
        }

        if (help !== null) {
            help.textContent = 'Tap a card to play it.';
        }
    }

    function syncCardPlayFormControls(form) {
        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        var input = getSelectedCardInput(form);
        var submitButton = form.querySelector('#card-play-submit');
        var touchCard = form.querySelector('.card--legal.card--selected');
        var hasSelection = input !== null && input.value !== '' && touchCard !== null;

        if (submitButton !== null) {
            submitButton.disabled = !hasSelection;
        }

        if (hasSelection === false) {
            clearCardSelection(form);
        }
    }

    function selectCard(form, button) {
        if (!(form instanceof HTMLFormElement) || !(button instanceof HTMLElement)) {
            return;
        }

        var input = getSelectedCardInput(form);
        if (input === null) {
            return;
        }

        var previous = document.querySelectorAll('#card-play-form .card--legal.card--selected');
        Array.prototype.forEach.call(previous, function (card) {
            card.classList.remove('card--selected');
        });
        button.classList.add('card--selected');

        var idx = button.getAttribute('data-card-index');
        input.value = String(idx === null ? '' : idx);

        var submitButton = form.querySelector('#card-play-submit');
        if (submitButton !== null) {
            submitButton.disabled = false;
        }

        var help = form.querySelector('#card-play-help');
        if (help !== null) {
            help.textContent = 'Playing card...';
        }
    }

    function submitForm(form) {
        if (!(form instanceof HTMLFormElement)) {
            return;
        }
        htmx.trigger(form, 'submit');
    }

    function attachDelegatedHandlers() {
        document.addEventListener('click', function (event) {
            var target = event.target;

            var submitButton = target.closest('#card-play-submit');
            if (submitButton !== null) {
                event.preventDefault();
                var form = getCardPlayForm();
                if (form === null) {
                    return;
                }
                var input = getSelectedCardInput(form);
                var help = form.querySelector('#card-play-help');

                if (input === null || input.value === '') {
                    if (help !== null) {
                        help.textContent = 'Select a legal card first.';
                    }
                    return;
                }

                submitForm(form);
                return;
            }

            var card = target.closest('.card--legal[data-card-index]');
            if (card === null) {
                return;
            }

            event.preventDefault();

            var handForm = getCardPlayForm();
            if (handForm === null) {
                return;
            }

            selectCard(handForm, card);
            submitForm(handForm);
        });

        document.body.addEventListener('htmx:afterSwap', function (event) {
            var target = event.target;
            if (!(target instanceof Element) || target.id !== 'game-board') {
                return;
            }
            clearCardSelection(getCardPlayForm());
            syncCardPlayFormControls(getCardPlayForm());
            restoreTrickHistoryState();
        }, true);
    }

    /* ---------------------------------------------------------------
     * Trick history toggle — persist open/closed state across HTMX
     * swaps so the panel doesn't collapse every time the board updates.
     * --------------------------------------------------------------- */

    var TRICK_HISTORY_KEY = 'trickHistoryOpen';

    function saveTrickHistoryState() {
        var details = document.getElementById('trick-history');
        if (details) {
            try {
                sessionStorage.setItem(TRICK_HISTORY_KEY, details.open ? '1' : '0');
            } catch (_) {
                // sessionStorage unavailable — ignore
            }
        }
    }

    function restoreTrickHistoryState() {
        var details = document.getElementById('trick-history');
        if (!details) { return; }
        try {
            var saved = sessionStorage.getItem(TRICK_HISTORY_KEY);
            if (saved === '1') {
                details.open = true;
            }
        } catch (_) {
            // sessionStorage unavailable — ignore
        }
    }

    function attachTrickHistoryToggle() {
        document.addEventListener('toggle', function (event) {
            if (event.target && event.target.id === 'trick-history') {
                saveTrickHistoryState();
            }
        }, true);
    }

    function initialize() {
        attachDelegatedHandlers();
        attachTrickHistoryToggle();
        var form = getCardPlayForm();
        clearCardSelection(form);
        syncCardPlayFormControls(form);
        restoreTrickHistoryState();
    }

    initialize();
})();

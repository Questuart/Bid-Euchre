/**
 * Browser game interactions.
 *
 * Responsibilities:
 * - tap/select a legal card and submit as a single confirm form
 * - auto-submit on desktop after selection
 * - reset hand form state after HTMX swaps
 */
(function () {
    if (typeof window === 'undefined' || typeof document === 'undefined') {
        return;
    }

    if (typeof htmx === 'undefined') {
        return;
    }

    function isLikelyTouchDevice() {
        return (
            window.matchMedia('(hover: none), (pointer: coarse)').matches ||
            ('ontouchstart' in window) ||
            (typeof navigator !== 'undefined' && navigator.maxTouchPoints > 0)
        );
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
            help.textContent = 'Tap a card to select it, then tap Play card.';
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
            if (isLikelyTouchDevice()) {
                help.textContent = 'Card selected. Tap Play card to submit.';
            } else {
                help.textContent = 'Card selected. Submitting...';
            }
        }
    }

    function attachDelegatedHandlers() {
        document.addEventListener('click', function (event) {
            var target = event.target;

            var submitButton = target.closest('#card-play-submit');
            if (submitButton !== null) {
                event.preventDefault();
                var submitForm = getCardPlayForm();
                if (submitForm === null) {
                    return;
                }
                var input = getSelectedCardInput(submitForm);
                var help = submitForm.querySelector('#card-play-help');

                if (input === null || input.value === '') {
                    if (help !== null) {
                        help.textContent = 'Select a legal card first.';
                    }
                    return;
                }

                htmx.trigger(submitForm, 'submit');
                return;
            }

            var card = target.closest('.card--legal[data-card-index]');
            if (card === null) {
                return;
            }

            var handForm = getCardPlayForm();
            if (handForm === null) {
                return;
            }

            event.preventDefault();
            selectCard(handForm, card);

            if (!isLikelyTouchDevice()) {
                htmx.trigger(handForm, 'submit');
            }
        });

        document.body.addEventListener('htmx:afterSwap', function (event) {
            var target = event.target;
            if (!(target instanceof Element) || target.id !== 'game-board') {
                return;
            }
            clearCardSelection(getCardPlayForm());
            syncCardPlayFormControls(getCardPlayForm());
        }, true);
    }

    function initialize() {
        attachDelegatedHandlers();
        clearCardSelection(getCardPlayForm());
        syncCardPlayFormControls(getCardPlayForm());
    }

    initialize();
})();

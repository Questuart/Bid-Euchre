/**
 * Browser game interactions.
 *
 * Responsibilities:
 * - tap/select a legal card and submit as a single confirm form
 * - optional AI pace control (localStorage-backed)
 * - delayed submission for pace profiles without breaking HTMX flow
 */
(function () {
    if (typeof window === 'undefined' || typeof document === 'undefined') {
        return;
    }

    if (typeof htmx === 'undefined') {
        return;
    }

    var PACE_STORAGE_KEY = 'be:ai-pace-profile';
    var DEFAULT_PACE = 'normal';
    var PACE_DELAYS_MS = {
        off: 0,
        fast: 250,
        normal: 700,
        slow: 1300,
    };

    /**
     * Read persisted pace profile.
     */
    function getStoredPace() {
        try {
            var value = window.localStorage.getItem(PACE_STORAGE_KEY);
            if (value === 'off' || value === 'fast' || value === 'normal' || value === 'slow') {
                return value;
            }
        } catch (_err) {
            // localStorage unavailable in some privacy-restricted modes.
        }
        return DEFAULT_PACE;
    }

    /**
     * Persist selected pace profile.
     */
    function setStoredPace(profile) {
        try {
            window.localStorage.setItem(PACE_STORAGE_KEY, profile);
        } catch (_err) {
            // Non-blocking; still keep behavior in-memory.
        }
    }

    var currentPace = getStoredPace();

    /**
     * Resolve form pace setting from currently selected mode.
     */
    function paceDelayForCurrent() {
        var delay = PACE_DELAYS_MS[currentPace] || PACE_DELAYS_MS.normal;
        return delay;
    }

    /**
     * Whether a form should be sent through paced submission.
     */
    function shouldPaceForm(form) {
        if (!(form instanceof HTMLFormElement)) {
            return false;
        }

        if (!form.action) {
            return false;
        }

        return /\/play\/[0-9a-f-]+\/(bid|play-card|next-hand)$/.test(form.action);
    }

    /**
     * Touch-capable device heuristic.
     */
    function isLikelyTouchDevice() {
        return (
            window.matchMedia('(hover: none), (pointer: coarse)').matches ||
            ('ontouchstart' in window) ||
            (typeof navigator !== 'undefined' && navigator.maxTouchPoints > 0)
        );
    }

    /**
     * Busy state used while delay timer is active.
     */
    function setFormBusy(form, busy) {
        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        var submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitButton === null) {
            return;
        }

        if (busy) {
            submitButton.dataset.autoDisabled = submitButton.disabled ? '0' : '1';
            submitButton.disabled = true;
            if (submitButton.dataset.labelBusy !== '1') {
                submitButton.dataset.labelBusy = submitButton.textContent;
                submitButton.textContent = 'Applying...';
            }
            return;
        }

        if (submitButton.dataset.autoDisabled === '1') {
            submitButton.disabled = false;
        }
        if (submitButton.dataset.labelBusy) {
            submitButton.textContent = submitButton.dataset.labelBusy;
        }
        delete submitButton.dataset.autoDisabled;
        delete submitButton.dataset.labelBusy;
    }

    function clearFormPacingState(form) {
        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        delete form.dataset.pacingBusy;
        delete form.dataset.pacingSkip;
        delete form.dataset.pacingArmed;
        setFormBusy(form, false);
    }

    /**
     * Queue HTMX form submit with pacing delay.
     */
    function schedulePacedSubmit(form) {
        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        if (form.dataset.pacingBusy === '1') {
            return;
        }

        var delay = paceDelayForCurrent();
        if (!shouldPaceForm(form) || delay <= 0) {
            form.dataset.pacingSkip = '1';
            htmx.trigger(form, 'submit');
            return;
        }

        form.dataset.pacingBusy = '1';
        form.dataset.pacingArmed = '1';
        setFormBusy(form, true);

        window.setTimeout(function () {
            if (!form.isConnected) {
                clearFormPacingState(form);
                return;
            }

            if (form.dataset.pacingArmed !== '1') {
                clearFormPacingState(form);
                return;
            }

            form.dataset.pacingSkip = '1';
            htmx.trigger(form, 'submit');
            delete form.dataset.pacingArmed;
        }, delay);
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

    function initPaceControl() {
        var select = document.getElementById('pace-profile');
        if (!(select instanceof HTMLSelectElement)) {
            return;
        }

        if (['off', 'fast', 'normal', 'slow'].indexOf(currentPace) === -1) {
            currentPace = DEFAULT_PACE;
        }

        select.value = currentPace;

        select.addEventListener('change', function (event) {
            var newValue = event.target.value;
            if (newValue !== 'off' && newValue !== 'fast' && newValue !== 'normal' && newValue !== 'slow') {
                currentPace = DEFAULT_PACE;
            } else {
                currentPace = newValue;
            }
            setStoredPace(currentPace);
        });
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

                schedulePacedSubmit(form);
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
                schedulePacedSubmit(handForm);
                return;
            }
        });

        document.addEventListener('submit', function (event) {
            var form = event.target;
            if (!(form instanceof HTMLFormElement)) {
                return;
            }

            if (form.dataset.pacingSkip === '1') {
                delete form.dataset.pacingSkip;
                return;
            }

            if (!shouldPaceForm(form)) {
                return;
            }

            event.preventDefault();
            schedulePacedSubmit(form);
        }, true);

        document.addEventListener('htmx:afterRequest', function (event) {
            var form = event.detail && event.detail.elt ? event.detail.elt : event.target;
            if (form instanceof Element) {
                form = form.closest('form') || form;
            }
            if (form instanceof HTMLFormElement) {
                clearFormPacingState(form);
            }
        }, true);

        document.addEventListener('htmx:sendError', function (event) {
            var form = event.detail && event.detail.elt ? event.detail.elt : event.target;
            if (form instanceof Element) {
                form = form.closest('form') || form;
            }
            if (form instanceof HTMLFormElement) {
                clearFormPacingState(form);
            }
        }, true);

        document.addEventListener('htmx:responseError', function (event) {
            var form = event.detail && event.detail.elt ? event.detail.elt : event.target;
            if (form instanceof Element) {
                form = form.closest('form') || form;
            }
            if (form instanceof HTMLFormElement) {
                clearFormPacingState(form);
            }
        }, true);

        document.body.addEventListener('htmx:afterSwap', function (event) {
            var target = event.target;
            if (!(target instanceof Element) || target.id !== 'game-board') {
                return;
            }
            clearCardSelection(getCardPlayForm());
            syncCardPlayFormControls(getCardPlayForm());
        }, true);

        document.addEventListener('DOMContentLoaded', function () {
            var form = getCardPlayForm();
            syncCardPlayFormControls(form);
            initPaceControl();
        });
    }

    function initialize() {
        initPaceControl();
        attachDelegatedHandlers();

        var form = getCardPlayForm();
        clearCardSelection(form);
        syncCardPlayFormControls(form);
    }

    initialize();
})();

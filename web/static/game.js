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
            help.textContent = 'Playing card\u2026';
        }
    }

    function submitForm(form) {
        if (!(form instanceof HTMLFormElement)) {
            return;
        }
        htmx.trigger(form, 'submit');
    }

    /**
     * Sync the outer #game-board data-match-status attribute from the hidden
     * carrier element inside the swapped innerHTML.  Without this, the
     * attribute goes stale after HTMX morph:innerHTML swaps (#2248).
     */
    function syncMatchStatus(gameBoard) {
        var carrier = document.getElementById('match-status-carrier');
        if (carrier) {
            var status = carrier.getAttribute('data-match-status');
            if (status) {
                gameBoard.setAttribute('data-match-status', status);
            }
        } else {
            // Setup partials omit the carrier — clear stale status (#2276)
            gameBoard.removeAttribute('data-match-status');
        }
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
            syncMatchStatus(target);
            clearCardSelection(getCardPlayForm());
            syncCardPlayFormControls(getCardPlayForm());
            restoreTrickHistoryState();
        }, true);
    }

    /* ---------------------------------------------------------------
     * Tab navigation — update active tab styling on HTMX content swap.
     * When tab links use hx-get + hx-target="#tab-content", the active
     * class must be toggled client-side after each swap.
     * --------------------------------------------------------------- */

    function updateActiveTab(clickedTab) {
        var tabs = document.querySelectorAll('.header-nav__tab');
        Array.prototype.forEach.call(tabs, function (tab) {
            tab.classList.remove('header-nav__tab--active');
            tab.setAttribute('aria-selected', 'false');
        });
        if (clickedTab) {
            clickedTab.classList.add('header-nav__tab--active');
            clickedTab.setAttribute('aria-selected', 'true');
        }
    }

    function getTabFromUrl(url) {
        // Extract the tab name from the URL path for back/forward navigation.
        // Patterns: /play/uuid -> game, /history/uuid -> history, etc.
        var match = url.match(/\/(play|history|leaderboard|comments|guide)\//);
        if (!match) { return null; }
        var page = match[1] === 'play' ? 'game' : match[1];
        return document.querySelector('.header-nav__tab[data-tab="' + page + '"]');
    }

    function reinitTabContent() {
        // After HTMX swaps tab content, re-execute inline scripts won't
        // run automatically.  Clone <script> tags inside #tab-content so
        // the browser treats them as new and executes them.
        var tabContent = document.getElementById('tab-content');
        if (!tabContent) { return; }
        var scripts = tabContent.querySelectorAll('script');
        for (var i = 0; i < scripts.length; i++) {
            var old = scripts[i];
            var replacement = document.createElement('script');
            replacement.textContent = old.textContent;
            old.parentNode.replaceChild(replacement, old);
        }
    }

    function attachTabHandlers() {
        // Update active tab when a tab link triggers an HTMX request
        document.addEventListener('click', function (event) {
            var tab = event.target.closest('.header-nav__tab[data-tab]');
            if (!tab) { return; }
            // Only intercept if HTMX will handle it (has hx-get)
            if (!tab.getAttribute('hx-get')) { return; }
            updateActiveTab(tab);
        });

        // After HTMX swaps tab content, reinitialize inline scripts
        // and restore persisted UI state (e.g. trick-history open/closed).
        document.body.addEventListener('htmx:afterSwap', function (event) {
            var target = event.target;
            if (target && target.id === 'tab-content') {
                reinitTabContent();
                restoreTrickHistoryState();
            }
        });

        // Handle browser back/forward — HTMX popstate restores content,
        // but we need to update the active tab indicator to match.
        window.addEventListener('popstate', function () {
            var tab = getTabFromUrl(window.location.pathname);
            if (tab) {
                updateActiveTab(tab);
            }
        });
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

    /* ---------------------------------------------------------------
     * Text size toggle — default (100%) and large (125%).
     * Persisted in localStorage. The inline <script> in base.html
     * applies the attribute before first paint to avoid FOUC.
     * --------------------------------------------------------------- */

    var TEXT_SIZE_KEY = 'textSize';

    function getTextSize() {
        try {
            return localStorage.getItem(TEXT_SIZE_KEY) || 'default';
        } catch (_) {
            // localStorage unavailable — fall back to document state
            return document.documentElement.getAttribute('data-text-size') || 'default';
        }
    }

    function setTextSize(size) {
        try {
            if (size === 'large') {
                localStorage.setItem(TEXT_SIZE_KEY, 'large');
                document.documentElement.setAttribute('data-text-size', 'large');
            } else {
                localStorage.removeItem(TEXT_SIZE_KEY);
                document.documentElement.removeAttribute('data-text-size');
            }
        } catch (_) {
            // localStorage unavailable — still apply the attribute for this session
            if (size === 'large') {
                document.documentElement.setAttribute('data-text-size', 'large');
            } else {
                document.documentElement.removeAttribute('data-text-size');
            }
        }
    }

    function toggleTextSize() {
        var current = getTextSize();
        setTextSize(current === 'large' ? 'default' : 'large');
    }

    function attachTextSizeToggle() {
        document.addEventListener('click', function (event) {
            var btn = event.target.closest('#text-size-toggle');
            if (btn) {
                event.preventDefault();
                toggleTextSize();
            }
        });
    }

    /* ---------------------------------------------------------------
     * Error handling — show user-friendly toast when HTMX requests
     * fail (network error, server error, timeout).
     * --------------------------------------------------------------- */

    var ERROR_TOAST_ID = 'error-toast';
    var OFFLINE_BANNER_ID = 'offline-banner';
    var _errorDismissTimer = null;

    function showErrorToast(message, persistent) {
        var existing = document.getElementById(ERROR_TOAST_ID);
        if (existing) {
            existing.remove();
        }

        if (_errorDismissTimer) {
            clearTimeout(_errorDismissTimer);
            _errorDismissTimer = null;
        }

        var toast = document.createElement('div');
        toast.id = ERROR_TOAST_ID;
        toast.className = 'error-toast';
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');

        var msgSpan = document.createElement('span');
        msgSpan.className = 'error-toast__message';
        msgSpan.textContent = message;
        toast.appendChild(msgSpan);

        var dismissBtn = document.createElement('button');
        dismissBtn.className = 'error-toast__dismiss';
        dismissBtn.setAttribute('aria-label', 'Dismiss error');
        dismissBtn.textContent = '\u00d7';
        dismissBtn.addEventListener('click', function () {
            dismissErrorToast();
        });
        toast.appendChild(dismissBtn);

        document.body.appendChild(toast);

        // Force reflow so the transition animates
        toast.offsetHeight; // eslint-disable-line no-unused-expressions
        toast.classList.add('error-toast--visible');

        if (!persistent) {
            _errorDismissTimer = setTimeout(function () {
                dismissErrorToast();
            }, 8000);
        }
    }

    function dismissErrorToast() {
        var toast = document.getElementById(ERROR_TOAST_ID);
        if (toast) {
            toast.classList.remove('error-toast--visible');
            setTimeout(function () {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }
        if (_errorDismissTimer) {
            clearTimeout(_errorDismissTimer);
            _errorDismissTimer = null;
        }
    }

    function showOfflineBanner() {
        if (document.getElementById(OFFLINE_BANNER_ID)) {
            return;
        }
        var banner = document.createElement('div');
        banner.id = OFFLINE_BANNER_ID;
        banner.className = 'offline-banner';
        banner.setAttribute('role', 'status');
        banner.setAttribute('aria-live', 'polite');
        banner.textContent = 'You are offline. Reconnecting\u2026';
        document.body.insertBefore(banner, document.body.firstChild);
    }

    function hideOfflineBanner() {
        var banner = document.getElementById(OFFLINE_BANNER_ID);
        if (banner && banner.parentNode) {
            banner.parentNode.removeChild(banner);
        }
    }

    function refreshGameBoard() {
        // After reconnecting (online event), reload the current page to
        // re-fetch the authoritative game state from the server.  This
        // handles stale HTMX partial state that may have accumulated
        // while the player was offline.
        var gameBoard = document.getElementById('game-board');
        if (gameBoard) {
            window.location.reload();
        }
    }

    /* ---------------------------------------------------------------
     * Card-play request lifecycle — manage in-flight state and
     * recovery so that stalled requests don't leave the player stuck.
     * --------------------------------------------------------------- */

    function isCardPlayRequest(event) {
        var elt = event.detail && event.detail.elt;
        return elt && (elt.id === 'card-play-form' || (elt.closest && elt.closest('#card-play-form')));
    }

    function setCardPlayInFlight(form) {
        if (!(form instanceof HTMLFormElement)) {
            return;
        }
        form.classList.add('card-play-form--in-flight');

        var submitButton = form.querySelector('#card-play-submit');
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = 'Playing card\u2026';
        }

        var help = form.querySelector('#card-play-help');
        if (help) {
            help.textContent = 'Playing card\u2026';
        }
    }

    function resetCardPlayForm() {
        var form = getCardPlayForm();
        if (!(form instanceof HTMLFormElement)) {
            return;
        }
        form.classList.remove('card-play-form--in-flight');

        var submitButton = form.querySelector('#card-play-submit');
        if (submitButton) {
            submitButton.textContent = 'Play card';
        }

        // Re-enable the button if a card is still selected
        var input = getSelectedCardInput(form);
        var hasSelection = input !== null && input.value !== '';
        if (submitButton) {
            submitButton.disabled = !hasSelection;
        }

        var help = form.querySelector('#card-play-help');
        if (help) {
            help.textContent = hasSelection
                ? 'Tap Play card to retry.'
                : 'Tap a card to play it.';
        }
    }

    function attachErrorHandlers() {
        // Card-play request starts — lock the form UI
        document.body.addEventListener('htmx:beforeRequest', function (event) {
            if (isCardPlayRequest(event)) {
                setCardPlayInFlight(getCardPlayForm());
            }
        });

        // Card-play request completed (any status) — reset form if error
        document.body.addEventListener('htmx:afterRequest', function (event) {
            if (!isCardPlayRequest(event)) {
                return;
            }
            // On success the board swaps (htmx:afterSwap handles cleanup).
            // On failure, reset the form so the player can retry.
            if (event.detail.failed || event.detail.successful === false) {
                resetCardPlayForm();
            }
        });

        // HTMX response errors (server returned 4xx/5xx)
        document.body.addEventListener('htmx:responseError', function (event) {
            var status = event.detail.xhr ? event.detail.xhr.status : 0;
            var message;
            if (status === 400) {
                // State desync — reload the page to recover the authoritative
                // server state.  This handles stale card-play buttons left by
                // HTMX morph swap failures.
                refreshGameBoard();
                return;
            } else if (status === 404) {
                message = 'Game not found. It may have expired.';
            } else if (status === 429) {
                message = 'Too many active matches. Complete or abandon one first.';
            } else if (status >= 500) {
                message = 'Server error \u2014 please try again in a moment.';
            } else {
                message = 'Something went wrong. Please try again.';
            }
            showErrorToast(message, false);
        });

        // HTMX send errors (network failure, DNS, CORS, etc.)
        document.body.addEventListener('htmx:sendError', function (event) {
            if (isCardPlayRequest(event)) {
                resetCardPlayForm();
            }
            if (!navigator.onLine) {
                showOfflineBanner();
            } else {
                showErrorToast('Connection lost. Check your network and try again.', true);
            }
        });

        // HTMX timeout — reset card-play form for retry
        document.body.addEventListener('htmx:timeout', function (event) {
            if (isCardPlayRequest(event)) {
                resetCardPlayForm();
            }
            showErrorToast('Request timed out. Please try again.', false);
        });

        // Browser online/offline events
        window.addEventListener('offline', function () {
            showOfflineBanner();
        });

        window.addEventListener('online', function () {
            hideOfflineBanner();
            dismissErrorToast();
            // Refresh game board to recover from stale HTMX state
            refreshGameBoard();
        });
    }

    function initialize() {
        attachDelegatedHandlers();
        attachTabHandlers();
        attachTrickHistoryToggle();
        attachTextSizeToggle();
        attachErrorHandlers();
        var form = getCardPlayForm();
        clearCardSelection(form);
        syncCardPlayFormControls(form);
        restoreTrickHistoryState();
    }

    initialize();
})();

/*!
 * Hermes dashboard interactions — vanilla JS, no dependencies.
 * Refresh buttons, session bookmarks, relative timestamps.
 * Autocomplete and service worker are handled by app-ui.js / base.html.
 */
(function () {
  'use strict';

  /* ---------------------------------------------------------------
     Helpers
     --------------------------------------------------------------- */
  function csrfToken() {
    var hui = window.HermesUI;
    var token = hui && typeof hui.csrfToken === 'function' ? hui.csrfToken() : null;
    if (token) { return token; }
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function toast(message, kind) {
    var hui = window.HermesUI;
    if (hui && typeof hui.toast === 'function') {
      hui.toast({ message: message, kind: kind || 'info' });
    } else {
      window.alert(message);
    }
  }

  /* ---------------------------------------------------------------
     Refresh buttons (header + latest-refresh card + empty state)
     --------------------------------------------------------------- */
  function initRefresh() {
    var buttons = Array.prototype.slice.call(
      document.querySelectorAll('[data-refresh-url]')
    );
    if (!buttons.length) { return; }

    var busy = false;

    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (busy) { return; }
        busy = true;
        buttons.forEach(function (b) {
          b.disabled = true;
          b.setAttribute('aria-busy', 'true');
        });

        fetch(btn.getAttribute('data-refresh-url'), {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken() },
          credentials: 'same-origin'
        })
          .then(function (response) {
            return response.json().catch(function () { return {}; })
              .then(function (data) { return { ok: response.ok, status: response.status, data: data }; });
          })
          .then(function (result) {
            if (result.ok) {
              var d = result.data || {};
              toast('Refresh complete — ' + (d.created || 0) + ' new, ' + (d.updated || 0) + ' updated.', 'success');
              window.setTimeout(function () { window.location.reload(); }, 900);
            } else {
              busy = false;
              buttons.forEach(function (b) {
                b.disabled = false;
                b.removeAttribute('aria-busy');
              });
              var message = (result.data && result.data.error) ||
                (result.status === 409 ? 'A refresh is already running.' :
                 result.status === 502 ? 'Refresh failed — all feeds errored.' :
                 'Refresh failed (HTTP ' + result.status + ').');
              toast(message, 'danger');
            }
          })
          .catch(function () {
            busy = false;
            buttons.forEach(function (b) {
              b.disabled = false;
              b.removeAttribute('aria-busy');
            });
            toast('Network error — the refresh could not be started.', 'danger');
          });
      });
    });
  }

  /* ---------------------------------------------------------------
     Bookmarks — event delegation on [data-save-url]
     --------------------------------------------------------------- */
  function paintSaveButton(btn, saved) {
    btn.setAttribute('aria-pressed', saved ? 'true' : 'false');
    btn.setAttribute('data-saved', saved ? '1' : '0');
    var label = (saved ? 'Remove bookmark' : 'Bookmark') +
      (btn.getAttribute('data-title') ? ': ' + btn.getAttribute('data-title') : '');
    btn.setAttribute('aria-label', label);
    btn.setAttribute('title', saved ? 'Remove bookmark' : 'Bookmark');
    var icon = btn.querySelector('i');
    if (icon) {
      icon.classList.toggle('dash-save-on', saved);
    }
  }

  function initSaveButtons() {
    document.addEventListener('click', function (event) {
      var btn = event.target.closest ? event.target.closest('[data-save-url]') : null;
      if (!btn) { return; }

      event.preventDefault();
      if (btn.getAttribute('data-busy') === '1') { return; }
      btn.setAttribute('data-busy', '1');

      fetch(btn.getAttribute('data-save-url'), {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken() },
        credentials: 'same-origin'
      })
        .then(function (response) {
          if (!response.ok) {
            throw new Error('HTTP ' + response.status);
          }
          return response.json();
        })
        .then(function (data) {
          var saved = !!(data && data.is_saved);
          paintSaveButton(btn, saved);
          if (data && typeof data.saved_total === 'number') {
            document.querySelectorAll('[data-saved-count]').forEach(function (el) {
              el.textContent = String(data.saved_total);
            });
          }
        })
        .catch(function () {
          /* CSRF/session failures: stay quiet, restore the button. */
        })
        .finally(function () {
          btn.removeAttribute('data-busy');
        });
    });
  }

  /* ---------------------------------------------------------------
     Relative timestamps — <time data-relative datetime="ISO">
     --------------------------------------------------------------- */
  var UNITS = [
    [31557600000, 'year'],
    [2629800000, 'month'],
    [604800000, 'week'],
    [86400000, 'day'],
    [3600000, 'hour'],
    [60000, 'minute']
  ];
  var formatter = null;
  try {
    if ('RelativeTimeFormat' in Intl) {
      formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
    }
  } catch (err) {
    formatter = null;
  }

  function relativeText(date) {
    if (!formatter) { return null; }
    var diff = date.getTime() - Date.now();
    var abs = Math.abs(diff);
    for (var i = 0; i < UNITS.length; i++) {
      if (abs >= UNITS[i][0]) {
        return formatter.format(Math.round(diff / UNITS[i][0]), UNITS[i][1]);
      }
    }
    return formatter.format(0, 'minute');
  }

  function updateRelativeTimes() {
    var nodes = document.querySelectorAll('time[data-relative]');
    Array.prototype.forEach.call(nodes, function (node) {
      var iso = node.getAttribute('datetime');
      if (!iso) { return; }
      var date = new Date(iso);
      if (isNaN(date.getTime())) { return; }
      var text = relativeText(date);
      if (text) {
        node.textContent = text;
      }
    });
  }

  function initRelativeTimes() {
    if (!document.querySelector('time[data-relative]')) { return; }
    updateRelativeTimes();
    window.setInterval(updateRelativeTimes, 60000);
  }

  /* ---------------------------------------------------------------
     Boot
     --------------------------------------------------------------- */
  initRefresh();
  initSaveButtons();
  initRelativeTimes();
})();

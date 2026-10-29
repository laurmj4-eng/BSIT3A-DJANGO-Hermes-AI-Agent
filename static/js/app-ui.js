/*!
 * HermesUI – reusable vanilla JS utilities
 * No framework dependencies; safe to load after tabler.js
 */
(function () {
  'use strict';

  window.HermesUI = {};

  /* -------------------------------------------------
     CSRF helper
     ------------------------------------------------- */
  window.HermesUI.csrfToken = function () {
    return getCookie('csrftoken');
  };

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + '=') {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  /* -------------------------------------------------
     Toast: create a toast in .dh-toast-stack and auto-dismiss
     ------------------------------------------------- */
  window.HermesUI.toast = function (options) {
    const {
      message = '',
      kind = 'info',
      timeout = 5000,
    } = options || {};

    const stack = document.querySelector('.dh-toast-stack');
    if (!stack) {
      const div = document.createElement('div');
      div.className = 'dh-toast-stack';
      div.setAttribute('aria-live', 'polite');
      div.setAttribute('role', 'status');
      document.body.appendChild(div);
    }

    const toast = document.createElement('div');
    toast.className = `dh-toast is-${kind}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'polite');
    toast.textContent = message;

    // Set appropriate styling based on kind
    const validKinds = ['success', 'danger', 'warning', 'info'];
    if (validKinds.includes(kind)) {
      toast.classList.add(`is-${kind}`);
    }

    stack.appendChild(toast);

    // Auto-dismiss
    if (timeout > 0) {
      setTimeout(() => {
        if (toast.parentNode) {
          toast.style.opacity = '0';
          toast.style.transform = 'translateY(1rem)';
          setTimeout(() => toast.remove(), 300);
        }
      }, timeout);
    }

    return toast;
  };

  /* -------------------------------------------------
     Autocomplete controller
     ------------------------------------------------- */
  function initAutocomplete() {
    const inputs = document.querySelectorAll('input[data-autocomplete-url]');

    inputs.forEach(function (input) {
      let debounceTimer;
      let activeRequest = 0;
      let abortController = null;
      let highlightedIndex = -1;

      const minChars = 2;
      const debounceDelay = 200;
      input.setAttribute('role', 'combobox');
      input.setAttribute('aria-autocomplete', 'list');
      input.setAttribute('aria-haspopup', 'listbox');
      input.setAttribute('aria-expanded', 'false');

      function fetchResults(query) {
        query = (query || input.value || '').trim();
        if (query.length < minChars) {
          hideAutocomplete(input);
          return;
        }

        const requestId = ++activeRequest;
        const url = input.getAttribute('data-autocomplete-url');
        if (abortController) {
          abortController.abort();
        }
        abortController = new AbortController();
        fetch(url + '?q=' + encodeURIComponent(query), { signal: abortController.signal })
          .then(function (response) {
            if (!response.ok) throw new Error('Autocomplete request failed');
            return response.json();
          })
          .then(function (data) {
            if (requestId !== activeRequest || query !== input.value.trim()) return;
            renderAutocomplete(input, data);
          })
          .catch(function (err) {
            if (err && err.name === 'AbortError') return;
            // Fail silently and hide only if this is still the current query.
            if (requestId === activeRequest && query === input.value.trim()) {
              hideAutocomplete(input);
            }
          });
      }

      function renderAutocomplete(input, data) {
        const wrapper = input.parentElement;
        let listEl = wrapper ? wrapper.querySelector('.dh-autocomplete-list') : null;

        if (!listEl) {
          listEl = document.createElement('ul');
          listEl.className = 'dh-autocomplete-list';
          listEl.id = input.getAttribute('aria-controls') || 'dh-autocomplete-' + Math.random().toString(36).slice(2);
          listEl.setAttribute('role', 'listbox');
          input.setAttribute('aria-controls', listEl.id);
          if (wrapper) {
            wrapper.style.position = 'relative';
            wrapper.appendChild(listEl);
          } else {
            input.parentNode.appendChild(listEl);
          }
        }

        highlightedIndex = -1;
        listEl.innerHTML = '';

        if (!data || !data.results || data.results.length === 0) {
          listEl.style.display = 'none';
          input.setAttribute('aria-expanded', 'false');
          input.removeAttribute('aria-activedescendant');
          return;
        }

        listEl.style.display = 'block';
        input.setAttribute('aria-expanded', 'true');

        data.results.forEach(function (item, idx) {
          const li = document.createElement('li');
          li.setAttribute('role', 'option');
          li.setAttribute('aria-selected', 'false');
          li.id = listEl.id + '-option-' + idx;
          li.setAttribute('data-index', idx);
          li.tabIndex = -1;
          li.innerHTML = `<span class="dh-autocomplete-label">${escapeHtml(item.label || item.title || item.name || '')}</span>`;
          li.addEventListener('click', function () {
            selectAutocompleteItem(input, item);
          });
          listEl.appendChild(li);
        });
      }

      function selectAutocompleteItem(input, item) {
        const label = item.label || item.title || item.name || '';
        input.value = label;
        hideAutocomplete(input);

        if (item.url) {
          window.location.href = item.url;
          return;
        }

        if (input.form) {
          if (typeof input.form.requestSubmit === 'function') {
            input.form.requestSubmit();
          } else {
            input.form.submit();
          }
        }
      }

      function hideAutocomplete(inputEl) {
        const listEl = inputEl.parentElement
          ? inputEl.parentElement.querySelector('.dh-autocomplete-list')
          : null;
        if (abortController) {
          abortController.abort();
          abortController = null;
        }
        clearTimeout(debounceTimer);
        activeRequest += 1;
        if (listEl) {
          listEl.style.display = 'none';
        }
        inputEl.setAttribute('aria-expanded', 'false');
        inputEl.removeAttribute('aria-activedescendant');
      }

      function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
      }

      function updateHighlighted(items, index) {
        items.forEach(function (item, i) {
          const active = i === index;
          item.classList.toggle('highlighted', active);
          item.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        if (items[index]) {
          input.setAttribute('aria-activedescendant', items[index].id);
        } else {
          input.removeAttribute('aria-activedescendant');
        }
        if (items[index] && typeof items[index].scrollIntoView === 'function') {
          items[index].scrollIntoView({ block: 'nearest' });
        }
      }

      // Input event
      input.addEventListener('input', function () {
        highlightedIndex = -1;
        clearTimeout(debounceTimer);
        hideAutocomplete(input);
        if (input.value.trim().length < minChars) return;
        debounceTimer = setTimeout(function () {
          fetchResults(input.value);
        }, debounceDelay);
      });

      // Keyboard navigation
      input.addEventListener('keydown', function (e) {
        const listEl = input.parentElement
          ? input.parentElement.querySelector('.dh-autocomplete-list')
          : null;
        if (!listEl || listEl.style.display === 'none') return;

        const items = Array.from(listEl.querySelectorAll('li[role="option"]'));

        if (e.key === 'ArrowDown') {
          e.preventDefault();
          highlightedIndex = Math.min(highlightedIndex + 1, items.length - 1);
          updateHighlighted(items, highlightedIndex);
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          highlightedIndex = Math.max(highlightedIndex - 1, 0);
          updateHighlighted(items, highlightedIndex);
        } else if (e.key === 'Enter') {
          if (highlightedIndex >= 0 && items[highlightedIndex]) {
            e.preventDefault();
            selectAutocompleteItem(input, {
              label: items[highlightedIndex].textContent,
              url: null,
            });
          } else {
            hideAutocomplete(input);
          }
        } else if (e.key === 'Escape' || e.key === 'Tab') {
          hideAutocomplete(input);
        }
      });

      // Click outside hides autocomplete
      document.addEventListener('click', function (e) {
        if (e.target !== input && !input.parentNode.contains(e.target)) {
          hideAutocomplete(input);
        }
      });

      // Clear pending debounce when focus leaves
      input.addEventListener('blur', function () {
        clearTimeout(debounceTimer);
      });
    });
  }

  /* -------------------------------------------------
     Theme-color meta
     ------------------------------------------------- */
  function updateThemeColorMeta() {
    const html = document.documentElement;
    const theme = getComputedStyle(html).getPropertyValue('--tblr-body-bg');
    const dark = theme === '#0e1020' || theme === 'rgb(14, 16, 32)';
    const color = dark ? '#0e1020' : '#f3f4fb';
    let meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'theme-color';
      document.head.appendChild(meta);
    }
    meta.content = color;
  }

  /* Initialize on DOM ready */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initAutocomplete();
      updateThemeColorMeta();
      document.addEventListener('tabler:theme-change', updateThemeColorMeta);
    });
  } else {
    initAutocomplete();
    updateThemeColorMeta();
    document.addEventListener('tabler:theme-change', updateThemeColorMeta);
  }
})();
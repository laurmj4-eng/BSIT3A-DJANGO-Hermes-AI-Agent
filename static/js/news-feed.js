(function () {
  'use strict';

  const REFRESH_URL = (window.__NEWS_REFRESH_URL__) || null;
  // URLs are injected via data attributes on the container to avoid template in JS.
  // Fallback: read from script tag data attributes if present.
  function getCfg() {
    const el = document.getElementById('newsFeedConfig');
    if (!el) return {};
    const cd = parseInt(el.getAttribute('data-cooldown-seconds'), 10);
    const rem = parseInt(el.getAttribute('data-cooldown-remaining'), 10);
    return {
      refreshUrl: el.getAttribute('data-refresh-url'),
      saveUrlTemplate: el.getAttribute('data-save-url-template'),
      readUrlTemplate: el.getAttribute('data-read-url-template'),
      cooldownSeconds: isNaN(cd) ? 60 : cd,
      cooldownRemaining: isNaN(rem) ? 0 : rem,
    };
  }

  const cfg = getCfg();
  const REFRESH_URL_FINAL = cfg.refreshUrl || REFRESH_URL;
  const SAVE_URL_TEMPLATE = cfg.saveUrlTemplate || '';
  const READ_URL_TEMPLATE = cfg.readUrlTemplate || '';
  const COOLDOWN_SECONDS = Number(cfg.cooldownSeconds) || 60;
  const INITIAL_COOLDOWN = (cfg.cooldownRemaining != null) ? Number(cfg.cooldownRemaining) : 0;

  // ---------- Module state ----------
  let cooldownUntil = Date.now() + INITIAL_COOLDOWN * 1000;
  let refreshInFlight = false;
  let cooldownTimer = null;
  const originalHtml = new WeakMap();

  function csrf() {
    if (window.HermesUI && typeof window.HermesUI.csrfToken === 'function') {
      return window.HermesUI.csrfToken();
    }
    const m = document.cookie.match(/(^| )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[2]) : null;
  }

  function toast(message, kind) {
    if (window.HermesUI && typeof window.HermesUI.toast === 'function') {
      window.HermesUI.toast({ message: message, kind: kind || 'info' });
    }
  }

  // ---------- Share (Web Share API with clipboard fallback) ----------
  async function copyShareLink(url, btn) {
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        await navigator.clipboard.writeText(url);
      } else {
        const ta = document.createElement('textarea');
        ta.value = url;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.top = '-1000px';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
      }
      toast('Link copied to clipboard', 'success');
      return true;
    } catch (err) {
      toast('Could not copy link', 'danger');
      return false;
    }
  }

  async function handleShare(btn) {
    const url = btn.getAttribute('data-share-url');
    if (!url) return;
    const title = btn.getAttribute('data-share-title') || document.title;
    if (navigator.share) {
      try {
        await navigator.share({ title: title, url: url });
        toast('Shared', 'success');
      } catch (err) {
        if (err && err.name === 'AbortError') return;
        await copyShareLink(url, btn);
      }
      return;
    }
    await copyShareLink(url, btn);
  }

  // ---------- Keyboard shortcuts ----------
  function isTypingTarget(el) {
    if (!el) return false;
    const tag = el.tagName ? el.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
    if (el.isContentEditable) return true;
    if (el.closest && el.closest('[contenteditable="true"]')) return true;
    return false;
  }

  function feedCards() {
    return Array.prototype.slice.call(document.querySelectorAll('.feed-article'));
  }

  function focusedCardIndex(cards) {
    const active = document.activeElement;
    if (!active || !active.closest) return -1;
    const card = active.closest('.feed-article');
    return card ? cards.indexOf(card) : -1;
  }

  function focusCard(cards, index) {
    if (!cards.length) return;
    const i = Math.max(0, Math.min(cards.length - 1, index));
    const card = cards[i];
    if (!card.hasAttribute('tabindex')) card.setAttribute('tabindex', '-1');
    card.focus();
    if (typeof card.scrollIntoView === 'function') {
      card.scrollIntoView({ block: 'nearest' });
    }
  }

  let helpPanel = null;
  let helpReturnFocus = null;

  function buildHelpPanel() {
    const panel = document.createElement('div');
    panel.className = 'news-feed-help';
    panel.id = 'newsFeedHelp';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-label', 'Keyboard shortcuts');
    panel.hidden = true;
    panel.innerHTML =
      '<h2>Keyboard shortcuts</h2>' +
      '<dl>' +
      '<dt>j / k</dt><dd>Next / previous article</dd>' +
      '<dt>s</dt><dd>Save focused article</dd>' +
      '<dt>r</dt><dd>Mark focused article read</dd>' +
      '<dt>/</dt><dd>Focus search</dd>' +
      '<dt>?</dt><dd>Toggle this help</dd>' +
      '<dt>Esc</dt><dd>Close this help</dd>' +
      '</dl>' +
      '<button type="button" class="btn btn-sm btn-outline-secondary mt-2" data-help-close>Close</button>';
    panel.addEventListener('click', function (e) {
      if (e.target.closest('[data-help-close]')) {
        closeHelp();
      }
    });
    panel.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeHelp();
        return;
      }
      if (e.key !== 'Tab') return;
      const focusable = panel.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });
    document.body.appendChild(panel);
    return panel;
  }

  function closeHelp() {
    if (!helpPanel || helpPanel.hidden) return;
    helpPanel.hidden = true;
    if (helpReturnFocus && typeof helpReturnFocus.focus === 'function') {
      helpReturnFocus.focus();
    }
    helpReturnFocus = null;
  }

  function openHelp() {
    if (!helpPanel) helpPanel = buildHelpPanel();
    helpReturnFocus = document.activeElement;
    helpPanel.hidden = false;
    const target = helpPanel.querySelector('[data-help-close]');
    if (target) target.focus();
  }

  function toggleHelp() {
    if (!helpPanel) helpPanel = buildHelpPanel();
    if (helpPanel.hidden) {
      openHelp();
    } else {
      closeHelp();
    }
  }

  function onShortcutKey(e) {
    if (e.defaultPrevented) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (isTypingTarget(e.target)) return;

    const key = e.key;
    const cards = feedCards();
    const idx = focusedCardIndex(cards);

    if (key === 'j' || key === 'J') {
      e.preventDefault();
      focusCard(cards, idx < 0 ? 0 : idx + 1);
      return;
    }
    if (key === 'k' || key === 'K') {
      e.preventDefault();
      focusCard(cards, idx < 0 ? cards.length - 1 : idx - 1);
      return;
    }
    if (key === 's' || key === 'S') {
      const card = idx >= 0 ? cards[idx] : null;
      const saveBtn = card ? card.querySelector('[data-save-id]') : null;
      if (saveBtn) { e.preventDefault(); handleSave(saveBtn); }
      return;
    }
    if (key === 'r' || key === 'R') {
      const card = idx >= 0 ? cards[idx] : null;
      const readBtn = card ? card.querySelector('[data-read-id]') : null;
      if (readBtn) { e.preventDefault(); handleRead(readBtn); }
      return;
    }
    if (key === '/') {
      const search = document.getElementById('q');
      if (search) {
        e.preventDefault();
        search.focus();
        if (typeof search.select === 'function') search.select();
      }
      return;
    }
    if (key === '?') {
      e.preventDefault();
      toggleHelp();
      return;
    }
    if (key === 'Escape' && helpPanel && !helpPanel.hidden) {
      closeHelp();
    }
  }

  // ---------- Refresh ----------
  function captureOriginal(btn) {
    if (!originalHtml.has(btn)) {
      originalHtml.set(btn, {
        html: btn.innerHTML,
        title: btn.getAttribute('title'),
        ariaLabel: btn.getAttribute('aria-label'),
      });
    }
    return originalHtml.get(btn);
  }

  function syncRefreshUI() {
    const buttons = document.querySelectorAll('#refreshBtn, .refresh-trigger');
    const status = document.getElementById('refreshAlert');
    const now = Date.now();
    const remaining = Math.max(0, Math.ceil((cooldownUntil - now) / 1000));
    const cooling = remaining > 0;

    buttons.forEach(function (btn) {
      const orig = captureOriginal(btn);
      if (refreshInFlight) {
        btn.disabled = true;
        btn.setAttribute('aria-busy', 'true');
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1" aria-hidden="true"></i> Fetching...';
      } else if (cooling) {
        btn.disabled = true;
        btn.setAttribute('aria-busy', 'false');
        const label = 'Refresh available in ' + remaining + 's';
        btn.title = label;
        btn.setAttribute('aria-label', label);
        btn.innerHTML = orig.html;
      } else {
        btn.disabled = false;
        btn.removeAttribute('aria-busy');
        if (orig.title) btn.setAttribute('title', orig.title); else btn.removeAttribute('title');
        if (orig.ariaLabel) btn.setAttribute('aria-label', orig.ariaLabel); else btn.removeAttribute('aria-label');
        btn.innerHTML = orig.html;
      }
    });

    if (!cooling && cooldownTimer) {
      clearInterval(cooldownTimer);
      cooldownTimer = null;
    }

    if (!cooling && status && status.getAttribute('data-cooldown-message') === '1') {
      status.classList.add('d-none');
      status.removeAttribute('data-cooldown-message');
    }

    const container = document.getElementById('articlesContainer');
    if (container) {
      container.setAttribute('aria-busy', refreshInFlight ? 'true' : 'false');
    }
  }

  function startCooldown(seconds) {
    const s = (typeof seconds === 'number' && !isNaN(seconds)) ? seconds : COOLDOWN_SECONDS;
    cooldownUntil = Date.now() + s * 1000;
    if (cooldownTimer) { clearInterval(cooldownTimer); cooldownTimer = null; }
    syncRefreshUI();
    cooldownTimer = setInterval(syncRefreshUI, 1000);
  }

  async function doRefresh() {
    if (refreshInFlight) return;
    if (Date.now() < cooldownUntil) { syncRefreshUI(); return; }

    refreshInFlight = true;
    syncRefreshUI();

    const buttons = document.querySelectorAll('#refreshBtn, .refresh-trigger');
    const status = document.getElementById('refreshAlert');
    if (status) {
      status.className = 'alert alert-info mt-3';
      status.textContent = 'Refreshing news feeds…';
      status.classList.remove('d-none');
    }

    try {
      const resp = await fetch(REFRESH_URL_FINAL, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf() },
      });
      let data = {};
      try { data = await resp.json(); } catch (e) { data = {}; }
      if (resp.status === 429) {
        const seconds = Number(data.retry_after) || COOLDOWN_SECONDS;
        startCooldown(seconds);
        const toastMsg = data.error || ('Refresh is cooling down. Try again in ' + seconds + 's.');
        toast(toastMsg, 'warning');
        if (status) {
          status.className = 'alert alert-warning mt-3';
          status.textContent = toastMsg;
          status.classList.remove('d-none');
          status.setAttribute('data-cooldown-message', '1');
        }
        return;
      }
      if (!resp.ok) {
        const msg = data.error || 'Refresh failed.';
        toast(msg, 'danger');
        if (status) {
          status.className = 'alert alert-danger mt-3';
          status.textContent = msg;
          status.classList.remove('d-none');
        }
        return;
      }
      const failed = (data.errors && data.errors.length) || 0;
      let msg;
      if (failed) {
        const failedSources = data.errors
          .map(function (error) { return error.source || error.key; })
          .filter(Boolean);
        msg = data.created + ' new, ' + data.updated + ' existing. ' + failed +
          ' feed(s) failed' + (failedSources.length ? ': ' + failedSources.join(', ') : '.') +
          (failedSources.length ? '.' : '');
        toast(msg, 'warning');
      } else {
        msg = data.created + ' new article(s) added, ' + data.updated + ' already known.';
        toast(msg, 'success');
      }
      if (status) {
        status.className = 'alert alert-' + (failed ? 'warning' : 'success') + ' mt-3';
        status.textContent = msg;
        status.classList.remove('d-none');
      }
      startCooldown(COOLDOWN_SECONDS);
      try { window.sessionStorage.setItem('hermes:feed-toast', msg); } catch (e) {}
      setTimeout(function () { window.location.reload(); }, 1200);
    } catch (err) {
      const msg = 'Refresh failed. Please try again.';
      toast(msg, 'danger');
      if (status) {
        status.className = 'alert alert-danger mt-3';
        status.textContent = msg;
        status.classList.remove('d-none');
      }
    } finally {
      refreshInFlight = false;
      syncRefreshUI();
    }
  }

  function updateArticleBadge(card, state, enabled) {
    const meta = card.querySelector('.feed-article-meta');
    if (!meta) return;
    let badge = meta.querySelector('[data-article-state="' + state + '"]');
    if (!enabled) {
      if (badge) badge.remove();
      return;
    }
    if (badge) return;
    badge = document.createElement('span');
    badge.className = 'badge feed-badge feed-badge-' + state;
    badge.setAttribute('data-article-state', state);
    if (state === 'saved') {
      const icon = document.createElement('i');
      icon.className = 'fas fa-bookmark me-1';
      icon.setAttribute('aria-hidden', 'true');
      badge.appendChild(icon);
      badge.appendChild(document.createTextNode('Saved'));
    } else {
      badge.textContent = 'Read';
    }
    meta.appendChild(badge);
  }

  // ---------- Bookmark delegation ----------
  async function handleSave(btn) {
    const id = btn.getAttribute('data-save-id');
    if (!id) return;
    btn.disabled = true;
    try {
      const url = SAVE_URL_TEMPLATE.replace('/0/', '/' + id + '/');
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf() },
      });
      if (!resp.ok) throw new Error('save failed');
      const data = await resp.json();
      const saved = !!data.is_saved;
      btn.setAttribute('data-saved', saved ? '1' : '0');
      btn.setAttribute('aria-pressed', saved ? 'true' : 'false');
      const label = saved ? 'Remove bookmark' : 'Save for later';
      btn.setAttribute('aria-label', label);
      btn.title = label;
      const accessibleLabel = btn.querySelector('[data-action-label]');
      if (accessibleLabel) accessibleLabel.textContent = label;
      const icon = btn.querySelector('i');
      if (icon) icon.classList.toggle('text-yellow', saved);
      const card = btn.closest('.feed-article');
      if (card) {
        card.classList.toggle('is-saved', saved);
        updateArticleBadge(card, 'saved', saved);
      }
      const savedCount = document.getElementById('savedCount');
      if (savedCount && typeof data.saved_total === 'number') {
        savedCount.textContent = data.saved_total;
      }
      toast(saved ? 'Saved for later' : 'Bookmark removed', 'success');
    } catch (err) {
      toast('Could not update bookmark', 'danger');
    } finally {
      btn.disabled = false;
    }
  }

  // ---------- Read toggle delegation ----------
  async function handleRead(btn) {
    const id = btn.getAttribute('data-read-id');
    if (!id) return;
    btn.disabled = true;
    try {
      const url = READ_URL_TEMPLATE.replace('/0/', '/' + id + '/');
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf() },
      });
      if (!resp.ok) throw new Error('read failed');
      const data = await resp.json();
      const read = !!data.is_read;
      btn.setAttribute('data-read', read ? '1' : '0');
      btn.setAttribute('aria-pressed', read ? 'true' : 'false');
      const label = read ? 'Mark as unread' : 'Mark as read';
      btn.setAttribute('aria-label', label);
      btn.title = label;
      const accessibleLabel = btn.querySelector('[data-action-label]');
      if (accessibleLabel) accessibleLabel.textContent = label;
      const card = btn.closest('.feed-article');
      if (card) {
        card.classList.toggle('is-read', read);
        updateArticleBadge(card, 'read', read);
      }
      const readCount = document.getElementById('readCount');
      if (readCount && typeof data.read_total === 'number') {
        readCount.textContent = data.read_total;
      }
      toast(read ? 'Marked as read' : 'Marked as unread', 'info');
    } catch (err) {
      toast('Could not update read state', 'danger');
    } finally {
      btn.disabled = false;
    }
  }

  // ---------- Relative times ----------
  function updateRelativeTimes() {
    let rtf;
    try { rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' }); }
    catch (e) { return; }
    const now = Date.now();
    document.querySelectorAll('[data-relative]').forEach(function (el) {
      const dt = el.getAttribute('datetime');
      if (!dt) return;
      const then = new Date(dt).getTime();
      if (isNaN(then)) return;
      const diffSec = Math.round((then - now) / 1000);
      const abs = Math.abs(diffSec);
      let value, unit;
      if (abs < 60) { value = diffSec; unit = 'second'; }
      else if (abs < 3600) { value = Math.round(diffSec / 60); unit = 'minute'; }
      else if (abs < 86400) { value = Math.round(diffSec / 3600); unit = 'hour'; }
      else if (abs < 2592000) { value = Math.round(diffSec / 86400); unit = 'day'; }
      else if (abs < 31536000) { value = Math.round(diffSec / 2592000); unit = 'month'; }
      else { value = Math.round(diffSec / 31536000); unit = 'year'; }
      try { el.textContent = rtf.format(value, unit); } catch (e) {}
      el.title = new Date(dt).toLocaleString();
    });
  }

  // ---------- View toggle ----------
  function applyView(view) {
    const container = document.getElementById('articlesContainer');
    if (!container) return;
    const v = view === 'grid' ? 'grid' : 'list';
    container.classList.remove('feed-view-list', 'feed-view-grid');
    container.classList.add('feed-view-' + v);
    document.querySelectorAll('[data-view]').forEach(function (btn) {
      const active = btn.getAttribute('data-view') === v;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    try { localStorage.setItem('hermes-feed-view', v); } catch (e) {}
  }

  // ---------- Offline saved reading list ----------
  const SAVED_KEY = 'hermes_saved_articles_v1';
  const SAVED_MAX = 200;

  function readSavedArticles() {
    try {
      const raw = localStorage.getItem(SAVED_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(parsed)) return [];
      const out = [];
      const seen = Object.create(null);
      for (let i = 0; i < parsed.length && out.length < SAVED_MAX; i++) {
        const entry = parsed[i];
        if (!entry || typeof entry.id === 'undefined') continue;
        const id = String(entry.id);
        if (seen[id]) continue;
        seen[id] = true;
        out.push({ id: id, title: entry.title || '', url: entry.url || '', ts: entry.ts || 0 });
      }
      return out;
    } catch (e) {
      return [];
    }
  }

  function writeSavedArticles(entries) {
    try {
      localStorage.setItem(SAVED_KEY, JSON.stringify(entries.slice(0, SAVED_MAX)));
    } catch (e) {}
  }

  function syncSavedArticles() {
    const cards = document.querySelectorAll('[data-article-id]');
    const savedOnPage = new Map();
    const pageIds = new Set();
    cards.forEach(function (card) {
      const id = card.getAttribute('data-article-id');
      if (!id) return;
      const key = String(id);
      pageIds.add(key);
      if (card.getAttribute('data-saved') !== '1') return;
      savedOnPage.set(key, {
        id: key,
        title: card.getAttribute('data-article-title') || '',
        url: card.getAttribute('data-article-url') || '',
      });
    });
    const existing = readSavedArticles();
    const merged = [];
    const seen = new Set();
    savedOnPage.forEach(function (entry) {
      const prev = existing.find(function (e) { return String(e.id) === entry.id; }) || {};
      merged.push({
        id: entry.id,
        title: entry.title || prev.title || '',
        url: entry.url || prev.url || '',
        ts: prev.ts || Date.now(),
      });
      seen.add(entry.id);
    });
    existing.forEach(function (e) {
      const id = String(e.id);
      if (!pageIds.has(id) && !seen.has(id)) {
        merged.push(e);
        seen.add(id);
      }
    });
    writeSavedArticles(merged);
  }

  // ---------- Init ----------
  function init() {
    syncSavedArticles();
    try {
      const storedToast = window.sessionStorage.getItem('hermes:feed-toast');
      if (storedToast) {
        window.sessionStorage.removeItem('hermes:feed-toast');
        toast(storedToast, 'success');
      }
    } catch (e) {}
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) refreshBtn.addEventListener('click', doRefresh);
    document.querySelectorAll('.refresh-trigger').forEach(function (b) {
      b.addEventListener('click', doRefresh);
    });

    document.querySelectorAll('#refreshBtn, .refresh-trigger').forEach(function (btn) {
      captureOriginal(btn);
    });

    syncRefreshUI();
    if (Date.now() < cooldownUntil && !cooldownTimer) {
      cooldownTimer = setInterval(syncRefreshUI, 1000);
    }

    // Delegated clicks
    document.addEventListener('click', function (e) {
      const shareBtn = e.target.closest('[data-share-url]');
      if (shareBtn) { e.preventDefault(); e.stopPropagation(); handleShare(shareBtn); return; }
      const saveBtn = e.target.closest('[data-save-id]');
      if (saveBtn) { e.preventDefault(); handleSave(saveBtn); return; }
      const readBtn = e.target.closest('[data-read-id]');
      if (readBtn) { e.preventDefault(); handleRead(readBtn); return; }
    });

    // Keyboard shortcuts (ignored while typing in a field)
    document.addEventListener('keydown', onShortcutKey);

    // Label the share control for browsers without the Web Share API.
    if (!navigator.share) {
      document.querySelectorAll('[data-share-label]').forEach(function (el) {
        el.textContent = 'Copy link';
      });
      document.querySelectorAll('.feed-share-btn').forEach(function (btn) {
        if (btn.querySelector('[data-share-label]')) return;
        btn.setAttribute('aria-label', 'Copy link');
        btn.setAttribute('title', 'Copy link');
      });
    }

    updateRelativeTimes();
    setInterval(updateRelativeTimes, 60000);

    let initialView = 'list';
    try { initialView = localStorage.getItem('hermes-feed-view') || 'list'; } catch (e) {}
    applyView(initialView);
    document.querySelectorAll('[data-view]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        applyView(btn.getAttribute('data-view'));
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

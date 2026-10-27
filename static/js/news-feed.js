(function () {
  'use strict';

  const REFRESH_URL = (window.__NEWS_REFRESH_URL__) || null;
  // URLs are injected via data attributes on the container to avoid template in JS.
  // Fallback: read from script tag data attributes if present.
  function getCfg() {
    const el = document.getElementById('newsFeedConfig');
    if (!el) return {};
    return {
      refreshUrl: el.getAttribute('data-refresh-url'),
      saveUrlTemplate: el.getAttribute('data-save-url-template'),
      readUrlTemplate: el.getAttribute('data-read-url-template'),
    };
  }

  const cfg = getCfg();
  const REFRESH_URL_FINAL = cfg.refreshUrl || REFRESH_URL;
  const SAVE_URL_TEMPLATE = cfg.saveUrlTemplate || '';
  const READ_URL_TEMPLATE = cfg.readUrlTemplate || '';

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

  // ---------- Refresh ----------
  async function doRefresh() {
    const buttons = document.querySelectorAll('#refreshBtn, .refresh-trigger');
    const originals = [];
    buttons.forEach(function (btn) {
      originals.push(btn.innerHTML);
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1" aria-hidden="true"></i> Fetching...';
    });
    const status = document.getElementById('refreshAlert');
    try {
      const resp = await fetch(REFRESH_URL_FINAL, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf() },
      });
      let data = {};
      try { data = await resp.json(); } catch (e) { data = {}; }
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
        msg = data.created + ' new, ' + data.updated + ' existing. ' + failed + ' feed(s) failed.';
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
      buttons.forEach(function (btn, i) {
        btn.disabled = false;
        btn.innerHTML = originals[i];
      });
    }
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
      btn.title = saved ? 'Remove bookmark' : 'Save for later';
      const icon = btn.querySelector('i');
      if (icon) icon.classList.toggle('text-yellow', saved);
      const card = btn.closest('.feed-article');
      if (card) card.classList.toggle('is-saved', saved);
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
      btn.title = read ? 'Mark as unread' : 'Mark as read';
      const card = btn.closest('.feed-article');
      if (card) card.classList.toggle('is-read', read);
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

  // ---------- Init ----------
  function init() {
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) refreshBtn.addEventListener('click', doRefresh);
    document.querySelectorAll('.refresh-trigger').forEach(function (b) {
      b.addEventListener('click', doRefresh);
    });

    // Delegated clicks
    document.addEventListener('click', function (e) {
      const saveBtn = e.target.closest('[data-save-id]');
      if (saveBtn) { e.preventDefault(); handleSave(saveBtn); return; }
      const readBtn = e.target.closest('[data-read-id]');
      if (readBtn) { e.preventDefault(); handleRead(readBtn); return; }
    });

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

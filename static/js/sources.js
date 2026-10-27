(function () {
  "use strict";

  function getCsrfToken() {
    const hui = window.HermesUI?.csrfToken?.();
    if (typeof hui === "string" && hui.length) return hui;
    const match = document.cookie.match(/(?:^| )csrftoken=([^;]+)/);
    return match ? match[1] : null;
  }

  const refreshBtn = document.getElementById("refreshSourcesBtn");
  if (!refreshBtn) return;

  const refreshUrl = refreshBtn.getAttribute("data-refresh-url");
  if (!refreshUrl) return;

  const originalLabel = refreshBtn.innerHTML;

  refreshBtn.addEventListener("click", function () {
    const btn = this;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span> Refreshing\u2026';

    fetch(refreshUrl, {
      method: "POST",
      headers: { "X-CSRFToken": getCsrfToken() },
    })
      .then((resp) => {
        return resp
          .json()
          .catch(() => ({}))
          .then((data) => ({ ok: resp.ok, status: resp.status, data }));
      })
      .then((result) => {
        const data = result.data || {};

        if (result.ok && (data.status === "success" || data.status === "partial")) {
          const parts = [];
          parts.push((data.created || 0) + " new");
          parts.push((data.updated || 0) + " updated");
          if (data.errors && data.errors.length) {
            parts.push(data.errors.length + " feed(s) with errors");
          }
          const kind = data.status === "partial" ? "warning" : "success";
          const title = data.status === "partial" ? "Refresh completed with warnings" : "Feeds updated";
          showAlert(kind, title, parts.join(", ") + ".");
          setTimeout(() => window.location.reload(), 1200);
          return;
        }

        const message = data.error || data.detail || "Refresh failed. Please try again.";
        showAlert("danger", "Refresh failed", message);
      })
      .catch((err) => {
        showAlert("danger", "Refresh failed", err.message || "Network error");
      })
      .finally(() => {
        btn.disabled = false;
        btn.innerHTML = originalLabel;
      });
  });

  function showAlert(kind, title, msg) {
    let alert = document.querySelector('.alert[data-testid="refresh-alert"]');

    if (!alert) {
      alert = document.createElement("div");
      alert.setAttribute("data-testid", "refresh-alert");
      document.querySelector(".page-body")?.prepend(alert);
    }

    alert.className = "alert alert-" + kind + " alert-dismissible fade show";
    alert.setAttribute("role", "alert");
    alert.innerHTML = "";

    const heading = document.createElement("h4");
    heading.className = "alert-heading";
    heading.textContent = title;

    const description = document.createElement("div");
    description.className = "alert-description";
    description.textContent = msg;

    const close = document.createElement("button");
    close.type = "button";
    close.className = "btn-close";
    close.setAttribute("data-bs-dismiss", "alert");
    close.setAttribute("aria-label", "Close");

    alert.append(heading, description, close);
  }
})();

/* Scroll-driven reveal for below-the-fold blocks.
   Content already in view is never hidden, so first paint and LCP stay intact. */
(function () {
  if (!('IntersectionObserver' in window)) { return; }
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) { return; }

  function init() {
    // Wait one frame so webfonts/canvas layout has settled before measuring.
    window.requestAnimationFrame(function () {
      var nodes = Array.prototype.slice.call(document.querySelectorAll('[data-reveal]'));
      if (!nodes.length) { return; }

      var viewport = window.innerHeight || document.documentElement.clientHeight || 0;
      var targets = nodes.filter(function (el) {
        var rect = el.getBoundingClientRect();
        return rect.height > 0 && rect.top > viewport * 0.88;
      });
      if (!targets.length) { return; }

      targets.forEach(function (el) {
        el.classList.add('reveal-armed');
      });

      var pending = targets.slice();
      var delay = 0;

      function reveal(el) {
        var wait = delay;
        if (wait > 0) { el.style.animationDelay = wait + 'ms'; }
        el.classList.add('is-revealed');
        delay = Math.min(delay + 70, 210);
        var idx = pending.indexOf(el);
        if (idx !== -1) { pending.splice(idx, 1); }
        observer.unobserve(el);
        // Lock the final state shortly after the animation window so a
        // throttled compositor can never leave the block invisible.
        window.setTimeout(function () {
          el.classList.remove('reveal-armed', 'is-revealed');
          el.classList.add('reveal-done');
          el.style.animationDelay = '';
        }, 900 + wait);
      }

      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) { reveal(entry.target); }
        });
      }, { rootMargin: '0px 0px -6% 0px', threshold: 0.1 });

      targets.forEach(function (el) {
        observer.observe(el);
      });

      // Fallback: some embedded/headless engines deliver IntersectionObserver
      // callbacks late. A scroll pass keeps content from staying hidden.
      var ticking = false;
      function revealInView() {
        ticking = false;
        var vh = window.innerHeight || document.documentElement.clientHeight || 0;
        pending.slice().forEach(function (el) {
          var rect = el.getBoundingClientRect();
          if (rect.top < vh * 0.94 && rect.bottom > 0) { reveal(el); }
        });
      }
      window.addEventListener('scroll', function () {
        if (ticking) { return; }
        ticking = true;
        window.requestAnimationFrame(revealInView);
      }, { passive: true });
      revealInView();
    });
  }

  if (document.readyState === 'complete') {
    init();
  } else {
    window.addEventListener('load', init, { once: true });
  }
})();

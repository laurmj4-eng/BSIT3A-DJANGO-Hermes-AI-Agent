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

      var observer = new IntersectionObserver(function (entries) {
        var delay = 0;
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) { return; }
          var el = entry.target;
          if (delay > 0) { el.style.animationDelay = delay + 'ms'; }
          el.classList.add('is-revealed');
          observer.unobserve(el);
          delay += 70;
        });
      }, { rootMargin: '0px 0px -6% 0px', threshold: 0.1 });

      targets.forEach(function (el) {
        observer.observe(el);
      });
    });
  }

  if (document.readyState === 'complete') {
    init();
  } else {
    window.addEventListener('load', init, { once: true });
  }
})();

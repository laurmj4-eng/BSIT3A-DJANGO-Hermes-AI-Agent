/* Hermes Agent live orbit — dependency-free Canvas 2D animation.
 * Dotted sphere + marching dashed orbit rings + travelling comets +
 * flowing side streams + HTML pill labels that swing front/behind.
 * No CDN, no WebGL: runs everywhere canvas runs.
 * Expects window.HERMES_MODELS = [{key,label,query,color,total}].
 */
(function () {
  var canvas = document.getElementById('model-orbit');
  if (!canvas) return;
  var wrap = document.getElementById('orbit-wrap');
  var labelLayer = document.getElementById('orbit-labels');
  var fallback = document.getElementById('orbit-fallback');
  var tooltip = document.getElementById('orbit-tip');
  var models = (window.HERMES_MODELS || []).slice(0, 6);
  var reduceMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  // Live by default; if the OS asks for reduced motion we start paused
  // but the user can force it on with the Pause/Play motion button.
  var motionOn = !reduceMotion;

  function showFallback() {
    if (fallback) fallback.classList.remove('d-none');
    if (labelLayer) labelLayer.style.display = 'none';
    canvas.classList.add('d-none');
  }
  if (!models.length || !labelLayer) { showFallback(); return; }
  var ctx = canvas.getContext('2d');
  if (!ctx) { showFallback(); return; }

  var DPR = Math.min(window.devicePixelRatio || 1, 2);
  var W = 600, H = 380, CX = 300, CY = 190, R = 100;

  function resize() {
    W = Math.max(280, wrap.clientWidth || 560);
    H = window.innerWidth < 992 ? 300 : 380;
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(W * DPR);
    canvas.height = Math.round(H * DPR);
    canvas.style.height = H + 'px';
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    CX = W / 2; CY = H / 2;
    R = Math.max(62, Math.min(W, H) * 0.27);
  }
  window.addEventListener('resize', resize);
  resize();

  // Even dot distribution on the unit sphere (fibonacci).
  var DOTS = 850;
  var sx = new Float32Array(DOTS), sy = new Float32Array(DOTS), sz = new Float32Array(DOTS);
  var GA = Math.PI * (3 - Math.sqrt(5));
  for (var i = 0; i < DOTS; i++) {
    var y = 1 - (i / (DOTS - 1)) * 2;
    var rad = Math.sqrt(Math.max(0, 1 - y * y));
    var th = GA * i;
    sx[i] = Math.cos(th) * rad;
    sy[i] = y;
    sz[i] = Math.sin(th) * rad;
  }

  // Orbit rings (rx, ry, tilt, dash speed) + one comet each.
  var rings = [
    { rx: 0, ry: 0, tilt: -0.16, dash: 26, off: 0, comet: 0.0, speed: 0.55 },
    { rx: 0, ry: 0, tilt: 0.14, dash: -20, off: 0, comet: 2.1, speed: 0.42 },
    { rx: 0, ry: 0, tilt: 0.34, dash: 16, off: 0, comet: 4.2, speed: 0.32 }
  ];
  function layoutRings() {
    rings[0].rx = R * 1.45; rings[0].ry = R * 0.52;
    rings[1].rx = R * 1.8;  rings[1].ry = R * 0.62;
    rings[2].rx = R * 2.2;  rings[2].ry = R * 0.72;
  }

  // Each model rides a ring with its own phase + speed.
  var nodes = models.map(function (m, idx) {
    var ring = rings[idx % rings.length];
    return {
      model: m, ring: ring,
      angle: (idx / models.length) * Math.PI * 2,
      speed: 0.34 + (idx % 3) * 0.09,
      x: 0, y: 0, front: true
    };
  });

  // Labels (crisp HTML pills, always clickable).
  nodes.forEach(function (n) {
    var el = document.createElement('a');
    el.className = 'orbit-label';
    el.href = '/news/?q=' + encodeURIComponent(n.model.query);
    el.style.borderColor = n.model.color || '#67e8f9';
    el.innerHTML = '<span class="orbit-pip" style="background:' +
      n.model.color + ';color:' + n.model.color + '"></span>' +
      '<span>' + n.model.label + '</span>';
    el.addEventListener('pointerenter', function () {
      if (tooltip) {
        tooltip.textContent = n.model.label + ' — ' + n.model.total + ' articles. Click to filter.';
        tooltip.classList.remove('d-none');
      }
    });
    el.addEventListener('pointerleave', function () {
      if (tooltip) tooltip.classList.add('d-none');
    });
    labelLayer.appendChild(el);
    n.el = el;
  });

  // Flowing side streams.
  var streams = [
    { side: -1, seeds: [] },
    { side: 1, seeds: [] }
  ];
  streams.forEach(function (s) {
    for (var k = 0; k < 42; k++) {
      s.seeds.push({ t: k / 42, lane: (k % 3 - 1) * R * 0.12, wob: Math.random() * 6.28 });
    }
  });

  // Drag to spin faster.
  var rotY = 0, vel = 0, dragging = false, px = 0;
  canvas.style.cursor = 'grab';
  canvas.style.touchAction = 'pan-y';
  canvas.addEventListener('pointerdown', function (ev) { dragging = true; px = ev.clientX; canvas.style.cursor = 'grabbing'; });
  window.addEventListener('pointerup', function () { dragging = false; canvas.style.cursor = 'grab'; });
  window.addEventListener('pointermove', function (ev) {
    if (!dragging) return;
    vel = (ev.clientX - px) * 0.006;
    px = ev.clientX;
  });
  // Tap a dot on touch / mouse.
  canvas.addEventListener('click', function (ev) {
    var r = canvas.getBoundingClientRect();
    var mx = ev.clientX - r.left, my = ev.clientY - r.top;
    var best = null, bd = 28 * 28;
    nodes.forEach(function (n) {
      var dx = n.x - mx, dy = n.y - my, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = n; }
    });
    if (best) window.location.href = '/news/?q=' + encodeURIComponent(best.model.query);
  });

  function ringXY(ring, a) {
    var x = Math.cos(a) * ring.rx;
    var y = Math.sin(a) * ring.ry;
    var c = Math.cos(ring.tilt), s = Math.sin(ring.tilt);
    return [CX + x * c - y * s, CY + x * s + y * c];
  }

  function drawBody() {
    var g = ctx.createRadialGradient(CX - R * 0.35, CY - R * 0.4, R * 0.1, CX, CY, R);
    g.addColorStop(0, '#16394a');
    g.addColorStop(0.45, '#0a212d');
    g.addColorStop(1, '#040b12');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(CX, CY, R, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawHalo() {
    ctx.save();
    ctx.strokeStyle = 'rgba(255,255,255,0.85)';
    ctx.lineWidth = Math.max(6, R * 0.09);
    ctx.shadowColor = 'rgba(255,255,255,0.9)';
    ctx.shadowBlur = 28;
    ctx.beginPath();
    ctx.arc(CX, CY, R * 1.22, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  function drawAxis() {
    ctx.save();
    ctx.strokeStyle = 'rgba(103,232,249,0.85)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(CX, CY - R * 1.72);
    ctx.lineTo(CX, CY + R * 1.72);
    ctx.stroke();
    ctx.restore();
  }

  function drawDots(time) {
    var cosY = Math.cos(rotY), sinY = Math.sin(rotY);
    for (var i = 0; i < DOTS; i++) {
      var x = sx[i] * cosY + sz[i] * sinY;
      var z = -sx[i] * sinY + sz[i] * cosY;
      var depth = (z + 1) / 2; // 0 back, 1 front
      var a = 0.10 + depth * 0.75;
      var s = 0.5 + depth * 1.25;
      ctx.fillStyle = depth > 0.5
        ? 'rgba(165,243,252,' + a.toFixed(3) + ')'
        : 'rgba(80,160,190,' + a.toFixed(3) + ')';
      ctx.beginPath();
      ctx.arc(CX + x * R, CY + sy[i] * R, s, 0, Math.PI * 2);
      ctx.fill();
    }
    void time;
  }

  function drawRings(dt) {
    rings.forEach(function (rg) {
      rg.off += rg.dash * dt;
      ctx.save();
      ctx.translate(CX, CY);
      ctx.rotate(rg.tilt);
      ctx.strokeStyle = 'rgba(103,232,249,0.55)';
      ctx.lineWidth = 1.6;
      ctx.setLineDash([5, 7]);
      ctx.lineDashOffset = rg.off;
      ctx.beginPath();
      ctx.ellipse(0, 0, rg.rx, rg.ry, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    });
    ctx.setLineDash([]);
  }

  function drawComets() {
    rings.forEach(function (rg) {
      for (var k = 0; k < 10; k++) {
        var a = rg.comet - k * 0.055;
        var p = ringXY(rg, a);
        var fade = 1 - k / 10;
        ctx.fillStyle = 'rgba(165,243,252,' + (fade * 0.9).toFixed(3) + ')';
        ctx.beginPath();
        ctx.arc(p[0], p[1], 3.4 * fade + 0.8, 0, Math.PI * 2);
        ctx.fill();
      }
    });
  }

  function drawNodes(dt) {
    nodes.forEach(function (n) {
      n.angle += n.speed * dt * (1 + Math.abs(vel) * 6);
      var p = ringXY(n.ring, n.angle);
      n.x = p[0]; n.y = p[1];
      n.front = Math.sin(n.angle) > -0.15;
      var scale = n.front ? 1 : 0.72;
      ctx.save();
      ctx.shadowColor = n.model.color;
      ctx.shadowBlur = 14;
      ctx.fillStyle = n.model.color;
      ctx.beginPath();
      ctx.arc(p[0], p[1], 6 * scale, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
      ctx.fillStyle = 'rgba(255,255,255,0.9)';
      ctx.beginPath();
      ctx.arc(p[0], p[1], 2 * scale, 0, Math.PI * 2);
      ctx.fill();

      n.el.style.transform = 'translate(' + Math.round(p[0] + 12) + 'px,' + Math.round(p[1] - 32) + 'px)';
      n.el.classList.toggle('is-behind', !n.front);
      n.el.classList.toggle('is-front', n.front);
      n.el.style.zIndex = n.front ? '3' : '1';
    });
  }

  function drawStreams(dt, time) {
    var spread = R * 2.1;
    streams.forEach(function (s) {
      s.seeds.forEach(function (sd) {
        sd.t += dt * 0.22;
        if (sd.t > 1) sd.t -= 1;
        var x = CX + s.side * (R * 1.5 + sd.t * spread);
        var y = CY + Math.sin(sd.t * 8 + sd.wob + time * 1.6) * R * 0.42 * (1 - sd.t * 0.3) + sd.lane;
        var a = (1 - sd.t) * 0.75;
        ctx.fillStyle = 'rgba(125,239,251,' + a.toFixed(3) + ')';
        ctx.beginPath();
        ctx.arc(x, y, 1.6, 0, Math.PI * 2);
        ctx.fill();
      });
    });
  }

  var last = performance.now();
  function frame(now) {
    requestAnimationFrame(frame);
    var dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    var time = now / 1000;

    layoutRings();
    ctx.clearRect(0, 0, W, H);

    if (motionOn) {
      rotY += dt * (0.55 + vel * 4);
      vel *= 0.94;
      rings.forEach(function (rg) { rg.comet += dt * rg.speed; });
    }

    drawHalo();
    drawBody();
    drawAxis();
    drawDots(time);
    drawRings(motionOn ? dt : 0);
    if (motionOn) drawComets();
    drawNodes(motionOn ? dt : 0);
    if (motionOn) drawStreams(dt, time);
  }

  var motionBtn = document.getElementById('orbit-motion');
  function paintBtn() {
    if (!motionBtn) return;
    motionBtn.innerHTML = motionOn
      ? '<i class="fas fa-pause me-1"></i> Pause motion'
      : '<i class="fas fa-play me-1"></i> Play motion';
  }
  paintBtn();
  if (motionBtn) {
    motionBtn.addEventListener('click', function () {
      motionOn = !motionOn;
      last = performance.now();
      paintBtn();
    });
  }

  requestAnimationFrame(frame);
})();

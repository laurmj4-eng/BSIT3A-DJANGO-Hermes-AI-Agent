/* Hermes cosmic hero — dependency-free live galaxy.
 *
 * A single fragment shader draws a tilted spiral galaxy: a warm bulge,
 * blue-white spiral arms, dust lanes, HII knots, a deep-space star field,
 * twinkling stars, diffraction-spike foreground stars, cosmic web filaments,
 * and occasional meteors. HTML pills float over the galactic plane and
 * link to the matching news filter.
 *
 * v6 — Photorealistic Hubble/JWST aesthetic matching reference image:
 * - High-definition logarithmic spiral arms with graceful curving arcs
 * - Photorealistic golden-amber core with blazing white nucleus
 * - Intricate dark dust lanes silhouetting inner arms
 * - Soft glowing pink/magenta HII emission nebulae & cyan star clusters
 * - Prominent 4-point diffraction spike foreground stars
 * - Smooth Gaussian-profile star field with realistic scintillation
 * - Subtle cosmic web filaments woven through deep space
 * - Interactive 3D yaw, pitch tilt, zoom, and mouse parallax
 *
 * Expects window.HERMES_MODELS = [{key,label,query,color,total}].
 */
(function () {
  'use strict';

  var scene = document.getElementById('cosmos-hero');
  var canvas = document.getElementById('cosmos-canvas');
  if (!scene || !canvas) return;

  var wrap = document.getElementById('orbit-wrap');
  var labelLayer = document.getElementById('orbit-labels');
  var fallback = document.getElementById('orbit-fallback');
  var tooltip = document.getElementById('orbit-tip');
  var motionBtn = document.getElementById('orbit-motion');
  var liveState = document.getElementById('cosmos-live-state');

  var speedInput = document.getElementById('orbit-speed');
  var zoomInBtn = document.getElementById('orbit-zoom-in');
  var zoomOutBtn = document.getElementById('orbit-zoom-out');
  var resetBtn = document.getElementById('orbit-reset');
  var fullscreenBtn = document.getElementById('orbit-fullscreen');
  var cosmosHint = document.getElementById('cosmos-hint');

  var models = (window.HERMES_MODELS || []).slice(0, 7);
  var motionQuery = window.matchMedia
    ? window.matchMedia('(prefers-reduced-motion: reduce)')
    : null;
  var reduceMotion = motionQuery ? motionQuery.matches : false;
  var speed = reduceMotion ? 0 : 1;
  var lastSpeed = 1;
  var labelsVisible = models.length > 0;
  var view = {
    yaw: 0,
    tilt: 0.62,
    targetTilt: 0.62,
    zoom: 1,
    targetZoom: 1,
    dragging: false
  };

  var gl = null;
  var program = null;
  var uniforms = null;
  var nodes = [];
  var hoveredNode = null;
  var labelHold = 0;
  var labelYawHold = 0;
  var visible = true;
  var DPR = 1;
  var sceneScale = 1;
  var elapsed = 0;
  var last = performance.now();
  var pointer = { x: 0, y: 0, tx: 0, ty: 0 };
  var resizeTimer = 0;
  var resizeObserver = null;
  var intersectionObserver = null;
  var rafId = 0;
  var running = false;
  var frameInterval = 1000 / 30;
  var lastDraw = 0;
  var settleFrames = 0;
  var pixelBudget = 1100000;
  var renderScale = 0.9;
  var slowFrames = 0;
  var qualityStage = 0;
  var sceneRect = null;
  var wrapW = 0;
  var wrapH = 0;
  var rectTick = 0;

  var VERTEX_SRC = [
    'attribute vec2 a_position;',
    'void main() {',
    '  gl_Position = vec4(a_position, 0.0, 1.0);',
    '}'
  ].join('\n');

  var FRAGMENT_SRC = `
precision highp float;

uniform vec2 u_res;
uniform vec2 u_center;
uniform vec2 u_pointer;
uniform float u_time;
uniform float u_scale;
uniform float u_yaw;
uniform float u_tilt;
uniform float u_zoom;

/* ===== Fast PRNG / Hash / Value Noise ===== */

float hash21(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

vec3 hash23(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
  p3 += dot(p3, p3.yxz + 33.33);
  return fract((p3.xxy + p3.yzz) * p3.zyx);
}

float valueNoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float a = hash21(i);
  float b = hash21(i + vec2(1.0, 0.0));
  float c = hash21(i + vec2(0.0, 1.0));
  float d = hash21(i + vec2(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 turn = mat2(0.86, 0.5, -0.5, 0.86);
  for (int i = 0; i < 5; i++) {
    v += a * valueNoise(p);
    p = turn * p * 2.02;
    a *= 0.49;
  }
  return v;
}

float fbm3(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 turn = mat2(0.8, 0.6, -0.6, 0.8);
  for (int i = 0; i < 3; i++) {
    v += a * valueNoise(p);
    p = turn * p * 2.08;
    a *= 0.5;
  }
  return v;
}

mat2 rotate2d(float a) {
  float c = cos(a);
  float s = sin(a);
  return mat2(c, -s, s, c);
}

/* Approximate blackbody color (Tanner Helland), clamped to display range. */
vec3 blackbody(float kelvin) {
  float t = clamp(kelvin, 1000.0, 40000.0) / 100.0;
  float r;
  float g;
  float b;
  if (t <= 66.0) {
    r = 255.0;
    g = 99.4708025861 * log(max(t, 10.0)) - 161.1195681661;
    b = 138.5177312231 * log(max(t - 10.0, 1.0)) - 305.0447927307;
  } else {
    r = 329.698727446 * pow(t - 60.0, -0.1332047592);
    g = 288.1221695283 * pow(t - 60.0, -0.0755148492);
    b = 255.0;
  }
  return clamp(vec3(r, g, b) / 255.0, 0.0, 1.0);
}

/* ===== Optical Point Spread Function (PSF) Star Generator ===== */

/* Generates crisp, razor-sharp pinpoint stars with optical Airy halos */
vec3 starFieldLayer(vec2 uv, float cells, float threshold, float seed, float twinkle) {
  vec2 sp = uv * cells;
  vec2 id = floor(sp);
  vec2 f = fract(sp) - 0.5;
  float h = hash21(id + seed);
  if (h < threshold) return vec3(0.0);

  vec2 off = vec2(hash21(id + seed + 13.7), hash21(id + seed + 71.3)) - 0.5;
  float d = length(f - off * 0.72);

  /* Optical PSF: razor-sharp nucleus + luminous Airy disc halo */
  float core = exp(-d * d * 2200.0);
  float halo = exp(-d * 24.0) * 0.35;
  float star = core * 3.2 + halo;

  /* Randomized magnitude / brightness */
  float mag = pow(hash21(id + seed + 47.0), 2.8) * 3.0 + 0.4;
  float tw = 0.70 + 0.30 * sin(twinkle + h * 137.0);

  /* Blackbody stellar colors: O/B, A, G, K/M populations. */
  vec3 rnd = hash23(id + seed + 91.0);
  vec3 col = blackbody(mix(3200.0, 18000.0, rnd.x));
  col = mix(col, blackbody(2600.0), step(0.86, rnd.y) * 0.45);
  col = mix(col, blackbody(22000.0), step(0.80, rnd.z) * 0.40);

  return col * star * mag * tw;
}

/* Foreground Telescope Star with 4-Point Diffraction Cross Spikes and Chromatic Flare */
vec3 diffractionStar(vec2 uv, vec2 center, float size, vec3 color, float twinkle) {
  vec2 d = uv - center;
  float dist = length(d);
  if (dist > size * 4.8) return vec3(0.0);

  /* Blistering white-hot nucleus */
  float nucleus = exp(-dist * dist / (size * size * 0.012)) * 4.2;
  float core = exp(-dist * dist / (size * size * 0.05)) * 1.8;
  float halo = exp(-dist / (size * 0.36)) * 0.40;
  float outerHalo = exp(-dist / (size * 0.85)) * 0.10;

  /* Razor-sharp horizontal and vertical diffraction spikes */
  float sx = exp(-abs(d.y) / (size * 0.010)) * exp(-abs(d.x) / (size * 2.8));
  float sy = exp(-abs(d.x) / (size * 0.010)) * exp(-abs(d.y) / (size * 2.8));
  float spike = (sx + sy) * 0.75;

  /* Subtle diagonal secondary flare */
  vec2 diag = vec2(d.x + d.y, d.x - d.y) * 0.7071;
  float sdiag = (exp(-abs(diag.y) / (size * 0.009)) * exp(-abs(diag.x) / (size * 1.8)) +
                 exp(-abs(diag.x) / (size * 0.009)) * exp(-abs(diag.y) / (size * 1.8))) * 0.20;

  /* Center is white-hot transitioning into saturated color */
  vec3 starColor = mix(vec3(1.0, 0.99, 0.96), color, clamp(dist / (size * 0.35), 0.0, 1.0));
  float total = (nucleus + core + halo + outerHalo + spike + sdiag) * twinkle;
  return starColor * total;
}

/* ===== Meteors / Shooting Stars ===== */

float segmentDistance(vec2 p, vec2 a, vec2 b) {
  vec2 pa = p - a;
  vec2 ba = b - a;
  float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
  return length(pa - ba * h);
}

float meteor(vec2 uv, vec2 origin, vec2 direction, float phase, float speed, float width) {
  float cycle = fract(u_time * speed + phase);
  vec2 head = origin + direction * cycle;
  vec2 tail = head - normalize(direction) * 0.16;
  float d = segmentDistance(uv, tail, head);
  float glow = smoothstep(width, 0.0, d);
  float gate = smoothstep(0.0, 0.015, cycle) * (1.0 - smoothstep(0.18, 0.32, cycle));
  return glow * gate;
}

/* ===== Fast Cosmic Web Filaments ===== */

float cosmicFilament(vec2 uv, float t) {
  vec2 p1 = uv * 3.4 + vec2(t * 0.003, t * 0.001);
  vec2 p2 = uv * 5.6 + vec2(-t * 0.002, t * 0.003);

  float n1 = fbm(p1);
  float r1 = 1.0 - abs(n1 * 2.0 - 1.0);
  r1 = pow(smoothstep(0.55, 0.95, r1), 3.5);

  float n2 = fbm(p2 + 3.7);
  float r2 = 1.0 - abs(n2 * 2.0 - 1.0);
  r2 = pow(smoothstep(0.58, 0.96, r2), 4.0);

  return r1 * 0.65 + r2 * 0.45;
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  float aspect = u_res.x / u_res.y;
  float t = u_time;
  vec2 ptr = u_pointer;

  /* ------------------------------------------------------------------
     1. Deep Space Void: obsidian-black with subtle indigo/cyan wash
     ------------------------------------------------------------------ */
  vec2 sky = (uv - 0.5) * vec2(aspect, 1.0);
  float skyR = length(sky);

  vec3 col = mix(
    vec3(0.002, 0.004, 0.010),
    vec3(0.005, 0.014, 0.038),
    uv.y * 0.7 + 0.15
  );

  /* Faint galactic band haze */
  float band = exp(-pow((uv.y - 0.56 + uv.x * 0.08) * 6.2, 2.0));
  col += vec3(0.010, 0.024, 0.055) * band * (0.30 + 0.70 * fbm(sky * 3.8 + 2.1));

  /* ------------------------------------------------------------------
     2. Cosmic Web Filaments (Intergalactic medium)
     ------------------------------------------------------------------ */
  float filaments = cosmicFilament(sky, t);
  vec3 filColor = mix(
    vec3(0.04, 0.12, 0.28),
    vec3(0.10, 0.07, 0.22),
    sin(sky.x * 2.0 + t * 0.05) * 0.5 + 0.5
  );
  col += filColor * filaments * 0.18;

  /* Diffuse background nebular wisps */
  float neb1 = fbm(sky * 2.4 + vec2(t * 0.004, -t * 0.002));
  float nebMask = smoothstep(0.50, 0.84, neb1) * exp(-skyR * 0.9);
  col += vec3(0.012, 0.055, 0.12) * nebMask * 0.35;

  /* ------------------------------------------------------------------
     3. Deep Field Stars (4 Tiers of Crisp, Bright Optical Pinpoint Stars)
     ------------------------------------------------------------------ */
  vec2 bgUv = (uv - 0.5) * (1.0 + ptr * 0.006) + 0.5;

  /* Micro stars: dense, sparkling pinpoints across the entire sky */
  col += starFieldLayer(bgUv, 1100.0, 0.985, 17.0, t * 2.8) * 0.55;

  /* Fine stars */
  col += starFieldLayer(bgUv, 560.0, 0.978, 43.0, t * 2.0) * 0.95;

  /* Medium prominent stars */
  col += starFieldLayer(bgUv, 260.0, 0.972, 89.0, t * 1.3) * 1.45;

  /* Bright major stars */
  col += starFieldLayer(bgUv, 130.0, 0.975, 141.0, t * 0.8) * 1.85;

  /* ------------------------------------------------------------------
     4. Prominent Foreground Telescope Stars (Hubble/JWST 4-Point Spikes)
     ------------------------------------------------------------------ */
  float tw1 = 0.85 + 0.15 * sin(t * 1.4 + 1.2);
  float tw2 = 0.88 + 0.12 * sin(t * 2.1 + 4.5);
  float tw3 = 0.90 + 0.10 * sin(t * 0.9 + 2.8);
  float tw4 = 0.86 + 0.14 * sin(t * 1.8 + 3.3);
  float tw5 = 0.89 + 0.11 * sin(t * 2.4 + 0.7);

  /* Deep space foreground stars */
  col += diffractionStar(sky, vec2(-0.52 * aspect, -0.34), 0.062, vec3(0.68, 0.88, 1.0), tw1);
  col += diffractionStar(sky, vec2(0.58 * aspect, -0.28), 0.052, vec3(0.75, 0.92, 1.0), tw2);
  col += diffractionStar(sky, vec2(-0.64 * aspect, 0.36), 0.046, vec3(1.0, 0.88, 0.68), tw3);
  col += diffractionStar(sky, vec2(0.38 * aspect, 0.38), 0.040, vec3(0.70, 0.90, 1.0), tw4);

  /* Foreground stars embedded in / silhouetted against outer galaxy arms */
  col += diffractionStar(sky, vec2(0.22 * aspect, -0.16), 0.038, vec3(0.65, 0.85, 1.0), tw5);
  col += diffractionStar(sky, vec2(-0.26 * aspect, 0.18), 0.034, vec3(1.0, 0.92, 0.75), tw2);

  /* ------------------------------------------------------------------
     5. Meteors (Shooting Stars)
     ------------------------------------------------------------------ */
  float m1 = meteor(uv, vec2(0.04, 0.94), vec2(0.82, -0.52), 0.18, 0.058, 0.0022);
  float m2 = meteor(uv, vec2(0.85, 0.96), vec2(-0.76, -0.44), 0.65, 0.042, 0.0018);
  col += vec3(0.78, 0.94, 1.0) * m1 * 1.8;
  col += vec3(0.90, 0.84, 1.0) * m2 * 1.4;

  /* ------------------------------------------------------------------
     6. Galaxy Coordinate Mapping (pseudo-3D inclined disk)
     ------------------------------------------------------------------ */
  vec2 p = (uv - u_center) * vec2(aspect, 1.0) * (u_scale / u_zoom);
  p += ptr * 0.032;
  p = rotate2d(u_yaw - 0.38) * p;

  /* keep projected ellipse so orbit labels stay aligned */
  p.y /= u_tilt;

  float rPlane = length(p);
  float theta = atan(p.y, p.x);

  /* disk thickness / height warp (2 noise samples) */
  float hA = fbm3(p * 3.2 + vec2(t * 0.006, 1.7));
  float hB = fbm3(p * 7.1 + vec2(-t * 0.004, 4.2));
  float diskHeight = ((hA - 0.5) * 0.18 + (hB - 0.5) * 0.09) * exp(-rPlane * 1.6);
  float r = sqrt(rPlane * rPlane + diskHeight * diskHeight);

  /* Differential rotation */
  float spin = t * 0.038;
  float shear = spin * (0.28 + 0.85 / (rPlane + 0.42));
  float thetaR = theta - shear;
  vec2 gp = vec2(cos(thetaR), sin(thetaR)) * r;

  /* Noise layers for spiral distortion */
  float n1 = fbm(gp * 2.3 + vec2(0.0, t * 0.005));
  float n2 = fbm(gp * 6.5 + vec2(3.1, -t * 0.010));
  float n3 = fbm(gp * 13.8 + vec2(1.7, t * 0.018));
  float n4 = fbm3(gp * 10.2 + vec2(-2.4, t * 0.012));

  /* ------------------------------------------------------------------
     7. Logarithmic Spiral Arms
     ------------------------------------------------------------------ */
  float warp = (n1 - 0.5) * 1.45 + (n3 - 0.5) * 0.35;
  float spiralTheta = thetaR + warp * 0.65;
  float armPhase = 2.0 * spiralTheta - 4.2 * log(r + 0.055);

  float armSharp = pow(0.5 + 0.5 * sin(armPhase), 7.0);
  float armBroad = pow(0.5 + 0.5 * sin(armPhase + 0.28), 2.2);
  float primaryArms = armSharp * 0.72 + armBroad * 0.28;

  float subArmPhase = 2.0 * spiralTheta - 4.2 * log(r + 0.055) + 3.14159;
  float subArms = pow(0.5 + 0.5 * sin(subArmPhase), 6.0) * 0.42;

  float spurs = pow(0.5 + 0.5 * sin(spiralTheta * 4.0 - 6.0 * log(r + 0.1) + n2 * 2.0), 4.0) * 0.25;
  float totalArms = primaryArms + subArms + spurs;

  /* ------------------------------------------------------------------
     7b. Ellipsoidal / barred bulge (fixed pattern speed)
     ------------------------------------------------------------------ */
  float barAngle = 0.22 + spin * 0.5;
  vec2 barP = rotate2d(-barAngle) * p;
  float ellR = length(vec2(barP.x / 1.35, barP.y / 0.62));
  float sersicBulge = exp(-2.1 * pow(max(ellR / 0.18, 0.0), 1.0 / 1.5));
  float peanut = exp(-pow(abs(barP.y) / 0.07, 2.0)) * exp(-barP.x * barP.x / 0.05) * 0.45;
  float bulge = sersicBulge + peanut * 0.35;

  float disk = exp(-r * 2.2);
  float coreGlow = exp(-r * r * 46.0);
  float nucleus = exp(-r * r * 190.0);
  float halo = exp(-r * 1.35);

  /* ------------------------------------------------------------------
     8. Dark Interstellar Dust Lanes (Sharp silhouettes between stars)
     ------------------------------------------------------------------ */
  float dustAngle = armPhase + 2.3 + (n2 - 0.5) * 1.8;
  float dustLane = pow(0.5 + 0.5 * sin(dustAngle), 5.0);
  float dustAngle2 = dustAngle + 0.62 + (n3 - 0.5) * 0.9;
  float dustLane2 = pow(0.5 + 0.5 * sin(dustAngle2), 8.0);
  float dustDist = smoothstep(0.04, 0.22, r) * exp(-r * 1.15);
  float dustNoise = smoothstep(0.20, 0.75, n2 * 0.55 + n3 * 0.45);
  float dustFilament = smoothstep(0.52, 0.86, n3 * 0.6 + n4 * 0.4);
  float dust = (dustLane * 0.78 + dustLane2 * 0.42) * dustDist * (0.55 + dustFilament * 0.45) * 1.05;
  float fineDust = smoothstep(0.48, 0.78, n4) * exp(-r * 1.6) * smoothstep(0.06, 0.28, r);
  dust += fineDust * 0.35;
  dust = clamp(dust, 0.0, 1.0);

  /* ------------------------------------------------------------------
     9. Color Grading: Matched to Reference Spiral Galaxy Image
     ------------------------------------------------------------------ */
  vec3 nucleusColor = vec3(1.0, 0.99, 0.94);
  vec3 goldenCore = mix(
    vec3(1.0, 0.56, 0.20),
    vec3(1.0, 0.88, 0.55),
    clamp(coreGlow * 1.6, 0.0, 1.0)
  );
  vec3 coreColor = mix(goldenCore, nucleusColor, clamp(nucleus * 1.8, 0.0, 1.0));

  vec3 armColor = mix(
    vec3(0.18, 0.48, 0.98),
    vec3(0.72, 0.90, 1.0),
    clamp(n2 * 1.15, 0.0, 1.0)
  );
  armColor = mix(armColor, vec3(0.24, 0.84, 0.88), smoothstep(0.25, 0.65, r) * 0.32);

  vec3 bulgeColor = mix(
    vec3(0.96, 0.66, 0.26),
    vec3(0.94, 0.84, 0.56),
    smoothstep(0.0, 0.22, r)
  );

  vec3 galaxy = vec3(0.0);

  /* Core + Nucleus bloom */
  galaxy += coreColor * (coreGlow * 1.6 + nucleus * 1.0) * 1.4;

  /* Bulge warm glow */
  galaxy += bulgeColor * bulge * 0.38;

  /* Translucent, luminous gas veil (AIRY, NOT OPAQUE CLOUDS) */
  float gasVeil = disk * (0.008 + totalArms * 0.95) * (0.35 + 0.65 * n1);
  gasVeil *= 1.0 - clamp(dust, 0.0, 1.0) * 0.85;
  galaxy += armColor * gasVeil * 0.80;

  /* Warm inner disk haze */
  galaxy += vec3(1.0, 0.58, 0.26) * exp(-r * 3.4) * 0.15;

  /* Outer cyan/blue galactic halo */
  galaxy += vec3(0.14, 0.32, 0.66) * halo * 0.06;

  /* Glowing teal cloud perimeter */
  float tealHalo = exp(-pow(r - 0.52, 2.0) * 7.5) * (0.40 + 0.60 * fbm3(gp * 2.8));
  galaxy += vec3(0.08, 0.32, 0.44) * tealHalo * 0.20;

  /* ------------------------------------------------------------------
     10. Dense Sparkling Stellar Populations (THE STARS IN THE ARMS)
     ------------------------------------------------------------------ */

  /* Population 1: Ultra-dense sparkling star dust (hundreds of thousands of sharp pinpoint stars) */
  vec2 s1 = gp * 340.0;
  vec2 id1 = floor(s1);
  vec2 f1 = fract(s1) - 0.5;
  float h1 = hash21(id1 + 17.0);
  vec2 o1 = vec2(hash21(id1 + 3.1), hash21(id1 + 9.7)) - 0.5;
  float d1 = length(f1 - o1 * 0.75);
  float star1 = (exp(-d1 * d1 * 2600.0) * 3.6 + exp(-d1 * 26.0) * 0.4);
  float p1Active = step(0.62, h1) * disk * (0.15 + primaryArms * 3.2);
  p1Active *= 1.0 - dust * 0.70;
  vec3 col1 = mix(blackbody(11000.0), blackbody(6500.0), h1);
  galaxy += col1 * star1 * p1Active * (0.7 + 1.3 * hash21(id1 + 55.0));

  /* Population 2: Medium OB Star Clusters & Supergiants (Brilliant sparkling jewels) */
  vec2 s2 = gp * 150.0;
  vec2 id2 = floor(s2);
  vec2 f2 = fract(s2) - 0.5;
  float h2 = hash21(id2 + 43.0);
  vec2 o2 = vec2(hash21(id2 + 11.3), hash21(id2 + 27.9)) - 0.5;
  float d2 = length(f2 - o2 * 0.72);
  float star2 = (exp(-d2 * d2 * 1500.0) * 4.8 + exp(-d2 * 18.0) * 0.7);
  float p2Active = step(0.75, h2) * disk * (0.10 + primaryArms * 3.8);
  p2Active *= 1.0 - dust * 0.80;
  vec3 col2 = mix(blackbody(22000.0), blackbody(9000.0), h2);
  col2 = mix(col2, blackbody(3800.0), step(0.85, hash21(id2 + 77.0)) * 0.65);
  galaxy += col2 * star2 * p2Active * (0.9 + 1.5 * hash21(id2 + 88.0));

  /* Population 3: Major Starburst Clusters & Glowing Knots */
  vec2 s3 = gp * 65.0;
  vec2 id3 = floor(s3);
  vec2 f3 = fract(s3) - 0.5;
  float h3 = hash21(id3 + 79.0);
  vec2 o3 = vec2(hash21(id3 + 15.1), hash21(id3 + 39.5)) - 0.5;
  float d3 = length(f3 - o3 * 0.70);
  float star3 = (exp(-d3 * d3 * 800.0) * 6.2 + exp(-d3 * 12.0) * 1.4);
  float p3Active = step(0.85, h3) * disk * primaryArms;
  p3Active *= 1.0 - dust * 0.85;
  vec3 col3 = mix(vec3(0.35, 0.90, 1.0), vec3(1.0, 0.42, 0.72), step(0.68, hash21(id3 + 12.0)));
  galaxy += col3 * star3 * p3Active * 1.9;

  /* Population 4: Dense Golden Bulge Stars */
  vec2 s4 = gp * 220.0;
  vec2 id4 = floor(s4);
  vec2 f4 = fract(s4) - 0.5;
  float h4 = hash21(id4 + 61.0);
  vec2 o4 = vec2(hash21(id4 + 8.3), hash21(id4 + 19.1)) - 0.5;
  float d4 = length(f4 - o4 * 0.7);
  float star4 = (exp(-d4 * d4 * 2000.0) * 3.5 + exp(-d4 * 20.0) * 0.5);
  float p4Active = step(0.55, h4) * bulge * 1.6;
  vec3 col4 = mix(blackbody(5200.0), blackbody(3600.0), h4);
  galaxy += col4 * star4 * p4Active;

  /* ------------------------------------------------------------------
     11. HII Emission Regions (Pink/Magenta knots) & Cyan Starbursts
     ------------------------------------------------------------------ */
  float knotTrigger = smoothstep(0.68, 0.92, n3) * armSharp * smoothstep(0.12, 0.32, r) * (1.0 - smoothstep(0.62, 1.05, r)) * disk;
  galaxy += vec3(1.0, 0.32, 0.62) * knotTrigger * 1.5;

  float cyanTrigger = smoothstep(0.72, 0.95, n4) * primaryArms * smoothstep(0.18, 0.40, r) * (1.0 - smoothstep(0.70, 1.15, r)) * disk;
  galaxy += vec3(0.38, 0.94, 1.0) * cyanTrigger * 1.3;

  /* ------------------------------------------------------------------
     12. Dust Reddening and Extinction
     ------------------------------------------------------------------ */
  float dustMask = clamp(dust, 0.0, 1.0);
  galaxy = mix(galaxy, galaxy * vec3(0.52, 0.30, 0.18), dustMask * 0.82);
  galaxy *= 1.0 - dustMask * 0.62;

  col += galaxy;

  /* ------------------------------------------------------------------
     13. Central Luminous Core Bloom Bleed
     ------------------------------------------------------------------ */
  float bloomDist = length((uv - u_center) * vec2(aspect, 1.0) * (u_scale / u_zoom));
  float bloomCore = exp(-bloomDist * bloomDist * 26.0) * 0.25;
  float bloomWarm = exp(-bloomDist * 7.5) * 0.08;
  col += vec3(1.0, 0.86, 0.52) * bloomCore;
  col += vec3(1.0, 0.70, 0.34) * bloomWarm;

  float bloomOuter = exp(-bloomDist * 3.2) * 0.038;
  col += vec3(0.28, 0.62, 0.92) * bloomOuter;

  /* ------------------------------------------------------------------
     14. Vignette, ACES Filmic Tone-Mapping & Dithering
     ------------------------------------------------------------------ */
  float vignette = smoothstep(1.85, 0.16, length((uv - 0.5) * vec2(aspect, 1.0)));
  col *= mix(0.58, 1.0, vignette);

  /* ACES Filmic Tone Mapping Curve */
  col = (col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14);
  col = clamp(col, 0.0, 1.0);

  /* Subtle gamma correction */
  col = pow(col, vec3(0.94));

  /* High-frequency dithering */
  col += (hash21(gl_FragCoord.xy + fract(t)) - 0.5) / 255.0;

  gl_FragColor = vec4(col, 1.0);
}
`;

  function compileShader(type, source) {
    var shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      var message = gl.getShaderInfoLog(shader);
      gl.deleteShader(shader);
      throw new Error(message || 'Shader compilation failed');
    }
    return shader;
  }

  function initGL() {
    try {
      gl = canvas.getContext('webgl', {
        alpha: false,
        antialias: false,
        depth: false,
        stencil: false,
        preserveDrawingBuffer: false,
        powerPreference: 'default'
      }) || canvas.getContext('experimental-webgl');

      if (!gl) return false;

      var vs = compileShader(gl.VERTEX_SHADER, VERTEX_SRC);
      var fs = compileShader(gl.FRAGMENT_SHADER, FRAGMENT_SRC);
      var prog = gl.createProgram();
      gl.attachShader(prog, vs);
      gl.attachShader(prog, fs);
      gl.linkProgram(prog);
      gl.deleteShader(vs);
      gl.deleteShader(fs);

      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
        var linkLog = gl.getProgramInfoLog(prog);
        gl.deleteProgram(prog);
        throw new Error(linkLog || 'Shader linking failed');
      }

      program = prog;
      gl.useProgram(program);

      var quad = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, quad);
      gl.bufferData(
        gl.ARRAY_BUFFER,
        new Float32Array([
          -1, -1, 1, -1, -1, 1,
          -1, 1, 1, -1, 1, 1
        ]),
        gl.STATIC_DRAW
      );

      var position = gl.getAttribLocation(program, 'a_position');
      gl.enableVertexAttribArray(position);
      gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

      uniforms = {
        res: gl.getUniformLocation(program, 'u_res'),
        center: gl.getUniformLocation(program, 'u_center'),
        pointer: gl.getUniformLocation(program, 'u_pointer'),
        time: gl.getUniformLocation(program, 'u_time'),
        scale: gl.getUniformLocation(program, 'u_scale'),
        yaw: gl.getUniformLocation(program, 'u_yaw'),
        tilt: gl.getUniformLocation(program, 'u_tilt'),
        zoom: gl.getUniformLocation(program, 'u_zoom')
      };

      gl.disable(gl.DEPTH_TEST);
      gl.disable(gl.BLEND);
      gl.clearColor(0.002, 0.004, 0.010, 1.0);
      scene.classList.remove('is-no-webgl');
      if (fallback) fallback.classList.add('d-none');
      if (labelLayer && labelsVisible) labelLayer.style.display = '';
      return true;
    } catch (err) {
      gl = null;
      program = null;
      uniforms = null;
      return false;
    }
  }

  function enableFallback() {
    scene.classList.add('is-no-webgl');
    if (labelLayer) labelLayer.style.display = 'none';
    if (fallback) fallback.classList.remove('d-none');
  }

  function resize() {
    if (!gl || !program || !uniforms) return;

    sceneRect = scene.getBoundingClientRect();
    var wrapRect = wrap.getBoundingClientRect();
    wrapW = Math.max(1, Math.round(wrapRect.width));
    wrapH = Math.max(1, Math.round(wrapRect.height));
    var width = Math.max(1, Math.round(sceneRect.width));
    var height = Math.max(1, Math.round(sceneRect.height));
    DPR = Math.min(window.devicePixelRatio || 1, 1);

    var pixelWidth = Math.max(1, Math.round(width * DPR));
    var pixelHeight = Math.max(1, Math.round(height * DPR));
    var budget = pixelBudget * renderScale * renderScale;
    var pixels = pixelWidth * pixelHeight;
    if (pixels > budget) {
      var fit = Math.sqrt(budget / pixels);
      pixelWidth = Math.max(1, Math.round(pixelWidth * fit));
      pixelHeight = Math.max(1, Math.round(pixelHeight * fit));
    }

    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
      canvas.width = pixelWidth;
      canvas.height = pixelHeight;
    }

    gl.viewport(0, 0, pixelWidth, pixelHeight);
    gl.uniform2f(uniforms.res, pixelWidth, pixelHeight);

    var targetDiameter = Math.min(
      wrapRect.height * 1.08,
      wrapRect.width * 0.94
    );
    sceneScale = Math.max(
      1.7,
      Math.min(height / Math.max(110, targetDiameter * 0.5), 8.5)
    );
    gl.uniform1f(uniforms.scale, sceneScale);

    var cx = (wrapRect.left + wrapRect.width * 0.5 - sceneRect.left) /
      Math.max(1, sceneRect.width);
    var cy = (wrapRect.top + wrapRect.height * 0.5 - sceneRect.top) /
      Math.max(1, sceneRect.height);
    /* gl_FragCoord.y is bottom-up; the DOM rect is measured top-down. */
    gl.uniform2f(
      uniforms.center,
      Math.max(0, Math.min(1, cx)),
      Math.max(0, Math.min(1, 1 - cy))
    );
  }

  function refreshRect() {
    if (!scene) return;
    sceneRect = scene.getBoundingClientRect();
    if (wrap) {
      wrapW = Math.max(1, wrap.clientWidth);
      wrapH = Math.max(1, wrap.clientHeight);
    }
  }

  function scheduleRect() {
    if (rectTick) return;
    rectTick = window.requestAnimationFrame(function () {
      rectTick = 0;
      refreshRect();
      kick(2);
    });
  }

  function scheduleResize() {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(function () {
      resize();
      kick(2);
    }, 80);
  }

  function buildLabels() {
    if (!labelLayer || !labelsVisible) return;

    models.forEach(function (model, index) {
      var color = model.color || '#67e8f9';
      var el = document.createElement('a');
      el.className = 'orbit-label';
      el.href = '/news/?q=' + encodeURIComponent(model.query || '');
      el.style.setProperty('--orbit-color', color);
      el.setAttribute('aria-label',
        (model.label || 'Model') + ', ' + (model.total || 0) + ' articles');

      var pip = document.createElement('span');
      pip.className = 'orbit-pip';
      var text = document.createElement('span');
      text.textContent = model.label || 'Model';

      el.appendChild(pip);
      el.appendChild(text);
      el.addEventListener('pointerenter', function () { showTip(nodeData); });
      el.addEventListener('pointerleave', hideTip);
      el.addEventListener('focus', function () { showTip(nodeData); });
      el.addEventListener('blur', hideTip);

      labelLayer.appendChild(el);

      var nodeData = {
        model: model,
        el: el,
        angle: (index / models.length) * Math.PI * 2 + 0.3,
        phase: index * 1.73,
        speed: 0.058,
        radius: 0.9 + (index % 2) * 0.12,
        lx: 0,
        ly: 0
      };
      nodes.push(nodeData);
    });
  }

  function showTip(node) {
    if (!tooltip || !node) return;
    if (!hoveredNode) {
      labelHold = elapsed;
      labelYawHold = view.yaw;
    }
    hoveredNode = node;
    tooltip.textContent = node.model.label + ' · ' +
      (node.model.total || 0) + ' articles — click to filter';
    tooltip.classList.remove('d-none');
    positionTip();
  }

  function hideTip() {
    hoveredNode = null;
    if (tooltip) tooltip.classList.add('d-none');
  }

  function positionTip() {
    if (!tooltip || !hoveredNode || !wrap) return;
    var zoomScale = Math.max(0.65, Math.min(1.5, Math.pow(view.zoom, 0.55)));
    var topOffset = 22 * zoomScale;
    tooltip.style.left = Math.round(hoveredNode.lx) + 'px';
    tooltip.style.top = Math.round(hoveredNode.ly - topOffset) + 'px';
    tooltip.style.transform = 'translate(-50%, -100%)';
  }

  function updateLabels() {
    if (!labelsVisible || !wrap) return;

    var width = wrapW || wrap.clientWidth;
    var height = wrapH || wrap.clientHeight;
    if (!width || !height) return;

    var cx = width * 0.5;
    var cy = height * 0.5;

    var yaw = hoveredNode ? labelYawHold : view.yaw;
    var zoom = view.zoom;
    var sceneW = Math.max(1, sceneRect.width || width);
    var sceneH = Math.max(1, sceneRect.height || height);
    var aspect = sceneW / sceneH;
    var scaleOverZoom = Math.max(0.0001, sceneScale / zoom);

    /* Inverse of the fragment shader:
       p = rotate2d(u_yaw - 0.38) * ((uv - u_center) * vec2(aspect, 1.0) * (u_scale / u_zoom) + ptr * 0.032);
       p.y /= u_tilt;
       GLSL rotate2d(a) is mat2(c,-s,s,c), i.e. standard R(-a); invert with R(a). */
    var rotAngle = yaw - 0.38;
    var cosRot = Math.cos(rotAngle);
    var sinRot = Math.sin(rotAngle);
    var labelTime = hoveredNode ? labelHold : elapsed;

    /* Text label scale zooms in/out together with the cosmic space */
    var labelScale = Math.max(0.65, Math.min(1.55, Math.pow(view.zoom, 0.55)));

    nodes.forEach(function (node) {
      var angle = node.angle + labelTime * node.speed;
      var radius = node.radius + Math.sin(labelTime * 0.22 + node.phase) * 0.028;

      var planeX = Math.cos(angle) * radius;
      var planeY = Math.sin(angle) * radius;
      var tiltedX = planeX;
      var tiltedY = planeY * view.tilt;

      /* Undo the shader rotation, then the pointer offset. */
      var p0x = tiltedX * cosRot - tiltedY * sinRot;
      var p0y = tiltedX * sinRot + tiltedY * cosRot;
      p0x -= pointer.x * 0.032;
      p0y -= pointer.y * 0.032;

      var x = cx + (p0x / scaleOverZoom / aspect) * sceneW;
      var y = cy - (p0y / scaleOverZoom) * sceneH;

      /* 3D depth sorting relative to camera view */
      var zDepth = Math.sin(angle + (view.yaw - 0.38));
      var front = zDepth > -0.15;
      var depthScale = front ? 1.0 : 0.88;
      var totalScale = (labelScale * depthScale).toFixed(3);

      node.lx = x;
      node.ly = y;

      node.el.style.transform = 'translate3d(' +
        x.toFixed(1) + 'px,' + y.toFixed(1) + 'px,0) translate(-50%, -50%) scale(' + totalScale + ')';

      node.el.classList.toggle('is-front', front);
      node.el.classList.toggle('is-behind', !front);
      node.el.style.zIndex = front ? '6' : '2';
      node.el.style.opacity = front ? '1' : Math.max(0.55, 0.85 + zDepth * 0.5).toFixed(2);
    });

    if (hoveredNode) positionTip();
  }

  function paintMotion() {
    var moving = speed > 0.001;
    scene.classList.toggle('is-paused', !moving);
    if (motionBtn) {
      motionBtn.innerHTML = moving
        ? '<i class="fas fa-pause me-1"></i> Pause motion'
        : '<i class="fas fa-play me-1"></i> Play motion';
      motionBtn.setAttribute('aria-label', moving ? 'Pause galaxy motion' : 'Play galaxy motion');
    }
    if (speedInput) speedInput.value = speed.toFixed(1);
    if (liveState) {
      liveState.textContent = moving ? 'LIVE COSMIC FEED' : 'COSMIC FEED PAUSED';
    }
  }

  function hideHint() {
    if (cosmosHint) cosmosHint.classList.add('is-hidden');
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function resetView() {
    view.yaw = 0;
    view.targetTilt = 0.62;
    view.targetZoom = 1;
    hideHint();
    kick(40);
  }

  function setZoom(next) {
    view.targetZoom = clamp(next, 0.62, 2.4);
    hideHint();
    kick(40);
  }

  function start() {
    if (running || !gl || !program) return;
    if (!visible || document.hidden) return;
    running = true;
    last = performance.now();
    lastDraw = 0;
    rafId = window.requestAnimationFrame(frame);
  }

  function stop() {
    running = false;
    if (rafId) {
      window.cancelAnimationFrame(rafId);
      rafId = 0;
    }
  }

  function kick(frames) {
    settleFrames = Math.max(settleFrames, frames || 24);
    if (!running) start();
  }

  function frame(now) {
    if (!running) return;
    rafId = 0;
    if (!gl || !program || !visible || document.hidden) {
      stop();
      return;
    }

    /* Hard 30fps cap: rAF may fire at 60-144Hz, the shader is expensive. */
    if (now - lastDraw < frameInterval - 0.5) {
      rafId = window.requestAnimationFrame(frame);
      return;
    }

    var rawDt = (now - last) / 1000;
    var dt = Math.min(rawDt, 0.05);
    last = now;
    lastDraw = now;

    if (speed > 0) {
      elapsed += dt * speed;
      if (!view.dragging) {
        view.yaw += dt * 0.012 * speed;
      }
    }

    view.tilt += (view.targetTilt - view.tilt) * 0.11;
    view.zoom += (view.targetZoom - view.zoom) * 0.11;

    pointer.x += (pointer.tx - pointer.x) * 0.045;
    pointer.y += (pointer.ty - pointer.y) * 0.045;

    gl.uniform1f(uniforms.time, elapsed);
    gl.uniform1f(uniforms.yaw, view.yaw);
    gl.uniform1f(uniforms.tilt, view.tilt);
    gl.uniform1f(uniforms.zoom, view.zoom);
    gl.uniform2f(uniforms.pointer, pointer.x, pointer.y);
    gl.drawArrays(gl.TRIANGLES, 0, 6);

    if (labelsVisible) updateLabels();
    if (settleFrames > 0) settleFrames--;

    /* Adaptive quality: degrade backing-store resolution on slow GPUs. */
    if (qualityStage < 2 && rawDt > 0.045) {
      slowFrames++;
      if (slowFrames >= (qualityStage === 0 ? 6 : 10)) {
        qualityStage++;
        renderScale = qualityStage === 1 ? 0.72 : 0.52;
        slowFrames = 0;
        resize();
      }
    } else if (slowFrames > 0 && rawDt <= 0.04) {
      slowFrames--;
    }

    if (speed <= 0.001 && settleFrames <= 0 && !view.dragging) {
      stop();
      return;
    }

    rafId = window.requestAnimationFrame(frame);
  }

  function setupViewControls() {
    var card = scene.closest('.hermes-orbit-card');

    setupViewGestures();

    if (speedInput) {
      speedInput.addEventListener('input', function () {
        var next = window.parseFloat(speedInput.value);
        if (!window.isFinite(next)) return;
        speed = clamp(next, 0, 2.4);
        if (speed > 0) lastSpeed = speed;
        paintMotion();
        kick(2);
      });
    }

    if (zoomInBtn) {
      zoomInBtn.addEventListener('click', function () {
        setZoom(view.targetZoom * 1.22);
      });
    }

    if (zoomOutBtn) {
      zoomOutBtn.addEventListener('click', function () {
        setZoom(view.targetZoom / 1.22);
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', resetView);
    }

    if (fullscreenBtn && card && card.requestFullscreen) {
      fullscreenBtn.addEventListener('click', function () {
        if (document.fullscreenElement) {
          if (document.exitFullscreen) document.exitFullscreen();
        } else {
          var request = card.requestFullscreen();
          if (request && request.catch) request.catch(function () {});
        }
      });

      document.addEventListener('fullscreenchange', function () {
        var active = document.fullscreenElement === card;
        fullscreenBtn.innerHTML = active
          ? '<i class="fas fa-compress"></i>'
          : '<i class="fas fa-expand"></i>';
        fullscreenBtn.setAttribute('aria-label', active ? 'Exit full screen' : 'Full screen');
        fullscreenBtn.title = active ? 'Exit full screen' : 'Full screen';
        window.setTimeout(scheduleResize, 90);
      });
    } else if (fullscreenBtn) {
      fullscreenBtn.hidden = true;
    }
  }

  function setupViewGestures() {
    if (!wrap) return;

    var activePointers = new Map();
    var pinchStart = 0;
    var pinchZoom = 1;
    var lastX = 0;
    var lastY = 0;

    function distance(a, b) {
      return Math.sqrt(
        Math.pow(a.x - b.x, 2) + Math.pow(a.y - b.y, 2)
      );
    }

    function skipDrag(event) {
      return !!(event.target && event.target.closest &&
        event.target.closest('a, button, input, label, .cosmos-toolbar, .orbit-label'));
    }

    function finishPointer(event) {
      activePointers.delete(event.pointerId);

      if (activePointers.size === 0) {
        view.dragging = false;
        pinchStart = 0;
        wrap.classList.remove('is-dragging');
        scene.classList.remove('is-interacting');
      } else if (activePointers.size === 1) {
        var remaining = activePointers.values().next().value;
        lastX = remaining.x;
        lastY = remaining.y;
        pinchStart = 0;
      }
    }

    wrap.addEventListener('pointerdown', function (event) {
      if (event.pointerType === 'mouse' && event.button !== 0) return;
      if (skipDrag(event)) return;

      activePointers.set(event.pointerId, {
        x: event.clientX,
        y: event.clientY
      });

      if (activePointers.size === 1) {
        view.dragging = true;
        lastX = event.clientX;
        lastY = event.clientY;
        wrap.classList.add('is-dragging');
        scene.classList.add('is-interacting');
      } else if (activePointers.size === 2) {
        var pair = Array.from(activePointers.values());
        pinchStart = Math.max(1, distance(pair[0], pair[1]));
        pinchZoom = view.targetZoom;
      }

      hideHint();
      kick(40);
      try { wrap.setPointerCapture(event.pointerId); } catch (err) {}
      event.preventDefault();
    });

    wrap.addEventListener('pointermove', function (event) {
      if (!activePointers.has(event.pointerId)) return;

      activePointers.set(event.pointerId, {
        x: event.clientX,
        y: event.clientY
      });

      if (activePointers.size >= 2) {
        var fingers = Array.from(activePointers.values());
        var spread = distance(fingers[0], fingers[1]);
        if (pinchStart > 0) {
          setZoom(pinchZoom * (spread / pinchStart));
        }
        event.preventDefault();
        return;
      }

      var dx = event.clientX - lastX;
      var dy = event.clientY - lastY;
      lastX = event.clientX;
      lastY = event.clientY;

      view.yaw -= dx * 0.006;
      view.targetTilt = clamp(view.targetTilt + dy * 0.0024, 0.34, 1.25);
      kick(40);
      event.preventDefault();
    });

    wrap.addEventListener('pointerup', finishPointer);
    wrap.addEventListener('pointercancel', finishPointer);

    wrap.addEventListener('wheel', function (event) {
      event.preventDefault();
      var delta = event.deltaY;
      if (event.deltaMode === 1) delta *= 16;
      if (event.deltaMode === 2) delta *= 100;
      setZoom(view.targetZoom * Math.exp(-delta * 0.0011));
      scene.classList.add('is-interacting');
    }, { passive: false });

    wrap.addEventListener('dblclick', function (event) {
      if (skipDrag(event)) return;
      resetView();
    });

    wrap.addEventListener('keydown', function (event) {
      var handled = true;

      switch (event.key) {
        case 'ArrowLeft':
          view.yaw += 0.09;
          break;
        case 'ArrowRight':
          view.yaw -= 0.09;
          break;
        case 'ArrowUp':
          view.targetTilt = clamp(view.targetTilt - 0.06, 0.34, 1.25);
          break;
        case 'ArrowDown':
          view.targetTilt = clamp(view.targetTilt + 0.06, 0.34, 1.25);
          break;
        case '+':
        case '=':
          setZoom(view.targetZoom * 1.2);
          break;
        case '-':
        case '_':
          setZoom(view.targetZoom / 1.2);
          break;
        case '0':
          resetView();
          break;
        default:
          handled = false;
      }

      if (handled) {
        hideHint();
        kick(40);
        event.preventDefault();
      }
    });
  }

  function boot() {
    buildLabels();
    paintMotion();

    if (motionBtn) {
      motionBtn.addEventListener('click', function () {
        if (speed > 0) {
          lastSpeed = speed;
          speed = 0;
        } else {
          speed = lastSpeed || 1;
        }
        last = performance.now();
        paintMotion();
        if (speed > 0) {
          start();
        } else {
          kick(1);
        }
      });
    }

    if (motionQuery) {
      var onMotionPreferenceChange = function (event) {
        reduceMotion = event.matches;
        if (reduceMotion) {
          if (speed > 0) lastSpeed = speed;
          speed = 0;
        } else {
          speed = lastSpeed || 1;
        }
        last = performance.now();
        paintMotion();
        if (speed > 0) start(); else kick(1);
      };
      if (motionQuery.addEventListener) {
        motionQuery.addEventListener('change', onMotionPreferenceChange);
      } else if (motionQuery.addListener) {
        motionQuery.addListener(onMotionPreferenceChange);
      }
    }

    if (!initGL()) {
      enableFallback();
      return;
    }

    refreshRect();
    resize();
    setupViewControls();
    window.addEventListener('resize', scheduleResize);
    window.addEventListener('load', scheduleResize);
    window.addEventListener('scroll', scheduleRect, { passive: true });

    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(scheduleResize);
    }
    window.setTimeout(scheduleResize, 220);

    if ('ResizeObserver' in window) {
      resizeObserver = new ResizeObserver(scheduleResize);
      resizeObserver.observe(scene);
      resizeObserver.observe(wrap);
    }

    if ('IntersectionObserver' in window) {
      intersectionObserver = new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        if (visible) start(); else stop();
      }, { threshold: 0.01 });
      intersectionObserver.observe(scene);
    }

    document.addEventListener('visibilitychange', function () {
      if (document.hidden) stop();
      else if (visible) start();
    });

    scene.addEventListener('pointerenter', refreshRect);
    scene.addEventListener('pointermove', function (event) {
      if (event.pointerType === 'touch' || reduceMotion) return;
      if (!sceneRect) sceneRect = scene.getBoundingClientRect();
      var rect = sceneRect;
      pointer.tx = ((event.clientX - rect.left) / Math.max(1, rect.width) - 0.5) * 2;
      pointer.ty = ((event.clientY - rect.top) / Math.max(1, rect.height) - 0.5) * 2;
      kick(40);
    });

    scene.addEventListener('pointerleave', function () {
      pointer.tx = 0;
      pointer.ty = 0;
      kick(30);
    });

    canvas.addEventListener('webglcontextlost', function (event) {
      event.preventDefault();
      stop();
      gl = null;
      program = null;
      uniforms = null;
      enableFallback();
    });

    canvas.addEventListener('webglcontextrestored', function () {
      if (initGL()) {
        refreshRect();
        resize();
        start();
      }
    });

    window.addEventListener('pagehide', function () {
      stop();
      if (resizeObserver) resizeObserver.disconnect();
      if (intersectionObserver) intersectionObserver.disconnect();
      window.clearTimeout(resizeTimer);
      if (rectTick) window.cancelAnimationFrame(rectTick);
    });

    settleFrames = Math.max(settleFrames, 2);
    start();
  }

  /* Defer shader compilation past first paint so it never blocks FCP/LCP. */
  window.requestAnimationFrame(function () {
    window.requestAnimationFrame(boot);
  });
})();

// Окно эпизода «машинист»: вид сбоку на поезд и путь. Рисует только состояние симулятора (км, скорость, ограничения,
// сигнал, погода, станции) и открытые данные участка; декорации (горы, деревья, опоры) детерминированы от километра.
(function (root) {
  "use strict";
  var ELEV = {};
  function elevOf(L) {
    if (ELEV[L.id]) return ELEV[L.id];
    var seg = L.segments.slice().sort(function (a, b) { return a.from_km - b.from_km; }), pts = [[seg[0].from_km, 0]], h = 0;
    seg.forEach(function (s) { h += (s.to_km - s.from_km) * s.grade_permille; pts.push([s.to_km, h]); });
    return (ELEV[L.id] = pts);
  }
  function hAt(pts, km) {
    if (km <= pts[0][0]) return pts[0][1];
    for (var i = 1; i < pts.length; i++) if (km <= pts[i][0]) { var a = pts[i - 1], b = pts[i]; return a[1] + (b[1] - a[1]) * (km - a[0]) / (b[0] - a[0]); }
    return pts[pts.length - 1][1];
  }
  function hash(n) { var x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }
  function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
  var TUNNELS = { ch_gotthard: [[70.45, 85.453]] };  // Готардский тоннель 15 003 м от Гёшенена (de.wikipedia, П)
  var LOOK = {
    de_krm: { car: 25, body: "--panel", stripe: "--limit", nose: true, pant: [1, 6] },
    jp_tokaido: { car: 25, body: "--panel", stripe: "--track", nose: true, pant: [3, 11] },
    ch_gotthard: { car: 20, body: "--rail", stripe: "--signal", nose: false, loco: 20, pant: [0] }
  };

  // S: {L, T, km, v, t, ghostKm, zones:[[a_m,b_m,lim,kind]], signal, weather, label}
  function draw(cv, S) {
    var dpr = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
    if (!w || !h) return;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    var x = cv.getContext("2d"); x.setTransform(dpr, 0, 0, dpr, 0, 0);
    var L = S.L, pts = elevOf(L), span = w < 500 ? 1.0 : 1.6, k0 = S.km - span * 0.6, k1 = k0 + span;
    var href = hAt(pts, S.km), vex = 4;  // вертикаль утрирована в 4 раза
    var X = function (k) { return (k - k0) / span * w; };
    var base = h * 0.66, mpp = span * 1000 / w;  // метров на пиксель по горизонтали
    var Y = function (k) { return base - (hAt(pts, k) - href) / mpp * vex; };
    var col = { sky: css("--sky"), ground: css("--ground"), rail: css("--rail"), fg: css("--fg"), muted: css("--muted"), panel: css("--panel"),
      limit: css("--limit"), signal: css("--signal"), track: css("--track"), ghost: css("--ghost"), line: css("--line"), ok: css("--ok"), bg: css("--bg") };
    var wet = S.weather !== "dry", dark = (getComputedStyle(document.documentElement).colorScheme || "").indexOf("dark") >= 0;
    // небо, солнце, облака
    var skyTop = dark ? "#0d1724" : "#9cc3e6", skyLow = dark ? "#26384a" : "#e8f1f8";
    if (wet) { skyTop = dark ? "#151c24" : "#9aa7b4"; skyLow = dark ? "#2b333c" : "#d3d9df"; }
    var g = x.createLinearGradient(0, 0, 0, h); g.addColorStop(0, skyTop); g.addColorStop(0.75, skyLow);
    x.fillStyle = g; x.fillRect(0, 0, w, h);
    if (!wet && !dark) { x.fillStyle = "#fff6d8"; x.beginPath(); x.arc(w * 0.85, h * 0.16, Math.min(w, h) * 0.06, 0, 6.3); x.fill(); }
    x.fillStyle = dark ? "#3a4757" : "#ffffff"; x.globalAlpha = wet ? 0.5 : 0.8;
    for (var ci = 0; ci < 6; ci++) { var cx = ((ci * 233 - S.km * 1000 / mpp * 0.05) % (w + 240) + w + 240) % (w + 240) - 120, cy = h * (0.08 + 0.14 * hash(ci)), cw = 50 + 60 * hash(ci + 5);
      x.beginPath(); x.ellipse(cx, cy, cw, cw * 0.24, 0, 0, 6.3); x.ellipse(cx + cw * 0.35, cy - cw * 0.12, cw * 0.45, cw * 0.22, 0, 0, 6.3); x.fill(); }
    x.globalAlpha = 1;
    // дальний план: горы, холмы или город (параллакс 0,15)
    var par = 0.15, off = S.km * 1000 / mpp * par, i, n;
    x.fillStyle = col.muted; x.globalAlpha = L.id === "ch_gotthard" ? 0.32 : 0.18;
    x.beginPath(); x.moveTo(0, h);
    for (i = -1; i <= Math.ceil(w / 40) + 1; i++) {
      var gx = i * 40 - (off % 40), idx = Math.floor(off / 40) + i, r = hash(idx + (L.id === "jp_tokaido" ? 99 : 0));
      var top = L.id === "ch_gotthard" ? h * (0.08 + 0.3 * r) : L.id === "jp_tokaido" ? h * (0.34 + 0.14 * r) : h * (0.3 + 0.12 * r);
      if (L.id === "jp_tokaido") { x.lineTo(gx, top); x.lineTo(gx + 40, top); } else x.lineTo(gx + 20, top);
    }
    x.lineTo(w, h); x.closePath(); x.fill();
    if (L.id === "ch_gotthard") {  // снег на вершинах
      x.fillStyle = col.panel; x.globalAlpha = 0.5;
      for (i = -1; i <= Math.ceil(w / 40) + 1; i++) { var sx = i * 40 - (off % 40) + 20, rr = hash(Math.floor(off / 40) + i), tp = h * (0.08 + 0.3 * rr);
        if (rr < 0.45) { x.beginPath(); x.moveTo(sx, tp); x.lineTo(sx - 7, tp + 9); x.lineTo(sx + 7, tp + 9); x.closePath(); x.fill(); } }
    }
    x.globalAlpha = 1;
    // средний план: деревья (параллакс 0,5)
    var p2 = 0.5, off2 = S.km * 1000 / mpp * p2;
    x.fillStyle = col.ok; x.globalAlpha = 0.28;
    for (i = -1; i <= Math.ceil(w / 26) + 1; i++) { var tx = i * 26 - (off2 % 26), ri = hash(Math.floor(off2 / 26) + i + 7);
      if (ri < 0.55) { var th = 10 + 14 * ri, ty = base - 6 + 10 * hash(i + Math.floor(off2 / 26)); x.beginPath(); x.moveTo(tx, ty - th); x.lineTo(tx - 6, ty); x.lineTo(tx + 6, ty); x.closePath(); x.fill(); } }
    x.globalAlpha = 1;
    // земля под путём
    var N = 80, ks = [];
    for (i = 0; i <= N; i++) ks.push(k0 + span * i / N);
    x.beginPath(); x.moveTo(0, h);
    ks.forEach(function (k) { x.lineTo(X(k), Y(k) + 5); }); x.lineTo(w, h); x.closePath();
    var gg = x.createLinearGradient(0, base - 20, 0, h); gg.addColorStop(0, dark ? "#24342a" : "#9fbf86"); gg.addColorStop(1, dark ? "#1a221c" : "#7d9a66"); x.fillStyle = gg; x.fill();
    // балласт: трапеция под путём
    x.beginPath(); ks.forEach(function (k, j) { var yy = Y(k) + 1; if (j) x.lineTo(X(k), yy); else x.moveTo(X(k), yy); });
    for (var bi = ks.length - 1; bi >= 0; bi--) x.lineTo(X(ks[bi]), Y(ks[bi]) + 9);
    x.closePath(); x.fillStyle = dark ? "#4a4f55" : "#a59f96"; x.fill();
    // насыпь и рельс
    x.beginPath(); ks.forEach(function (k, j) { var yy = Y(k) + 2; if (j) x.lineTo(X(k), yy); else x.moveTo(X(k), yy); });
    x.strokeStyle = col.muted; x.lineWidth = 4; x.globalAlpha = 0.5; x.stroke(); x.globalAlpha = 1;
    x.beginPath(); ks.forEach(function (k, j) { var yy = Y(k); if (j) x.lineTo(X(k), yy); else x.moveTo(X(k), yy); });
    x.strokeStyle = col.rail; x.lineWidth = 2; x.stroke();
    // шпалы каждые 15 м: видно движение
    x.strokeStyle = col.rail; x.lineWidth = 1; x.globalAlpha = 0.45;
    for (var m = Math.ceil(k0 * 1000 / 15) * 15; m <= k1 * 1000; m += 15) { var kk = m / 1000, px = X(kk), py = Y(kk); x.beginPath(); x.moveTo(px, py); x.lineTo(px, py + 4); x.stroke(); }
    x.globalAlpha = 1;
    // опоры контактной сети каждые 60 м и провод
    var poleTop = 36;
    x.strokeStyle = col.muted; x.lineWidth = 1.5;
    for (m = Math.ceil(k0 * 1000 / 60) * 60; m <= k1 * 1000; m += 60) { kk = m / 1000; px = X(kk); py = Y(kk); x.beginPath(); x.moveTo(px, py); x.lineTo(px, py - poleTop); x.lineTo(px + 6, py - poleTop); x.stroke(); }
    x.beginPath(); ks.forEach(function (k, j) { var yy = Y(k) - poleTop + 4; if (j) x.lineTo(X(k), yy); else x.moveTo(X(k), yy); }); x.lineWidth = 0.8; x.stroke();
    // станции: платформа и здание
    L.stations.forEach(function (st) {
      if (st.km < k0 - 0.5 || st.km > k1 + 0.5) return;
      var a = st.km - 0.4, b = st.km + 0.02;
      x.fillStyle = col.line; x.strokeStyle = col.muted; x.lineWidth = 1; x.beginPath(); x.moveTo(X(a), Y(a) + 5); x.lineTo(X(b), Y(b) + 5); x.lineTo(X(b), Y(b) + 12); x.lineTo(X(a), Y(a) + 12); x.closePath(); x.fill(); x.stroke();
      var bx = X(st.km - 0.2), by = Y(st.km - 0.2);
      x.fillStyle = dark ? "#3b4350" : "#e9e3d6"; x.strokeStyle = dark ? "#59616b" : "#8f8676"; x.lineWidth = 1;
      x.fillRect(bx - 34, by - 40, 68, 30); x.strokeRect(bx - 34, by - 40, 68, 30);
      x.fillStyle = dark ? "#6b3a33" : "#a5503f"; x.beginPath(); x.moveTo(bx - 40, by - 40); x.lineTo(bx, by - 56); x.lineTo(bx + 40, by - 40); x.closePath(); x.fill();
      x.fillStyle = dark ? "#f2d38a" : "#9cc3e6"; for (var wi = -26; wi <= 18; wi += 11) x.fillRect(bx + wi, by - 32, 6, 8);
      x.strokeStyle = dark ? "#8f9aa6" : "#5d6772"; x.beginPath(); x.moveTo(X(a), Y(a) - 24); x.lineTo(X(b), Y(b) - 24); x.stroke();
      x.fillStyle = "#1f4f8f"; x.fillRect(bx - 32, by - 74, 64, 14);
      x.fillStyle = "#ffffff"; x.font = "600 10px " + css("--sans"); x.textAlign = "center"; x.fillText(st.name.length > 14 ? st.name.slice(0, 13) + "…" : st.name, bx, by - 63.5);
      var mx = X(st.km), my = Y(st.km); x.fillStyle = col.signal; x.fillRect(mx - 1, my - 14, 2, 14); x.textAlign = "left";
    });
    // щиты ограничений у начала каждой зоны
    (S.zones || []).forEach(function (z) {
      var a = z[0] / 1000; if (a < k0 || a > k1) return;
      var px = X(a), py = Y(a), kind = z[3];
      if (kind === "signal") {
        x.fillStyle = col.fg; x.fillRect(px - 1, py - 40, 2, 40);
        x.fillStyle = col.fg; x.fillRect(px - 5, py - 54, 10, 16);
        x.fillStyle = col.signal; x.beginPath(); x.arc(px, py - 49, 3.2, 0, 6.3); x.fill();
        x.fillStyle = col.muted; x.beginPath(); x.arc(px, py - 42, 2.4, 0, 6.3); x.fill();
        return;
      }
      x.fillStyle = col.fg; x.fillRect(px - 1, py - 30, 2, 30);
      x.fillStyle = kind === "temp" ? col.signal : col.panel; x.strokeStyle = col.fg; x.lineWidth = 1.2;
      x.fillRect(px - 15, py - 48, 30, 18); x.strokeRect(px - 15, py - 48, 30, 18);
      x.fillStyle = col.fg; x.font = "700 11px " + css("--mono"); x.textAlign = "center"; x.fillText(String(z[2]), px, py - 35); x.textAlign = "left";
    });
    // поезда
    function train(km, ghost, gcol) {
      var look = LOOK[L.id] || LOOK.de_krm, len = S.T.length_m / 1000, a = km - len, carL = look.car / 1000;
      var gc = gcol || col.ghost, bodyCol = ghost ? gc : css(look.body), stripe = ghost ? gc : css(look.stripe);
      x.globalAlpha = ghost ? 0.45 : 1;
      var ncar = Math.max(1, Math.round(len / carL)), cl = len / ncar;
      if (S.pusher && look.loco) {  // толкач: второй локомотив в хвосте
        var pa = a - 0.022, pb = a - 0.002;
        if (pb > k0 && pa < k1) { var qa = X(pa), qya = Y(pa), qb = X(pb), qyb = Y(pb), qang = Math.atan2(qyb - qya, qb - qa), ql = Math.hypot(qb - qa, qyb - qya);
          x.save(); x.translate(qa, qya - 2); x.rotate(qang); x.fillStyle = ghost ? col.ghost : css("--limit"); x.strokeStyle = ghost ? col.ghost : col.fg; x.lineWidth = 1;
          x.fillRect(0, -20, ql, 20); x.strokeRect(0, -20, ql, 20); x.beginPath(); x.moveTo(ql * 0.4, -20); x.lineTo(ql * 0.5, -29); x.lineTo(ql * 0.64, -29); x.stroke(); x.restore(); } }
      for (var c = 0; c < ncar; c++) {
        var ka = a + c * cl + cl * 0.04, kb = a + (c + 1) * cl - cl * 0.04;
        if (kb < k0 - 0.05 || ka > k1 + 0.05) continue;
        var xa = X(ka), ya = Y(ka), xb = X(kb), yb = Y(kb), ang = Math.atan2(yb - ya, xb - xa), lenPx = Math.hypot(xb - xa, yb - ya);
        var isLoco = (look.loco && c === ncar - 1), hgt = isLoco ? 20 : (look.loco ? 16 : 18);
        x.save(); x.translate(xa, ya - 2); x.rotate(ang);
        x.fillStyle = isLoco && !ghost ? css("--limit") : bodyCol; x.strokeStyle = ghost ? gc : col.fg; x.lineWidth = 1;
        x.beginPath();
        if (look.nose && c === ncar - 1) { x.moveTo(0, -hgt); x.lineTo(lenPx * 0.62, -hgt); x.quadraticCurveTo(lenPx, -hgt * 0.7, lenPx, 0); x.lineTo(0, 0); }
        else if (look.nose && c === 0) { x.moveTo(lenPx, -hgt); x.lineTo(lenPx * 0.38, -hgt); x.quadraticCurveTo(0, -hgt * 0.7, 0, 0); x.lineTo(lenPx, 0); }
        else { x.rect(0, -hgt, lenPx, hgt); }
        x.closePath(); x.fill(); x.stroke();
        if (!ghost) {
          x.fillStyle = stripe; x.fillRect(lenPx * 0.06, -6, lenPx * 0.88, 2.5);
          if (!look.loco || isLoco) { x.fillStyle = col.sky; for (var wv = 0.12; wv < 0.86; wv += 0.15) x.fillRect(lenPx * wv, -hgt + 4, lenPx * 0.09, 5); }
          x.fillStyle = col.fg; x.beginPath(); x.arc(lenPx * 0.16, 1, 2.4, 0, 6.3); x.fill(); x.beginPath(); x.arc(lenPx * 0.84, 1, 2.4, 0, 6.3); x.fill();
        }
        if ((look.pant.indexOf(c) >= 0 && !look.loco) || isLoco) { x.strokeStyle = ghost ? col.ghost : col.fg; x.beginPath(); x.moveTo(lenPx * 0.4, -hgt); x.lineTo(lenPx * 0.5, -hgt - 9); x.lineTo(lenPx * 0.64, -hgt - 9); x.stroke(); }
        x.restore();
      }
      x.globalAlpha = 1;
    }
    if (S.ghostKm !== null && S.ghostKm !== undefined) train(S.ghostKm, true);
    (S.ghosts || []).forEach(function (gh) { if (gh.km !== null && gh.km !== undefined) train(gh.km, true, gh.color); });
    train(S.km, false);
    // тоннель поверх пути
    (TUNNELS[L.id] || []).forEach(function (tn) {
      var a = Math.max(k0, tn[0]), b = Math.min(k1, tn[1]); if (b <= a) return;
      x.fillStyle = col.muted; x.globalAlpha = 0.85;
      x.beginPath(); x.moveTo(X(a), Y(a) - 30);
      for (var j = 0; j <= 30; j++) { var kj = a + (b - a) * j / 30; x.lineTo(X(kj), Y(kj) - 30 - 30 * hash(Math.floor(kj * 20))); }
      x.lineTo(X(b), 0); x.lineTo(X(a), 0); x.closePath(); x.fill();
      x.beginPath(); for (j = 0; j <= 30; j++) { kj = a + (b - a) * j / 30; var yy2 = Y(kj) - 30; if (j) x.lineTo(X(kj), yy2); else x.moveTo(X(kj), yy2); }
      for (j = 30; j >= 0; j--) { kj = a + (b - a) * j / 30; x.lineTo(X(kj), Y(kj) + 6); } x.closePath(); x.fillStyle = col.fg; x.globalAlpha = 0.55; x.fill();
      x.globalAlpha = 1;
      [tn[0], tn[1]].forEach(function (pk) { if (pk < k0 || pk > k1) return; var qx = X(pk), qy = Y(pk); x.strokeStyle = col.fg; x.lineWidth = 3; x.beginPath(); x.arc(qx, qy - 6, 22, Math.PI, 2 * Math.PI); x.stroke(); });
    });
    // осадки
    if (wet) {
      var sd = Math.floor((S.t || 0) * 4);
      x.strokeStyle = S.weather === "wet" ? col.track : col.signal; x.fillStyle = col.signal; x.globalAlpha = 0.45; x.lineWidth = 1;
      for (i = 0; i < 70; i++) { var rx = ((i * 97 + sd * 17) % (w + 30)) - 15, ry = ((i * 53 + sd * 31) % h);
        if (S.weather === "wet") { x.beginPath(); x.moveTo(rx, ry); x.lineTo(rx - 4, ry + 11); x.stroke(); }
        else { x.beginPath(); x.ellipse(rx, ry, 2.6, 1.4, i, 0, 6.3); x.fill(); } }
      x.globalAlpha = 1;
    }
    // подписи
    x.fillStyle = col.fg; x.font = "600 12px " + css("--mono");
    if (S.caption) { x.fillStyle = col.panel; x.globalAlpha = 0.75; var tw = x.measureText(S.caption).width; x.fillRect(4, h - 22, tw + 8, 18); x.globalAlpha = 1; x.fillStyle = col.fg; x.fillText(S.caption, 8, h - 8); }
  }

  // полоса всего маршрута: профиль, станции, ты и Extella
  function strip(cv, L, km, ghostKm, more) {
    var dpr = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
    if (!w || !h) return;
    if (cv.width !== Math.round(w * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    var x = cv.getContext("2d"); x.setTransform(dpr, 0, 0, dpr, 0, 0);
    var pts = elevOf(L), st = L.stations, k0 = st[0].km, k1 = st[st.length - 1].km;
    var hs = pts.map(function (p) { return p[1]; }), hmin = Math.min.apply(null, hs), hmax = Math.max.apply(null, hs); if (hmax - hmin < 1) hmax = hmin + 1;
    var X = function (k) { return 6 + (k - k0) / (k1 - k0) * (w - 12); }, Y = function (hh) { return h - 8 - (hh - hmin) / (hmax - hmin) * (h - 18); };
    x.clearRect(0, 0, w, h);
    x.beginPath(); pts.forEach(function (p, i) { if (p[0] < k0 || p[0] > k1 + 0.01) return; if (i) x.lineTo(X(p[0]), Y(p[1])); else x.moveTo(X(p[0]), Y(p[1])); });
    x.strokeStyle = css("--muted"); x.lineWidth = 1.5; x.stroke();
    st.forEach(function (s) { if (s.pass) return; x.fillStyle = css("--fg"); x.fillRect(X(s.km) - 1, h - 8, 2, 6); });
    function dot(k, c, r) { x.fillStyle = c; x.beginPath(); x.arc(X(k), Y(hAt(pts, k)), r, 0, 6.3); x.fill(); }
    if (ghostKm !== null && ghostKm !== undefined) dot(ghostKm, css("--ghost"), 4.5);
    (more || []).forEach(function (g) { if (g.km !== null && g.km !== undefined) dot(g.km, g.color, 4); });
    dot(km, css("--fg"), 4.5);
  }
  root.TrainScene = { draw: draw, strip: strip };
})(this);

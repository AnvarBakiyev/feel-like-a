// Кабина машиниста: вид вперёд через лобовое стекло и дисплей скорости на пульте.
// Рисует только состояние симулятора и открытые данные участка; опоры, деревья и горы детерминированы от километра.
(function (root) {
  "use strict";
  function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
  function hash(n) { var x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }
  function fit(cv) {
    var dpr = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
    if (!w || !h) return null;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    var x = cv.getContext("2d"); x.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { x: x, w: w, h: h };
  }
  var TUN = { ch_gotthard: [[70.45, 85.453]] };
  function gradeAt(L, km) { var s = L.segments; for (var i = 0; i < s.length; i++) if (s[i].from_km <= km && km < s[i].to_km) return s[i].grade_permille; return 0; }

  function shade(hex, k) {  // осветлить (k>0) или затемнить (k<0) цвет #rrggbb
    var m = /^#?([0-9a-f]{6})$/i.exec(hex || ""); if (!m) return hex;
    var n = parseInt(m[1], 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    var f = function (c) { return Math.max(0, Math.min(255, Math.round(k > 0 ? c + (255 - c) * k : c * (1 + k)))); };
    return "rgb(" + f(r) + "," + f(g) + "," + f(b) + ")";
  }
  function front(cv, S) {
    var F = fit(cv); if (!F) return; var x = F.x, w = F.w, h = F.h;
    var col = { sky: css("--sky"), ground: css("--ground"), rail: css("--rail"), fg: css("--fg"), muted: css("--muted"), panel: css("--panel"),
      limit: css("--limit"), signal: css("--signal"), track: css("--track"), ghost: css("--ghost"), line: css("--line"), ok: css("--ok"), bg: css("--bg") };
    var dark = (getComputedStyle(document.documentElement).colorScheme || "").indexOf("dark") >= 0;
    var L = S.L, km = S.km, cam = 2.4, f = Math.max(h * 1.1, w * 0.8);
    var gNow = gradeAt(L, km), gAhead = gradeAt(L, km + 0.4);
    var hor = h * 0.42 + (gAhead - gNow) * 1.6;
    var P = function (dz, sx, sy) { var z = Math.max(1, dz); return [w / 2 + sx * f / z, hor + (cam - sy) * f / z]; };
    var bend = function (dz) { if (L.id !== "ch_gotthard") return 0; var k = km + dz / 1000; return 0.0009 * Math.sin(k * 2.1) * dz * dz / 100; };
    var inTunnel = (TUN[L.id] || []).some(function (tn) { return km >= tn[0] && km <= tn[1]; });
    var m0 = km * 1000, i, m, dz;
    var skyTop = dark ? "#0d1724" : "#9cc3e6", skyLow = dark ? "#26384a" : "#e8f1f8";
    var grass = dark ? "#1f2b22" : "#9fbf86", grassFar = dark ? "#2a3a33" : "#c3d6b4";
    if (S.weather !== "dry") { skyTop = dark ? "#151c24" : "#9aa7b4"; skyLow = dark ? "#2b333c" : "#d3d9df"; }
    if (inTunnel) {
      // тоннель: тёмный свод, лампы на стенах проносятся мимо
      x.fillStyle = "#07090c"; x.fillRect(0, 0, w, h);
      for (m = Math.ceil((m0 + 4) / 50) * 50; m < m0 + 900; m += 50) {
        dz = m - m0;
        [-2.6, 2.6].forEach(function (sx) { var p = P(dz, sx, 3.2), r = Math.max(1, 90 / dz); x.fillStyle = "#f2d38a"; x.globalAlpha = Math.max(0.15, 1 - dz / 900); x.beginPath(); x.arc(p[0], p[1], r, 0, 6.3); x.fill(); });
      }
      x.globalAlpha = 1;
      var ring = function (d) { var a = P(d, -3, 0), b = P(d, 3, 6.2); return [a[0], b[1], b[0] - a[0], a[1] - b[1]]; };
      x.strokeStyle = "#1c232b"; x.lineWidth = 1;
      for (m = Math.ceil((m0 + 4) / 25) * 25; m < m0 + 600; m += 25) { var rr = ring(m - m0); x.strokeRect(rr[0], rr[1], rr[2], rr[3]); }
    } else {
      // небо, солнце или облака, туман у горизонта
      var g = x.createLinearGradient(0, 0, 0, hor); g.addColorStop(0, skyTop); g.addColorStop(1, skyLow);
      x.fillStyle = g; x.fillRect(0, 0, w, hor + 1);
      if (S.weather === "dry" && !dark) { x.fillStyle = "#fff6d8"; x.globalAlpha = 0.9; x.beginPath(); x.arc(w * 0.78, hor * 0.32, Math.min(w, h) * 0.05, 0, 6.3); x.fill(); x.globalAlpha = 1; }
      x.fillStyle = dark ? "#3a4757" : "#ffffff"; x.globalAlpha = S.weather === "dry" ? 0.75 : 0.5;
      for (i = 0; i < 7; i++) { var cx = ((i * 211 + km * 4) % (w + 200)) - 100, cy = hor * (0.12 + 0.12 * hash(i)), cw = 60 + 70 * hash(i + 9);
        x.beginPath(); x.ellipse(cx, cy, cw, cw * 0.22, 0, 0, 6.3); x.ellipse(cx + cw * 0.35, cy - cw * 0.1, cw * 0.45, cw * 0.2, 0, 0, 6.3); x.fill(); }
      x.globalAlpha = 1;
      // горы с ледниками, холмы или город на горизонте
      var off = km * 6;
      var drawRidge = function (alpha, amp, seed, colr) {
        x.fillStyle = colr; x.globalAlpha = alpha; x.beginPath(); x.moveTo(0, hor + 1);
        for (var j = 0; j <= 30; j++) { var gx = j * w / 30, r = hash(Math.floor(j + off / (5 + seed)) + seed * 13); x.lineTo(gx, hor - h * amp * (0.3 + 0.7 * r)); }
        x.lineTo(w, hor + 1); x.closePath(); x.fill(); x.globalAlpha = 1;
      };
      if (L.id === "ch_gotthard") {
        drawRidge(1, 0.34, 1, dark ? "#2c3642" : "#8d9cab");
        x.fillStyle = dark ? "#cdd6df" : "#ffffff"; x.globalAlpha = 0.8;
        for (var j2 = 0; j2 <= 30; j2++) { var r2 = hash(Math.floor(j2 + off / 6) + 13); if (r2 > 0.6) { var px2 = j2 * w / 30, py2 = hor - h * 0.34 * (0.3 + 0.7 * r2); x.beginPath(); x.moveTo(px2, py2); x.lineTo(px2 - 9, py2 + 10); x.lineTo(px2 + 9, py2 + 10); x.closePath(); x.fill(); } }
        x.globalAlpha = 1;
        drawRidge(1, 0.16, 2, dark ? "#243028" : "#6f8a6a");
      } else if (L.id === "jp_tokaido") {
        drawRidge(1, 0.08, 3, dark ? "#2a3440" : "#a9b6c4");
        x.fillStyle = dark ? "#2f3a46" : "#b8c2cc";
        for (i = 0; i < 40; i++) { var bx = ((i * 37 + km * 30) % (w + 40)) - 20, bh = 6 + 22 * hash(i + Math.floor(km)), bw = 10 + 12 * hash(i + 3); x.fillRect(bx, hor - bh, bw, bh); }
      } else {
        drawRidge(1, 0.1, 4, dark ? "#2a3440" : "#a3b2a0");
        drawRidge(1, 0.05, 5, dark ? "#24302a" : "#86a07f");
      }
      // поля: полосы, сходящиеся к горизонту, светлее вдали
      var gg = x.createLinearGradient(0, hor, 0, h); gg.addColorStop(0, grassFar); gg.addColorStop(1, grass);
      x.fillStyle = gg; x.fillRect(0, hor, w, h - hor);
      x.strokeStyle = dark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.05)"; x.lineWidth = 1;
      for (i = -12; i <= 12; i++) { var e = P(6, i * 6, 0); x.beginPath(); x.moveTo(w / 2, hor); x.lineTo(e[0], e[1] + 300); x.stroke(); }
      for (m = Math.ceil(m0 / 40) * 40; m < m0 + 800; m += 40) { var yy = P(m - m0 + 1, 0, 0)[1]; x.beginPath(); x.moveTo(0, yy); x.lineTo(w, yy); x.stroke(); }
    }
    // балластная призма под рельсами
    x.fillStyle = inTunnel ? "#1b1f24" : (dark ? "#4a4f55" : "#a59f96");
    x.beginPath(); var bl = P(3, -2.1, 0), br = P(3, 2.1, 0), fl = P(2000, -2.1, 0), fr = P(2000, 2.1, 0);
    x.moveTo(bl[0], h + 40); x.lineTo(fl[0], fl[1]); x.lineTo(fr[0], fr[1]); x.lineTo(br[0], h + 40); x.closePath(); x.fill();
    // шпалы
    x.strokeStyle = inTunnel ? "#2d333a" : (dark ? "#6b6258" : "#6d5b48");
    for (m = Math.ceil((m0 + 3) / 6) * 6; m < m0 + 260; m += 6) {
      dz = m - m0; if (dz < 3) continue; var b = bend(dz), p1 = P(dz, -1.3 + b, 0), p2 = P(dz, 1.3 + b, 0);
      x.globalAlpha = Math.max(0.2, 1 - dz / 260); x.lineWidth = Math.max(0.6, Math.min(7, 40 / dz)); x.beginPath(); x.moveTo(p1[0], p1[1]); x.lineTo(p2[0], p2[1]); x.stroke();
    }
    x.globalAlpha = 1;
    // рельсы: тёмная подошва и блестящая головка
    [-0.72, 0.72].forEach(function (sx) {
      ["#3b3f45", inTunnel ? "#7d8691" : "#d9dee4"].forEach(function (c, k) {
        x.beginPath();
        for (var d = 3; d <= 2000; d *= 1.06) { var p = P(d, sx + bend(d) + (k ? 0 : 0.02), 0.15); if (d === 3) x.moveTo(p[0], p[1]); else x.lineTo(p[0], p[1]); }
        x.strokeStyle = c; x.lineWidth = k ? 1.6 : 3.2; x.stroke();
      });
    });
    if (!inTunnel) {
      // деревья и кусты по обе стороны (детерминированы от метра)
      var trees = [];
      for (m = Math.ceil((m0 + 8) / 23) * 23; m < m0 + 1100; m += 23) { var hv = hash(m * 0.37); if (hv > (L.id === "jp_tokaido" ? 0.75 : 0.45)) trees.push({ d: m - m0, s: (hv > 0.72 ? 1 : -1) * (7 + 14 * hash(m)), h: 5 + 9 * hash(m + 1), kind: L.id === "ch_gotthard" ? "pine" : "tree" }); }
      trees.reverse().forEach(function (t) {
        var base = P(t.d, t.s + bend(t.d), 0), top = P(t.d, t.s + bend(t.d), t.h), wpx = Math.max(1, (base[1] - top[1]) * 0.45);
        x.globalAlpha = Math.max(0.35, 1 - t.d / 1100);
        x.fillStyle = dark ? "#1d3324" : "#4f7a45";
        if (t.kind === "pine") { x.beginPath(); x.moveTo(top[0], top[1]); x.lineTo(base[0] - wpx * 0.6, base[1]); x.lineTo(base[0] + wpx * 0.6, base[1]); x.closePath(); x.fill(); }
        else { x.fillStyle = dark ? "#3a2c22" : "#6b513a"; x.fillRect(base[0] - wpx * 0.06, top[1] + (base[1] - top[1]) * 0.55, wpx * 0.12, (base[1] - top[1]) * 0.45);
          x.fillStyle = dark ? "#1d3324" : "#5b8a4d"; x.beginPath(); x.ellipse(top[0], top[1] + (base[1] - top[1]) * 0.35, wpx * 0.5, (base[1] - top[1]) * 0.38, 0, 0, 6.3); x.fill(); }
      });
      x.globalAlpha = 1;
    }
    // опоры контактной сети через 60 м и провод
    var poles = [];
    for (m = Math.ceil((m0 + 6) / 60) * 60; m < m0 + 1200; m += 60) poles.push(m - m0);
    poles.reverse().forEach(function (d) {
      [-3.2, 3.2].forEach(function (sx) {
        var b0 = P(d, sx + bend(d), 0), b1 = P(d, sx + bend(d), 7.5), arm = P(d, (sx > 0 ? 1 : -1) * 0.2 + bend(d), 7.1);
        x.strokeStyle = inTunnel ? "#39414b" : (dark ? "#8f9aa6" : "#5d6772"); x.lineWidth = Math.max(0.6, 50 / d); x.globalAlpha = Math.max(0.3, 1 - d / 1200);
        x.beginPath(); x.moveTo(b0[0], b0[1]); x.lineTo(b1[0], b1[1]); x.lineTo(arm[0], arm[1]); x.stroke();
      });
    });
    x.globalAlpha = 1;
    x.beginPath(); for (var d2 = 6; d2 <= 1500; d2 *= 1.08) { var pw = P(d2, bend(d2), 6.6); if (d2 === 6) x.moveTo(pw[0], pw[1]); else x.lineTo(pw[0], pw[1]); }
    x.strokeStyle = dark ? "#8f9aa6" : "#3d454e"; x.lineWidth = 1; x.stroke();
    // объекты впереди
    var objs = [];
    (S.stations || []).forEach(function (st) { var a = st.km * 1000 - 400 - m0, b = st.km * 1000 - m0; if (b > 2 && a < 1600) objs.push({ d: Math.max(3, a), kind: "platform", a: Math.max(3, a), b: b, name: st.name }); });
    (S.zones || []).forEach(function (z) { var d = z[0] - m0; if (d > 3 && d < 1600) objs.push({ d: d, kind: z[3], lim: z[2] }); });
    (TUN[L.id] || []).forEach(function (tn) { var d = tn[0] * 1000 - m0; if (d > 3 && d < 1600) objs.push({ d: d, kind: "portal" }); });
    if (S.ghostAheadM !== null && S.ghostAheadM !== undefined && S.ghostAheadM > 15 && S.ghostAheadM < 1600) objs.push({ d: S.ghostAheadM, kind: "ghost", color: col.ghost, label: "Extella" });
    (S.ghosts || []).forEach(function (gh) { if (gh.d > 15 && gh.d < 1600) objs.push({ d: gh.d, kind: "ghost", color: gh.color, label: gh.label }); });
    if (S.stopM !== null && S.stopM !== undefined && S.stopM > 3 && S.stopM < 1600) objs.push({ d: S.stopM, kind: "stop" });
    objs.sort(function (a, b) { return b.d - a.d; });
    x.textAlign = "center";
    objs.forEach(function (o) {
      var bd = bend(o.d);
      if (o.kind === "platform") {
        // платформа: край, покрытие, навес на столбах, павильон, отметка остановки
        var q = function (d, sx, sy) { return P(d, sx + bend(d), sy); };
        var pa = q(o.a, 1.9, 0.9), pb = q(o.b, 1.9, 0.9), pc = q(o.b, 7, 0.9), pd = q(o.a, 7, 0.9);
        x.fillStyle = dark ? "#59616b" : "#c9ced3"; x.beginPath(); x.moveTo(pa[0], pa[1]); x.lineTo(pb[0], pb[1]); x.lineTo(pc[0], pc[1]); x.lineTo(pd[0], pd[1]); x.closePath(); x.fill();
        var ea = q(o.a, 1.9, 0), eb = q(o.b, 1.9, 0);
        x.fillStyle = dark ? "#3a4048" : "#8f979f"; x.beginPath(); x.moveTo(pa[0], pa[1]); x.lineTo(pb[0], pb[1]); x.lineTo(eb[0], eb[1]); x.lineTo(ea[0], ea[1]); x.closePath(); x.fill();
        x.strokeStyle = col.signal; x.lineWidth = 1; x.beginPath(); var ya = q(o.a, 2.2, 0.91), yb = q(o.b, 2.2, 0.91); x.moveTo(ya[0], ya[1]); x.lineTo(yb[0], yb[1]); x.stroke();
        var ca = q(o.a + 60, 3.2, 4.4), cb = q(o.b, 3.2, 4.4), cc = q(o.b, 6.5, 4.4), cd = q(o.a + 60, 6.5, 4.4);
        if (o.b > o.a + 60) { x.fillStyle = dark ? "#2b323b" : "#6c7883"; x.beginPath(); x.moveTo(ca[0], ca[1]); x.lineTo(cb[0], cb[1]); x.lineTo(cc[0], cc[1]); x.lineTo(cd[0], cd[1]); x.closePath(); x.fill();
          x.strokeStyle = dark ? "#2b323b" : "#6c7883"; for (var cpos = o.a + 60; cpos < o.b; cpos += 30) { var c0 = q(cpos, 4.8, 0.9), c1 = q(cpos, 4.8, 4.4); x.lineWidth = Math.max(0.5, 40 / cpos); x.beginPath(); x.moveTo(c0[0], c0[1]); x.lineTo(c1[0], c1[1]); x.stroke(); } }
        var sg = q(o.b, 2.6, 2.4), sz = Math.max(4, 1000 / Math.max(o.b, 5));
        if (o.b > 3) { x.fillStyle = col.signal; x.fillRect(sg[0] - sz * 0.12, sg[1], sz * 0.24, sz * 1.6);
          x.fillStyle = "#1f4f8f"; x.fillRect(sg[0] - sz * 1.3, sg[1] - sz * 0.9, sz * 2.6, sz * 0.9);
          x.fillStyle = "#ffffff"; x.font = "600 " + Math.max(7, Math.min(15, sz * 0.5)) + "px " + css("--sans"); x.fillText(o.name.length > 14 ? o.name.slice(0, 13) + "…" : o.name, sg[0], sg[1] - sz * 0.27); }
      } else if (o.kind === "perm" || o.kind === "temp") {
        var base = P(o.d, 2.8 + bd, 0), top = P(o.d, 2.8 + bd, 3.2), s = Math.max(3, 1100 / o.d);
        x.strokeStyle = "#3b3f45"; x.lineWidth = Math.max(0.8, 60 / o.d); x.beginPath(); x.moveTo(base[0], base[1]); x.lineTo(top[0], top[1]); x.stroke();
        x.fillStyle = o.kind === "temp" ? "#f2b33d" : "#ffffff"; x.strokeStyle = "#151a21"; x.lineWidth = Math.max(0.8, s * 0.1);
        x.beginPath(); x.moveTo(top[0], top[1] - s * 1.6); x.lineTo(top[0] + s, top[1] - s * 0.6); x.lineTo(top[0], top[1] + s * 0.4); x.lineTo(top[0] - s, top[1] - s * 0.6); x.closePath(); x.fill(); x.stroke();
        if (s > 5) { x.fillStyle = "#151a21"; x.font = "700 " + Math.min(18, s * 0.62) + "px " + css("--mono"); x.fillText(String(o.lim), top[0], top[1] - s * 0.38); }
      } else if (o.kind === "signal") {
        var sb = P(o.d, 3 + bd, 0), st2 = P(o.d, 3 + bd, 4.6), r = Math.max(1.5, 260 / o.d);
        x.strokeStyle = "#3b3f45"; x.lineWidth = Math.max(1, 70 / o.d); x.beginPath(); x.moveTo(sb[0], sb[1]); x.lineTo(st2[0], st2[1]); x.stroke();
        x.fillStyle = "#151a21"; x.fillRect(st2[0] - r * 1.7, st2[1] - r * 4.6, r * 3.4, r * 4.8);
        x.fillStyle = "#f2b33d"; x.shadowColor = "#f2b33d"; x.shadowBlur = r * 3; x.beginPath(); x.arc(st2[0], st2[1] - r * 3.2, r, 0, 6.3); x.fill(); x.shadowBlur = 0;
        x.fillStyle = "#3a4048"; x.beginPath(); x.arc(st2[0], st2[1] - r * 1.2, r * 0.85, 0, 6.3); x.fill();
      } else if (o.kind === "portal") {
        var l0 = P(o.d, -3.4 + bd, 0), r0 = P(o.d, 3.4 + bd, 0), t0 = P(o.d, bd, 6.6), wd = r0[0] - l0[0];
        x.fillStyle = dark ? "#3b4652" : "#7e8a96"; x.beginPath(); x.moveTo(l0[0] - wd * 2.5, l0[1]); x.lineTo(l0[0] - wd * 1.2, t0[1] - wd * 1.4); x.lineTo(r0[0] + wd * 1.2, t0[1] - wd * 1.6); x.lineTo(r0[0] + wd * 2.5, r0[1]); x.closePath(); x.fill();
        x.fillStyle = dark ? "#55606b" : "#a7aeb5"; x.fillRect(l0[0] - wd * 0.25, t0[1] - wd * 0.35, wd * 1.5, (l0[1] - t0[1]) + wd * 0.35);
        x.fillStyle = "#07090c"; x.beginPath(); x.moveTo(l0[0], l0[1]); x.lineTo(l0[0], t0[1] + (l0[1] - t0[1]) * 0.38); x.quadraticCurveTo(t0[0], t0[1] - (l0[1] - t0[1]) * 0.22, r0[0], t0[1] + (l0[1] - t0[1]) * 0.38); x.lineTo(r0[0], r0[1]); x.closePath(); x.fill();
      } else if (o.kind === "ghost") {
        var gl = P(o.d, -1.5 + bd, 0.5), gr = P(o.d, 1.5 + bd, 0.5), gt = P(o.d, bd, 4.1), gwd = gr[0] - gl[0], ght = gl[1] - gt[1];
        x.globalAlpha = 0.55; x.fillStyle = o.color || col.ghost; x.beginPath(); x.moveTo(gl[0], gl[1]); x.lineTo(gl[0], gt[1] + ght * 0.25); x.quadraticCurveTo(gl[0], gt[1], gl[0] + gwd * 0.25, gt[1]); x.lineTo(gr[0] - gwd * 0.25, gt[1]); x.quadraticCurveTo(gr[0], gt[1], gr[0], gt[1] + ght * 0.25); x.lineTo(gr[0], gr[1]); x.closePath(); x.fill();
        x.fillStyle = "#ff5a4f"; x.beginPath(); x.arc(gl[0] + gwd * 0.18, gl[1] - ght * 0.2, Math.max(1, gwd * 0.06), 0, 6.3); x.arc(gr[0] - gwd * 0.18, gl[1] - ght * 0.2, Math.max(1, gwd * 0.06), 0, 6.3); x.fill();
        x.globalAlpha = 1;
        if (gwd > 22) { x.fillStyle = "#ffffff"; x.font = "600 " + Math.min(14, gwd * 0.18) + "px " + css("--sans"); x.fillText(o.label || "Extella", (gl[0] + gr[0]) / 2, gt[1] + ght * 0.5); }
      } else if (o.kind === "stop") {
        var s1 = P(o.d, -1.6 + bd, 0.05), s2 = P(o.d, 1.6 + bd, 0.05);
        x.strokeStyle = "#3ccf7e"; x.lineWidth = 3; x.setLineDash([6, 4]); x.beginPath(); x.moveTo(s1[0], s1[1]); x.lineTo(s2[0], s2[1]); x.stroke(); x.setLineDash([]);
        if (s2[0] - s1[0] > 40) { x.fillStyle = "#3ccf7e"; x.font = "600 11px " + css("--sans"); x.fillText(S.stopLabel || "", (s1[0] + s2[0]) / 2, s1[1] - 6); }
      }
    });
    x.textAlign = "left";
    // туман у горизонта
    if (!inTunnel) { var fg = x.createLinearGradient(0, hor - 30, 0, hor + 40); fg.addColorStop(0, "rgba(0,0,0,0)"); fg.addColorStop(0.5, S.weather !== "dry" ? (dark ? "rgba(40,48,58,0.6)" : "rgba(220,226,232,0.65)") : (dark ? "rgba(38,56,74,0.25)" : "rgba(232,241,248,0.35)")); fg.addColorStop(1, "rgba(0,0,0,0)"); x.fillStyle = fg; x.fillRect(0, hor - 30, w, 70); }
    // стекло: дождь каплями или листья
    if (S.weather !== "dry" && !inTunnel) {
      var sd = Math.floor((S.t || 0) * 3);
      for (i = 0; i < 70; i++) { var rx = (i * 97 + sd * 13) % w, ry = (i * 53 + sd * 7) % h;
        if (S.weather === "wet") { x.fillStyle = "rgba(255,255,255,0.35)"; x.beginPath(); x.ellipse(rx, ry, 1.6, 2.6, 0, 0, 6.3); x.fill(); }
        else { x.fillStyle = i % 2 ? "#c9822f" : "#a8552b"; x.globalAlpha = 0.8; x.beginPath(); x.ellipse(rx, ry, 4, 2, i, 0, 6.3); x.fill(); x.globalAlpha = 1; } }
    }
    // рама стекла и нижний край приборной доски
    x.fillStyle = "#2a323c"; x.fillRect(0, 0, w, 5);
    var dg = x.createLinearGradient(0, h - 26, 0, h); dg.addColorStop(0, "rgba(35,42,51,0)"); dg.addColorStop(1, "rgba(35,42,51,0.95)"); x.fillStyle = dg; x.fillRect(0, h - 26, w, 26);
  }

  // Дисплей на пульте: стрелочный спидометр с меткой допустимой скорости, цель и расстояние до неё, список впереди.
  // D: {v, perm, limit, vmax, target:{speed, distM}|null, ahead:[{distM, speed}], atp, units:{kmh,km,m}}
  function dmi(cv, D) {
    var F = fit(cv); if (!F) return; var x = F.x, w = F.w, h = F.h;
    var dark = "#11161c", ink = "#e8edf3", dim = "#8b97a6", warn = "#f2b33d", red = "#f08783", ok = "#6fd09c", white = "#ffffff";
    x.fillStyle = dark; x.fillRect(0, 0, w, h);
    var R = Math.min(h * 0.44, w * 0.26), cx = R + 46, cy = h / 2 + 6;
    var a0 = Math.PI * 0.75, a1 = Math.PI * 2.25, vm = D.vmax;
    var ang = function (v) { return a0 + (a1 - a0) * Math.min(1, Math.max(0, v / vm)); };
    // шкала
    x.strokeStyle = dim; x.fillStyle = dim; x.font = "600 10px ui-monospace,Menlo,monospace"; x.textAlign = "center";
    var step = vm > 200 ? 50 : 20;
    for (var v = 0; v <= vm; v += step / 2) { var a = ang(v), big = v % step === 0;
      x.lineWidth = big ? 2 : 1; x.beginPath(); x.moveTo(cx + Math.cos(a) * (R - (big ? 10 : 6)), cy + Math.sin(a) * (R - (big ? 10 : 6))); x.lineTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R); x.stroke();
      if (big) x.fillText(String(v), cx + Math.cos(a) * (R - 20), cy + Math.sin(a) * (R - 20) + 3); }
    // допустимая: дуга по краю (серая до допустимой, красная выше)
    x.lineWidth = 6;
    x.strokeStyle = "#3a4552"; x.beginPath(); x.arc(cx, cy, R + 6, a0, ang(D.perm)); x.stroke();
    if (D.target && D.target.speed < D.perm) { x.strokeStyle = warn; x.beginPath(); x.arc(cx, cy, R + 6, ang(D.target.speed), ang(D.perm)); x.stroke(); }
    x.strokeStyle = red; x.lineWidth = 4; var ap = ang(D.perm); x.beginPath(); x.moveTo(cx + Math.cos(ap) * (R + 2), cy + Math.sin(ap) * (R + 2)); x.lineTo(cx + Math.cos(ap) * (R + 14), cy + Math.sin(ap) * (R + 14)); x.stroke();
    // стрелка
    var av = ang(D.v), over = D.v > D.perm + 0.5;
    x.strokeStyle = over ? red : white; x.lineWidth = 4; x.lineCap = "round"; x.beginPath(); x.moveTo(cx, cy); x.lineTo(cx + Math.cos(av) * (R - 14), cy + Math.sin(av) * (R - 14)); x.stroke(); x.lineCap = "butt";
    x.fillStyle = over ? red : white; x.beginPath(); x.arc(cx, cy, 16, 0, 6.3); x.fill();
    x.fillStyle = dark; x.font = "700 13px ui-monospace,Menlo,monospace"; x.fillText(String(Math.round(D.v)), cx, cy + 4.5);
    x.fillStyle = dim; x.font = "600 10px ui-monospace,Menlo,monospace"; x.fillText(D.units.kmh, cx, cy + R * 0.55);
    // слева: полоса расстояния до цели
    var bx = 12, by = 18, bh = h - 40;
    x.fillStyle = "#1c242d"; x.fillRect(bx, by, 14, bh);
    if (D.target) { var frac = Math.min(1, D.target.distM / 4000); x.fillStyle = warn; x.fillRect(bx, by + bh * (1 - frac), 14, bh * frac);
      x.fillStyle = ink; x.textAlign = "left"; x.font = "600 11px ui-monospace,Menlo,monospace";
      x.fillText(D.target.distM >= 1000 ? (D.target.distM / 1000).toFixed(1).replace(".", ",") + " " + D.units.km : Math.round(D.target.distM) + " " + D.units.m, bx - 2, h - 8); }
    // справа: впереди
    var px = cx + R + 30, pw = w - px - 10; x.textAlign = "left";
    if (pw > 90) {
      x.fillStyle = dim; x.font = "600 10px ui-monospace,Menlo,monospace"; x.fillText(D.units.ahead, px, 20);
      (D.ahead || []).slice(0, 5).forEach(function (r, i) {
        var yy = 40 + i * 22;
        x.fillStyle = r.speed < D.limit ? warn : ink; x.font = "700 15px ui-monospace,Menlo,monospace"; x.fillText(String(r.speed), px, yy);
        x.fillStyle = dim; x.font = "600 11px ui-monospace,Menlo,monospace";
        x.fillText(r.distM >= 1000 ? (r.distM / 1000).toFixed(1).replace(".", ",") + " " + D.units.km : Math.round(r.distM) + " " + D.units.m, px + 42, yy);
      });
      if (D.atp) { x.fillStyle = red; x.font = "700 12px ui-monospace,Menlo,monospace"; x.fillText(D.units.atp, px, h - 12); }
    }
    x.textAlign = "left";
  }
  root.TrainCab = { front: front, dmi: dmi };
})(this);

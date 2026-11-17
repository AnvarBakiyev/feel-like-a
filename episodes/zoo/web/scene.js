/* Живая карта зоопарка: холст, на котором нарисовано только состояние игры.
   Звери, смотрители и посетители двигаются сами; декорации (деревья, кусты) детерминированы
   от координаты и о скрытом ничего не говорят. Сцена не считает игру: всё, что она показывает,
   приходит снаружи через setEvening() и playDay(). */
(function (root) {
  "use strict";
  var TAU = Math.PI * 2;
  function rng(seed) { var s = seed >>> 0; return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function clamp(x, a, b) { return x < a ? a : x > b ? b : x; }
  function ease(t) { return t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }
  var PC = {}; function P(d) { return PC[d] || (PC[d] = new Path2D(d)); }

  /* ---------- раскладки: широкая (ноутбук) и высокая (телефон) ---------- */
  var LAYOUT = {
    wide: { w: 1000, h: 620,
      pool: [34, 70, 330, 215], birds: [394, 54, 212, 196], cats: [636, 70, 330, 215],
      yard: [34, 352, 292, 196], tropic: [674, 352, 292, 196],
      kiosk: [440, 318, 120, 86], gate: [416, 500, 168, 120], plaza: [500, 300] },
    tall: { w: 620, h: 940,
      pool: [24, 60, 572, 200], birds: [24, 300, 270, 190], cats: [326, 300, 270, 190],
      yard: [24, 530, 270, 190], tropic: [326, 530, 270, 190],
      kiosk: [250, 736, 120, 80], gate: [226, 822, 168, 118], plaza: [310, 506] }
  };
  var SECT = ["pool", "birds", "cats", "yard", "tropic"];
  var SEASON = {
    heat:   { grass: "#93c36c", grass2: "#a9d27f", grass3: "#7fb35c", tree: ["#3d8c50", "#2f7745", "#4fa05f"], bloom: null },
    spring: { grass: "#9ccc74", grass2: "#b4db8a", grass3: "#88bd63", tree: ["#58a862", "#f3a9c4", "#7cc07a"], bloom: "#f7c5d8" },
    flu:    { grass: "#a3b866", grass2: "#b7c877", grass3: "#8fa656", tree: ["#d98a2b", "#c9562a", "#e2b33c"], bloom: null }
  };
  var SHIRT = ["#e4572e", "#f2c230", "#3a86c8", "#8e5bd1", "#ef8fb1", "#39a0a0", "#f08a4b", "#5a6b7a", "#ffffff", "#c94f7c"];
  var SKIN = ["#f2d3b8", "#e0b08c", "#c68a62", "#8d5a3b", "#f6dfcb"];

  function Scene(canvas, opts) {
    opts = opts || {};
    this.cv = canvas; this.ctx = canvas.getContext("2d");
    this.layoutName = "wide"; this.L = LAYOUT.wide;
    this.season = SEASON[opts.scenario] || SEASON.heat;
    this.lang = opts.lang || "ru";
    this.t = 0; this.last = 0; this.running = false;
    this.mode = "idle";             // idle: день без чисел (первый экран), evening: вечер, day: день проигрывается
    this.clock = 0.5;               // 0 утро .. 1 вечер, для света
    this.weather = "clear";
    this.st = {};                   // состояние секций
    SECT.forEach(function (s) { this.st[s] = { keepers: [1, 1], closed: false, alert: null, show: false }; }, this);
    this.cashiers = [1, 1]; this.kiosk = [1, 1];
    this.people = []; this.fx = []; this.queue = 0; this.half = 0;
    this.cubs = false; this.dead = {};
    this.hover = null; this.focus = null;
    this.reduced = !!(root.matchMedia && root.matchMedia("(prefers-reduced-motion: reduce)").matches);
    this.decor = null; this.animals = null;
    this.day = null;                // проигрываемый день
    this.dusk = 0;                  // 0 день .. 1 вечер, меняется плавно
    this.onframe = null; this.onsfx = null;
    this.rt = 0;                    // настоящее время: вечером зверям время замедлено, а всплывающим мелочам нет
    this.react = {};                // до какого момента секция «отвечает» на нажатие
    this.build();
    this.resize();
  }

  Scene.prototype.setLayout = function (name) {
    if (!LAYOUT[name] || name === this.layoutName) return;
    this.layoutName = name; this.L = LAYOUT[name]; this.people = []; this.build(); this.resize();
  };
  Scene.prototype.setScenario = function (sc) { this.season = SEASON[sc] || SEASON.heat; this.build(); };
  Scene.prototype.rect = function (id) { var r = this.L[id]; return { x: r[0] / this.L.w, y: r[1] / this.L.h, w: r[2] / this.L.w, h: r[3] / this.L.h }; };

  Scene.prototype.resize = function () {
    var cv = this.cv, box = cv.getBoundingClientRect(), dpr = Math.min(2.5, root.devicePixelRatio || 1);
    var cw = Math.max(1, box.width), ch = cw * this.L.h / this.L.w;
    cv.width = Math.round(cw * dpr); cv.height = Math.round(ch * dpr);
    this.k = cv.width / this.L.w;
    if (!this.running) this.draw();
  };

  /* ---------- постоянные вещи: деревья, кусты, звери ---------- */
  Scene.prototype.build = function () {
    var L = this.L, R = rng(71), self = this, trees = [], i;
    function free(x, y, pad) {
      var ok = true;
      ["pool", "birds", "cats", "yard", "tropic", "kiosk", "gate"].forEach(function (s) {
        var r = L[s]; if (x > r[0] - pad && x < r[0] + r[2] + pad && y > r[1] - pad && y < r[1] + r[3] + pad) ok = false;
      });
      self.paths().forEach(function (p) {
        var ax = p[0], ay = p[1], bx = p[2], by = p[3], dx = bx - ax, dy = by - ay, t = clamp(((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy), 0, 1);
        var px = ax + dx * t, py = ay + dy * t; if (Math.hypot(x - px, y - py) < 34 + pad) ok = false;
      });
      if (Math.hypot(x - L.plaza[0], (y - L.plaza[1]) * 1.3) < 96) ok = false;
      var kk = L.kiosk, gg = L.gate;
      if (x > kk[0] - 34 && x < kk[0] + kk[2] + 34 && y > kk[1] - 30 && y < kk[1] + kk[3] + 44) ok = false;
      if (x > gg[0] - 30 && x < gg[0] + gg[2] + 30 && y > gg[1] - 40) ok = false;
      return ok;
    }
    for (i = 0; i < 420 && trees.length < (L.w > 700 ? 46 : 34); i++) {
      var x = R() * L.w, y = R() * L.h;
      if (free(x, y, 8)) trees.push({ x: x, y: y, s: .75 + R() * .7, c: Math.floor(R() * 3), sway: R() * TAU, bush: R() < .34 });
    }
    trees.sort(function (a, b) { return a.y - b.y; });
    var tufts = [];
    for (i = 0; i < 150; i++) tufts.push({ x: R() * L.w, y: R() * L.h, r: 14 + R() * 46, c: R() < .5 ? 1 : 2 });
    var flowers = [];
    for (i = 0; i < 70; i++) { var fx = R() * L.w, fy = R() * L.h; if (free(fx, fy, 2)) flowers.push({ x: fx, y: fy, c: Math.floor(R() * 4) }); }
    this.decor = { trees: trees, tufts: tufts, flowers: flowers };

    var A = {}, r;
    r = L.pool;   // морские львы плавают по овалу, пингвины стоят на камнях
    A.sealions = [0, 1, 2, 3].map(function (n) { return { ph: n * 1.7 + R(), sp: .42 + R() * .25, ry: .62 + R() * .3, jump: 0 }; });
    A.penguins = []; for (i = 0; i < 9; i++) A.penguins.push({ u: R(), v: R(), ph: R() * TAU, sp: .5 + R() * .8 });
    A.leopards = [{ ph: 0, sp: .22, lane: .42 }, { ph: 2.4, sp: .17, lane: .72 }];
    A.birds = []; for (i = 0; i < 9; i++) A.birds.push({ ph: R() * TAU, sp: .6 + R() * .9, rx: .2 + R() * .22, ry: .16 + R() * .2, c: Math.floor(R() * 4), cy: R() });
    A.flamingos = [{ u: .3 }, { u: .46 }, { u: .64 }];
    A.goats = []; for (i = 0; i < 6; i++) A.goats.push({ u: R(), v: R(), tu: R(), tv: R(), wait: R() * 3, c: Math.floor(R() * 3), flip: 1, ph: R() * TAU });
    A.lemurs = [{ ph: 0 }, { ph: 2.1 }];
    A.flies = []; for (i = 0; i < 7; i++) A.flies.push({ ph: R() * TAU, sp: .7 + R(), u: R(), v: R(), c: Math.floor(R() * 3) });
    this.animals = A;
  };

  Scene.prototype.paths = function () {
    var L = this.L, pl = L.plaza, g = L.gate, out = [];
    out.push([g[0] + g[2] / 2, g[1] + 20, pl[0], pl[1]]);
    SECT.forEach(function (s) { var a = anchor(L, s); out.push([pl[0], pl[1], a[0], a[1]]); });
    var k = L.kiosk; out.push([pl[0], pl[1], k[0] + k[2] / 2, k[1] + k[3] / 2]);
    return out;
  };
  function anchor(L, s) {   // точка, где дорожка подходит к секции
    var r = L[s], pl = L.plaza, cx = r[0] + r[2] / 2, cy = r[1] + r[3] / 2;
    var x = clamp(pl[0], r[0] + 30, r[0] + r[2] - 30), y = clamp(pl[1], r[1] + 20, r[1] + r[3] - 20);
    if (pl[1] > r[1] + r[3]) y = r[1] + r[3] + 12; else if (pl[1] < r[1]) y = r[1] - 12;
    if (pl[0] > r[0] + r[2]) x = r[0] + r[2] + 12; else if (pl[0] < r[0]) x = r[0] - 12;
    if (x > r[0] && x < r[0] + r[2] && y > r[1] && y < r[1] + r[3]) { x = cx; y = r[1] + r[3] + 12; }
    return [x, y];
  }
  Scene.prototype.viewSpot = function (s, R) {   // где стоит зритель у секции
    var L = this.L, r = L[s], a = anchor(L, s), spread = Math.min(r[2], 190);
    var horizontal = (a[1] <= r[1] || a[1] >= r[1] + r[3]);
    if (horizontal) return [clamp(a[0] + (R() - .5) * spread, r[0] + 14, r[0] + r[2] - 14), a[1] + (R() - .5) * 14 + (a[1] > r[1] ? 6 : -6)];
    return [a[0] + (R() - .5) * 14 + (a[0] > r[0] ? 6 : -6), clamp(a[1] + (R() - .5) * Math.min(r[3], 150), r[1] + 14, r[1] + r[3] - 14)];
  };

  /* ---------- состояние снаружи ---------- */
  Scene.prototype.setEvening = function (s) {
    // s: {weather, keepers:{pool:[у,д],..}, cashiers:[..], kiosk:[..], shows, alerts:{pool:"low"|..}, closed:{}, cubs, dead:{}}
    // закат играет только после дня; если вечер открыт сразу (новая игра, возврат на вкладку), свет уже вечерний
    if (this.mode !== "evening" && !this.justPlayed) this.dusk = 1;
    this.justPlayed = false;
    this.mode = "evening"; this.day = null; this.people = []; this.fx = []; this.queue = 0;
    this.apply(s);
  };
  Scene.prototype.setIdle = function (s) { this.mode = "idle"; this.day = null; this.apply(s || {}); if (!this.people.length) this.populate(this.L.w > 700 ? 26 : 16, Math.random); };
  Scene.prototype.apply = function (s) {
    var self = this;
    if (s.weather) this.weather = s.weather;
    SECT.forEach(function (id) {
      var st = self.st[id];
      if (s.keepers && s.keepers[id]) { var was = Math.max(st.keepers[0], st.keepers[1]), now = Math.max(s.keepers[id][0], s.keepers[id][1]); if (now > was) { st.popFrom = was; st.popT = self.rt; } st.keepers = s.keepers[id].slice(); }
      st.alert = (s.alerts && s.alerts[id]) || null;
      st.closed = !!(s.closed && s.closed[id]);
    });
    if (s.cashiers) this.cashiers = s.cashiers.slice();
    if (s.kiosk) this.kiosk = s.kiosk.slice();
    this.shows = s.shows == null ? (this.shows || 0) : s.shows;
    this.cubs = !!s.cubs; this.dead = s.dead || {};
    if (!this.running) this.draw();
  };
  Scene.prototype.playDay = function (rep, cb) {
    // rep: отчёт дня из симулятора. cb(p, done): p от 0 до 1
    var self = this, vis = rep.by_half ? rep.by_half.map(function (h) { return h.admitted; }) : [rep.visitors * .45, rep.visitors * .55];
    this.mode = "day"; this.people = []; this.fx = [];
    this.weather = rep.weather || "clear";
    var cap = this.L.w > 700 ? 86 : 60;
    this.day = { t: 0, dur: this.reduced ? 0.01 : 11, vis: vis, lost: rep.by_half ? rep.by_half.map(function (h) { return h.queue_lost; }) : [0, rep.queue_lost || 0],
      crowd: rep.by_half ? rep.by_half.map(function (h) { return h.crowding || 0; }) : [0, 0],
      shows: rep.shows || 0, cap: cap, spawned: 0, cb: cb, R: rng(1000 + (rep.day || 0) * 7), showDone: [false, false], coins: 0, rep: rep };
    SECT.forEach(function (id) {
      var st = self.st[id];
      if (rep.keepers_on && rep.keepers_on[id]) st.keepers = rep.keepers_on[id].slice();
      st.alert = rep.violations && rep.violations[id] ? "bad" : (rep.fed && rep.fed[id] != null && rep.fed[id] < .999 ? "hungry" : null);
    });
    var notes = rep.notes || [];
    this.st.birds.closed = notes.indexOf("hpai") >= 0; this.st.tropic.closed = notes.indexOf("tropic_closed") >= 0;
    this.st.pool.closedPm = notes.indexOf("pool_closed_pm") >= 0;
    this.half = 0; this.populate(Math.round(clamp(vis[0] * cap / 1500, 2, cap) * .4), this.day.R);
    var ev = rep.events || [], has = function (pfx) { return ev.some(function (e) { return e.indexOf(pfx) === 0; }); };
    if (has("school")) this.special("school"); if (has("vet_visit")) this.special("vet"); if (has("inspection")) this.special("inspector"); if (has("press")) this.special("press");
    this.start();
  };
  Scene.prototype.skipDay = function () { if (this.day) this.day.t = this.day.dur; };

  Scene.prototype.start = function () {
    if (this.reduced && this.mode !== "day") { this.dusk = this.mode === "evening" ? 1 : 0; this.draw(); return; }
    if (this.running) return; this.running = true; this.last = 0;
    var self = this;
    function frame(ts) {
      if (!self.running) return;
      var dt = self.last ? Math.min(.05, (ts - self.last) / 1000) : .016; self.last = ts;
      self.step(dt); self.draw();
      if (self.onframe) self.onframe();
      root.requestAnimationFrame(frame);
    }
    root.requestAnimationFrame(frame);
  };
  Scene.prototype.stop = function () { this.running = false; };

  /* ---------- шаг ---------- */
  Scene.prototype.sfx = function (n) { if (this.onsfx) this.onsfx(n); };
  Scene.prototype.step = function (dt) {
    this.rt += dt;
    this.t += dt * (this.mode === "evening" ? .28 : 1);
    var target = this.mode === "evening" ? 1 : 0;
    this.dusk += clamp(target - this.dusk, -dt * 1.6, dt * 1.6);
    var d = this.day, self = this, L = this.L;
    if (this.mode === "day" && d) {
      d.t += dt; var p = clamp(d.t / d.dur, 0, 1); this.clock = p; this.half = p < .5 ? 0 : 1;
      // сколько людей должно быть на карте сейчас: по принятым посетителям половины дня
      var scale = d.cap / 1500, want = Math.round(clamp(d.vis[this.half] * scale, 2, d.cap) * (p > .93 ? (1 - p) / .07 : 1));
      var alive = this.people.filter(function (q) { return !q.vip; }).length;
      if (alive < want && d.R() < dt * 26) this.spawn(d.R);
      // очередь у входа: люди, которые не дождались кассы
      this.queue = d.lost[this.half] > 0 ? clamp(Math.round(d.lost[this.half] / 12), 3, 16) : 0;
      // кормление при публике: в середине каждой половины, если назначено
      for (var h = 0; h < 2; h++) {
        var at = h === 0 ? .22 : .72;
        if (d.shows > h && !d.showDone[h] && p >= at) { d.showDone[h] = true; this.startShow(); }
      }
      if (this.show) { this.show.t += dt; if (this.show.t > 2.6) this.show = null; }
      // деньги всплывают у касс и киосков
      d.coins += dt * (d.vis[this.half] / 220);
      while (d.coins > 1) { d.coins -= 1; var gk = d.R() < .55 ? L.gate : L.kiosk;
        this.fx.push({ k: "coin", x: gk[0] + gk[2] * (.25 + d.R() * .5), y: gk[1] + gk[3] * .35, t: 0, life: 1.1 }); this.sfx("coin"); }
      if (d.cb) d.cb(p, false);
      if (p >= 1) { var cb = d.cb; this.day = null; this.justPlayed = true; this.mode = "evening"; this.people = []; this.queue = 0; this.show = null; if (cb) cb(1, true); }
    } else if (this.mode === "idle") {
      this.clock = .32 + .2 * Math.sin(this.t * .05);
      if (this.people.length < (L.w > 700 ? 34 : 22) && Math.random() < dt * 5) this.spawn(Math.random);
      if (!this.show && Math.random() < dt * .05) this.startShow();
      if (this.show) { this.show.t += dt; if (this.show.t > 2.6) this.show = null; }
    } else { this.clock = 1; }

    // люди идут по точкам; днём время сжато, поэтому идут быстрее
    var fast = this.mode === "day" ? 2.7 : 1;
    this.people.forEach(function (q) { walk(q, dt * fast); });
    this.people.forEach(function (q) { if (q.balloon && self.mode !== "evening" && Math.random() < dt * .012) { self.fx.push({ k: "balloon", x: q.x, y: q.y - 34, c: q.balloon, t: 0, life: 5, ph: Math.random() * TAU }); q.balloon = null; } });
    this.people = this.people.filter(function (q) { return !q.gone; });
    this.fx.forEach(function (f) { f.t += dt; }); this.fx = this.fx.filter(function (f) { return f.t < f.life; });

    // козы бродят
    var A = this.animals;
    A.goats.forEach(function (g) {
      if (g.wait > 0) { g.wait -= dt; return; }
      var dx = g.tu - g.u, dy = g.tv - g.v, dist = Math.hypot(dx, dy);
      if (dist < .02) { g.tu = Math.random(); g.tv = Math.random(); g.wait = 1 + Math.random() * 4; }
      else { g.u += dx / dist * dt * .06; g.v += dy / dist * dt * .06; g.flip = dx >= 0 ? 1 : -1; g.ph += dt * 8; }
    });
  };

  function walk(q, dt) {
    if (q.gone) return;
    if (q.wait > 0) { q.wait -= dt; return; }
    var tx = q.path[q.i][0], ty = q.path[q.i][1], dx = tx - q.x, dy = ty - q.y, dist = Math.hypot(dx, dy), v = q.v * dt;
    if (dist <= v) { q.x = tx; q.y = ty; q.i++; if (q.stops[q.i - 1]) q.wait = q.stops[q.i - 1]; if (q.i >= q.path.length) q.gone = true; }
    else { q.x += dx / dist * v; q.y += dy / dist * v; q.face = dx >= 0 ? 1 : -1; q.walk += dt * 9; }
  }
  Scene.prototype.populate = function (n, R) {   // зоопарк не начинается пустым: часть людей уже внутри
    for (var i = 0; i < n; i++) { this.spawn(R); var q = this.people[this.people.length - 1], T = R() * 14; for (var k = 0; k < 40 && T > 0; k++) { walk(q, .35); T -= .35; } }
    this.people = this.people.filter(function (q) { return !q.gone; });
  };
  Scene.prototype.spawn = function (R) {
    var L = this.L, g = L.gate, pl = L.plaza, self = this;
    var open = SECT.filter(function (s) { return !self.st[s].closed && !(s === "pool" && self.st.pool.closedPm && self.half === 1); });
    if (!open.length) open = ["yard"];
    var n = 1 + Math.floor(R() * 3), path = [[g[0] + g[2] * (.3 + R() * .4), g[1] + 30], [pl[0] + (R() - .5) * 30, pl[1] + (R() - .5) * 24]], stops = [0, 0];
    var showOn = this.show && this.show.t < 1.2;
    for (var i = 0; i < n; i++) {
      var s = showOn && i === 0 ? "pool" : open[Math.floor(R() * open.length)];
      var a = anchor(L, s), v = this.viewSpot(s, R);
      path.push([a[0] + (R() - .5) * 16, a[1] + (R() - .5) * 10]); stops.push(0);
      path.push(v); stops.push(1.2 + R() * 2.4);
      path.push([pl[0] + (R() - .5) * 40, pl[1] + (R() - .5) * 30]); stops.push(0);
      if (R() < .4 && this.kiosk[this.half] > 0) { var k = L.kiosk; path.push([k[0] + k[2] * (.2 + R() * .6), k[1] + k[3] + 8]); stops.push(1 + R() * 1.5); }
    }
    path.push([g[0] + g[2] * (.3 + R() * .4), g[1] + 40]); stops.push(0);
    path.push([g[0] + g[2] * (.3 + R() * .4), L.h + 30]); stops.push(0);
    var kid = R() < .28;
    this.people.push({ x: g[0] + g[2] * (.3 + R() * .4), y: L.h + 20, path: path, stops: stops, i: 0, wait: 0, v: 46 + R() * 22,
      shirt: SHIRT[Math.floor(R() * SHIRT.length)], skin: SKIN[Math.floor(R() * SKIN.length)], kid: kid, face: 1, walk: R() * 6, hat: R() < .2, um: Math.floor(R() * SHIRT.length), balloon: kid && R() < .45 ? SHIRT[Math.floor(R() * 6)] : null });
  };
  Scene.prototype.special = function (kind) {
    var L = this.L, g = L.gate, pl = L.plaza, self = this, gx = g[0] + g[2] / 2;
    function route(stops) { var path = [[gx, g[1] + 30], [pl[0], pl[1]]], st = [0, 0];
      stops.forEach(function (s) { var a = anchor(L, s); path.push([a[0], a[1]]); st.push(2.2); path.push([pl[0], pl[1]]); st.push(0); });
      path.push([gx, g[1] + 40]); st.push(0); path.push([gx, L.h + 30]); st.push(0); return { path: path, stops: st }; }
    if (kind === "school") {
      for (var i = 0; i < 9; i++) { var r = route(["yard", "birds"]); r.path = r.path.map(function (p) { return [p[0] + (i % 3) * 7 - 7, p[1] + Math.floor(i / 3) * 6]; });
        this.people.push({ x: gx + (i % 3) * 7 - 7, y: L.h + 20 + i * 5, path: r.path, stops: r.stops, i: 0, wait: i * .12, v: 40, shirt: i === 0 ? "#3a86c8" : "#f2c230", skin: SKIN[i % SKIN.length], kid: i !== 0, face: 1, walk: i, um: 1, vip: true }); }
    } else {
      var r2 = route(kind === "vet" ? ["pool", "cats"] : kind === "press" ? ["cats"] : ["pool", "birds", "cats", "tropic", "yard"]);
      this.people.push({ x: gx, y: L.h + 20, path: r2.path, stops: r2.stops, i: 0, wait: .4, v: kind === "inspector" ? 62 : 48, shirt: kind === "vet" ? "#ffffff" : kind === "press" ? "#2b2a2c" : "#3b4a66", skin: SKIN[1], kid: false, face: 1, walk: 0, um: 2, vip: true, role: kind });
    }
  };
  Scene.prototype.startShow = function () {
    if (this.st.pool.closed || this.dead.pool) return;
    this.show = { t: 0 }; this.animals.sealions[0].jump = 1; this.sfx("show");
    var r = this.L.pool; for (var i = 0; i < 12; i++) this.fx.push({ k: "splash", x: r[0] + r[2] * .5 + (Math.random() - .5) * 40, y: r[1] + r[3] * .55, vx: (Math.random() - .5) * 60, vy: -40 - Math.random() * 60, t: -1.1 - Math.random() * .2, life: .7 });
  };

  /* ---------- рисование ---------- */
  Scene.prototype.draw = function () {
    var c = this.ctx, L = this.L, k = this.k, self = this, S = this.season;
    c.setTransform(k, 0, 0, k, 0, 0);
    c.fillStyle = S.grass; c.fillRect(0, 0, L.w, L.h);
    // пятна травы
    this.decor.tufts.forEach(function (t) { c.fillStyle = t.c === 1 ? S.grass2 : S.grass3; c.globalAlpha = .5; c.beginPath(); c.ellipse(t.x, t.y, t.r, t.r * .55, 0, 0, TAU); c.fill(); });
    c.globalAlpha = 1;
    // дорожки
    c.lineCap = "round"; c.lineJoin = "round";
    var paths = this.paths();
    c.strokeStyle = "#cdb98a"; c.lineWidth = 46; paths.forEach(function (p) { c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(p[2], p[3]); c.stroke(); });
    c.strokeStyle = "#ecdcb4"; c.lineWidth = 40; paths.forEach(function (p) { c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(p[2], p[3]); c.stroke(); });
    c.fillStyle = "#cdb98a"; c.beginPath(); c.ellipse(L.plaza[0], L.plaza[1], 62, 44, 0, 0, TAU); c.fill();
    c.fillStyle = "#ecdcb4"; c.beginPath(); c.ellipse(L.plaza[0], L.plaza[1], 58, 40, 0, 0, TAU); c.fill();
    // цветы
    var FC = ["#fff6d6", "#f7a8c4", "#f6d24a", "#ffffff"];
    this.decor.flowers.forEach(function (f) { c.fillStyle = FC[f.c]; c.beginPath(); c.arc(f.x, f.y, 1.8, 0, TAU); c.fill(); });

    // секции, сзади вперёд
    var order = SECT.slice().sort(function (a, b) { return L[a][1] - L[b][1]; });
    order.forEach(function (s) { self["draw_" + s](c, L[s], self.st[s]); self.frame(c, s); });
    this.draw_kiosk(c, L.kiosk);

    // всё, что стоит на земле, по глубине: деревья, люди, смотрители
    var items = [];
    this.decor.trees.forEach(function (t) { items.push({ y: t.y, f: function () { self.tree(c, t); } }); });
    this.people.forEach(function (q) { items.push({ y: q.y, f: function () { self.person(c, q); } }); });
    SECT.forEach(function (s) { self.keeperSpots(s).forEach(function (kp, i) { items.push({ y: kp[1], f: function () { self.keeper(c, kp[0], kp[1], i, s); } }); }); });
    items.push({ y: L.gate[1] + 60, f: function () { self.draw_gate(c, L.gate); } });
    items.sort(function (a, b) { return a.y - b.y; });
    items.forEach(function (it) { it.f(); });

    this.drawFx(c);
    this.drawWeather(c);
    this.drawLight(c);
  };

  Scene.prototype.frame = function (c, s) {   // подсветка секции под курсором и тревоги
    var r = this.L[s], st = this.st[s], hot = this.hover === s || this.focus === s;
    if (st.alert) {
      var pulse = .5 + .5 * Math.sin(this.t * 4);
      c.strokeStyle = st.alert === "low" ? "rgba(214,138,20," + (.55 + .4 * pulse) + ")" : "rgba(214,64,48," + (.55 + .4 * pulse) + ")";
      c.lineWidth = 5; rr(c, r[0] - 3, r[1] - 3, r[2] + 6, r[3] + 6, 22); c.stroke();
    }
    if (hot) { c.strokeStyle = "rgba(255,255,255,.95)"; c.lineWidth = 4; rr(c, r[0] - 2, r[1] - 2, r[2] + 4, r[3] + 4, 21); c.stroke(); }
    if (st.closed || this.dead[s]) {
      c.fillStyle = "rgba(40,44,52,.46)"; rr(c, r[0], r[1], r[2], r[3], 20); c.fill();
      c.save(); c.translate(r[0] + r[2] / 2, r[1] + r[3] / 2); c.rotate(-.08);
      c.fillStyle = "#f2c230"; rr(c, -62, -15, 124, 30, 6); c.fill(); c.fillStyle = "#3a2c12"; c.font = "700 15px Podkova, Georgia, serif"; c.textAlign = "center"; c.textBaseline = "middle";
      c.fillText(this.lang === "ru" ? "закрыто" : "closed", 0, 1); c.restore();
    }
  };
  function rr(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }
  function shadow(c, x, y, rx, ry) { c.fillStyle = "rgba(30,50,30,.18)"; c.beginPath(); c.ellipse(x, y, rx, ry, 0, 0, TAU); c.fill(); }

  /* --- бассейн: морские львы и пингвины --- */
  Scene.prototype.draw_pool = function (c, r) {
    var x = r[0], y = r[1], w = r[2], h = r[3], t = this.t, self = this, A = this.animals;
    c.fillStyle = "#d9d2c2"; rr(c, x, y, w, h, 20); c.fill();                           // каменный берег
    c.fillStyle = "#c7bfad"; rr(c, x + 6, y + 6, w - 12, h - 12, 16); c.fill();
    var wx = x + 16, wy = y + h * .34, ww = w - 32, wh = h * .58;
    c.save(); rr(c, wx, wy, ww, wh, 26); c.clip();
    c.fillStyle = "#39a9c4"; c.fillRect(wx, wy, ww, wh);
    c.fillStyle = "#2b93b0"; c.beginPath(); c.ellipse(wx + ww * .5, wy + wh * .62, ww * .42, wh * .36, 0, 0, TAU); c.fill();
    c.strokeStyle = "rgba(255,255,255,.5)"; c.lineWidth = 2;                             // блики
    for (var i = 0; i < 7; i++) { var bx = wx + ((i * 97 + t * 14) % ww), by = wy + 14 + (i * 31) % (wh - 24); c.beginPath(); c.moveTo(bx, by); c.quadraticCurveTo(bx + 9, by - 4, bx + 18, by); c.stroke(); }
    // львы в воде
    A.sealions.forEach(function (s, n) {
      if (self.dead.pool) return;
      var a = t * s.sp + s.ph, sx = wx + ww * .5 + Math.cos(a) * ww * .36, sy = wy + wh * .55 + Math.sin(a) * wh * .3 * s.ry, dir = -Math.sin(a) >= 0 ? 1 : -1, jy = 0;
      if (n === 0 && self.show) { var q = clamp((self.show.t - .1) / 1.1, 0, 1); jy = -Math.sin(q * Math.PI) * 58; sx = wx + ww * .5; sy = wy + wh * .52; dir = 1; }
      c.fillStyle = "rgba(20,70,90,.25)"; c.beginPath(); c.ellipse(sx, sy + 9, 22, 6, 0, 0, TAU); c.fill();
      sealion(c, sx, sy + jy, dir, 1, Math.sin(a * 3) * .08 + (jy ? -.5 : 0));
      if (!jy) { c.strokeStyle = "rgba(255,255,255,.65)"; c.lineWidth = 1.6; c.beginPath(); c.ellipse(sx, sy + 7, 20 + 3 * Math.sin(t * 3 + n), 5, 0, 0, TAU); c.stroke(); }
    });
    c.restore();
    c.strokeStyle = "#a79e8a"; c.lineWidth = 3; rr(c, wx, wy, ww, wh, 26); c.stroke();
    // ледяная скала с пингвинами
    var ix = x + w * .08, iy = y + h * .07, iw = w * .46, ih = h * .25;
    c.fillStyle = "#eef4f6"; c.beginPath(); c.moveTo(ix, iy + ih); c.lineTo(ix + iw * .1, iy + ih * .3); c.lineTo(ix + iw * .3, iy + ih * .45); c.lineTo(ix + iw * .45, iy); c.lineTo(ix + iw * .7, iy + ih * .4); c.lineTo(ix + iw * .88, iy + ih * .2); c.lineTo(ix + iw, iy + ih); c.closePath(); c.fill();
    c.fillStyle = "#d3e3ea"; c.beginPath(); c.moveTo(ix + iw * .45, iy); c.lineTo(ix + iw * .7, iy + ih * .4); c.lineTo(ix + iw * .56, iy + ih); c.lineTo(ix + iw * .36, iy + ih); c.closePath(); c.fill();
    if (!this.dead.pool) A.penguins.forEach(function (p) {
      var px = ix + 10 + p.u * (iw - 20) + Math.sin(t * p.sp + p.ph) * 5, py = iy + ih + 4 + p.v * 12;
      penguin(c, px, py, Math.sin(t * p.sp * 4 + p.ph) * .16);
    });
    // трибуна для кормления
    if (this.shows > 0 || this.show) {
      var sx2 = x + w * .66, sy2 = y + h * .1; c.fillStyle = "#8a6238"; rr(c, sx2, sy2, w * .26, 12, 3); c.fill(); c.fillStyle = "#a67845"; rr(c, sx2 + 6, sy2 + 14, w * .26 - 12, 10, 3); c.fill();
      c.fillStyle = "#f2c230"; c.beginPath(); c.moveTo(sx2 + w * .13, sy2 - 22); c.lineTo(sx2 + w * .13 + 16, sy2 - 16); c.lineTo(sx2 + w * .13, sy2 - 10); c.closePath(); c.fill();
      c.strokeStyle = "#6a4a26"; c.lineWidth = 2; c.beginPath(); c.moveTo(sx2 + w * .13, sy2 - 22); c.lineTo(sx2 + w * .13, sy2); c.stroke();
    }
  };
  function sealion(c, x, y, dir, s, tilt) {
    c.save(); c.translate(x, y); c.scale(dir * s, s); c.rotate(tilt || 0);
    c.fillStyle = "#4b3d34"; c.fill(P("M-24,4 C-20,-9 -3,-13 8,-9 C13,-16 19,-19 24,-15 C28,-12 28,-6 23,-3 C19,0 15,7 6,9 C-5,12 -17,11 -24,4 Z"));
    c.fill(P("M-23,4 L-34,-2 L-31,5 L-34,11 Z")); c.fill(P("M3,7 L-3,17 L8,14 Z"));
    c.fillStyle = "#6a5a4e"; c.fill(P("M-14,6 C-6,10 6,8 14,2 C8,8 -2,11 -14,6 Z"));
    c.fillStyle = "#1b1512"; c.beginPath(); c.arc(21, -12, 1.7, 0, TAU); c.fill(); c.beginPath(); c.arc(27.5, -9, 1.5, 0, TAU); c.fill();
    c.strokeStyle = "rgba(255,255,255,.55)"; c.lineWidth = .8; c.beginPath(); c.moveTo(25, -7); c.lineTo(31, -5); c.moveTo(25, -6); c.lineTo(30, -2); c.stroke();
    c.restore();
  }
  function penguin(c, x, y, tilt) {
    c.save(); c.translate(x, y); c.rotate(tilt);
    c.fillStyle = "#f08a2b"; c.fillRect(-4, -2, 3, 2.5); c.fillRect(1, -2, 3, 2.5);
    c.fillStyle = "#20262e"; c.beginPath(); c.ellipse(0, -10, 6, 9, 0, 0, TAU); c.fill(); c.beginPath(); c.arc(0, -19, 4.6, 0, TAU); c.fill();
    c.fillStyle = "#fff"; c.beginPath(); c.ellipse(0, -9, 4, 7, 0, 0, TAU); c.fill(); c.beginPath(); c.arc(-1.8, -19, 1.5, 0, TAU); c.arc(1.8, -19, 1.5, 0, TAU); c.fill();
    c.fillStyle = "#20262e"; c.beginPath(); c.arc(-1.8, -19.2, .7, 0, TAU); c.arc(1.8, -19.2, .7, 0, TAU); c.fill();
    c.fillStyle = "#f08a2b"; c.beginPath(); c.moveTo(-1.6, -17.3); c.lineTo(1.6, -17.3); c.lineTo(0, -14.6); c.closePath(); c.fill();
    c.restore();
  }

  /* --- барсы --- */
  Scene.prototype.draw_cats = function (c, r) {
    var x = r[0], y = r[1], w = r[2], h = r[3], t = this.t, self = this;
    c.fillStyle = "#b8b2a4"; rr(c, x, y, w, h, 20); c.fill();
    c.fillStyle = "#cfcabc"; rr(c, x + 8, y + h * .5, w - 16, h * .44, 14); c.fill();               // нижняя терраса
    c.fillStyle = "#a39c8c"; c.beginPath(); c.moveTo(x + 10, y + h * .56); c.lineTo(x + w * .18, y + h * .2); c.lineTo(x + w * .34, y + h * .34); c.lineTo(x + w * .5, y + h * .1); c.lineTo(x + w * .7, y + h * .3); c.lineTo(x + w * .84, y + h * .16); c.lineTo(x + w - 10, y + h * .56); c.closePath(); c.fill();
    c.fillStyle = "#eef2f4"; c.beginPath(); c.moveTo(x + w * .42, y + h * .22); c.lineTo(x + w * .5, y + h * .1); c.lineTo(x + w * .59, y + h * .21); c.lineTo(x + w * .53, y + h * .2); c.lineTo(x + w * .49, y + h * .25); c.closePath(); c.fill();
    c.beginPath(); c.moveTo(x + w * .78, y + h * .25); c.lineTo(x + w * .84, y + h * .16); c.lineTo(x + w * .9, y + h * .27); c.closePath(); c.fill();
    c.fillStyle = "#8f8878"; c.beginPath(); c.ellipse(x + w * .2, y + h * .8, 22, 12, 0, 0, TAU); c.fill(); c.beginPath(); c.ellipse(x + w * .8, y + h * .74, 28, 14, 0, 0, TAU); c.fill();
    // бревно
    c.strokeStyle = "#7a5533"; c.lineWidth = 9; c.beginPath(); c.moveTo(x + w * .34, y + h * .88); c.lineTo(x + w * .62, y + h * .7); c.stroke();
    if (this.dead.cats) return;
    this.animals.leopards.forEach(function (lp, n) {
      var hot = (self.react.cats || 0) > self.rt, a = t * lp.sp + lp.ph, u = .5 + .36 * Math.sin(a), dir = Math.cos(a) >= 0 ? 1 : -1, lx = x + 26 + u * (w - 52), ly = y + h * lp.lane + 14 - (hot ? Math.abs(Math.sin(self.rt * 9 + n)) * 7 : 0);
      var resting = !hot && n === 1 && Math.sin(t * .07) > .2;
      shadow(c, lx, ly + 2, 26, 6);
      leopard(c, lx, ly, dir, 1, t * 6 + n, resting);
    });
    if (this.cubs) { for (var i = 0; i < 2; i++) { var cx2 = x + w * (.42 + i * .1) + Math.sin(t * 1.3 + i * 2) * 10, cy2 = y + h * .93; leopard(c, cx2, cy2, Math.cos(t * 1.3 + i * 2) >= 0 ? 1 : -1, .48, t * 10 + i, false); } }
  };
  function leopard(c, x, y, dir, s, ph, rest) {
    c.save(); c.translate(x, y); c.scale(dir * s, s);
    var sw = Math.sin(ph) * (rest ? 0 : 3);
    c.strokeStyle = "#d8d3c8"; c.lineWidth = 6; c.lineCap = "round"; c.beginPath(); c.moveTo(-22, -12); c.quadraticCurveTo(-40, -10 + Math.sin(ph * .5) * 4, -44, -24 + Math.sin(ph * .5) * 5); c.stroke();
    c.strokeStyle = "#5c574f"; c.lineWidth = 6; c.beginPath(); c.moveTo(-43, -21 + Math.sin(ph * .5) * 5); c.lineTo(-44, -25 + Math.sin(ph * .5) * 5); c.stroke();
    c.fillStyle = "#cfc9bd";
    if (rest) { c.beginPath(); c.ellipse(0, -7, 24, 8, 0, 0, TAU); c.fill(); }
    else { c.fillRect(-18 + sw, -8, 5, 9); c.fillRect(12 - sw, -8, 5, 9); c.fillStyle = "#dedad0"; c.fillRect(-12 - sw, -8, 5, 9); c.fillRect(17 + sw, -8, 5, 9); }
    c.fillStyle = "#dedad0"; c.beginPath(); c.ellipse(0, rest ? -9 : -14, 23, rest ? 8 : 9, 0, 0, TAU); c.fill();
    c.beginPath(); c.arc(23, rest ? -12 : -20, 8, 0, TAU); c.fill();
    c.beginPath(); c.moveTo(17, rest ? -18 : -26); c.lineTo(19, rest ? -24 : -32); c.lineTo(23, rest ? -19 : -27); c.closePath(); c.fill();
    c.beginPath(); c.moveTo(24, rest ? -19 : -27); c.lineTo(28, rest ? -24 : -32); c.lineTo(30, rest ? -17 : -25); c.closePath(); c.fill();
    c.fillStyle = "#fff"; c.beginPath(); c.ellipse(27, rest ? -9 : -17, 4.5, 3.4, 0, 0, TAU); c.fill();
    c.fillStyle = "#5c574f"; var by = rest ? -9 : -14;
    [[-12, -3], [-4, 2], [4, -4], [11, 1], [-17, 2], [14, -5], [-7, -6]].forEach(function (p) { c.beginPath(); c.arc(p[0], by + p[1], 1.9, 0, TAU); c.fill(); });
    c.fillStyle = "#23201c"; c.beginPath(); c.arc(25, rest ? -13.5 : -21.5, 1.3, 0, TAU); c.fill(); c.beginPath(); c.arc(31, rest ? -10 : -18, 1.2, 0, TAU); c.fill();
    c.restore();
  }

  /* --- птичий дом: вольер-купол, попугаи и фламинго --- */
  Scene.prototype.draw_birds = function (c, r) {
    var x = r[0], y = r[1], w = r[2], h = r[3], t = this.t, cx = x + w / 2, self = this;
    c.fillStyle = "#b9d7a0"; rr(c, x, y, w, h, 20); c.fill();
    c.fillStyle = "#6fc3d2"; c.beginPath(); c.ellipse(cx, y + h * .8, w * .3, h * .1, 0, 0, TAU); c.fill();     // прудик
    c.strokeStyle = "#7a5533"; c.lineWidth = 5; c.beginPath(); c.moveTo(cx - w * .2, y + h * .78); c.lineTo(cx - w * .2, y + h * .34); c.moveTo(cx - w * .2, y + h * .46); c.lineTo(cx - w * .34, y + h * .36); c.moveTo(cx - w * .2, y + h * .4); c.lineTo(cx - w * .06, y + h * .3); c.stroke();
    c.beginPath(); c.moveTo(cx + w * .22, y + h * .78); c.lineTo(cx + w * .22, y + h * .42); c.moveTo(cx + w * .22, y + h * .5); c.lineTo(cx + w * .36, y + h * .42); c.stroke();
    if (!this.dead.birds) {
      this.animals.flamingos.forEach(function (f, i) { flamingo(c, x + w * f.u, y + h * .86, i === 1 ? -1 : 1, Math.sin(t * .8 + i) * .05); });
      var BC = [["#e4572e", "#f2c230"], ["#2f9e62", "#f2c230"], ["#3a86c8", "#f6d24a"], ["#f2c230", "#e4572e"]];
      this.animals.birds.forEach(function (b, i) {
        var up = (self.react.birds || 0) > self.rt, a = (up ? self.rt * 3.4 : t * b.sp) + b.ph, perched = !up && Math.sin(a * .35 + i) > .35;
        var bx = perched ? cx + (i % 2 ? w * .3 : -w * .28) + (i % 3) * 7 - 7 : cx + Math.cos(a) * w * b.rx, by = perched ? y + h * (.4 + (i % 3) * .03) : y + h * (.32 + b.cy * .16) + Math.sin(a * 1.7) * h * b.ry * .5;
        bird(c, bx, by, perched ? (i % 2 ? -1 : 1) : (-Math.sin(a) >= 0 ? 1 : -1), BC[b.c], perched ? 0 : Math.sin(t * 16 + i));
      });
    }
    // купол из сетки
    c.strokeStyle = "rgba(60,78,88,.55)"; c.lineWidth = 2.2;
    c.beginPath(); c.moveTo(x + 12, y + h * .92); c.quadraticCurveTo(x + 10, y + 8, cx, y + 6); c.quadraticCurveTo(x + w - 10, y + 8, x + w - 12, y + h * .92); c.stroke();
    c.lineWidth = 1; c.strokeStyle = "rgba(60,78,88,.3)";
    for (var i = 1; i < 6; i++) { var u = i / 6; c.beginPath(); c.moveTo(lerp(x + 12, x + w - 12, u), y + h * .92); c.quadraticCurveTo(lerp(x + 10, x + w - 10, u), y + 30, cx, y + 6); c.stroke(); }
    for (i = 1; i < 5; i++) { var v = i / 5, yy = lerp(y + 6, y + h * .92, v), half = (w / 2 - 12) * Math.sqrt(Math.min(1, v * 1.5)); c.beginPath(); c.ellipse(cx, yy, half, 5, 0, 0, Math.PI); c.stroke(); }
    c.fillStyle = "#f2c230"; c.beginPath(); c.arc(cx, y + 6, 4, 0, TAU); c.fill();
  };
  function bird(c, x, y, dir, col, flap) {
    c.save(); c.translate(x, y); c.scale(dir, 1);
    c.fillStyle = col[0]; c.beginPath(); c.ellipse(0, 0, 6, 4.4, -.2, 0, TAU); c.fill(); c.beginPath(); c.arc(5.5, -3.4, 3.4, 0, TAU); c.fill();
    c.beginPath(); c.moveTo(-5, 0); c.lineTo(-13, 3); c.lineTo(-6, 3.5); c.closePath(); c.fill();
    c.fillStyle = col[1]; c.beginPath(); c.moveTo(-3, -1); c.lineTo(2, -1 - 7 * (flap || 0) - 2); c.lineTo(3, 1.5); c.closePath(); c.fill();
    c.fillStyle = "#3a2c12"; c.beginPath(); c.moveTo(8.4, -3.8); c.lineTo(12, -2.6); c.lineTo(8.4, -1.6); c.closePath(); c.fill();
    c.fillStyle = "#fff"; c.beginPath(); c.arc(6.4, -4.2, 1.2, 0, TAU); c.fill(); c.fillStyle = "#111"; c.beginPath(); c.arc(6.6, -4.2, .6, 0, TAU); c.fill();
    c.restore();
  }
  function flamingo(c, x, y, dir, tilt) {
    c.save(); c.translate(x, y); c.scale(dir, 1); c.rotate(tilt);
    c.strokeStyle = "#e88aa8"; c.lineWidth = 1.6; c.beginPath(); c.moveTo(-1, -14); c.lineTo(-1, 0); c.moveTo(2, -14); c.lineTo(3, -7); c.lineTo(1, -5); c.stroke();
    c.fillStyle = "#f6a3bd"; c.beginPath(); c.ellipse(0, -18, 8, 5.5, -.15, 0, TAU); c.fill();
    c.strokeStyle = "#f6a3bd"; c.lineWidth = 2.6; c.lineCap = "round"; c.beginPath(); c.moveTo(6, -20); c.quadraticCurveTo(12, -26, 8, -31); c.quadraticCurveTo(5, -36, 10, -37); c.stroke();
    c.fillStyle = "#f6a3bd"; c.beginPath(); c.arc(10, -37, 2.6, 0, TAU); c.fill(); c.fillStyle = "#2a2422"; c.beginPath(); c.moveTo(12, -37.6); c.lineTo(16, -35.4); c.lineTo(12, -35.2); c.closePath(); c.fill();
    c.restore();
  }

  /* --- контактный двор: козы за заборчиком --- */
  Scene.prototype.draw_yard = function (c, r) {
    var x = r[0], y = r[1], w = r[2], h = r[3], self = this, t = this.t;
    c.fillStyle = "#e6cf86"; rr(c, x, y, w, h, 20); c.fill();
    c.fillStyle = "#d9bf6e"; for (var i = 0; i < 16; i++) { c.beginPath(); c.ellipse(x + 22 + (i * 53) % (w - 44), y + 24 + (i * 37) % (h - 48), 16, 6, (i % 3) * .5, 0, TAU); c.fill(); }
    // сарай
    var bx = x + w * .68, by = y + h * .12, bw = w * .26, bh = h * .34;
    c.fillStyle = "#b5503a"; c.fillRect(bx, by + bh * .36, bw, bh * .64); c.fillStyle = "#8f3b2a"; c.beginPath(); c.moveTo(bx - 6, by + bh * .4); c.lineTo(bx + bw / 2, by); c.lineTo(bx + bw + 6, by + bh * .4); c.closePath(); c.fill();
    c.fillStyle = "#5e2a1e"; c.fillRect(bx + bw * .36, by + bh * .56, bw * .28, bh * .44); c.strokeStyle = "#f2e6cf"; c.lineWidth = 1.6; c.strokeRect(bx + bw * .36, by + bh * .56, bw * .28, bh * .44);
    // стог и корыто
    c.fillStyle = "#e9c75a"; c.beginPath(); c.ellipse(x + w * .16, y + h * .28, 22, 16, 0, 0, TAU); c.fill(); c.strokeStyle = "#c9a23c"; c.lineWidth = 1.4; for (i = 0; i < 4; i++) { c.beginPath(); c.arc(x + w * .16, y + h * .28, 5 + i * 5, 3.6, 5.8); c.stroke(); }
    c.fillStyle = "#7a5533"; rr(c, x + w * .34, y + h * .2, 46, 10, 3); c.fill(); c.fillStyle = "#6fc3d2"; c.fillRect(x + w * .34 + 3, y + h * .2 + 2, 40, 4);
    if (!this.dead.yard) {
      var gs = this.animals.goats.slice().sort(function (a, b) { return a.v - b.v; });
      var hop = (self.react.yard || 0) > self.rt;
      gs.forEach(function (g, gi) { var gx = x + 26 + g.u * (w - 52), gy = y + h * .5 + g.v * (h * .42); shadow(c, gx, gy + 1, 14, 4); if (hop) gy -= Math.abs(Math.sin(self.rt * 10 + gi * 1.3)) * 9; goat(c, gx, gy, g.flip, g.c, g.wait > 0 ? 0 : g.ph, g.wait > 1.5); });
    }
    // заборчик спереди
    c.strokeStyle = "#8a6238"; c.lineWidth = 3; c.beginPath(); c.moveTo(x + 8, y + h - 16); c.lineTo(x + w - 8, y + h - 16); c.moveTo(x + 8, y + h - 8); c.lineTo(x + w - 8, y + h - 8); c.stroke();
    c.lineWidth = 4; for (i = 0; i <= 9; i++) { var px = x + 10 + i * (w - 20) / 9; c.beginPath(); c.moveTo(px, y + h - 22); c.lineTo(px, y + h - 3); c.stroke(); }
  };
  function goat(c, x, y, dir, col, ph, graze) {
    var body = ["#f6f1e6", "#d9b98c", "#8a7460"][col], sw = Math.sin(ph) * 2.4;
    c.save(); c.translate(x, y); c.scale(dir, 1);
    c.strokeStyle = "#5a4a3a"; c.lineWidth = 2.4; c.lineCap = "round";
    c.beginPath(); c.moveTo(-8 + sw, -6); c.lineTo(-8 + sw, 0); c.moveTo(-4 - sw, -6); c.lineTo(-4 - sw, 0); c.moveTo(6 + sw, -6); c.lineTo(6 + sw, 0); c.moveTo(9 - sw, -6); c.lineTo(9 - sw, 0); c.stroke();
    c.fillStyle = body; rr(c, -12, -17, 24, 12, 6); c.fill();
    c.beginPath(); c.moveTo(-12, -14); c.lineTo(-16, -17); c.lineTo(-12, -11); c.closePath(); c.fill();
    c.save(); c.translate(11, -15); c.rotate(graze ? .9 : 0);
    c.fillStyle = body; rr(c, -2, -9, 9, 9, 4); c.fill(); rr(c, 3, -4, 7, 5, 2); c.fill();
    c.strokeStyle = "#8a7a5c"; c.lineWidth = 1.6; c.beginPath(); c.moveTo(0, -9); c.quadraticCurveTo(-3, -15, -6, -13); c.moveTo(3, -9); c.quadraticCurveTo(2, -15, -1, -15); c.stroke();
    c.fillStyle = "#23201c"; c.beginPath(); c.arc(3.4, -5.4, .9, 0, TAU); c.fill();
    c.strokeStyle = body; c.lineWidth = 1.4; c.beginPath(); c.moveTo(7, 1); c.lineTo(7, 4); c.stroke();
    c.restore(); c.restore();
  }

  /* --- тропический дом: оранжерея, лемуры, бабочки --- */
  Scene.prototype.draw_tropic = function (c, r) {
    var x = r[0], y = r[1], w = r[2], h = r[3], t = this.t, self = this, cold = this.st.tropic.alert === "cold";
    c.fillStyle = "#cfe3c2"; rr(c, x, y, w, h, 20); c.fill();
    var gx = x + 14, gy = y + h * .2, gw = w - 28, gh = h * .7;
    c.fillStyle = "#3f8f52"; c.fillRect(gx, gy + gh * .55, gw, gh * .45);
    // пальмы и лианы внутри
    for (var i = 0; i < 4; i++) { var px = gx + gw * (.14 + i * .24), py = gy + gh * .96; palm(c, px, py, .8 + (i % 2) * .25, Math.sin(t * .9 + i) * .05); }
    c.strokeStyle = "#7a5533"; c.lineWidth = 4; c.beginPath(); c.moveTo(gx + gw * .2, gy + gh * .46); c.quadraticCurveTo(gx + gw * .5, gy + gh * .58, gx + gw * .82, gy + gh * .42); c.stroke();
    if (!this.dead.tropic) {
      this.animals.lemurs.forEach(function (l, n) { var u = .34 + n * .3 + Math.sin(t * .25 + l.ph) * .06, lx = gx + gw * u, ly = gy + gh * (.5 + Math.sin(u * 3.1) * .04) - ((self.react.tropic || 0) > self.rt ? Math.abs(Math.sin(self.rt * 8 + n * 1.5)) * 14 : 0); lemur(c, lx, ly, n ? -1 : 1, t * 2 + l.ph); });
      var FC = ["#f2c230", "#e4572e", "#7ec8e3"];
      this.animals.flies.forEach(function (f) { var a = t * f.sp + f.ph, fx = gx + gw * (.1 + f.u * .8) + Math.cos(a) * 14, fy = gy + gh * (.2 + f.v * .5) + Math.sin(a * 1.3) * 10, o = Math.abs(Math.sin(t * 12 + f.ph));
        c.fillStyle = FC[f.c]; c.beginPath(); c.ellipse(fx - 2.4 * o, fy, 2.4 * o, 3.2, 0, 0, TAU); c.ellipse(fx + 2.4 * o, fy, 2.4 * o, 3.2, 0, 0, TAU); c.fill(); });
    }
    // стеклянный дом
    c.fillStyle = cold ? "rgba(150,190,220,.34)" : "rgba(205,240,232,.34)"; c.beginPath(); c.moveTo(gx, gy + gh); c.lineTo(gx, gy + gh * .3); c.quadraticCurveTo(gx + gw / 2, gy - gh * .34, gx + gw, gy + gh * .3); c.lineTo(gx + gw, gy + gh); c.closePath(); c.fill();
    c.strokeStyle = "#2f6b5a"; c.lineWidth = 3; c.stroke();
    c.lineWidth = 1.4; c.strokeStyle = "rgba(47,107,90,.6)";
    for (i = 1; i < 7; i++) { var ux = gx + gw * i / 7, top = gy + gh * .3 - Math.sin(i / 7 * Math.PI) * gh * .32; c.beginPath(); c.moveTo(ux, gy + gh); c.lineTo(ux, top); c.stroke(); }
    c.beginPath(); c.moveTo(gx, gy + gh * .62); c.lineTo(gx + gw, gy + gh * .62); c.moveTo(gx, gy + gh * .3); c.lineTo(gx + gw, gy + gh * .3); c.stroke();
    c.strokeStyle = "rgba(255,255,255,.5)"; c.lineWidth = 3; c.beginPath(); c.moveTo(gx + gw * .12, gy + gh * .5); c.lineTo(gx + gw * .2, gy + gh * .22); c.stroke();
    c.fillStyle = "#2f6b5a"; c.fillRect(gx + gw * .44, gy + gh * .66, gw * .12, gh * .34); c.fillStyle = "rgba(205,240,232,.7)"; c.fillRect(gx + gw * .455, gy + gh * .69, gw * .09, gh * .28);
  };
  function palm(c, x, y, s, sway) {
    c.save(); c.translate(x, y); c.scale(s, s);
    c.strokeStyle = "#7a5533"; c.lineWidth = 5; c.lineCap = "round"; c.beginPath(); c.moveTo(0, 0); c.quadraticCurveTo(4, -22, 0, -44); c.stroke();
    c.translate(0, -44); c.rotate(sway); c.fillStyle = "#2f8f4e";
    for (var i = 0; i < 6; i++) { c.save(); c.rotate(-1.4 + i * .56); c.beginPath(); c.moveTo(0, 0); c.quadraticCurveTo(16, -12, 32, -2); c.quadraticCurveTo(16, -4, 0, 0); c.fill(); c.restore(); }
    c.restore();
  }
  function lemur(c, x, y, dir, ph) {
    c.save(); c.translate(x, y); c.scale(dir, 1);
    var sw = Math.sin(ph) * 6;
    for (var i = 0; i < 7; i++) { var u = i / 6; c.fillStyle = i % 2 ? "#f4f2ee" : "#2b2a2c"; c.beginPath(); c.arc(-8 - u * 6 + sw * u * u, 2 + u * 22, 3, 0, TAU); c.fill(); }
    c.fillStyle = "#8f8c88"; c.beginPath(); c.ellipse(0, -8, 7, 9, 0, 0, TAU); c.fill();
    c.beginPath(); c.arc(3, -19, 6, 0, TAU); c.fill(); c.beginPath(); c.arc(-1.5, -24, 2.4, 0, TAU); c.arc(7.5, -24, 2.4, 0, TAU); c.fill();
    c.fillStyle = "#f4f2ee"; c.beginPath(); c.ellipse(3.6, -18, 4.6, 4.2, 0, 0, TAU); c.fill(); c.beginPath(); c.ellipse(1, -6, 3.4, 6, 0, 0, TAU); c.fill();
    c.fillStyle = "#2b2a2c"; c.beginPath(); c.arc(1.4, -19, 1.9, 0, TAU); c.arc(6.2, -19, 1.9, 0, TAU); c.fill(); c.beginPath(); c.arc(4, -15.6, 1.1, 0, TAU); c.fill();
    c.fillStyle = "#f2c230"; c.beginPath(); c.arc(1.4, -19, .9, 0, TAU); c.arc(6.2, -19, .9, 0, TAU); c.fill();
    c.restore();
  }

  /* --- киоск и вход --- */
  Scene.prototype.draw_kiosk = function (c, r) {
    var x = r[0], y = r[1], w = r[2], h = r[3], n = this.kiosk[this.mode === "evening" ? 1 : this.half] || 0;
    shadow(c, x + w / 2, y + h - 4, w * .5, 9);
    c.fillStyle = "#f6efe0"; rr(c, x + 12, y + h * .38, w - 24, h * .56, 5); c.fill(); c.fillStyle = "#e3d8c2"; c.fillRect(x + 12, y + h * .6, w - 24, 5);
    var sw = (w - 8) / 6;
    for (var i = 0; i < 6; i++) { c.fillStyle = i % 2 ? "#fff8ea" : "#e4572e"; c.beginPath(); c.moveTo(x + 4 + i * sw, y + h * .4); c.lineTo(x + 4 + (i + 1) * sw, y + h * .4); c.lineTo(x + 10 + (i + 1) * sw * .93, y + h * .12); c.lineTo(x + 10 + i * sw * .93, y + h * .12); c.closePath(); c.fill(); }
    for (i = 0; i < 6; i++) { c.fillStyle = i % 2 ? "#fff8ea" : "#e4572e"; c.beginPath(); c.arc(x + 4 + (i + .5) * sw, y + h * .4, sw / 2, 0, Math.PI); c.fill(); }
    for (i = 0; i < Math.min(n, 4); i++) { var kx = x + 26 + i * ((w - 52) / Math.max(1, Math.min(n, 4) - 1 || 1)) * (n > 1 ? 1 : 0) + (n === 1 ? (w - 52) / 2 : 0); c.fillStyle = "#e0b08c"; c.beginPath(); c.arc(kx, y + h * .5, 4, 0, TAU); c.fill(); c.fillStyle = "#fff"; rr(c, kx - 5, y + h * .44 - 6, 10, 5, 2); c.fill(); }
    if (!n) { c.fillStyle = "rgba(40,44,52,.5)"; rr(c, x + 12, y + h * .38, w - 24, h * .56, 5); c.fill(); }
  };
  Scene.prototype.draw_gate = function (c, r) {
    var x = r[0], y = r[1], w = r[2], n = this.cashiers[this.mode === "evening" ? 1 : this.half] || 1, cx = x + w / 2;
    // будки касс
    var booths = Math.min(n, 4), bw = 24, total = booths * bw + (booths - 1) * 6, bx0 = cx - total / 2;
    for (var i = 0; i < booths; i++) { var bx = bx0 + i * (bw + 6), by = y + 34; shadow(c, bx + bw / 2, by + 30, 14, 4);
      c.fillStyle = "#f6efe0"; rr(c, bx, by, bw, 30, 3); c.fill(); c.fillStyle = "#2f6b5a"; c.beginPath(); c.moveTo(bx - 3, by + 2); c.lineTo(bx + bw / 2, by - 9); c.lineTo(bx + bw + 3, by + 2); c.closePath(); c.fill();
      c.fillStyle = "#bfe3ea"; c.fillRect(bx + 5, by + 7, bw - 10, 10); c.fillStyle = "#e0b08c"; c.beginPath(); c.arc(bx + bw / 2, by + 13, 3.4, 0, TAU); c.fill(); }
    // арка
    c.strokeStyle = "#7a5533"; c.lineWidth = 8; c.lineCap = "round"; c.beginPath(); c.moveTo(x + 10, y + 64); c.lineTo(x + 10, y + 18); c.moveTo(x + w - 10, y + 64); c.lineTo(x + w - 10, y + 18); c.stroke();
    c.fillStyle = "#f2c230"; rr(c, x + 2, y - 2, w - 4, 28, 8); c.fill(); c.strokeStyle = "#7a5533"; c.lineWidth = 3; c.stroke();
    c.fillStyle = "#3a2c12"; c.font = "800 17px Podkova, Georgia, serif"; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText(this.lang === "ru" ? "ЗООПАРК" : "RED HOOK ZOO", cx, y + 13);
    // очередь: те, кому не хватило кассы
    for (i = 0; i < this.queue; i++) { var qx = cx - 30 + (i % 4) * 20 + Math.sin(this.t * 2 + i) * 1.5, qy = y + 78 + Math.floor(i / 4) * 12; this.person(c, { x: qx, y: qy, shirt: SHIRT[i % SHIRT.length], skin: SKIN[i % SKIN.length], kid: i % 5 === 0, face: 1, walk: 0, um: i, angry: true }); }
  };

  /* --- люди и деревья --- */
  Scene.prototype.person = function (c, q) {
    var s = q.kid ? .72 : 1, bob = q.wait > 0 || !q.path ? 0 : Math.abs(Math.sin(q.walk)) * 1.6, leg = q.wait > 0 || !q.path ? 0 : Math.sin(q.walk) * 2.2;
    c.save(); c.translate(q.x, q.y); c.scale(s, s);
    c.fillStyle = "rgba(30,50,30,.2)"; c.beginPath(); c.ellipse(0, 0, 6, 2.2, 0, 0, TAU); c.fill();
    c.strokeStyle = "#3b3f4a"; c.lineWidth = 2.6; c.lineCap = "round"; c.beginPath(); c.moveTo(-2, -6); c.lineTo(-2 - leg, 0); c.moveTo(2, -6); c.lineTo(2 + leg, 0); c.stroke();
    c.fillStyle = q.shirt; rr(c, -4.6, -15 - bob, 9.2, 10.5, 3.4); c.fill();
    c.fillStyle = q.skin; c.beginPath(); c.arc(0, -19 - bob, 3.9, 0, TAU); c.fill();
    if (q.hat) { c.fillStyle = "#f6efe0"; c.beginPath(); c.ellipse(0, -21.6 - bob, 5.6, 1.7, 0, 0, TAU); c.fill(); c.beginPath(); c.arc(0, -22 - bob, 3.2, Math.PI, 0); c.fill(); }
    if (this.weather === "rain" && !q.angry) { c.fillStyle = SHIRT[q.um % SHIRT.length]; c.beginPath(); c.arc(0, -27 - bob, 10, Math.PI, 0); c.closePath(); c.fill(); c.strokeStyle = "#3b3f4a"; c.lineWidth = 1; c.beginPath(); c.moveTo(0, -27 - bob); c.lineTo(0, -14 - bob); c.stroke(); }
    if (q.balloon) { var bx = Math.sin(this.t * 2 + q.x) * 2; c.strokeStyle = "rgba(60,60,70,.7)"; c.lineWidth = .8; c.beginPath(); c.moveTo(4, -13 - bob); c.quadraticCurveTo(6, -24 - bob, 5 + bx, -32 - bob); c.stroke();
      c.fillStyle = q.balloon; c.beginPath(); c.ellipse(5 + bx, -38 - bob, 5.2, 6.4, 0, 0, TAU); c.fill(); c.fillStyle = "rgba(255,255,255,.5)"; c.beginPath(); c.ellipse(3.4 + bx, -40 - bob, 1.4, 2, -.4, 0, TAU); c.fill(); }
    if (q.role) { c.fillStyle = "#fff"; c.strokeStyle = "#33260f"; c.lineWidth = 1; rr(c, -7, -37 - bob, 14, 11, 3); c.fill(); c.stroke();
      if (q.role === "vet") { c.fillStyle = "#d64030"; c.fillRect(-1.2, -35 - bob, 2.4, 7); c.fillRect(-3.6, -32.7 - bob, 7.2, 2.4); }
      else if (q.role === "inspector") { c.strokeStyle = "#33260f"; c.lineWidth = 1.2; c.beginPath(); c.moveTo(-4, -33.5 - bob); c.lineTo(4, -33.5 - bob); c.moveTo(-4, -30.5 - bob); c.lineTo(2, -30.5 - bob); c.stroke(); }
      else { c.fillStyle = "#33260f"; c.beginPath(); c.arc(0, -31.5 - bob, 2.6, 0, TAU); c.fill(); c.fillRect(-4.5, -35 - bob, 3, 1.6); } }
    if (q.angry) { c.fillStyle = "#d64030"; c.font = "700 9px sans-serif"; c.textAlign = "center"; c.fillText("!", 6, -22 + Math.sin(this.t * 5 + q.x) * 1.5); }
    c.restore();
  };
  Scene.prototype.keeperSpots = function (s) {
    var r = this.L[s], st = this.st[s], n = st.keepers[this.mode === "day" ? this.half : 0], m = st.keepers[1], out = [];
    if (this.mode !== "day") n = Math.max(n, m);
    n = Math.min(n, 6);
    for (var i = 0; i < n; i++) {
      var u = (i + 1) / (n + 1), kx = r[0] + r[2] * (s === "tropic" ? .5 : u), ky = r[1] + r[3] - 26 - (i % 2) * 7;
      if (s === "tropic") kx = r[0] + 24 + i * 16, ky = r[1] + r[3] - 10;
      if (s === "pool") ky = r[1] + r[3] * .3 + (i % 2) * 6, kx = r[0] + r[2] * (.56 + u * .38);
      if (s === "pool" && this.show && i < 2) { kx = r[0] + r[2] * (.5 + i * .09); ky = r[1] + r[3] * .32; }
      if (s === "cats") ky = r[1] + r[3] - 12, kx = r[0] + 22 + i * 18;
      if (s === "birds") ky = r[1] + r[3] - 8, kx = r[0] + 24 + i * 18;
      out.push([kx, ky]);
    }
    return out;
  };
  Scene.prototype.keeper = function (c, x, y, i, s) {
    var busy = s === "pool" && this.show && i < 2, wave = busy ? Math.sin(this.t * 10) * .5 : Math.sin(this.t * 1.4 + i * 2 + x) * .12;
    c.save(); c.translate(x, y);
    var st0 = this.st[s], age = st0.popT != null && i >= st0.popFrom ? this.rt - st0.popT : 9;
    if (age < .45) { var kq = age / .45, sc2 = kq < .6 ? kq / .6 * 1.25 : 1.25 - (kq - .6) / .4 * .25; c.scale(sc2, sc2); c.translate(0, -Math.sin(kq * Math.PI) * 8); }
    c.fillStyle = "rgba(30,50,30,.22)"; c.beginPath(); c.ellipse(0, 0, 6.5, 2.4, 0, 0, TAU); c.fill();
    c.strokeStyle = "#3d3324"; c.lineWidth = 2.8; c.lineCap = "round"; c.beginPath(); c.moveTo(-2.2, -7); c.lineTo(-2.2, 0); c.moveTo(2.2, -7); c.lineTo(2.2, 0); c.stroke();
    c.fillStyle = "#1f7a4d"; rr(c, -5, -17, 10, 11.5, 3.4); c.fill();
    c.strokeStyle = "#1f7a4d"; c.lineWidth = 2.6; c.beginPath(); c.moveTo(4.4, -14); c.lineTo(8.5, -15 - 6 * Math.abs(wave) - (busy ? 5 : 0)); c.stroke();
    c.fillStyle = "#e0b08c"; c.beginPath(); c.arc(0, -21, 4.1, 0, TAU); c.fill();
    c.fillStyle = "#c9a96a"; c.beginPath(); c.ellipse(0, -23.6, 6.4, 1.9, 0, 0, TAU); c.fill(); c.beginPath(); c.arc(0, -24, 3.5, Math.PI, 0); c.fill();
    if (busy) { c.fillStyle = "#9fb4bd"; rr(c, -11, -9, 6, 6, 1.5); c.fill(); c.fillStyle = "#cfe0e6"; c.beginPath(); c.ellipse(9.5, -23 - 6 * Math.abs(wave), 3.2, 1.3, .5, 0, TAU); c.fill(); }
    c.restore();
  };
  Scene.prototype.tree = function (c, t) {
    var S = this.season, sw = Math.sin(this.t * .9 + t.sway) * 1.6 * (this.reduced ? 0 : 1);
    c.save(); c.translate(t.x, t.y); c.scale(t.s, t.s);
    shadow(c, 3, 2, t.bush ? 13 : 17, t.bush ? 4 : 6);
    if (t.bush) { c.fillStyle = S.tree[1] === "#f3a9c4" ? "#58a862" : S.tree[1]; c.beginPath(); c.arc(-6, -6, 8, 0, TAU); c.arc(5, -8, 9, 0, TAU); c.arc(0, -3, 8, 0, TAU); c.fill(); c.restore(); return; }
    c.fillStyle = "#7a5533"; c.fillRect(-2.6, -16, 5.2, 16);
    c.fillStyle = S.tree[t.c]; c.beginPath(); c.arc(sw - 8, -24, 11, 0, TAU); c.arc(sw + 8, -25, 12, 0, TAU); c.arc(sw, -35, 13, 0, TAU); c.fill();
    c.fillStyle = "rgba(255,255,255,.16)"; c.beginPath(); c.arc(sw - 4, -38, 7, 0, TAU); c.fill();
    c.restore();
  };

  Scene.prototype.drawFx = function (c) {
    var self = this;
    this.fx.forEach(function (f) {
      if (f.t < 0) return; var u = f.t / f.life;
      if (f.k === "coin") { c.globalAlpha = 1 - u; c.fillStyle = "#f2c230"; c.strokeStyle = "#b8860b"; c.lineWidth = 1; c.beginPath(); c.arc(f.x, f.y - u * 30, 4.2, 0, TAU); c.fill(); c.stroke(); c.fillStyle = "#7a5a00"; c.font = "700 6px sans-serif"; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText("$", f.x, f.y - u * 30 + .4); c.globalAlpha = 1; }
      else if (f.k === "balloon") { var by = f.y - f.t * 46, bxx = f.x + Math.sin(f.t * 2.2 + f.ph) * 9; c.globalAlpha = 1 - Math.max(0, u - .7) / .3; c.strokeStyle = "rgba(60,60,70,.6)"; c.lineWidth = .8; c.beginPath(); c.moveTo(bxx, by + 6); c.quadraticCurveTo(bxx + 3, by + 13, bxx, by + 20); c.stroke();
        c.fillStyle = f.c; c.beginPath(); c.ellipse(bxx, by, 5.4, 6.6, 0, 0, TAU); c.fill(); c.globalAlpha = 1; }
      else if (f.k === "say") { var sy = f.y - ease(Math.min(1, f.t * 4)) * 10; c.globalAlpha = u > .75 ? (1 - u) / .25 : 1; c.font = "700 13px Podkova, Georgia, serif"; var tw = c.measureText(f.text).width + 16;
        c.fillStyle = "#fffdf5"; c.strokeStyle = "#7a5533"; c.lineWidth = 1.6; rr(c, f.x - tw / 2, sy - 22, tw, 22, 9); c.fill(); c.stroke(); c.beginPath(); c.moveTo(f.x - 5, sy - .5); c.lineTo(f.x, sy + 7); c.lineTo(f.x + 5, sy - .5); c.closePath(); c.fill();
        c.fillStyle = "#33260f"; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText(f.text, f.x, sy - 10.5); c.globalAlpha = 1; }
      else if (f.k === "splash") { c.globalAlpha = 1 - u; c.fillStyle = "#e9fbff"; c.beginPath(); c.arc(f.x + f.vx * f.t, f.y + f.vy * f.t + 140 * f.t * f.t, 2.6, 0, TAU); c.fill(); c.globalAlpha = 1; }
    });
  };
  Scene.prototype.drawWeather = function (c) {
    var L = this.L, t = this.t, i;
    if (this.dusk > .6) return;
    if (this.weather === "rain") {
      c.fillStyle = "rgba(60,80,110,.2)"; c.fillRect(0, 0, L.w, L.h);
      c.strokeStyle = "rgba(220,235,255,.6)"; c.lineWidth = 1.4;
      for (i = 0; i < 110; i++) { var rx = (i * 137.5 + t * 120) % (L.w + 60) - 30, ry = (i * 71.3 + t * 520) % (L.h + 40) - 20; c.beginPath(); c.moveTo(rx, ry); c.lineTo(rx - 5, ry + 15); c.stroke(); }
    } else if (this.weather === "hot" || this.weather === "advisory") {
      c.fillStyle = this.weather === "advisory" ? "rgba(255,120,30,.16)" : "rgba(255,170,60,.1)"; c.fillRect(0, 0, L.w, L.h);
      c.fillStyle = "rgba(255,225,130,.5)"; for (i = 0; i < 5; i++) { c.beginPath(); c.arc(L.w - 60, 54, 30 + i * 13 + Math.sin(t * 2 + i) * 3, 0, TAU); c.globalAlpha = .1; c.fill(); } c.globalAlpha = 1;
      c.fillStyle = "#ffd75a"; c.beginPath(); c.arc(L.w - 60, 54, 24, 0, TAU); c.fill();
    } else {
      c.fillStyle = "rgba(255,255,255,.14)"; for (i = 0; i < 3; i++) { var cx = ((t * 9 + i * 420) % (L.w + 400)) - 200, cy = 90 + i * 190; c.beginPath(); c.ellipse(cx, cy, 130, 46, 0, 0, TAU); c.fill(); }
    }
  };
  Scene.prototype.drawLight = function (c) {
    var L = this.L, p = this.clock, self = this;
    if (this.dusk > 0.01) {
      var k2 = ease(this.dusk), mix = function (a) { return Math.round(255 - (255 - a) * k2); };
      c.globalCompositeOperation = "multiply"; c.fillStyle = "rgb(" + mix(154) + "," + mix(155) + "," + mix(208) + ")"; c.fillRect(0, 0, L.w, L.h); c.globalCompositeOperation = "source-over";
      // фонари вдоль дорожек
      c.globalCompositeOperation = "lighter";
      var lamps = [[L.plaza[0], L.plaza[1]]]; this.paths().forEach(function (pp) { lamps.push([lerp(pp[0], pp[2], .5), lerp(pp[1], pp[3], .5)]); lamps.push([pp[2], pp[3]]); });
      lamps.push([L.gate[0] + L.gate[2] / 2, L.gate[1] + 30]); lamps.push([L.kiosk[0] + L.kiosk[2] / 2, L.kiosk[1] + L.kiosk[3] / 2]);
      var kept = []; lamps.forEach(function (l) { if (!kept.some(function (m) { return Math.hypot(m[0] - l[0], m[1] - l[1]) < 70; })) kept.push(l); });
      kept.forEach(function (l, i) { var g = c.createRadialGradient(l[0], l[1], 2, l[0], l[1], 64); var fl = (.3 + .03 * Math.sin(self.t * 3 + i)) * k2; g.addColorStop(0, "rgba(255,196,110," + fl + ")"); g.addColorStop(1, "rgba(255,196,110,0)"); c.fillStyle = g; c.fillRect(l[0] - 66, l[1] - 66, 132, 132);
        c.fillStyle = "rgba(255,236,170," + (.9 * k2) + ")"; c.beginPath(); c.arc(l[0], l[1] - 14, 2.2, 0, TAU); c.fill(); });
      c.globalCompositeOperation = "source-over";
      c.fillStyle = "#fff3c4"; for (var i = 0; i < 26; i++) { var sx = (i * 173.7) % L.w, sy = (i * 97.3) % (L.h * .16); c.globalAlpha = (.35 + .3 * Math.sin(this.t * 1.5 + i)) * k2; c.beginPath(); c.arc(sx, sy + 4, 1.1, 0, TAU); c.fill(); } c.globalAlpha = 1;
      // звери спят
      if (this.mode === "evening") { c.fillStyle = "rgba(255,255,255," + (.75 * k2) + ")"; c.font = "700 13px Podkova, Georgia, serif"; c.textAlign = "left";
        ["cats", "yard", "tropic"].forEach(function (id, n) { var r = L[id], zx = r[0] + r[2] * .6, zy = r[1] + r[3] * .36, o = (self.t * .8 + n) % 3; for (var z = 0; z < 3; z++) { if (z <= o) c.fillText("z", zx + z * 9, zy - z * 9); } }); }
    } else if (this.mode === "day") {
      // утро тёплое, день ясный, к закрытию снова тёплый свет
      var warm = p < .2 ? (1 - p / .2) * .16 : p > .78 ? (p - .78) / .22 * .26 : 0;
      if (warm > 0) { c.fillStyle = "rgba(255,150,70," + warm + ")"; c.fillRect(0, 0, L.w, L.h); }
    }
  };

  Scene.prototype.poke = function (s) {
    if (!s || !this.L[s] || s === "gate" || s === "kiosk" || this.dead[s] || this.st[s].closed) return;
    if ((this.react[s] || 0) > this.rt) return;
    this.react[s] = this.rt + 1.8;
    var r = this.L[s], ru = this.lang === "ru", say = { cats: ru ? "Р-р-р!" : "Rrrr!", birds: ru ? "Чик-чирик!" : "Tweet!", yard: ru ? "Ме-е-е!" : "Meh-eh!", tropic: ru ? "У-у-у!" : "Woo-oop!", pool: ru ? "Ар! Ар!" : "Arf! Arf!" }[s];
    if (s === "pool") { if (!this.show) this.startShow(); } else this.sfx("animal:" + s);
    this.fx.push({ k: "say", x: r[0] + r[2] * .5, y: r[1] + r[3] * (s === "pool" ? .3 : .34), text: say, t: 0, life: 1.7 });
  };
  Scene.prototype.hit = function (px, py) {   // px, py в долях холста
    var L = this.L, x = px * L.w, y = py * L.h, out = null;
    SECT.concat(["gate", "kiosk"]).forEach(function (s) { var r = L[s]; if (x >= r[0] && x <= r[0] + r[2] && y >= r[1] && y <= r[1] + r[3]) out = s; });
    return out;
  };

  root.ZooScene = { create: function (cv, o) { return new Scene(cv, o); }, LAYOUT: LAYOUT, SECT: SECT };
})(typeof window !== "undefined" ? window : this);

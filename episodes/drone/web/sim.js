// Эпизод «курьер дронов»: симулятор смены для браузера. Перенос ../sim.py строка в строку (тот же порядок операций).
// Мир зерна берётся готовым из Python (в нём уже посчитаны ветер по высотам, плотность воздуха, порывы и заказы),
// поэтому в шаге остаются только + − × / и sqrt, и результат совпадает до последнего знака. Тест: parity.mjs.
(function (root) {
  "use strict";
  var DT = 1.0, SHIFT_S = 7200, END_S = 9000;
  var CITIES = ["almaty", "dubai", "rotterdam"];
  var ALTS = [30, 60, 100, 120];
  var SPEEDS = { eco: 12.0, fast: 18.0 };
  var D = {
    empty_kg: 65.0, mtow_kg: 95.0, payload_max: 40.0, battery_wh: 3968.8,
    hover_c: 44.48917540868399,          // = 8211.0 / 65.0 ** 1.25, значение взято из Python как есть
    wind_max: 12.0, wind_abort: 15.0,
    climb_ms: 3.0, climb_k: 1.15, descend_k: 0.9,
    service_s: 40.0, swap_depot_s: 90.0, swap_pad_s: 120.0, reserve: 0.08,
    pmax_w: 16000.0, pmax_hot_c: 40.0, pmax_46_w: 12000.0
  };
  var CRUISE_A = -0.32, CRUISE_B = 0.32;
  var SC = { base: 1000, delivered: 40, late_per_s: 0.1, undelivered: 60, forced: 250, lost: 600, pad: 10,
             energy_per_pct: 2, energy_min: -200, energy_max: 100 };

  // round() Питона: половина к чётному на точном двоичном значении
  function pyround(x, nd) {
    var p = nd ? Math.pow(10, nd) : 1, y = x * p, f = y - Math.trunc(y), r;
    if (f === 0.5 || f === -0.5) r = 2 * Math.round(y / 2);
    else r = Math.sign(y) * Math.round(Math.abs(y));
    return nd ? r / p : r;
  }

  // sum() Питона 3.12 для чисел с запятой: суммирование с поправкой по Нейемайеру
  function pysum(xs) {
    var f = 0.0, c = 0.0, i, t, x;
    for (i = 0; i < xs.length; i++) {
      x = xs[i]; t = f + x;
      if (Math.abs(f) >= Math.abs(x)) c += (f - t) + x; else c += (x - t) + f;
      f = t;
    }
    return xs.length ? f + c : 0;
  }

  function clock(t) {
    t = Math.trunc(t + 0.5);
    var h = 13 + Math.floor(t / 3600), m = Math.floor(t / 60) % 60, s = t % 60;
    return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }
  function rej(field, code, ru, en) { return { field: field, code: code, ru: ru, en: en }; }
  function f1(x) { return (Math.round(x * 10) / 10).toFixed(1); }
  function f0(x) { return Math.round(x).toFixed(0); }

  function seg_circle(ax, ay, bx, by, cx, cy, r) {
    var dx = bx - ax, dy = by - ay, L2 = dx * dx + dy * dy;
    var t = L2 === 0 ? 0.0 : ((cx - ax) * dx + (cy - ay) * dy) / L2;
    t = t < 0 ? 0.0 : (t > 1 ? 1.0 : t);
    var px = ax + t * dx - cx, py = ay + t * dy - cy;
    return px * px + py * py < r * r;
  }

  function Game(world) {
    this.W = world; this.city = world.city;
    this.M = world.map; this.pts = {};
    for (var i = 0; i < this.M.points.length; i++) this.pts[this.M.points[i].id] = this.M.points[i];
    this.t = 0.0;
    this.drones = [];
    for (i = 0; i < 3; i++) this.drones.push({ id: i, mode: "dock", x: 0.0, y: 0.0, agl: 0.0, soc: 1.0, load: [], route: [], wp: 0,
                                               phase: "", alt: 60, va: 12.0, busy: 0.0, gs: 0.0, wh: 0.0, pads: 0 });
    this.orders = [];
    for (i = 0; i < world.orders.length; i++) {
      var o = world.orders[i];
      this.orders.push({ t: o.t, point: o.point, kg: o.kg, due: o.due, id: o.id, status: "wait", drone: null, at: null });
    }
    this.counts = { delivered: 0, late_s: 0.0, forced: 0, lost: 0, pads: 0, wh: 0.0, ref_wh: 0.0 };
    this.journal = []; this.events = [];
  }
  var GP = Game.prototype;

  GP.hour = function () {
    return this.W.hours[Math.min(this.W.hours.length - 1, 1 + Math.floor(Math.trunc(this.t) / 3600))];
  };
  GP.ground = function (x, y) {
    var T = this.M.terrain, fx = (x - T.x0) / T.step, fy = (y - T.y0) / T.step;
    var i = Math.trunc(fx), j = Math.trunc(fy);
    i = i < 0 ? 0 : (i > T.nx - 2 ? T.nx - 2 : i); j = j < 0 ? 0 : (j > T.ny - 2 ? T.ny - 2 : j);
    var ax = fx - i, ay = fy - j;
    ax = ax < 0 ? 0.0 : (ax > 1 ? 1.0 : ax); ay = ay < 0 ? 0.0 : (ay > 1 ? 1.0 : ay);
    var z = T.z, n = T.nx;
    return (z[j * n + i] * (1 - ax) * (1 - ay) + z[j * n + i + 1] * ax * (1 - ay) +
            z[(j + 1) * n + i] * (1 - ax) * ay + z[(j + 1) * n + i + 1] * ax * ay);
  };
  GP.wind = function (alt, truth) {
    if (truth === undefined) truth = true;
    var hs = this.W.hours, f = this.t / 3600.0 + 1.0, i = Math.trunc(f);
    if (i > hs.length - 2) i = hs.length - 2;
    var a = f - i, key = truth ? "truth" : "fc";
    var u = hs[i][key][alt][0] * (1 - a) + hs[i + 1][key][alt][0] * a;
    var v = hs[i][key][alt][1] * (1 - a) + hs[i + 1][key][alt][1] * a;
    if (truth) { var g = this.W.gust[Math.floor(Math.trunc(this.t) / 10)]; u *= g; v *= g; }
    return [u, v];
  };
  GP.dens = function (z) {
    var d = this.hour().dens, f = z / 100.0, i = Math.trunc(f);
    i = i < 0 ? 0 : (i > d.length - 2 ? d.length - 2 : i);
    var a = f - i;
    a = a < 0 ? 0.0 : (a > 1 ? 1.0 : a);
    return d[i] * (1 - a) + d[i + 1] * a;
  };
  GP.mass = function (dr) {
    var kg = [];
    for (var i = 0; i < dr.load.length; i++) kg.push(this.orders[dr.load[i]].kg);
    return D.empty_kg + pysum(kg);
  };
  GP.p_hover = function (m, z) {
    return D.hover_c * m * Math.sqrt(Math.sqrt(m)) * this.dens(z);
  };
  GP.target = function (tok) {
    if (tok === "depot") return this.M.depot;
    if (tok[0] === "o") return this.pts[this.orders[parseInt(tok.slice(1), 10)].point];
    return this.pts[parseInt(tok.slice(1), 10)];
  };

  GP.check = function (dec) {
    var out = [], i = dec.drone, k, nf;
    if (typeof i !== "number" || i % 1 !== 0 || i < 0 || i > 2)
      return [rej("drone", "unknown", "Дронов три: 0, 1 и 2.", "There are three drones: 0, 1 and 2.")];
    var dr = this.drones[i];
    if (dec.recall) {
      if (dr.mode !== "air") out.push(rej("recall", "not_air", "Дрон " + i + " не в воздухе.", "Drone " + i + " is not in the air."));
      return out;
    }
    var route = dec.route;
    if (dr.mode !== "dock") return [rej("drone", "busy", "Дрон " + i + " сейчас не на складе.", "Drone " + i + " is not at the depot.")];
    if (dr.busy > 0) return [rej("drone", "swap", "Дрон " + i + " меняет батарею, ещё " + Math.trunc(dr.busy + 0.999) + " с.",
                                 "Drone " + i + " is swapping its battery, " + Math.trunc(dr.busy + 0.999) + " s more.")];
    if (!Array.isArray(route) || !route.length || route.length > 5)
      return [rej("route", "len", "Маршрут: от 1 до 5 остановок.", "A route has 1 to 5 stops.")];
    var alt = dec.alt === undefined ? 60 : dec.alt;
    if (ALTS.indexOf(alt) < 0) out.push(rej("alt", "alt", "Высота полёта: 30, 60, 100 или 120 м.", "Altitude: 30, 60, 100 or 120 m."));
    var speed = dec.speed === undefined ? "eco" : dec.speed;
    if (!(speed in SPEEDS)) out.push(rej("speed", "speed", "Скорость: эконом или быстро.", "Speed: eco or fast."));
    var kg = 0.0, seen = {}, pts = [this.M.depot];
    for (k = 0; k < route.length; k++) {
      var tok = route[k];
      if (typeof tok !== "string" || tok.length < 2 || "op".indexOf(tok[0]) < 0 || !/^[0-9]+$/.test(tok.slice(1))) {
        out.push(rej("route", "token", "Остановка «" + tok + "» не заказ (o…) и не площадка (p…).",
                     "Stop '" + tok + "' is neither an order (o…) nor a pad (p…)."));
        continue;
      }
      var n = parseInt(tok.slice(1), 10);
      if (tok[0] === "o") {
        if (n >= this.orders.length || this.orders[n].t > this.t) {
          out.push(rej("route", "no_order", "Заказа " + n + " ещё нет.", "Order " + n + " does not exist yet.")); continue;
        }
        var o = this.orders[n];
        if (o.status !== "wait" || seen[n]) {
          out.push(rej("route", "taken", "Заказ " + n + " уже доставлен или в пути.", "Order " + n + " is already delivered or on its way.")); continue;
        }
        seen[n] = true; kg += o.kg;
      } else {
        if (!(n in this.pts) || !this.pts[n].pad) {
          out.push(rej("route", "no_pad", "Точка " + n + " не площадка зарядки.", "Point " + n + " is not a charging pad.")); continue;
        }
      }
      pts.push(this.target(tok));
    }
    if (out.length) return out;
    if (kg > D.payload_max || D.empty_kg + kg > D.mtow_kg)
      out.push(rej("route", "mass", "Груз " + f1(kg) + " кг: дрон берёт не больше 40 кг, взлётная масса до 95 кг.",
                   "Load " + f1(kg) + " kg: the drone takes at most 40 kg, take-off mass up to 95 kg."));
    pts.push(this.M.depot);
    for (k = 0; k < pts.length - 1; k++) {
      var a = pts[k], b = pts[k + 1];
      for (var j = 0; j < this.M.nofly.length; j++) {
        nf = this.M.nofly[j];
        if (seg_circle(a.x, a.y, b.x, b.y, nf.x, nf.y, nf.r))
          out.push(rej("route", "nofly", "Плечо " + a.ru + " → " + b.ru + " проходит через зону «" + nf.ru + "».",
                       "Leg " + a.en + " → " + b.en + " crosses the zone '" + nf.en + "'."));
      }
    }
    var w0 = this.wind(30), w = Math.sqrt(w0[0] * w0[0] + w0[1] * w0[1]);
    if (w > D.wind_max)
      out.push(rej("drone", "wind", "Ветер у склада " + f1(w) + " м/с, предел дрона 12 м/с.",
                   "Wind at the depot " + f1(w) + " m/s, the drone's limit is 12 m/s."));
    var p = this.p_hover(D.empty_kg + kg, this.M.depot.z), hr = this.hour();
    if (p > hr.pmax)
      out.push(rej("route", "heat", "При " + f0(hr.t) + " °C батарея даёт " + f1(hr.pmax / 1000) + " кВт, а висение с грузом " +
                   f1(kg) + " кг требует " + f1(p / 1000) + " кВт.",
                   "At " + f0(hr.t) + " °C the battery gives " + f1(hr.pmax / 1000) + " kW, hovering with " + f1(kg) +
                   " kg needs " + f1(p / 1000) + " kW."));
    return out;
  };

  GP.decide = function (dec) {
    var r = this.check(dec);
    if (r.length) return r;
    var dr = this.drones[dec.drone], i;
    if (dec.recall) {
      dr.route = dr.route.slice(0, dr.wp).concat(["depot"]);
      if (dr.phase === "service") dr.phase = "climb";
      return [];
    }
    dr.mode = "air"; dr.route = dec.route.slice().concat(["depot"]); dr.wp = 0; dr.phase = "climb";
    dr.alt = dec.alt === undefined ? 60 : dec.alt; dr.va = SPEEDS[dec.speed === undefined ? "eco" : dec.speed]; dr.busy = 0.0;
    dr.load = [];
    for (i = 0; i < dec.route.length; i++) if (dec.route[i][0] === "o") dr.load.push(parseInt(dec.route[i].slice(1), 10));
    for (i = 0; i < dr.load.length; i++) { this.orders[dr.load[i]].status = "air"; this.orders[dr.load[i]].drone = dr.id; }
    this.events.push([this.t, "takeoff", dr.id]);
    return [];
  };

  GP.step = function () {
    var hr = this.hour(), di, i;
    for (di = 0; di < this.drones.length; di++) {
      var dr = this.drones[di];
      if (dr.mode === "dock" || dr.mode === "pad") {
        if (dr.busy > 0) {
          dr.busy -= DT;
          if (dr.busy <= 0) {
            dr.busy = 0.0; dr.soc = 1.0;
            if (dr.mode === "pad") { dr.mode = "air"; dr.phase = "climb"; dr.wp += 1; }
          }
        }
        continue;
      }
      if (dr.mode !== "air") continue;
      var m = this.mass(dr), zg = this.ground(dr.x, dr.y), ph = this.p_hover(m, zg + dr.agl);
      var wv = this.wind(dr.alt), u = wv[0], v = wv[1];
      var w = Math.sqrt(u * u + v * v);
      var P = ph;
      if (dr.phase === "climb") {
        P = ph * D.climb_k; dr.agl += D.climb_ms * DT;
        if (dr.agl >= dr.alt) { dr.agl = dr.alt + 0.0; dr.phase = "cruise"; }
      } else if (dr.phase === "cruise") {
        var tg = this.target(dr.route[dr.wp]), dx = tg.x - dr.x, dy = tg.y - dr.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        var ex = dist > 0 ? dx / dist : 0.0, ey = dist > 0 ? dy / dist : 0.0;
        var wa = u * ex + v * ey, wc = -u * ey + v * ex, va = dr.va;
        var gs = wc * wc < va * va ? (Math.sqrt(va * va - wc * wc) + wa) : wa;
        gs = gs < 0 ? 0.0 : gs;
        dr.gs = gs;
        var uu = va / 15.0;
        P = ph * (1 + CRUISE_A * uu + CRUISE_B * uu * uu);
        var stp = gs * DT;
        if (stp >= dist) { dr.x = tg.x; dr.y = tg.y; dr.phase = "descend"; }
        else { dr.x += ex * stp; dr.y += ey * stp; }
      } else if (dr.phase === "descend") {
        P = ph * D.descend_k; dr.gs = 0.0;
        var tok = dr.route[dr.wp], low = (tok === "depot" || tok[0] === "p") ? 0.0 : 20.0;
        dr.agl -= D.climb_ms * DT;
        if (dr.agl <= low) {
          dr.agl = low;
          if (tok === "depot") {
            dr.mode = "dock"; dr.phase = ""; dr.busy = D.swap_depot_s; dr.route = []; dr.wp = 0;
            for (i = 0; i < dr.load.length; i++) { this.orders[dr.load[i]].status = "wait"; this.orders[dr.load[i]].drone = null; }
            dr.load = [];
            this.events.push([this.t, "dock", dr.id]);
          } else if (tok[0] === "p") {
            dr.mode = "pad"; dr.busy = D.swap_pad_s; this.counts.pads += 1; dr.pads += 1;
            this.events.push([this.t, "pad", dr.id, parseInt(tok.slice(1), 10)]);
          } else {
            dr.phase = "service"; dr.busy = D.service_s;
          }
        }
      } else if (dr.phase === "service") {
        dr.busy -= DT;
        if (dr.busy <= 0) {
          var oi = parseInt(dr.route[dr.wp].slice(1), 10); dr.busy = 0.0;
          var at = dr.load.indexOf(oi);
          if (at >= 0) {
            dr.load.splice(at, 1);
            var od = this.orders[oi];
            od.status = "done"; od.at = this.t + DT;
            this.counts.delivered += 1;
            var late = this.t + DT - od.due;
            this.counts.late_s += late > 0 ? late : 0.0;
            this.events.push([this.t, "deliver", dr.id, oi]);
          }
          dr.wp += 1; dr.phase = "climb";
        }
      }
      if (dr.mode !== "air") continue;
      var used = P * DT / 3600.0;
      dr.wh += used; this.counts.wh += used;
      dr.soc -= used / (D.battery_wh * hr.cap);
      if (dr.soc <= 0) { this._down(dr, "lost"); continue; }
      if (P > hr.pmax || w > D.wind_abort || (dr.soc < D.reserve && dr.phase !== "descend")) this._forced(dr);
    }
    this.t += DT;
    if (Math.trunc(this.t) % 10 === 0) this._log();
  };

  GP._forced = function (dr) {
    var here = null, all = [this.M.depot].concat(this.M.points);
    for (var i = 0; i < all.length; i++) {
      var p = all[i], dx = p.x - dr.x, dy = p.y - dr.y;
      if (dx * dx + dy * dy < 50 * 50) here = p;
    }
    if (here === this.M.depot) { dr.route = dr.route.slice(0, dr.wp).concat(["depot"]); dr.phase = "descend"; return; }
    if (here !== null && here.pad) {
      if (dr.route[dr.wp] !== "p" + here.id) dr.route.splice(dr.wp, 0, "p" + here.id);
      dr.phase = "descend"; return;
    }
    this._down(dr, "forced");
  };

  GP._down = function (dr, kind) {
    dr.mode = kind; dr.phase = ""; dr.gs = 0.0;
    this.counts[kind] += 1;
    for (var i = 0; i < dr.load.length; i++) this.orders[dr.load[i]].status = kind === "lost" ? "lost" : "stuck";
    this.events.push([this.t, kind, dr.id, pyround(dr.x), pyround(dr.y)]);
  };

  GP._log = function () {
    var d = [];
    for (var i = 0; i < this.drones.length; i++) {
      var x = this.drones[i];
      d.push([pyround(x.x), pyround(x.y), pyround(x.agl), pyround(x.soc * 1000) / 10, x.mode, x.load.length]);
    }
    this.journal.push({ t: this.t, d: d });
  };

  GP.done = function () {
    if (this.t >= END_S) return true;
    if (this.t < SHIFT_S) return false;
    for (var i = 0; i < this.drones.length; i++) if (this.drones[i].mode === "air" || this.drones[i].mode === "pad") return false;
    return true;
  };

  GP.observe = function () {
    var hr = this.hour(), out_d = [], i, a;
    for (i = 0; i < this.drones.length; i++) {
      var d = this.drones[i], wv = d.mode === "air" ? this.wind(d.alt) : null;
      out_d.push({ id: d.id, mode: d.mode, phase: d.phase, x: d.x, y: d.y, agl: d.agl, soc: d.soc,
                   load: d.load.slice(), load_kg: pyround(this.mass(d) - D.empty_kg, 1), route: d.route.slice(d.wp), gs: d.gs,
                   busy: d.busy, wind_here: wv === null ? null : [pyround(wv[0], 2), pyround(wv[1], 2)] });
    }
    var w0 = this.wind(30), orders = [];
    for (i = 0; i < this.orders.length; i++) {
      var o = this.orders[i];
      if (o.t <= this.t) orders.push({ id: o.id, point: o.point, kg: o.kg, due: o.due, status: o.status });
    }
    var fc = [];
    for (i = 0; i < this.W.hours.length; i++) {
      var h = this.W.hours[i], wind = {};
      for (a = 0; a < ALTS.length; a++) wind[ALTS[a]] = h.fc[ALTS[a]];
      fc.push({ hour: 12 + i, t: h.t_fc, wind: wind });
    }
    return { t: this.t, clock: clock(this.t), city: this.city, drones: out_d, orders: orders,
             depot_wind: [pyround(w0[0], 2), pyround(w0[1], 2)], temp_now: hr.t, cap_now: hr.cap, pmax_now: hr.pmax,
             forecast: fc, map: { depot: this.M.depot, points: this.M.points, nofly: this.M.nofly } };
  };

  GP.ref_wh = function (o) {
    var p = this.pts[o.point], d = Math.sqrt(p.x * p.x + p.y * p.y);
    var c = 1 + CRUISE_A * 0.8 + CRUISE_B * 0.64;
    var hl = D.hover_c * (D.empty_kg + o.kg) * Math.sqrt(Math.sqrt(D.empty_kg + o.kg));
    var he = D.hover_c * D.empty_kg * Math.sqrt(Math.sqrt(D.empty_kg));
    return (hl + he) * c * d / 12.0 / 3600.0;
  };

  GP.score = function () {
    var parts = {}, c = this.counts, i, undelivered = 0, refs = [];
    for (i = 0; i < this.orders.length; i++) {
      if (this.orders[i].status !== "done") undelivered += 1;
      else refs.push(this.ref_wh(this.orders[i]));
    }
    var ref = pysum(refs);
    parts.delivered = SC.delivered * c.delivered;
    parts.late = -SC.late_per_s * c.late_s;
    parts.undelivered = -SC.undelivered * undelivered;
    parts.forced = -SC.forced * c.forced;
    parts.lost = -SC.lost * c.lost;
    parts.pads = -SC.pad * c.pads;
    var e = 0.0;
    if (ref > 0) {
      e = -SC.energy_per_pct * (100.0 * c.wh / ref - 100.0);
      e = e < SC.energy_min ? SC.energy_min : (e > SC.energy_max ? SC.energy_max : e);
    }
    parts.energy = e;
    var sc = 0.0, keys = ["delivered", "late", "undelivered", "forced", "lost", "pads", "energy"];
    for (i = 0; i < keys.length; i++) sc += parts[keys[i]];
    sc = SC.base + sc;
    var rp = {};
    for (i = 0; i < keys.length; i++) rp[keys[i]] = pyround(parts[keys[i]], 1);
    return { score: pyround(sc, 1), raw: sc, parts: rp,
             counts: { delivered: c.delivered, orders: this.orders.length, late_s: pyround(c.late_s), forced: c.forced,
                       lost: c.lost, pads: c.pads, kwh: pyround(c.wh / 1000, 2), ref_kwh: pyround(ref / 1000, 2) } };
  };

  var API = { Game: Game, clock: clock, seg_circle: seg_circle, pyround: pyround, pysum: pysum, D: D, SC: SC, ALTS: ALTS, SPEEDS: SPEEDS,
              CITIES: CITIES, DT: DT, SHIFT_S: SHIFT_S, END_S: END_S, CRUISE_A: CRUISE_A, CRUISE_B: CRUISE_B };
  if (typeof module !== "undefined" && module.exports) module.exports = API; else root.DroneSim = API;
})(this);

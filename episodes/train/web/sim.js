// Эпизод «машинист»: симулятор рейса для браузера. Перенос ../sim.py строка в строку (тот же порядок операций),
// мир зерна берётся готовым из Python (DATA.worlds), чтобы генератор и округления совпадали. Тест: parity.mjs.
(function (root) {
  "use strict";
  var G = 9.81, DT = 0.5;
  var P = {
    late_free_s: 30, atp_service_over_kmh: 5, atp_emergency_over_kmh: 15, atp_decel_share: 0.8, stop_window_m: 50,
    sand_k: 1.25, sand_s: 600, slip_k: 0.85, slide_k: 0.7, pusher_cost: 100,
    score: { base: 1000, late_per_s: 2, energy_per_pct: 4, stop_per_m: 5, stop_free_m: 2, atp: 150, emergency: 400, missed_stop: 500, harsh_per_s: 1, harsh_ms2: 1.0 }
  };

  function clock(t) {
    t = Math.floor(t + 0.5);
    var h = 10 + Math.floor(t / 3600), m = Math.floor(t / 60) % 60, s = t % 60;
    return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }
  function rej(field, code, ru, en) { return { field: field, code: code, ru: ru, en: en }; }

  function Game(line, train, world) {
    this.L = line; this.T = train; this.W = world;
    this.line_id = line.id;
    this.seg = line.segments.slice().sort(function (a, b) { return a.from_km - b.from_km; });
    this.stations = line.stations.filter(function (s) { return !s.pass; });
    this.tt = line.timetable || null;
    this.t = 0.0; this.x = 1000.0 * this.stations[0].km; this.v = 0.0; this.a = 0.0;
    this.lever = 0.0; this.sand_on = false; this.sand_left = P.sand_s; this.pusher = false;
    this.departed = false; this.stop_idx = 1; this.at_station = true; this.dwell_until = null;
    this.atp = null; this.emerg = false; this.sig_seen = false;
    this.E_in = 0.0; this.E_back = 0.0; this.harsh_s = 0.0;
    this.counts = { atp: 0, emergency: 0, missed_stops: 0, slip_s: 0.0, slide_s: 0.0 };
    this.stops = []; this.journal = []; this.decisions = []; this.slip = false; this.slide = false;
    this.dep_time = (this.tt ? this.tt[0].dep_s : 0) + world.depart_delay_s;
  }
  var GP = Game.prototype;

  GP.at = function (x) {
    var km = x / 1000.0;
    for (var i = 0; i < this.seg.length; i++) { var s = this.seg[i]; if (s.from_km <= km && km < s.to_km) return s; }
    return this.seg[this.seg.length - 1];
  };
  GP.zones = function () {
    var z = [], i;
    for (i = 0; i < this.seg.length; i++) z.push([1000.0 * this.seg[i].from_km, 1000.0 * this.seg[i].to_km, this.seg[i].limit_kmh]);
    for (i = 0; i < this.W.temp.length; i++) z.push([1000.0 * this.W.temp[i].from_km, 1000.0 * this.W.temp[i].to_km, this.W.temp[i].limit_kmh]);
    var sg = this.W.signal;
    if (sg && this.signal_visible()) z.push([1000.0 * sg.km, 1000.0 * (sg.km + sg.length_km), sg.limit_kmh]);
    return z;
  };
  GP.signal_visible = function () {
    var sg = this.W.signal;
    if (!sg) return false;
    if (this.sig_seen) return true;
    var dist = 1000.0 * sg.km - this.x;
    var vt = sg.limit_kmh / 3.6;
    var need = (this.v * this.v - vt * vt) / (2 * this.brake_curve_decel(1000.0 * sg.km)) * 1.3 + 500.0;
    if (dist <= 1000.0 * sg.sight_km || dist <= need) this.sig_seen = true;
    return this.sig_seen;
  };
  GP.limit_now = function () {
    var lo = this.x - this.T.length_m, v = 1e9, z = this.zones();
    for (var i = 0; i < z.length; i++) if (z[i][1] > lo && z[i][0] <= this.x) v = Math.min(v, z[i][2]);
    return v / 3.6;
  };
  GP.brake_curve_decel = function (to_x) {
    if (to_x === undefined || to_x === null) to_x = this.x;
    var gmin = this.at(this.x).grade_permille;
    for (var i = 0; i < this.seg.length; i++) {
      var s = this.seg[i];
      if (1000.0 * s.to_km > this.x && 1000.0 * s.from_km < to_x && s.grade_permille < gmin) gmin = s.grade_permille;
    }
    var d = this.T.brake.service_ms2 * P.atp_decel_share + G * gmin / 1000.0;
    return d > 0.1 ? d : 0.1;
  };
  GP.permitted = function () {
    var lim = this.limit_now(), z = this.zones();
    for (var i = 0; i < z.length; i++) {
      var a = z[i][0], lk = z[i][2];
      if (a > this.x && a - this.x < 25000) {
        var vt = lk / 3.6;
        lim = Math.min(lim, Math.sqrt(vt * vt + 2 * this.brake_curve_decel(a) * (a - this.x)));
      }
    }
    var st = this.next_stop();
    if (st && !this.at_station) {
      var sx = 1000.0 * st.km;
      var dist = sx - this.x + P.stop_window_m;
      lim = Math.min(lim, Math.sqrt(2 * this.brake_curve_decel(sx) * Math.max(0.0, dist)) + 0.5);
    }
    return lim;
  };
  GP.next_stop = function () { return this.stop_idx < this.stations.length ? this.stations[this.stop_idx] : null; };
  GP.due = function () { return !this.departed ? this.dep_time : (this.dwell_until || 0.0); };
  GP.mass = function () { return this.T.mass_t + (this.pusher ? this.T.pusher.mass_t : 0); };
  GP.mu = function (v) {
    var k = this.W.adhesion_factor * (this.sand_on ? P.sand_k : 1.0);
    return (7.5 / (v * 3.6 + 44.0) + 0.161) * k;
  };
  GP.adh_force = function (v) {
    var pw = this.T.mass_t * this.T.powered_share + (this.pusher ? this.T.pusher.mass_t : 0);
    return this.mu(v) * pw * 1000.0 * G;
  };
  GP.tractive_max = function (v) {
    var T = this.T, f0 = T.start_tractive_kN * 1000.0, p = T.power_kW * 1000.0;
    if (this.pusher) { f0 += T.pusher.start_tractive_kN * 1000.0; p += T.pusher.power_kW * 1000.0; }
    return v < 1e-6 ? f0 : Math.min(f0, p / v);
  };
  GP.resist = function (v) {
    var vk = v * 3.6, m = this.mass(), r;
    if (this.T.resistance === "strahl") {
      r = G * m * (2.2 + 80.0 / (vk + 38.0) + 0.00032 * vk * vk);
    } else {
      var A = this.T.davis[0], B = this.T.davis[1], C = this.T.davis[2];
      r = (A + B * vk + C * vk * vk) * 1000.0;
    }
    var s = this.at(this.x);
    var grade = m * 1000.0 * G * s.grade_permille / 1000.0;
    var R = s.radius_m, curve = 0.0;
    if (R) curve = m * G * (R > 300 ? 650.0 / (R - 55.0) : 500.0 / (R - 30.0));
    return [r + curve, grade];
  };

  GP.observe = function () {
    var st = this.next_stop(), z = this.zones().slice().sort(function (a, b) { return a[0] - b[0] || a[1] - b[1] || a[2] - b[2]; }), ahead = [];
    for (var i = 0; i < z.length; i++) if (z[i][1] > this.x && z[i][0] - this.x < 30000) ahead.push({ from_km: z[i][0] / 1000, to_km: z[i][1] / 1000, limit_kmh: z[i][2] });
    var tt = (this.tt && st) ? this.tt[this.stop_idx] : null;
    return {
      t: this.t, clock: clock(this.t), km: this.x / 1000.0, v_kmh: this.v * 3.6, a_ms2: this.a, lever: this.lever,
      limit_kmh: this.limit_now() * 3.6, permitted_kmh: this.permitted() * 3.6, grade_permille: this.at(this.x).grade_permille, ahead: ahead.slice(0, 10),
      next_stop: st ? { name: st.name, km: st.km, dist_m: 1000.0 * st.km - this.x, arr_s: tt ? tt.arr_s : null, arr_clock: tt ? clock(tt.arr_s) : null } : null,
      departed: this.departed, due_s: this.due(), due_clock: clock(this.due()), at_station: this.at_station,
      weather: this.W.weather, warnings: this.W.temp, depart_delay_s: this.W.depart_delay_s,
      signal: this.signal_visible() ? this.W.signal : null, slip: this.slip, slide: this.slide, sand_on: this.sand_on, sand_left_s: this.sand_left,
      pusher: this.pusher, pusher_available: !!this.T.pusher, atp: this.atp, emergency: this.emerg,
      energy_kwh: (this.E_in - this.E_back) / 3.6e6, stops: this.stops.slice(), line: this.line_id
    };
  };

  GP.check = function (dec) {
    var out = [], ok = {};
    if ("pusher" in dec) {
      if (this.departed) out.push(rej("pusher", "late", "Толкач ставят только до отправления.", "A banking engine is only added before departure."));
      else if (!this.T.pusher) out.push(rej("pusher", "none", "На этом участке толкача нет.", "No banking engine on this line."));
      else ok.pusher = !!dec.pusher;
    }
    if ("lever" in dec) {
      var lv = dec.lever;
      if (typeof lv !== "number" || lv < -1 || lv > 1) out.push(rej("lever", "range", "Рычаг от −1 (тормоз) до 1 (тяга).", "Lever goes from −1 (brake) to 1 (power)."));
      else if (lv > 0 && this.at_station && this.t < this.due())
        out.push(rej("lever", "early", "Отправление в " + clock(this.due()) + ", сейчас " + clock(this.t) + ": раньше графика нельзя.",
          "Departure is at " + clock(this.due()) + ", it is " + clock(this.t) + ": you cannot leave early."));
      else ok.lever = lv;
    }
    if ("sand" in dec) {
      if (dec.sand && this.sand_left <= 0) out.push(rej("sand", "empty", "Песок кончился.", "Out of sand."));
      else ok.sand = !!dec.sand;
    }
    if (dec.emergency) ok.emergency = true;
    return [out, ok];
  };
  GP.decide = function (dec) {
    var r = this.check(dec), out = r[0], ok = r[1];
    if ("pusher" in ok) this.pusher = ok.pusher;
    if ("lever" in ok) this.lever = ok.lever;
    if ("sand" in ok) this.sand_on = ok.sand;
    if (ok.emergency && !this.emerg) { this.emerg = true; this.counts.emergency += 1; }
    var other = Object.keys(dec).some(function (k) { return k !== "lever"; });
    if (out.length || other) this.decisions.push({ t: this.t, dec: dec, rej: out });
    return out;
  };

  GP.step = function () {
    var S = P;
    if (this.at_station && this.v < 0.01 && (this.lever <= 0 || this.t < this.due())) { this.t += DT; this._log(); return; }
    if (this.at_station && this.lever > 0) { this.at_station = false; this.departed = true; }
    var lever = this.lever;
    var perm = this.permitted(), over = (this.v - perm) * 3.6;
    if (over > S.atp_emergency_over_kmh && !this.emerg) { this.emerg = true; this.counts.emergency += 1; }
    else if (!this.emerg && (this.atp || over > S.atp_service_over_kmh)) {
      if (!this.atp) { this.atp = "service"; this.counts.atp += 1; }
      if (over < -2) this.atp = null; else lever = -1.0;
    }
    var m = this.mass() * 1000.0 * (this.T.rot_mass || 1.06);
    var rg = this.resist(this.v), r = rg[0], grade = rg[1], acc, dec;
    this.slip = false; this.slide = false;
    if (this.sand_on) { this.sand_left = Math.max(0.0, this.sand_left - DT); if (this.sand_left <= 0) this.sand_on = false; }
    if (this.emerg) {
      dec = Math.min(this.T.brake.emergency_ms2, this.mu(this.v) * G);
      acc = (-r - grade) / m - dec;
    } else if (lever > 0) {
      var f = lever * this.tractive_max(this.v), adh = this.adh_force(this.v);
      if (f > adh) { this.slip = true; this.counts.slip_s += DT; f = adh * S.slip_k; }
      acc = (f - r - grade) / m;
      this.E_in += f * this.v * DT / (this.T.eff_traction || 0.85);
    } else {
      var dem = -lever * this.T.brake.service_ms2, lim = this.mu(this.v) * G;
      dec = dem;
      if (dem > lim) { this.slide = true; this.counts.slide_s += DT; dec = lim * S.slide_k; }
      acc = (-r - grade) / m - dec;
      if (dec > 0) {
        var p = dec * m * this.v;
        if (p > this.T.power_kW * 1000.0) p = this.T.power_kW * 1000.0;
        this.E_back += p * DT * (this.T.regen_eff || 0.0);
      }
    }
    if (this.v <= 0.0 && acc < 0 && lever <= 0) acc = 0.0;
    if (Math.abs(acc) > S.score.harsh_ms2) this.harsh_s += DT;
    this.a = acc;
    var v_new = this.v + acc * DT;
    if (v_new < 0) v_new = 0.0;
    this.x += (this.v + v_new) / 2.0 * DT;
    this.v = v_new; this.t += DT;
    if (this.emerg && this.v < 0.01) { this.emerg = false; this.atp = null; this.lever = 0.0; }
    var st = this.next_stop();
    if (st) {
      var d = this.x - 1000.0 * st.km;
      if (this.v < 0.01 && Math.abs(d) <= S.stop_window_m) {
        var tt = this.tt ? this.tt[this.stop_idx] : null;
        this.stops.push({ name: st.name, t: this.t, err_m: d, late_s: tt ? this.t - tt.arr_s : null });
        this.at_station = true; this.lever = 0.0;
        var dep = (tt && tt.dep_s !== null && tt.dep_s !== undefined) ? tt.dep_s : this.t + (st.dwell_s || 0);
        this.dwell_until = Math.max(this.t + (st.dwell_s || 0), dep);
        this.stop_idx += 1;
      } else if (d > S.stop_window_m) {
        this.counts.missed_stops += 1;
        this.stops.push({ name: st.name, t: this.t, err_m: d, late_s: null, missed: true });
        this.stop_idx += 1;
      }
    }
    this._log();
  };
  GP._log = function () {
    if (Math.floor(this.t * 2 + 0.5) % 20 === 0)
      this.journal.push({ t: this.t, km: this.x / 1000.0, v: this.v * 3.6, e: (this.E_in - this.E_back) / 3.6e6, lim: this.limit_now() * 3.6, perm: this.permitted() * 3.6, atp: this.atp, emerg: this.emerg, slip: this.slip });
  };
  GP.done = function () { return this.stop_idx >= this.stations.length || this.t > 4 * 3600; };
  GP.score = function () {
    var Sc = P.score, parts = {}, late = 0.0, stop_err = 0.0;
    for (var i = 0; i < this.stops.length; i++) {
      var s = this.stops[i];
      if (s.missed) continue;
      if (s.late_s !== null) late += Math.max(0.0, s.late_s - P.late_free_s);
      stop_err += Math.max(0.0, Math.abs(s.err_m) - Sc.stop_free_m);
    }
    var unfinished = this.stop_idx >= this.stations.length ? 0 : 1;
    var kwh = (this.E_in - this.E_back) / 3.6e6, ref = this.L.ref_kwh;
    parts.late = -Sc.late_per_s * late;
    parts.energy = ref ? -Sc.energy_per_pct * (100.0 * kwh / ref - 100.0) : 0.0;
    if (unfinished && parts.energy > 0) parts.energy = 0.0;
    parts.stop_precision = -Sc.stop_per_m * stop_err;
    parts.protection = -Sc.atp * this.counts.atp - Sc.emergency * this.counts.emergency;
    parts.missed_stops = -Sc.missed_stop * this.counts.missed_stops;
    parts.comfort = -Sc.harsh_per_s * this.harsh_s;
    parts.pusher = this.pusher ? -P.pusher_cost : 0;
    parts.unfinished = -1000 * unfinished;
    var sum = 0;  // как sum(parts.values()) в Python: сначала сумма частей, потом база
    ["late", "energy", "stop_precision", "protection", "missed_stops", "comfort", "pusher", "unfinished"].forEach(function (k) { sum += parts[k]; });
    var sc = Sc.base + sum;
    return { score: sc, parts: parts, kwh: kwh, time_min: this.t / 60.0, stops: this.stops, counts: this.counts };
  };

  var API = { Game: Game, clock: clock, P: P, G: G, DT: DT };
  if (typeof module !== "undefined" && module.exports) module.exports = API; else root.TrainSim = API;
})(this);

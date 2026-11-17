// Эпизод «Зоопарк»: перенос zoo/sim.py строка в строку. Тест совпадения: zoo/web/parity.mjs.
// Мир (world_ny.json) передаётся аргументом: страница кладёт его в себя, файлов не читает.
//   const g = new ZooSim.Game(seed, place, team, scenario, world);
//   while (!g.done()) { const obs = g.observe(); const rej = g.decide({...}); g.step(); }
//   g.score();
// check(dec) возвращает [отказы, принятое] и ничего не меняет: страница зовёт его на каждый ввод.
(function (root) {
"use strict";
const D = (typeof module !== "undefined" && module.exports) ? require("./det.js") : root.ZooDet;
const { rnd, cents, fnv, Rng, clamp, sum, split_lr, days_in_month, weekday } = D;

const SECTIONS = ["pool", "cats", "birds", "yard", "tropic"];
const HALF_N = 2;
const WD_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];
const WD_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HALF_RU = ["утро", "день"];
const HALF_EN = ["morning", "afternoon"];
const FEEDS = ["fish", "meat", "hay", "produce"];
const THAWED = ["fish", "meat"];

// ---------- Python наизнанку ----------
const isObj = (x) => x !== null && typeof x === "object" && !Array.isArray(x);
// isinstance(x, int) and not isinstance(x, bool)
const isIntStrict = (x) => Number.isInteger(x);
// isinstance(x, int) как есть: в Python True это 1 (в sim.py так проверяют кассиров, киоск и шоу)
const isIntPy = (x) => Number.isInteger(x) || typeof x === "boolean";
// isinstance(x, (int, float)) and not isinstance(x, bool)
const isNumPy = (x) => typeof x === "number";
// истинность как в Python: 0, "", [], {}, null ложны
const truthy = (x) => Array.isArray(x) ? x.length > 0 : isObj(x) ? Object.keys(x).length > 0 : !!x;
const or = (x, d) => (truthy(x) ? x : d);
const has = (o, k) => isObj(o) && Object.prototype.hasOwnProperty.call(o, k);
const get = (o, k, d) => (has(o, k) ? o[k] : d);
const clone = (x) => JSON.parse(JSON.stringify(x));
const pad = (n, k) => String(n).padStart(k, "0");
const range = (lo, hi) => { const a = []; for (let d = lo; d <= hi; d++) a.push(d); return a; };
// str() для чисел в текстах отказов. Внимание: Python печатает float 40.0 как «40.0», а JSON отдаёт в JS число 40.
// Все числа в решениях игры целые или с дробной частью, поэтому строки совпадают.
const pstr = (x) => String(x);

// «%.nf» и round(x, n) Python: округление половинок к чётному по точному двоичному значению.
function pyfix(x, n) {
  const neg = x < 0;
  const a = Math.abs(x);
  if (!isFinite(a) || a >= 1e21) return (neg ? "-" : "") + a.toFixed(n);
  const s = a.toFixed(100);                      // точное десятичное представление double
  const dot = s.indexOf(".");
  const ip = s.slice(0, dot), fp = s.slice(dot + 1);
  let digits = ip + fp.slice(0, n).padEnd(n, "0");
  const rest = fp.slice(n);
  const first = rest.length ? rest.charCodeAt(0) - 48 : 0;
  const restNZ = /[1-9]/.test(rest.slice(1));
  const last = digits.charCodeAt(digits.length - 1) - 48;
  if (first > 5 || (first === 5 && (restNZ || last % 2 === 1))) digits = (BigInt(digits) + 1n).toString();
  digits = digits.padStart(n + 1, "0");
  const out = n ? digits.slice(0, digits.length - n) + "." + digits.slice(digits.length - n) : digits;
  return (neg ? "-" : "") + out;
}
const pyround = (x, n) => Number(pyfix(x, n));
const f1 = (x) => pyfix(x, 1);
const f2 = (x) => pyfix(x, 2);

const rej = (field, code, ru, en) => ({ field, code, ru, en });

const OPTIONS = {
  heatwave: ["shade", "close_midday", "none"], cubs_press: ["press", "quiet"], cubs_watch: ["keeper", "camera", "none"],
  hpai: ["all_indoor", "vulnerable", "none"], pump: ["fast", "slow"], power: ["generator", "move", "none"],
  sealion: ["vet_now", "vet_full", "wait"], school: ["accept", "decline"], donor: ["tour", "decline"], sick: ["ok"],
};
const card_options = (kind) => OPTIONS[kind].slice();

const DEFAULT = { heatwave: "close_midday", cubs_press: "quiet", cubs_watch: "none", hpai: "none", pump: "slow", power: "none",
  sealion: "vet_now", school: "decline", donor: "decline", sick: "ok" };

// Варианты, которые запрещает закон: Проверка отказывает
const FORBIDDEN = {
  "heatwave|none": ["Морские млекопитающие не остаются на улице при Heat Advisory без тени и укрытия (9 CFR 3.103, пороги NWS): нужно «тень» или «закрыть днём».",
    "Marine mammals cannot stay outdoors in a Heat Advisory without shade and shelter (9 CFR 3.103, NWS thresholds): choose shade or close midday."],
  "sealion|wait": ["Морской лев не ест больше 24 часов: по 9 CFR 3.105 нужно сразу сообщить ветеринару, ждать нельзя.",
    "A sea lion off food for more than 24 hours must be reported to the vet at once (9 CFR 3.105); waiting is not allowed."],
};

// ---------- мир ----------
function make_world(seed, place, team, scenario, W) {
  const sc = W.scenarios[scenario];
  const [y, m, d0] = sc.start;
  const n = W.days;
  const R = (label) => new Rng(fnv(String(seed) + ":" + label));
  const dim = days_in_month(y, m);
  const wx = W.weather[sc.weather];
  const wd0 = weekday(y, m, d0);
  const rw = R("weather");
  const days = [];
  for (let i = 0; i < n; i++) {
    const date = pad(y, 4) + "-" + pad(m, 2) + "-" + pad(d0 + i, 2);
    const u = rw.u();
    const p_hot = wx.hot_days / dim, p_rain = wx.rain_days / dim;
    const w = u < p_hot ? "hot" : u < p_hot + p_rain ? "rain" : "clear";
    days.push({ date, wd: (wd0 + i) % 7, weather: w, holiday: has(W.holidays, date) ? W.holidays[date] : 1.0 });
  }
  const rn = R("noise");
  const noise = [];
  for (let i = 0; i < n; i++) { const r = []; for (let h = 0; h < HALF_N; h++) r.push(1 + W.noise * (2 * rn.u() - 1)); noise.push(r); }
  const re = R("events");
  const used = new Set();
  const E = W.events;

  function free_day(lo, hi, pred) {
    pred = pred || (() => true);
    let cand = range(lo, hi).filter((d) => !used.has(d) && pred(d));
    if (!cand.length) cand = range(lo, hi).filter((d) => pred(d));
    if (!cand.length) cand = range(lo, hi);
    const d = cand[re.int(0, cand.length - 1)];
    used.add(d);
    return d;
  }

  const events = [];
  sc.events.forEach((kind, k) => {
    const ev = { id: kind + "_" + k, kind };
    if (kind === "heatwave") {
      const d = free_day(10, 20);
      for (let j = 0; j < E.heatwave.days; j++) { days[d + j].weather = "advisory"; used.add(d + j); }
      ev.day = d; ev.show = d - E.heatwave.notice; ev.hidden = {};
    } else if (kind === "cubs") {
      const d = free_day(6, 14);
      ev.day = d; ev.show = null; ev.hidden = { boost: E.cubs.boost[re.int(0, 2)], u_loss: re.u() };
      events.push(ev);
      events.push({ id: "cubs_press_" + k, kind: "cubs_press", day: d + 1, show: d + 1, parent: ev.id });
      events.push({ id: "cubs_watch_" + k, kind: "cubs_watch", day: d + 1, show: d + 1, parent: ev.id });
      return;
    } else if (kind === "hpai") {
      const d = free_day(4, 9);
      ev.day = d; ev.show = d; ev.hidden = { u: re.u() };
    } else if (kind === "inspection") {
      ev.day = free_day(6, 27); ev.show = null;
    } else if (kind === "pump") {
      const d = free_day(3, 26);
      ev.day = d; ev.show = d + 1;        // сломался в день d, карточка вечером дня d про день d+1
    } else if (kind === "power") {
      const d = free_day(5, 26);
      ev.day = d; ev.show = d - E.power.notice; ev.hidden = { u: re.u() };
    } else if (kind === "sealion") {
      const d = free_day(3, 26);
      ev.day = d; ev.show = d + 1; ev.hidden = { u: re.u() };
    } else if (kind === "school") {
      const d = free_day(2, 27, (x) => days[x].wd < 5);
      ev.day = d; ev.show = d - 3;
    } else if (kind === "donor") {
      const d = free_day(5, 25);
      ev.day = d; ev.show = d - 2; ev.hidden = { amount: E.donor.amounts[re.pick_w([0.4, 0.4, 0.2])] };
    } else if (kind === "sick") {
      const d = free_day(1, 27);
      ev.day = d; ev.show = d;
    } else if (kind === "no_show") {
      ev.day = free_day(2, 27, (x) => W.suppliers.frozen.days.includes(days[x].wd)); ev.show = null;
    }
    events.push(ev);
  });
  events.sort((a, b) => a.day - b.day || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  return { seed, place, team, scenario, days, noise, events };
}

function default_schedule(W) {
  const row = { keepers: {}, cashiers: [2, 3], kiosk: [2, 3], shows: 0 };
  for (const s of SECTIONS) row.keepers[s] = W.sections[s].min.slice();
  const out = {};
  for (let w = 0; w < 7; w++) out[String(w)] = clone(row);
  return out;
}

class Game {
  constructor(seed, place, team, scenario, world) {
    const W = this.Wd = world;
    this.X = make_world(seed, place, team, scenario, W);
    this.t = 0;
    const sc = W.scenarios[scenario];
    const [y, m] = sc.start;
    this.base_day = W.visitors_year * W.places[place].mult * sc.month_share / days_in_month(y, m);
    this.staff = [];
    for (let i = 0; i < W.teams[team]; i++) this.staff.push({ id: "k" + (i + 1), start: 0 });
    this.next_id = W.teams[team] + 1;
    const S = W.start_stock;
    this.freezer = Object.assign({}, S.freezer); this.thawed_next = Object.assign({}, S.thawed);
    this.hay = S.hay; this.produce = S.produce.map((x) => x.slice());
    this.schedule = default_schedule(W);
    this.price = W.prices.adult; this.free_wed = false;
    this.orders = {};
    this.vet_tomorrow = false; this.vet_visits = 0;
    this.choices = {};
    this.rep = W.reputation.start;
    this.week_hours = 0.0;
    this.violations = [];          // [день, секция, причина]
    this.dead = [];                // [день, что]
    this.flags = {};               // долгие последствия: hpai_hit_from, cubs_lost_from
    this.totals = {};
    for (const k of ["tickets", "food", "souvenirs", "donations", "school", "cogs", "card_fees", "wages", "feed", "refunds", "electricity", "vet", "event_costs"]) this.totals[k] = 0.0;
    this.counts = { visitors: 0, demand: 0, queue_lost: 0, section_violation_days: 0, inspection_findings: 0, deaths: 0, thaw_waste_kg: 0.0, produce_waste_kg: 0.0, shows: 0 };
    this.journal = [];
    this.last_report = null;
    this.pending_rejections = []; this.pending_decisions = [];
  }

  // --- служебное ---
  done() { return this.t >= this.Wd.days; }

  ev(kind) { return this.X.events.filter((e) => e.kind === kind); }

  choice(e) { return has(this.choices, e.id) ? this.choices[e.id] : get(DEFAULT, e.kind, undefined); }

  headcount(day, include_pending = false) { return this.staff.filter((s) => include_pending || s.start <= day).length; }

  sick_out(day) { return this.ev("sick").filter((e) => e.day <= day && day < e.day + this.Wd.events.sick.days).length; }

  // Добавки к минимуму смены от событий: перевод животных при отключении света, экскурсия донора.
  extra_min(day) {
    const add = {};
    for (const s of SECTIONS) add[s] = [0, 0];
    for (const e of this.ev("power")) if (e.day === day && this.choice(e) === "move") add.tropic = [1, 1];
    for (const e of this.ev("donor")) if (e.day === day && this.choice(e) === "tour") add.cats = [this.Wd.events.donor.cats_halves, 0];
    return add;
  }

  // --- спрос ---
  demand_mult(day, hidden) {
    const W = this.Wd, Dy = this.X.days[day];
    let m = W.weekday_mult[Dy.wd] * Dy.holiday * W.weather_mult[Dy.weather];
    const notes = []; let extra = 0.0;
    if (Dy.weather === "advisory") notes.push("advisory");
    const E = W.events;
    for (const e of this.X.events) {
      const k = e.kind;
      if (k === "heatwave" && e.day <= day && day < e.day + E.heatwave.days && this.choice(e) === "close_midday") {
        m *= E.heatwave.close_mult; notes.push("closed_midday");
      } else if (k === "cubs_press" && day >= e.day + 1) {
        const parent = this.X.events.find((x) => x.id === e.parent);
        if (get(this.flags, "cubs_lost_from", null) !== null && day >= this.flags.cubs_lost_from) continue;
        if (this.choice(e) === "press") {
          if (hidden) m *= 1 + parent.hidden.boost;
          else { const b = E.cubs.boost; m *= 1 + sum(b) / b.length; extra += 0.1; }
        } else {
          m *= 1 + E.cubs.quiet_boost;
        }
        notes.push("cubs");
      } else if (k === "hpai" && day >= e.day) {
        m *= E.hpai.mult[this.choice(e)];
        if (hidden && get(this.flags, "hpai_hit_from", null) !== null && day >= this.flags.hpai_hit_from) m *= E.hpai.hit_mult;
        if (!hidden && this.choice(e) !== "all_indoor") extra += 0.05;
        notes.push("hpai");
      } else if (k === "pump" && day === e.day + 1 && this.choice(e) === "slow") {
        m *= E.pump.slow_mult; notes.push("pool_closed_pm");
      } else if (k === "power" && day === e.day && this.choice(e) === "move") {
        m *= E.power.move_mult; notes.push("tropic_closed");
      }
    }
    if (!hidden && get(this.flags, "hpai_hit_from", null) !== null && day >= this.flags.hpai_hit_from) m *= E.hpai.hit_mult;
    if (!hidden && get(this.flags, "cubs_lost_from", null) !== null && day >= this.flags.cubs_lost_from) notes.push("cubs_lost");
    // цена
    const pi = this.price / W.prices.adult;
    m *= Math.pow(pi, pi > 1 ? W.elasticity.up : W.elasticity.down);
    return [m * this.rep, notes, extra];
  }

  expected(day, hidden) {
    const [m, notes, extra] = this.demand_mult(day, hidden);
    const W = this.Wd, Dy = this.X.days[day];
    const out = [];
    for (let h = 0; h < HALF_N; h++) {
      let v = this.base_day * W.halves.share[h] * m;
      if (h === 1 && Dy.wd === 2 && this.free_wed) v *= W.free_wed.afternoon_mult;
      out.push(v);
    }
    return [out, notes, extra];
  }

  // --- наблюдение ---
  open_cards() {
    const ev_ = this.t - 1;
    const cards = [];
    for (const e of this.X.events) {
      if (get(e, "show", null) === null || ["cubs", "inspection", "no_show"].includes(e.kind)) continue;
      const k = e.kind;
      let deadline = e.day - 1;
      let first = e.show - 1;
      if (k === "pump" || k === "sealion") { first = e.day; deadline = e.day; }
      if (k === "cubs_press" || k === "cubs_watch") { first = e.day - 1; deadline = e.day - 1; }
      if (first <= ev_ && ev_ <= deadline) {
        cards.push({ id: e.id, kind: k, day: (k === "pump" || k === "sealion") ? e.day + 1 : e.day, options: card_options(k),
          chosen: has(this.choices, e.id) ? this.choices[e.id] : null, default: DEFAULT[k], decide_by_evening_of: deadline });
      }
    }
    return cards;
  }

  observe() {
    const W = this.Wd, t = this.t, n = W.days;
    const fc = [];
    for (let d = t; d < Math.min(t + 3, n); d++) {
      const [g, notes, extra] = this.expected(d, false);
      const band = W.noise + extra;
      const Dy = this.X.days[d];
      fc.push({ day: d, date: Dy.date, wd: Dy.wd, weather: Dy.weather, notes,
        visitors: g.map((x) => rnd(x)), low: g.map((x) => rnd(x * (1 - band))), high: g.map((x) => rnd(x * (1 + band))) });
    }
    const nxt = t < n ? this.X.days[t] : null;
    const sup = {};
    for (const [s, S] of Object.entries(W.suppliers)) {
      const prices_kg = {};
      for (const [k, v] of Object.entries(S.items)) prices_kg[k] = v.price_kg;
      sup[s] = { days: S.days, delivers_tomorrow: nxt !== null && S.days.includes(nxt.wd), prices_kg,
        min_order: get(S, "min_order", null), min_kg: get(S, "min_kg", null), case_kg: get(S, "case_kg", null), bale_kg: get(S, "bale_kg", null) };
    }
    const freezer = {}; for (const [k, v] of Object.entries(this.freezer)) freezer[k] = cents(v);
    const thawed = {}; for (const [k, v] of Object.entries(this.thawed_next)) thawed[k] = cents(v);
    const totals = {}; for (const [k, v] of Object.entries(this.totals)) totals[k] = cents(v);
    return {
      day: t, date: nxt ? nxt.date : null, wd: nxt ? nxt.wd : null, days_total: n,
      reputation: pyround(this.rep, 3),
      stock: { freezer, thawed_for_tomorrow: thawed, hay: cents(this.hay),
        produce: this.produce.map(([a, b]) => [cents(a), b]), freezer_kg: W.freezer_kg, hay_store_kg: W.hay_store_kg },
      need_kg_per_day: { fish: W.sections.pool.need_kg, meat: W.sections.cats.need_kg, hay: W.sections.yard.need_kg,
        produce: W.sections.birds.need_kg + W.sections.tropic.need_kg },
      staff: this.staff.map((s) => Object.assign({}, s)), sick_tomorrow: t < n ? this.sick_out(t) : 0,
      schedule: clone(this.schedule), min_tomorrow: t < n ? this.min_for(t) : null,
      price: this.price, free_wed: this.free_wed, suppliers: sup, forecast: fc, cards: this.open_cards(),
      vet_visits: this.vet_visits, vet_visits_min: W.vet_visits_min,
      yesterday: this.last_report, totals, counts: Object.assign({}, this.counts),
      violations: this.violations.length,
    };
  }

  min_for(day) {
    const add = this.extra_min(day);
    const out = {};
    for (const s of SECTIONS) { out[s] = []; for (let h = 0; h < HALF_N; h++) out[s].push(this.Wd.sections[s].min[h] + add[s][h]); }
    return out;
  }

  // --- Проверка --- (ничего не меняет)
  check(dec) {
    const W = this.Wd, t = this.t;
    const out = [];
    const ok = { orders: {}, choices: {}, hire: 0, fire: 0 };
    if (t >= W.days) return [[rej("day", "over", "Месяц закончился.", "The month is over.")], ok];
    const nxt = this.X.days[t], wd = nxt.wd;
    const cards = {};
    for (const c of this.open_cards()) cards[c.id] = c;
    // что прислано не в той форме, отклоняется с причиной, а не роняет Проверку
    const isDict = (x) => x !== null && typeof x === "object" && !Array.isArray(x);
    if (!isDict(dec)) return [[rej("decision", "form", "Решение должно быть объектом.", "A decision must be an object.")], ok];
    dec = Object.assign({}, dec);
    for (const k of ["choices", "thaw", "orders", "schedule"]) {
      if (dec[k] !== undefined && dec[k] !== null && !isDict(dec[k])) {
        out.push(rej(k, "form", "Поле «" + k + "» должно быть объектом.", "Field '" + k + "' must be an object."));
        delete dec[k];
      }
    }
    // карточки
    for (const [cid, opt] of Object.entries(or(get(dec, "choices", null), {}))) {
      if (!has(cards, cid)) { out.push(rej("choices." + cid, "no_card", "Карточки «" + cid + "» сейчас нет.", "There is no card '" + cid + "' now.")); continue; }
      if (!cards[cid].options.includes(opt)) { out.push(rej("choices." + cid, "option", "Нет варианта «" + pstr(opt) + "».", "No option '" + pstr(opt) + "'.")); continue; }
      const fb = FORBIDDEN[cards[cid].kind + "|" + opt];
      if (fb) { out.push(rej("choices." + cid, "law", fb[0], fb[1])); continue; }
      ok.choices[cid] = opt;
    }
    // найм
    let hire = or(get(dec, "hire", 0), 0), fire = or(get(dec, "fire", 0), 0);
    const hb = this.headcount(t, true);
    if (!isIntStrict(hire) || hire < 0 || hire > 3) {
      out.push(rej("hire", "range", "Нанять можно от 0 до 3 смотрителей за вечер.", "You can hire 0 to 3 keepers per evening.")); hire = 0;
    }
    if (!isIntStrict(fire) || fire < 0 || fire > hb) {
      out.push(rej("fire", "range", "Уволить можно не больше, чем есть смотрителей (" + pstr(hb) + ").", "You cannot let go more keepers than you have (" + pstr(hb) + ").")); fire = 0;
    }
    ok.hire = hire; ok.fire = fire;
    const hb_after = hb + hire - fire;
    // смены
    if (has(dec, "schedule")) {
      const sch = dec.schedule; let good = true; const S = W.staff;
      for (let w = 0; w < 7; w++) {
        const r = isObj(sch) ? get(sch, String(w), undefined) : null;
        const kp = isObj(r) ? get(or(r, {}), "keepers", undefined) : null;
        if (badRow(r, kp, W)) {
          out.push(rej("schedule." + w, "form", WD_RU[w] + ": нужны смотрители по пяти секциям на утро и день, кассиры и киоск по два числа (0–8), шоу 0–2.",
            WD_EN[w] + ": need keepers for five sections for morning and afternoon, cashiers and kiosk as two numbers (0-8), shows 0-2."));
          good = false; continue;
        }
        for (let h = 0; h < HALF_N; h++) {
          if (kp.cats[h] > 0 && kp.cats[h] < 2 && h === 0) {
            out.push(rej("schedule." + w, "two_keepers", WD_RU[w] + " " + HALF_RU[h] + ": в вольер барсов входят вдвоём, а в смене " + pstr(kp.cats[h]) + ".",
              WD_EN[w] + " " + HALF_EN[h] + ": two keepers enter the snow leopard enclosure together, the shift has " + pstr(kp.cats[h]) + ".")); good = false;
          }
          if (kp.cats[0] === 0 && h === 0) {
            out.push(rej("schedule." + w, "two_keepers", WD_RU[w] + " утро: вольер барсов убирают утром вдвоём, а в смене никого.",
              WD_EN[w] + " morning: the snow leopard enclosure is cleaned in the morning by two keepers, the shift has none.")); good = false;
          }
          if (kp.pool[h] < 1) {
            out.push(rej("schedule." + w, "water", WD_RU[w] + " " + HALF_RU[h] + ": в бассейне никого, а хлор и pH воды проверяют каждый день (9 CFR 3.106).",
              WD_EN[w] + " " + HALF_EN[h] + ": nobody at the pool, while chlorine and pH are checked daily (9 CFR 3.106).")); good = false;
          }
          if (kp.yard[h] < 1) {
            out.push(rej("schedule." + w, "contact", WD_RU[w] + " " + HALF_RU[h] + ": в контактном дворе посетители, а смотрителя в смене нет.",
              WD_EN[w] + " " + HALF_EN[h] + ": visitors are in the petting yard, but no keeper is on shift.")); good = false;
          }
          const tot = sum(SECTIONS.map((s) => kp[s][h]));
          if (tot > hb_after) {
            out.push(rej("schedule." + w, "headcount", WD_RU[w] + " " + HALF_RU[h] + ": " + pstr(tot) + " смотрителей в смене, а в штате " + pstr(hb_after) + ".",
              WD_EN[w] + " " + HALF_EN[h] + ": " + pstr(tot) + " keepers on shift, but you employ " + pstr(hb_after) + ".")); good = false;
          }
          if (SECTIONS.some((s) => kp[s][h] > S.max_per_half)) {
            out.push(rej("schedule." + w, "space", WD_RU[w] + " " + HALF_RU[h] + ": в одной секции не больше " + pstr(S.max_per_half) + " смотрителей.",
              WD_EN[w] + " " + HALF_EN[h] + ": at most " + pstr(S.max_per_half) + " keepers per section.")); good = false;
          }
          if (r.cashiers[h] < 1) {
            out.push(rej("schedule." + w, "gate", WD_RU[w] + " " + HALF_RU[h] + ": на кассе никого, вход не откроется.",
              WD_EN[w] + " " + HALF_EN[h] + ": nobody at the gate, the zoo cannot open.")); good = false;
          }
        }
        const sh = Number(get(r, "shows", 0));
        for (let h = 0; h < sh; h++) {
          if (kp.pool[h] < W.shows.pool_keepers_needed) {
            out.push(rej("schedule." + w, "show", WD_RU[w] + ": кормление при публике (" + HALF_RU[h] + ") ведут двое, а бассейн не остаётся без смотрителя: нужно " + pstr(W.shows.pool_keepers_needed) + " в бассейне.",
              WD_EN[w] + ": a public feeding (" + HALF_EN[h] + ") takes two keepers and the pool is never left alone: need " + pstr(W.shows.pool_keepers_needed) + " at the pool.")); good = false;
          }
        }
      }
      if (good) {
        ok.schedule = {};
        for (let w = 0; w < 7; w++) {
          const r = sch[String(w)], keepers = {};
          for (const s of SECTIONS) keepers[s] = r.keepers[s].slice();
          ok.schedule[String(w)] = { keepers, cashiers: r.cashiers.slice(), kiosk: r.kiosk.slice(), shows: get(r, "shows", 0) };
        }
      }
    }
    // разморозка: из того, что в морозилке сейчас
    if (has(dec, "thaw")) {
      const th = or(dec.thaw, {}), okth = {};
      for (const k of THAWED) {
        const q = get(th, k, 0);
        const have = get(this.freezer, k, 0) + get(this.thawed_next, k, 0);
        if (!isNumPy(q) || q < 0) { out.push(rej("thaw." + k, "qty", "Разморозка: нужно число килограммов.", "Thawing: need a number of kilograms.")); continue; }
        if (q > have + 1e-9) {
          out.push(rej("thaw." + k, "stock", "Разморозить " + pstr(q) + " кг нельзя: в морозилке " + f1(have) + " кг.",
            "Cannot thaw " + pstr(q) + " kg: the freezer holds " + f1(have) + " kg.")); continue;
        }
        okth[k] = q;
      }
      ok.thaw = okth;
    }
    // заказы
    const new_thaw = {};
    for (const k of THAWED) new_thaw[k] = get(or(get(ok, "thaw", null), {}), k, get(this.thawed_next, k, 0.0));
    const freezer_after = sum(Object.values(this.freezer)) + sum(Object.values(this.thawed_next)) - sum(THAWED.map((k) => new_thaw[k]));
    for (const [s, items0] of Object.entries(or(get(dec, "orders", null), {}))) {
      if (!has(W.suppliers, s)) { out.push(rej("orders." + s, "no_supplier", "Нет поставщика «" + s + "».", "No supplier '" + s + "'.")); continue; }
      const S = W.suppliers[s];
      if (items0 !== null && items0 !== undefined && !isDict(items0)) {
        out.push(rej("orders." + s, "form", S.ru + ": заказ пишется как «товар: килограммы».",
          S.en + ": an order is written as 'item: kilograms'.")); continue;
      }
      let bad = false;
      for (const [it, q] of Object.entries(or(items0, {}))) {
        if (!has(S.items, it)) { out.push(rej("orders." + s, "no_item", S.ru + " не возит «" + it + "».", S.en + " does not carry '" + it + "'.")); bad = true; }
        else if (!isNumPy(q) || q < 0) { out.push(rej("orders." + s, "qty", "Количество должно быть числом килограммов.", "Quantity must be kilograms.")); bad = true; }
        else if (get(S, "case_kg", 0) && q % S.case_kg) {
          out.push(rej("orders." + s, "case", S.ru + ": мороженое идёт коробками по " + pstr(S.case_kg) + " кг, а заказано " + pstr(q) + ".",
            S.en + ": frozen feed comes in " + pstr(S.case_kg) + " kg cases, ordered " + pstr(q) + ".")); bad = true;
        } else if (get(S, "bale_kg", 0) && q % S.bale_kg) {
          out.push(rej("orders." + s, "bale", S.ru + ": сено тюками по " + pstr(S.bale_kg) + " кг.", S.en + ": hay comes in " + pstr(S.bale_kg) + " kg bales.")); bad = true;
        }
      }
      if (bad) continue;
      const items = {};
      for (const [k, v] of Object.entries(or(items0, {}))) if (v > 0) items[k] = v;
      if (!Object.keys(items).length) continue;
      if (!S.days.includes(wd)) {
        out.push(rej("orders." + s, "day", S.ru + " возит только " + S.days.map((x) => WD_RU[x]).join(", ") + ", а завтра " + WD_RU[wd] + ".",
          S.en + " delivers only " + S.days.map((x) => WD_EN[x]).join(", ") + "; tomorrow is " + WD_EN[wd] + ".")); continue;
      }
      const total = cents(sum(Object.entries(items).map(([k, q]) => S.items[k].price_kg * q)));
      const kg = sum(Object.values(items));
      if (get(S, "min_order", 0) && total < S.min_order) {
        out.push(rej("orders." + s, "min", S.ru + ": заказ $" + f2(total) + " меньше минимума $" + pstr(S.min_order) + ".",
          S.en + ": order $" + f2(total) + " is below the $" + pstr(S.min_order) + " minimum.")); continue;
      }
      if (get(S, "min_kg", 0) && kg < S.min_kg) {
        out.push(rej("orders." + s, "min", S.ru + ": меньше " + pstr(S.min_kg) + " кг не возит.", S.en + ": minimum " + pstr(S.min_kg) + " kg.")); continue;
      }
      if (s === "frozen" && freezer_after + kg > W.freezer_kg + 1e-9) {
        out.push(rej("orders.frozen", "freezer", "Морозилка вмещает " + pstr(W.freezer_kg) + " кг, а с заказом выйдет " + pstr(rnd(freezer_after + kg)) + ".",
          "The freezer holds " + pstr(W.freezer_kg) + " kg; with this order it would be " + pstr(rnd(freezer_after + kg)) + ".")); continue;
      }
      if (s === "hay" && this.hay + kg > W.hay_store_kg + 1e-9) {
        out.push(rej("orders.hay", "store", "Сенник вмещает " + pstr(W.hay_store_kg) + " кг, а с заказом выйдет " + pstr(rnd(this.hay + kg)) + ".",
          "The hay store holds " + pstr(W.hay_store_kg) + " kg; with this order it would be " + pstr(rnd(this.hay + kg)) + ".")); continue;
      }
      ok.orders[s] = { items, total };
    }
    // цена
    if (has(dec, "price")) {
      const p = dec.price, [lo, hi] = W.prices.bounds, base = W.prices.adult;
      if (!isNumPy(p) || p < base * lo || p > base * hi) {
        out.push(rej("price", "bounds", "Взрослый билет от $" + f2(base * lo) + " до $" + f2(base * hi) + ".",
          "Adult ticket between $" + f2(base * lo) + " and $" + f2(base * hi) + "."));
      } else {
        ok.price = cents(p);
      }
    }
    if (has(dec, "free_wed")) {
      if (typeof dec.free_wed === "boolean") ok.free_wed = dec.free_wed;
      else out.push(rej("free_wed", "form", "Бесплатные часы в среду: да или нет.", "Free Wednesday hours: true or false."));
    }
    if (has(dec, "vet_visit")) {
      if (typeof dec.vet_visit === "boolean") ok.vet_visit = dec.vet_visit;
      else out.push(rej("vet_visit", "form", "Визит ветеринара: да или нет.", "Vet visit: true or false."));
    }
    return [out, ok];
  }

  decide(dec) {
    const [out, ok] = this.check(dec);
    const t = this.t;
    for (const [s, o] of Object.entries(ok.orders)) {
      if (has(this.orders, s)) this.totals.feed -= this.orders[s].total;
      this.orders[s] = o;
      this.totals.feed += o.total;
    }
    if (has(ok, "thaw")) {
      for (const [k, q] of Object.entries(ok.thaw)) {
        this.freezer[k] += get(this.thawed_next, k, 0.0);
        this.thawed_next[k] = q;
        this.freezer[k] -= q;
      }
    }
    for (let i = 0; i < ok.hire; i++) { this.staff.push({ id: "k" + this.next_id, start: t + this.Wd.staff.hire_delay_days }); this.next_id += 1; }
    for (let i = 0; i < ok.fire; i++) {
      const ks = this.staff.slice().sort((a, b) => (b.start - a.start) || (parseInt(b.id.slice(1), 10) - parseInt(a.id.slice(1), 10)));
      this.staff.splice(this.staff.indexOf(ks[0]), 1);
    }
    if (has(ok, "schedule")) this.schedule = ok.schedule;
    if (has(ok, "price")) this.price = ok.price;
    if (has(ok, "free_wed")) this.free_wed = ok.free_wed;
    if (has(ok, "vet_visit")) this.vet_tomorrow = ok.vet_visit;
    Object.assign(this.choices, ok.choices);
    this.pending_rejections = this.pending_rejections.concat(out);
    this.pending_decisions.push(clone(dec));   // копия: журнал не меняется, если игрок потом правит свой объект
    return out;
  }

  // --- день ---
  step() {
    const W = this.Wd, t = this.t, X = this.X, E = W.events, S = W.staff;
    const Dy = X.days[t];
    const rep = { day: t, date: Dy.date, wd: Dy.wd, weather: Dy.weather, events: [] };
    let costs_ev = 0.0, vet_cost = 0.0;
    const viol = {};
    for (const s of SECTIONS) viol[s] = [];
    // карточки с ценой
    for (const e of X.events) {
      const k = e.kind, ch = has(DEFAULT, k) ? this.choice(e) : null;
      if (k === "heatwave" && e.day === t && ch === "shade") { costs_ev += E.heatwave.shade_cost; rep.events.push("shade"); }
      if (k === "cubs_press" && e.day === t && ch === "press") { costs_ev += E.cubs.press_cost; rep.events.push("press"); }
      if (k === "cubs_watch" && e.day <= t && t < e.day + E.cubs.watch_days) {
        if (ch === "keeper") costs_ev += E.cubs.watch_cost_night;
        else if (ch === "camera" && e.day === t) costs_ev += E.cubs.cam_cost;
      }
      if (k === "pump" && e.day + 1 === t) costs_ev += ch === "fast" ? E.pump.fast_cost : E.pump.slow_cost;
      if (k === "power" && e.day === t && ch === "generator") costs_ev += E.power.generator_cost;
      if (k === "sealion" && e.day + 1 === t) vet_cost += ch === "vet_full" ? E.sealion.vet_full_cost : S.vet.emergency;
    }
    // поставки утром
    const delivered = {};
    const no_show = this.ev("no_show").some((e) => e.day === t);
    for (const [s, o] of Object.entries(this.orders)) {
      if (s === "frozen" && no_show) { this.totals.refunds += o.total; rep.events.push("no_delivery_frozen"); continue; }
      for (const [it, q] of Object.entries(o.items)) {
        if (it === "fish" || it === "meat") this.freezer[it] += q;
        else if (it === "hay") this.hay += q;
        else if (it === "produce") this.produce.push([q, t + W.suppliers.produce.shelf_days - 1]);
      }
      delivered[s] = o.items;
    }
    this.orders = {};
    rep.delivered = delivered;
    // люди
    const row = this.schedule[String(Dy.wd)];
    const avail = Math.max(0, this.headcount(t) - this.sick_out(t));
    const on = {};
    for (const s of SECTIONS) on[s] = [0, 0];
    const cut_order = ["birds", "tropic", "yard", "cats", "pool"];
    for (let h = 0; h < HALF_N; h++) {
      const want = {};
      for (const s of SECTIONS) want[s] = row.keepers[s][h];
      let over = sum(SECTIONS.map((s) => want[s])) - avail;
      for (const s of cut_order) while (over > 0 && want[s] > 0) { want[s] -= 1; over -= 1; }
      for (const s of SECTIONS) on[s][h] = want[s];
    }
    const mins = this.min_for(t);
    for (const s of SECTIONS) for (let h = 0; h < HALF_N; h++) if (on[s][h] < mins[s][h]) viol[s].push("care");
    let shows = 0;
    for (let h = 0; h < Math.min(Number(get(row, "shows", 0)), HALF_N); h++) {
      if (on.pool[h] >= W.shows.pool_keepers_needed && !X.events.some((e) => e.kind === "pump" && e.day + 1 === t && this.choice(e) === "slow")) shows += 1;
    }
    // экскурсия донора
    let donation_extra = 0.0;
    for (const e of this.ev("donor")) {
      if (e.day === t && this.choice(e) === "tour") {
        if (on.cats[0] >= W.sections.cats.min[0] + E.donor.cats_halves) {
          donation_extra += e.hidden.amount; rep.events.push("donor_" + pstr(e.hidden.amount));
        } else {
          this.rep = clamp(this.rep - 0.02, W.reputation.min, W.reputation.max); rep.events.push("donor_cancelled");
        }
      }
    }
    // корм
    const fed = {};
    const need = {};
    for (const s of SECTIONS) need[s] = W.sections[s].need_kg;
    const th = this.thawed_next;
    for (const [feed, s] of [["fish", "pool"], ["meat", "cats"]]) {
      const given = Math.min(get(th, feed, 0.0), need[s]);
      const waste = get(th, feed, 0.0) - given;
      this.counts.thaw_waste_kg = cents(this.counts.thaw_waste_kg + waste);
      fed[s] = given / need[s];
    }
    this.thawed_next = { fish: 0.0, meat: 0.0 };
    const h_given = Math.min(this.hay, need.yard); this.hay -= h_given; fed.yard = h_given / need.yard;
    const p_need = need.birds + need.tropic; let p_left = p_need;
    this.produce.sort((a, b) => a[1] - b[1]);
    for (const lot of this.produce) {
      if (lot[1] >= t && p_left > 0) { const use = Math.min(lot[0], p_left); lot[0] -= use; p_left -= use; }
    }
    const p_ratio = (p_need - p_left) / p_need;
    fed.birds = fed.tropic = p_ratio;
    for (const s of SECTIONS) if (fed[s] < W.fed_ok) viol[s].push("underfed");
    // морской лев: без полного обследования болезнь возвращается
    for (const e of this.ev("sealion")) {
      if (t === e.day + 4 && this.choice(e) === "vet_now" && e.hidden.u < E.sealion.relapse_risk) {
        viol.pool.push("sealion_relapse"); vet_cost += S.vet.emergency; rep.events.push("sealion_relapse");
      }
    }
    // свет в тропическом доме
    for (const e of this.ev("power")) {
      if (e.day === t && this.choice(e) === "none") {
        viol.tropic.push("cold"); rep.events.push("tropic_cold");
        if (e.hidden.u < E.power.death_risk) { this.dead.push([t, "tropic"]); rep.events.push("death_tropic"); }
      }
    }
    // птичий грипп
    for (const e of this.ev("hpai")) {
      if (t === e.day + 4 && e.hidden.u < E.hpai.risk[this.choice(e)] && get(this.flags, "hpai_hit_from", null) === null) {
        this.flags.hpai_hit_from = t + 1; this.dead.push([t, "birds"]); rep.events.push("hpai_hit");
        this.rep = clamp(this.rep + E.hpai.hit_rep, W.reputation.min, W.reputation.max);
      }
    }
    // котята
    for (const e of this.ev("cubs")) {
      if (t === e.day) rep.events.push("cubs_born");
      if (t === e.day + 3 && get(this.flags, "cubs_lost_from", null) === null) {
        const watch = this.X.events.find((x) => x.kind === "cubs_watch" && get(x, "parent", undefined) === e.id);
        const ch = watch ? this.choice(watch) : "none";
        const risk = { keeper: 0.0, camera: 0.05, none: E.cubs.loss_risk }[ch];
        if (e.hidden.u_loss < risk) { this.flags.cubs_lost_from = t + 1; this.dead.push([t, "cubs"]); rep.events.push("cubs_lost"); }
      }
    }
    // посетители
    const [exp, notes] = this.expected(t, true);
    rep.notes = notes;
    const mix = W.mix, P = W.prices;
    let tickets = 0.0, food = 0.0, souv = 0.0, don = 0.0;
    let adm_all = 0, demand_all = 0, queue = 0, tx = 0;
    // теснота: мир без ключа crowding считается ровно как раньше, старые журналы не меняются
    const CR = W.crowding || null; let crowd = 0.0;
    const by_half = [];
    for (let h = 0; h < HALF_N; h++) {
      const g = rnd(exp[h] * X.noise[t][h]);
      demand_all += g;
      const names = ["adult", "child", "group", "member", "free"];
      const parts = split_lr(g, [mix.adult, mix.child, mix.group, mix.member, mix.free]);
      const cats = {}; names.forEach((k, i) => { cats[k] = parts[i]; });
      const free_pm = (h === 1 && Dy.wd === 2 && this.free_wed);
      const need_gate = cats.adult + cats.child + cats.free;
      const cap = rnd(row.cashiers[h] * W.gate_per_cashier_hour * W.halves.hours[h]);
      const lost = Math.max(0, need_gate - cap);
      // кто не прошёл, уходит: взрослые и дети пропорционально
      if (lost) {
        const [la, lc, lf] = need_gate ? split_lr(lost, [cats.adult, cats.child, cats.free]) : [0, 0, 0];
        cats.adult -= la; cats.child -= lc; cats.free -= lf;
      }
      queue += lost;
      const adm = sum(names.map((k) => cats[k]));
      const tk = free_pm ? 0.0 : cats.adult * this.price + cats.child * this.price * P.child_share + cats.group * P.group;
      const kcap = row.kiosk[h] * W.kiosk_per_worker_hour * W.halves.hours[h];
      const buyers = Math.min(adm * 0.7, kcap);
      // когда в половину дня пришло больше, чем зоопарк вмещает без толчеи, посетитель
      // тратит меньше: очередь к киоску, негде сесть, часть вольеров не видно
      const over = CR ? Math.max(0.0, adm / CR.comfort_per_half - 1.0) : 0.0;
      const drop = CR ? Math.min(CR.spend_drop_max, CR.spend_drop_k * over) : 0.0;
      crowd = Math.max(crowd, over);
      const fd = buyers * W.spend.food / 0.7 * (1 - drop);
      const sv = adm * W.spend.souvenir * (1 - drop);
      // в бесплатную половину дня жертвуют заметно охотнее: вход по пожертвованию
      const dmult = free_pm ? (W.free_wed.donation_mult || 1.0) : 1.0;
      const dn = adm * (W.spend.donation * dmult + W.spend.donation_per_show * shows);
      tickets += tk; food += fd; souv += sv; don += dn; adm_all += adm; tx += adm;
      by_half.push({ half: h, demand: g, admitted: adm, queue_lost: lost, gate_capacity: cap,
        kiosk_short: rnd(adm * 0.7 - buyers), crowding: pyround(over, 3) });
    }
    let school = 0.0;
    for (const e of this.ev("school")) {
      if (e.day === t && this.choice(e) === "accept") {
        const kids = E.school.kids; school = kids * E.school.price;
        food += kids * 3.0; adm_all += kids;
        if (on.yard[0] < W.sections.yard.min[0] + 1) {
          this.rep = clamp(this.rep - 0.02, W.reputation.min, W.reputation.max); rep.events.push("school_unguided");
        } else {
          rep.events.push("school_" + pstr(kids));
        }
      }
    }
    don += donation_extra;
    const revenue = tickets + food + souv + don + school;
    const cogs = food * W.spend.food_cost + souv * W.spend.souvenir_cost;
    const fee = W.card_share * (tickets + food + souv) * W.card_fee_pct + W.card_fee_fixed * rnd(W.card_share * tx * 0.5);
    // зарплата
    const kh_terms = [];
    for (const s of SECTIONS) for (let h = 0; h < HALF_N; h++) kh_terms.push(on[s][h] * W.halves.hours[h]);
    const kh = sum(kh_terms);
    const paid_h = Math.max(kh, this.headcount(t) * S.keeper.salaried_h_week / 7.0);  // смотрители на окладе: 40 ч в неделю в любом случае
    let wages = paid_h * S.keeper.wage;
    wages += sum([0, 1].map((h) => row.cashiers[h] * W.halves.hours[h])) * S.cashier.wage;
    wages += sum([0, 1].map((h) => row.kiosk[h] * W.halves.hours[h])) * S.kiosk.wage;
    wages += S.guard.count * S.guard.hours * S.guard.wage + S.vet_tech.hours * S.vet_tech.wage;
    wages *= 1 + S.burden;
    this.week_hours += kh;
    let ot = 0.0;
    if (Dy.wd === 6 || t === W.days - 1) {
      const over = this.week_hours - S.overtime_after_h * Math.max(1, this.headcount(t));
      if (over > 0) ot = over * S.keeper.wage * (S.overtime_mult - 1) * (1 + S.burden);
      rep.overtime = cents(ot); this.week_hours = 0.0;
    }
    wages = cents(wages + ot);
    if (this.vet_tomorrow) { vet_cost += S.vet.wage * S.vet.visit_hours; this.vet_visits += 1; rep.events.push("vet_visit"); }
    this.vet_tomorrow = false;
    const elec = W.electricity.kwh_day * W.electricity.price * (1 + (Dy.weather === "advisory" ? W.electricity.advisory_extra : 0));
    // списания
    const wasted_p = sum(this.produce.filter(([, b]) => b <= t).map(([a]) => a));
    this.produce = this.produce.filter(([a, b]) => b > t && a > 1e-9).map(([a, b]) => [a, b]);
    this.counts.produce_waste_kg = cents(this.counts.produce_waste_kg + wasted_p);
    // нарушения дня
    const vdays = SECTIONS.filter((s) => viol[s].length);
    for (const s of vdays) this.violations.push([t, s, viol[s]]);
    this.counts.section_violation_days += vdays.length;
    // инспекция
    for (const e of this.ev("inspection")) {
      if (e.day === t) {
        const lb = E.inspection.lookback;
        const found = this.violations.filter((v) => t - lb < v[0] && v[0] <= t);
        this.counts.inspection_findings += found.length;
        rep.events.push("inspection_" + pstr(found.length));
      }
    }
    // репутация
    const R = W.reputation;
    const qrate = queue / Math.max(1, demand_all);
    const closedN = notes.filter((n_) => ["closed_midday", "pool_closed_pm", "tropic_closed"].includes(n_)).length;
    this.rep = clamp(this.rep + R.drift - R.queue_k * qrate - R.violation * vdays.length - R.closed_k * closedN
      + W.shows.rep * shows - (CR ? CR.rep_k * crowd : 0.0), R.min, R.max);
    // итоги дня
    const T = this.totals;
    T.tickets += tickets; T.food += food; T.souvenirs += souv; T.donations += don; T.school += school;
    T.cogs += cogs; T.card_fees += fee; T.wages += wages; T.electricity += elec; T.vet += vet_cost; T.event_costs += costs_ev;
    for (const k of Object.keys(T)) T[k] = cents(T[k]);
    const C = this.counts;
    C.visitors += adm_all; C.demand += demand_all; C.queue_lost += queue; C.shows += shows; C.deaths = this.dead.length;
    const fedR = {}; for (const s of SECTIONS) fedR[s] = pyround(fed[s], 3);
    const violR = {}; for (const s of vdays) violR[s] = viol[s];
    const freezerA = {}; for (const [k, v] of Object.entries(this.freezer)) freezerA[k] = cents(v);
    Object.assign(rep, { by_half, keepers_on: on, available_keepers: avail, shows, fed: fedR,
      violations: violR, revenue: cents(revenue), cogs: cents(cogs), card_fee: cents(fee), wages,
      vet: cents(vet_cost), electricity: cents(elec), event_costs: cents(costs_ev), visitors: adm_all, demand: demand_all, queue_lost: queue,
      reputation: pyround(this.rep, 4), crowding: pyround(crowd, 3),
      stock_after: { freezer: freezerA, hay: cents(this.hay), produce: cents(sum(this.produce.map(([a]) => a))) },
      decisions: this.pending_decisions, rejections: this.pending_rejections });
    this.pending_decisions = []; this.pending_rejections = [];
    this.journal.push(rep);
    const lr = {};
    for (const k of ["day", "date", "weather", "visitors", "demand", "queue_lost", "revenue", "violations", "fed", "events", "shows", "reputation"]) lr[k] = rep[k];
    this.last_report = lr;
    this.t += 1;
    return rep;
  }

  score() {
    const W = this.Wd, T = this.totals, C = this.counts, P = W.penalties;
    const price = {};
    for (const k of THAWED) price[k] = W.suppliers.frozen.items[k].price_kg;
    const leftover = sum(THAWED.map((k) => this.freezer[k] * price[k])) + this.hay * W.suppliers.hay.items.hay.price_kg;
    const vet_missing = (this.done() && this.vet_visits < W.vet_visits_min) ? 1 : 0;
    const parts = {
      revenue: cents(T.tickets + T.food + T.souvenirs + T.donations + T.school),
      cogs: -T.cogs, card_fees: -T.card_fees, wages: -T.wages,
      feed: -cents(T.feed - T.refunds), leftover_feed: cents(leftover),
      electricity: -T.electricity, vet: -T.vet, event_costs: -T.event_costs,
      section_violations: -C.section_violation_days * P.section_day,
      inspection: -C.inspection_findings * P.inspection,
      deaths: -this.dead.length * P.death,
      queue: -C.queue_lost * P.queue,
      vet_visits: -vet_missing * P.vet_visits_missing,
    };
    const skip = ["section_violations", "inspection", "deaths", "queue", "vet_visits"];
    const profit = sum(Object.entries(parts).filter(([k]) => !skip.includes(k)).map(([, v]) => v));
    return { score: cents(sum(Object.values(parts))), profit: cents(profit), parts, counts: Object.assign({}, C), vet_visits: this.vet_visits };
  }
}

// форма строки смены: тот же порядок проверок и то же короткое замыкание, что в sim.py
function badRow(r, kp, W) {
  if (!isObj(kp)) return true;
  for (const s of SECTIONS) {
    const v = get(kp, s, undefined);
    if (!Array.isArray(v) || v.length !== 2 || v.some((x) => !isIntStrict(x) || x < 0)) return true;
  }
  for (const f of ["cashiers", "kiosk"]) {
    const v = get(r, f, undefined);
    if (!Array.isArray(v) || v.length !== 2 || v.some((x) => !isIntPy(x) || x < 0 || x > 8)) return true;
  }
  const sh = get(r, "shows", 0);
  if (!isIntPy(sh) || !(0 <= sh && sh <= W.shows.max)) return true;
  return false;
}

const SETTINGS = ["place", "team", "scenario"];
const MAX_DECISIONS_PER_STEP = 10;

// Пересчёт счёта из журнала решений. decisions: [[шаг, решение], ...] в порядке подачи.
// Журнал чужой, поэтому всё проверяется: неверный ввод даёт исключение, а не счёт.
function replay(seed, settings, decisions, world) {
  const W = world;
  if (!Number.isInteger(seed) || !(0 <= seed && seed < 2 ** 32)) throw new Error("seed: целое от 0 до 2^32-1");
  if (!isObj(settings) || Object.keys(settings).length !== SETTINGS.length || SETTINGS.some((k) => !has(settings, k))) throw new Error("settings: ровно place, team, scenario");
  for (const [k, pool] of [["place", W.places], ["team", W.teams], ["scenario", W.scenarios]]) {
    const names = Object.keys(pool).filter((x) => x[0] !== "_").sort();   // _tag это пометка источника, а не значение
    if (names.indexOf(settings[k]) < 0) throw new Error("settings." + k + ": одно из " + names.join(", "));
  }
  const g = new Game(seed, settings.place, settings.team, settings.scenario, W);
  const by_step = {};
  let last = -1;
  for (const item of decisions) {
    if (!Array.isArray(item) || item.length !== 2) throw new Error("decisions: пары (шаг, решение)");
    const [t, dec] = item;
    if (!Number.isInteger(t) || t < last || !(0 <= t && t < g.X.days.length)) throw new Error("decisions: шаги по порядку и в пределах месяца");
    if (!isObj(dec)) throw new Error("decisions: решение должно быть объектом");
    last = t;
    (by_step[t] = by_step[t] || []).push(clone(dec));
    if (by_step[t].length > MAX_DECISIONS_PER_STEP) throw new Error("decisions: не больше " + MAX_DECISIONS_PER_STEP + " решений на шаг");
  }
  while (!g.done()) {
    for (const dec of by_step[g.t] || []) g.decide(dec);
    g.step();
  }
  const s = g.score();
  return { score: s.score, parts: s.parts, counts: s.counts };
}

// Журнал дней (g.journal или runs/*.json["journal"]) -> decisions для replay.
const decisions_of = (journal) => journal.flatMap((d) => d.decisions.map((dec) => [d.day, dec]));

const API = { Game, replay, make_world, decisions_of, default_schedule, card_options, DEFAULT, OPTIONS, SECTIONS, FEEDS,
  WD_RU, WD_EN, HALF_RU, HALF_EN, rnd, cents, fnv, Rng, clamp, split_lr, pyround };
if (typeof module !== "undefined" && module.exports) module.exports = API;
else root.ZooSim = API;
})(typeof window !== "undefined" ? window : globalThis);

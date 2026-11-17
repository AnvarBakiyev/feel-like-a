// Месяц кофейни: перенос sim/sim.py строка в строку. Тест совпадения: web/parity.mjs.
// Город (city_ny.json) передаётся аргументом: страница кладёт его в себя, файлов не читает.
(function (root) {
"use strict";
const DRINKS = ["latte", "cold_brew", "drip", "tea"];
const DP_N = 3;
const WD_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];
const WD_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const SUP_RU = { dairy: "Молочный поставщик", roaster: "Обжарщик", bakery: "Пекарня" };
const SUP_EN = { dairy: "The dairy", roaster: "The roaster", bakery: "The bakery" };
const ITEM_RU = { latte: "латте", cold_brew: "колд-брю", drip: "фильтр-кофе", tea: "чай", croissant: "круассан" };
const DP_RU = ["утро", "день", "вечер"];
const DP_EN = ["morning", "midday", "evening"];

// ---------- переносимые основы ----------
const rnd = (x) => Math.floor(x + 0.5);
const cents = (x) => Math.floor(x * 100 + 0.5) / 100;
function fnv(s) {
  let h = 2166136261 >>> 0;
  const b = new TextEncoder().encode(s);
  for (const ch of b) { h ^= ch; h = Math.imul(h, 16777619) >>> 0; }
  return h >>> 0;
}
class Rng {
  constructor(seed) { this.a = seed >>> 0; }
  u() {
    this.a = (this.a + 0x6D2B79F5) >>> 0;
    let t = this.a;
    t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
    t = (t ^ ((t + (Math.imul(t ^ (t >>> 7), t | 61) >>> 0)) >>> 0)) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  int(lo, hi) { return lo + Math.floor(this.u() * (hi - lo + 1)); }
  pick_w(w) {
    let s = 0; for (const x of w) s += x;
    const x = this.u() * s; let acc = 0;
    for (let i = 0; i < w.length; i++) { acc += w[i]; if (x < acc) return i; }
    return w.length - 1;
  }
}
const clamp = (x, lo, hi) => (x < lo ? lo : x > hi ? hi : x);
const sum = (a) => { let s = 0; for (const x of a) s += x; return s; };
function split_lr(n, shares) {
  const tot = sum(shares);
  const raw = shares.map((s) => (n * s) / tot);
  const base = raw.map((r) => Math.floor(r));
  const rest = n - sum(base);
  const order = shares.map((_, i) => i).sort((i, j) => (-(raw[i] - base[i])) - (-(raw[j] - base[j])) || i - j);
  for (const i of order.slice(0, rest)) base[i] += 1;
  return base;
}
const days_in_month = (y, m) => [31, (y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0)) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1];
function weekday(y, m, d) {
  const t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4];
  const yy = m < 3 ? y - 1 : y;
  const w = (yy + Math.floor(yy / 4) - Math.floor(yy / 100) + Math.floor(yy / 400) + t[m - 1] + d) % 7;
  return (w + 6) % 7;
}
const pad = (n, k) => String(n).padStart(k, "0");
const f2 = (x) => x.toFixed(2);
// str() Python для чисел в текстах отказов: целое float печатается с ".0" только если пришло дробным; у нас решения целые
const pstr = (x) => String(x);
const rej = (field, code, ru, en) => ({ field, code, ru, en });
const isInt = (x) => Number.isInteger(x);
const isNum = (x) => typeof x === "number" && isFinite(x);
const isObj = (x) => x !== null && typeof x === "object" && !Array.isArray(x);
// истинность как в Python: пустой список и пустой объект ложны
const truthy = (x) => Array.isArray(x) ? x.length > 0 : isObj(x) ? Object.keys(x).length > 0 : !!x;
const or = (x, d) => (truthy(x) ? x : d);
const form = (field, ru, en) => rej(field, "form", "Неверная форма поля «" + field + "»: " + ru + ".", "Wrong form of '" + field + "': " + en + ".");
const EMPTY_OK = () => ({ orders: {}, prices: {}, hire: 0, fire: 0, buy: [], choices: {} });
const clone = (x) => JSON.parse(JSON.stringify(x));
const pyround = (x, n) => { const k = Math.pow(10, n); return Math.round(x * k) / k; };

// ---------- мир ----------
function make_world(seed, street, money, scenario, C) {
  const sc = C.scenarios[scenario];
  const [y, m, d0] = sc.start;
  const n = C.days;
  const R = (label) => new Rng(fnv(String(seed) + ":" + label));
  const days = [];
  const wd0 = weekday(y, m, d0);
  const wx = C.weather[sc.weather];
  const dim = days_in_month(y, m);
  const rw = R("weather");
  for (let i = 0; i < n; i++) {
    const dd = d0 + i;
    const date = pad(y, 4) + "-" + pad(m, 2) + "-" + pad(dd, 2);
    const u = rw.u();
    const p_snow = wx.snow_days / dim, p_rain = wx.rain_days / dim;
    const w = u < p_snow ? "snow" : u < p_snow + p_rain ? "rain" : "clear";
    days.push({ date, wd: (wd0 + i) % 7, weather: w, holiday: date in C.holidays ? C.holidays[date] : 1.0 });
  }
  const rn = R("noise");
  const noise = [];
  for (let i = 0; i < n; i++) { const r = []; for (let j = 0; j < DP_N; j++) r.push(1 + C.noise * (2 * rn.u() - 1)); noise.push(r); }
  const re = R("events");
  const used = new Set();
  const events = [];
  const range = (lo, hi) => { const a = []; for (let d = lo; d <= hi; d++) a.push(d); return a; };
  function free_day(lo, hi, pred = () => true) {
    let cand = range(lo, hi).filter((d) => !used.has(d) && pred(d));
    if (!cand.length) { cand = range(lo, hi).filter((d) => pred(d)); if (!cand.length) cand = range(lo, hi); }
    const d = cand[re.int(0, cand.length - 1)];
    used.add(d);
    return d;
  }
  const E = C.events;
  const dairy_days = C.suppliers.dairy.days;
  sc.events.forEach((kind, k) => {
    const ev = { id: kind + "_" + k, kind };
    if (kind === "blogger") { ev.day = free_day(3, 20); ev.show = ev.day - 2; ev.hidden = { boost: E.blogger.outcomes[re.pick_w(E.blogger.weights)] }; }
    else if (kind === "repair") { ev.day = free_day(5, 20); ev.show = ev.day - E.repair.notice; ev.hidden = { recover: E.repair.sign_recover[re.int(0, 2)] }; }
    else if (kind === "inspection") { ev.day = free_day(4, 27); ev.show = ev.day - E.inspection.notice; ev.hidden = { u: re.u() }; }
    else if (kind === "breakdown") { ev.day = free_day(2, 27); ev.show = ev.day + 1; }
    else if (kind === "sick") { ev.day = free_day(1, 27); ev.show = ev.day; }
    else if (kind === "dairy_up") { ev.day = free_day(5, 20); ev.show = ev.day - E.dairy_up.notice; }
    else if (kind === "catering") { ev.day = free_day(2, 27, (d) => days[d].wd < 5); ev.show = ev.day; }
    else if (kind === "fair") { ev.day = free_day(7, 27, (d) => days[d].wd === 5); ev.show = ev.day - E.fair.notice; }
    else if (kind === "no_show") { ev.day = free_day(2, 27, (d) => dairy_days.includes(days[d].wd)); ev.show = null; }
    else if (kind === "blizzard") { ev.day = free_day(8, 24); ev.show = ev.day - E.blizzard.notice; ev.hidden = { keep: E.blizzard.severity[re.int(0, 2)] }; days[ev.day].weather = "blizzard"; }
    else if (kind === "competitor") { ev.day = E.competitor.open_day; used.add(ev.day); ev.show = ev.day - 2; ev.hidden = { s: E.competitor.strength[re.int(0, 2)] }; }
    events.push(ev);
  });
  events.sort((a, b) => a.day - b.day || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  const ri = R("invest");
  const hidden_inv = { marketing_lift: C.investments.marketing.lift[ri.int(0, 2)] };
  return { hidden_inv, seed, street, money, scenario, days, noise, events };
}

const OPTIONS = {
  blogger: ["accept", "decline"], repair: ["sign", "none"], inspection: ["clean", "none"],
  breakdown: ["fast", "slow"], sick: ["agency", "short"], dairy_up: ["ok"], catering: ["accept", "decline"],
  fair: ["ok"], blizzard: ["open", "close"], competitor: ["loyalty", "promo", "none"], complaint: ["coupons", "reply", "ignore"],
};
const card_options = (kind) => OPTIONS[kind].slice();
const DEFAULT = { blogger: "decline", repair: "none", inspection: "none", breakdown: "slow", sick: "short", dairy_up: "ok",
  catering: "decline", fair: "ok", blizzard: "open", competitor: "none", complaint: "ignore", no_show: "none" };

// ---------- игра ----------
class Game {
  constructor(seed, street, money, scenario, C) {
    this.C = C;
    this.W = make_world(seed, street, money, scenario, C);
    this.t = 0;
    const st = C.streets[street];
    this.base = st.guests;
    this.rent_day = st.rent_month / C.days;
    this.cash = C.money[money];
    this.loan = 0.0;
    this.rep = C.reputation.start;
    this.prices = {};
    for (const k of DRINKS.concat(["croissant"])) this.prices[k] = C.menu[k].price;
    this.discounts = [];
    const S = C.staff;
    this.staff = [];
    for (let i = 0; i < S.start_baristas; i++) this.staff.push({ id: "b" + (i + 1), role: "barista", start: 0 });
    for (let i = 0; i < S.start_leads; i++) this.staff.push({ id: "l" + (i + 1), role: "lead", start: 0 });
    this.next_id = S.start_baristas + 1;
    this.schedule = {};
    for (let w = 0; w < 7; w++) this.schedule[String(w)] = { barista: [2, 2, 1], lead: [1, 0, 0] };
    const g = this.base;
    const lat = C.menu.latte;
    const milk_day = g * lat.share * lat.milk_l;
    const beans_day = g * sum(DRINKS.map((k) => C.menu[k].share * C.menu[k].beans_g));
    const sd = C.start_stock_days;
    this.milk = [[cents(milk_day * sd.milk), 2]];
    this.beans_g = rnd(beans_day * sd.beans);
    this.cups = rnd(g * sd.cups);
    this.croissant = 0;
    this.orders = {};
    this.choices = {};
    this.cards_extra = [];
    this.grade_b_from = null;
    this.week_hours = { barista: 0.0, lead: 0.0 };
    this.totals = {};
    for (const k of ["revenue", "purchases", "refunds", "wages", "rent", "fixed", "card_fees", "event_costs", "agency", "investments"]) this.totals[k] = 0.0;
    this.counts = { stockout_guests: 0, queue_guests: 0, guests: 0, demand: 0, written_off_milk_l: 0.0, written_off_croissant: 0 };
    this.journal = [];
    this.last_report = null;
    this.pending_rejections = [];
    this.pending_decisions = [];
    this.bought = {};
    this.clean_paid = new Set();
  }
  done() { return this.t >= this.C.days; }
  ev(kind) { return this.W.events.filter((e) => e.kind === kind); }
  choice(e) { return e.id in this.choices ? this.choices[e.id] : DEFAULT[e.kind]; }
  milk_price(day) {
    let p = this.C.suppliers.dairy.items.milk.price;
    for (const e of this.ev("dairy_up")) if (day >= e.day) p = cents(p * (1 + this.C.events.dairy_up.pct));
    return p;
  }
  has(inv, day) { return inv in this.bought && day >= this.bought[inv]; }
  headcount(role, day, include_pending = false) { return this.staff.filter((s) => s.role === role && (include_pending || s.start <= day)).length; }
  sick_out(day) { return this.ev("sick").filter((e) => e.day <= day && day <= e.day + this.C.events.sick.days - 1).length; }
  eff_price(item, dp) {
    let p = this.prices[item];
    for (const d of this.discounts) if (d.item === item && d.dayparts.includes(dp)) p = cents(p * (1 - d.pct / 100.0));
    return p;
  }
  cost_of(item, day) {
    const C = this.C;
    if (item === "croissant") return C.suppliers.bakery.items.croissant.price;
    const m = C.menu[item], beans = C.suppliers.roaster.items.beans, cups = C.suppliers.roaster.items.cups, milk = C.suppliers.dairy.items.milk;
    return cents(m.beans_g * beans.price / beans.grams + m.milk_l * this.milk_price(day) / milk.liters + m.cup * cups.price / cups.count + m.other);
  }
  demand_mult(day, hidden) {
    const C = this.C, W = this.W, D = W.days[day];
    let m = C.weekday_mult[D.wd] * D.holiday;
    const notes = []; let extra = 0.0;
    const w = D.weather;
    if (w !== "blizzard") m *= C.weather_mult[w];
    for (const e of W.events) {
      const k = e.kind, E = C.events[k] || {};
      if (k === "fair" && day === e.day) { m *= E.mult; notes.push("fair"); }
      else if (k === "repair" && e.day <= day && day < e.day + E.days) {
        let loss = 1 - E.mult;
        if (this.choice(e) === "sign") {
          if (hidden) loss *= 1 - e.hidden.recover;
          else { const r = E.sign_recover; loss *= 1 - sum(r) / r.length; extra += 0.08; }
        }
        m *= 1 - loss; notes.push("repair");
      } else if (k === "blogger" && this.choice(e) === "accept" && e.day < day && day <= e.day + E.days) {
        if (hidden) m *= 1 + e.hidden.boost; else extra += 0.2;
        notes.push("blogger");
      } else if (k === "blizzard" && day === e.day) {
        if (hidden) m *= e.hidden.keep; else { const sv = E.severity; m *= sum(sv) / sv.length; extra += 0.2; }
        notes.push("blizzard");
      } else if (k === "competitor" && day >= e.day) {
        let s = hidden ? e.hidden.s : sum(E.strength) / E.strength.length;
        if (!hidden) extra += 0.08;
        if (this.choice(e) === "promo" && day < e.day + E.promo_days) s *= 0.5;
        const pidx = this.price_index(1);
        const f = clamp(1 + 1.5 * (pidx - 1) - 2 * (this.rep - 1), 0.5, 1.5);
        m *= 1 - s * f; notes.push("competitor");
      }
    }
    if ("marketing" in this.bought) {
      const I = C.investments.marketing, d0 = this.bought.marketing;
      if (d0 <= day && day < d0 + I.days) {
        if (hidden) m *= 1 + W.hidden_inv.marketing_lift;
        else { m *= 1 + sum(I.lift) / I.lift.length; extra += 0.06; }
        notes.push("marketing");
      }
    }
    if (this.grade_b_from !== null && day >= this.grade_b_from) { m *= C.events.inspection.b_mult; notes.push("grade_b"); }
    return [m * this.rep, notes, extra];
  }
  price_index(dp) {
    const M = this.C.menu;
    const num = sum(DRINKS.map((k) => M[k].share * this.eff_price(k, dp)));
    const den = sum(DRINKS.map((k) => M[k].share * M[k].price));
    return num / den;
  }
  expected_guests(day, hidden) {
    const C = this.C;
    const [m, notes, extra] = this.demand_mult(day, hidden);
    const out = [];
    for (let dp = 0; dp < DP_N; dp++) {
      const pi = this.price_index(dp);
      const pm = Math.pow(pi, pi > 1 ? C.elasticity_drinks.up : C.elasticity_drinks.down[dp]);
      out.push(this.base * C.hours.share[dp] * m * pm);
    }
    return [out, notes, extra];
  }
  closed(day) { return this.W.events.some((e) => e.kind === "blizzard" && e.day === day && this.choice(e) === "close"); }
  open_cards() {
    const t = this.t, ev_ = t - 1;
    const cards = [];
    for (const e of this.W.events.concat(this.cards_extra)) {
      if (e.show === null || e.show === undefined) continue;
      const deadline = "deadline" in e ? e.deadline : (e.kind === "breakdown" ? e.day : e.day - 1);
      if (e.show - 1 <= ev_ && ev_ <= deadline) {
        const c = { id: e.id, kind: e.kind, day: e.day, options: card_options(e.kind),
          chosen: e.id in this.choices ? this.choices[e.id] : null, default: DEFAULT[e.kind], decide_by_evening_of: deadline };
        if (e.kind === "breakdown") c.day = e.day + 1;
        cards.push(c);
      }
    }
    return cards;
  }
  observe() {
    const C = this.C, t = this.t;
    const fc = [];
    for (let d = t; d < Math.min(t + 3, C.days); d++) {
      const [g, notes, extra] = this.expected_guests(d, false);
      const band = C.noise + extra;
      const D = this.W.days[d];
      fc.push({ day: d, date: D.date, wd: D.wd, weather: D.weather, notes,
        guests: g.map((x) => rnd(x)), low: g.map((x) => rnd(x * (1 - band))), high: g.map((x) => rnd(x * (1 + band))),
        closed_if_chosen: this.closed(d) });
    }
    const nxt = t < C.days ? this.W.days[t] : null;
    const sup = {};
    for (const [s, S] of Object.entries(C.suppliers)) {
      const items = {};
      for (const [it, I] of Object.entries(S.items)) items[it] = it !== "milk" ? I.price : this.milk_price(t);
      sup[s] = { days: S.days, delivers_tomorrow: nxt !== null && S.days.includes(nxt.wd),
        min_order: "min_order" in S ? S.min_order : null, min_qty: "min_qty" in S ? S.min_qty : null, prices: items };
    }
    const costs = {};
    for (const k of DRINKS.concat(["croissant"])) costs[k] = this.cost_of(k, t);
    const inv = {};
    for (const [k, v] of Object.entries(C.investments)) inv[k] = { cost: v.cost, bought_from_day: k in this.bought ? this.bought[k] : null };
    return {
      day: t, date: nxt ? nxt.date : null, wd: nxt ? nxt.wd : null, days_total: C.days,
      cash: cents(this.cash), loan: cents(this.loan), reputation: pyround(this.rep, 3),
      stock: { milk_l: this.milk.map(([a, b]) => [cents(a), b]), beans_lb: cents(this.beans_g / C.suppliers.roaster.items.beans.grams),
        cups: this.cups, croissant: this.croissant },
      staff: this.staff.map((s) => Object.assign({}, s)), schedule: clone(this.schedule),
      prices: Object.assign({}, this.prices), discounts: clone(this.discounts), costs,
      suppliers: sup, forecast: fc, cards: this.open_cards(), grade: this.grade_b_from !== null && this.grade_b_from <= t ? "B" : "A",
      investments: inv, yesterday: this.last_report, totals: Object.fromEntries(Object.entries(this.totals).map(([k, v]) => [k, cents(v)])),
      counts: Object.assign({}, this.counts),
    };
  }
  check(dec) {
    const C = this.C, t = this.t;
    const out = [];
    if (t >= C.days) return [[rej("day", "over", "Месяц закончился.", "The month is over.")], null];
    if (!isObj(dec)) return [[form("decision", "нужен объект JSON", "a JSON object is required")], EMPTY_OK()];
    const D = this.W.days[t], wd = D.wd;
    let cash = this.cash;
    const ok = {};
    let orders = or(dec.orders, {});
    if (!isObj(orders)) { out.push(form("orders", "нужен объект {поставщик: {позиция: количество}}", "an object {supplier: {item: qty}} is required")); orders = {}; }
    const ok_orders = {};
    for (const [s, items0] of Object.entries(orders)) {
      if (truthy(items0) && !isObj(items0)) { out.push(form("orders." + s, "нужен объект {позиция: количество}", "an object {item: qty} is required")); continue; }
      if (!(s in C.suppliers)) { out.push(rej("orders." + s, "no_supplier", "Нет поставщика «" + s + "».", "No supplier '" + s + "'.")); continue; }
      const S = C.suppliers[s];
      const items = {};
      for (const [k, v] of Object.entries(items0 || {})) if (truthy(v)) items[k] = v;
      if (!Object.keys(items).length) continue;
      let bad = false;
      for (const [it, q] of Object.entries(items)) {
        if (!(it in S.items)) { out.push(rej("orders." + s, "no_item", SUP_RU[s] + " не возит «" + it + "».", SUP_EN[s] + " does not carry '" + it + "'.")); bad = true; }
        else if (!isInt(q) || q < 0) { out.push(rej("orders." + s, "qty", "Количество должно быть целым: " + pstr(q) + ".", "Quantity must be a whole number: " + pstr(q) + ".")); bad = true; }
      }
      if (bad) continue;
      if (!S.days.includes(wd)) {
        const ds_ru = S.days.map((x) => WD_RU[x]).join(", "), ds_en = S.days.map((x) => WD_EN[x]).join(", ");
        out.push(rej("orders." + s, "day", SUP_RU[s] + " возит только " + ds_ru + ", а завтра " + WD_RU[wd] + ".",
          SUP_EN[s] + " delivers only " + ds_en + "; tomorrow is " + WD_EN[wd] + "."));
        continue;
      }
      const price = {};
      for (const it of Object.keys(items)) price[it] = it === "milk" ? this.milk_price(t) : S.items[it].price;
      const total = cents(sum(Object.entries(items).map(([it, q]) => price[it] * q)));
      if ("min_order" in S && total < S.min_order) {
        out.push(rej("orders." + s, "min", SUP_RU[s] + ": заказ $" + f2(total) + " меньше минимума $" + pstr(S.min_order) + ".",
          SUP_EN[s] + ": order $" + f2(total) + " is below the $" + pstr(S.min_order) + " minimum."));
        continue;
      }
      if ("min_qty" in S && sum(Object.values(items)) < S.min_qty) {
        out.push(rej("orders." + s, "min", SUP_RU[s] + ": меньше " + S.min_qty + " штук не возит.", SUP_EN[s] + ": minimum " + S.min_qty + " pieces."));
        continue;
      }
      const prev = s in this.orders ? this.orders[s].total : 0.0;
      if (total > cash + prev + 1e-9) {
        out.push(rej("orders." + s, "cash", "Не хватает денег: заказ $" + f2(total) + ", на счёте $" + f2(cash) + ".",
          "Not enough cash: order $" + f2(total) + ", balance $" + f2(cash) + "."));
        continue;
      }
      cash -= total - prev;
      ok_orders[s] = { items, total };
    }
    ok.orders = ok_orders;
    let prices = or(dec.prices, {});
    if (!isObj(prices)) { out.push(form("prices", "нужен объект {позиция: цена}", "an object {item: price} is required")); prices = {}; }
    const ok_prices = {};
    const [lo, hi] = C.price_bounds;
    for (const [it, p] of Object.entries(prices)) {
      if (!(it in this.prices)) { out.push(rej("prices." + it, "no_item", "Нет позиции «" + it + "».", "No item '" + it + "'.")); continue; }
      const base = C.menu[it].price, cost = this.cost_of(it, t);
      if (!isNum(p) || p <= cost) {
        out.push(rej("prices." + it, "below_cost", ITEM_RU[it] + ": цена $" + pstr(p) + " не выше себестоимости $" + f2(cost) + ".",
          it + ": price $" + pstr(p) + " is not above cost $" + f2(cost) + "."));
        continue;
      }
      if (p < base * lo || p > base * hi) {
        out.push(rej("prices." + it, "bounds", ITEM_RU[it] + ": цена должна быть от $" + f2(base * lo) + " до $" + f2(base * hi) + ".",
          it + ": price must be between $" + f2(base * lo) + " and $" + f2(base * hi) + "."));
        continue;
      }
      ok_prices[it] = cents(p);
    }
    ok.prices = ok_prices;
    if ("discounts" in dec && truthy(dec.discounts) && !Array.isArray(dec.discounts)) {
      out.push(form("discounts", "нужен список скидок", "a list of discounts is required"));
    } else if ("discounts" in dec) {
      const ok_d = [];
      or(dec.discounts, []).forEach((d, i) => {
        if (!isObj(d)) { out.push(rej("discounts." + i, "form", "Скидка " + (i + 1) + ": нужна позиция, процент и части дня 0–2.", "Discount " + (i + 1) + ": needs item, percent and dayparts 0-2.")); return; }
        const it = d.item, pct = d.pct, dps = "dayparts" in d ? d.dayparts : [0, 1, 2];
        if (typeof it !== "string" || !(it in this.prices) || !isNum(pct) || !Array.isArray(dps) || !dps.length || dps.some((x) => !isInt(x) || ![0, 1, 2].includes(x))) {
          out.push(rej("discounts." + i, "form", "Скидка " + (i + 1) + ": нужна позиция, процент и части дня 0–2.", "Discount " + (i + 1) + ": needs item, percent and dayparts 0-2."));
          return;
        }
        if (pct <= 0 || pct > C.max_discount_pct) {
          out.push(rej("discounts." + i, "pct", "Скидка " + (i + 1) + ": от 1 до " + C.max_discount_pct + " %.", "Discount " + (i + 1) + ": 1 to " + C.max_discount_pct + "%."));
          return;
        }
        const p = cents((it in ok_prices ? ok_prices[it] : this.prices[it]) * (1 - pct / 100.0)), cost = this.cost_of(it, t);
        if (p <= cost) {
          out.push(rej("discounts." + i, "below_cost", "Скидка " + pstr(pct) + " % на " + ITEM_RU[it] + " даёт $" + f2(p) + ", это не выше себестоимости $" + f2(cost) + ": запрещено.",
            pstr(pct) + "% off " + it + " makes $" + f2(p) + ", not above cost $" + f2(cost) + ": not allowed."));
          return;
        }
        if (ok_d.some((x) => x.item === it && x.dayparts.some((y) => dps.includes(y)))) {
          out.push(rej("discounts." + i, "double", "Две скидки на " + ITEM_RU[it] + " в одну часть дня.", "Two discounts on " + it + " in the same daypart."));
          return;
        }
        ok_d.push({ item: it, pct, dayparts: dps.slice().sort((a, b) => a - b) });
      });
      ok.discounts = ok_d;
    }
    let hire = or(dec.hire, 0), fire = or(dec.fire, 0);
    const hb = this.headcount("barista", 0, true);
    if (!isInt(hire) || hire < 0 || hire > 3) { out.push(rej("hire", "range", "Нанять можно от 0 до 3 человек за вечер.", "You can hire 0 to 3 people per evening.")); hire = 0; }
    if (!isInt(fire) || fire < 0 || fire > hb) { out.push(rej("fire", "range", "Уволить можно не больше, чем есть бариста (" + hb + ").", "You cannot let go more baristas than you have (" + hb + ").")); fire = 0; }
    ok.hire = hire; ok.fire = fire;
    if ("schedule" in dec) {
      const sch = dec.schedule; let good = true;
      const hb_after = hb + hire - fire;
      for (let w = 0; w < 7; w++) {
        const row = isObj(sch) ? sch[String(w)] : null;
        if (!isObj(row) || !Array.isArray(row.barista) || !Array.isArray(row.lead) || row.barista.length !== 3 || row.lead.length !== 3) {
          out.push(rej("schedule." + w, "form", WD_RU[w] + ": нужны три числа бариста и три старшего.", WD_EN[w] + ": need three barista numbers and three lead numbers.")); good = false; continue;
        }
        const b = row.barista, l = row.lead;
        if (b.concat(l).some((x) => !isInt(x)) || b.some((x) => x < 0)) {
          out.push(rej("schedule." + w, "form", WD_RU[w] + ": старший 0 или 1, бариста целым числом от 0.", WD_EN[w] + ": lead is 0 or 1, baristas a whole number from 0.")); good = false; continue;
        }
        if (l[0] < 1) { out.push(rej("schedule." + w, "no_lead", WD_RU[w] + ": утром нет старшего, кофейня не откроется.", WD_EN[w] + ": no lead in the morning, the shop cannot open.")); good = false; }
        if (l.some((x) => x < 0 || x > 1)) {
          out.push(rej("schedule." + w, "form", WD_RU[w] + ": старший 0 или 1, бариста целым числом.", WD_EN[w] + ": lead is 0 or 1, baristas a whole number.")); good = false; continue;
        }
        for (let dp = 0; dp < 3; dp++) {
          if (b[dp] + l[dp] > C.max_per_daypart) { out.push(rej("schedule." + w, "space", WD_RU[w] + " " + DP_RU[dp] + ": за стойкой помещается " + C.max_per_daypart + " человек.", WD_EN[w] + " " + DP_EN[dp] + ": only " + C.max_per_daypart + " fit behind the bar.")); good = false; }
          if (b[dp] > hb_after) { out.push(rej("schedule." + w, "headcount", WD_RU[w] + " " + DP_RU[dp] + ": " + b[dp] + " бариста, а в штате " + hb_after + ".", WD_EN[w] + " " + DP_EN[dp] + ": " + b[dp] + " baristas, but you employ " + hb_after + ".")); good = false; }
        }
      }
      if (good) { ok.schedule = {}; for (let w = 0; w < 7; w++) ok.schedule[String(w)] = { barista: sch[String(w)].barista.slice(), lead: sch[String(w)].lead.slice() }; }
    }
    const ok_b = [];
    let buy = or(dec.buy, []);
    if (!Array.isArray(buy)) { out.push(form("buy", "нужен список, например [\"machine2\"]", "a list is required, e.g. [\"machine2\"]")); buy = []; }
    for (const k of buy) {
      if (typeof k !== "string") { out.push(form("buy", "в списке нужны названия вложений", "the list needs investment names")); continue; }
      if (!(k in C.investments)) { out.push(rej("buy." + k, "no_item", "Нет такого вложения: «" + k + "».", "No such investment: '" + k + "'.")); continue; }
      if (k in this.bought || ok_b.includes(k)) { out.push(rej("buy." + k, "twice", "Это уже куплено.", "Already bought.")); continue; }
      const cost = C.investments[k].cost;
      if (cost > cash + 1e-9) { out.push(rej("buy." + k, "cash", "Не хватает денег: стоит $" + cost + ", на счёте $" + f2(cash) + ".", "Not enough cash: costs $" + cost + ", balance $" + f2(cash) + ".")); continue; }
      cash -= cost; ok_b.push(k);
    }
    ok.buy = ok_b;
    const cards = {};
    for (const c of this.open_cards()) cards[c.id] = c;
    const ok_c = {};
    let choices = or(dec.choices, {});
    if (!isObj(choices)) { out.push(form("choices", "нужен объект {id карточки: вариант}", "an object {card id: option} is required")); choices = {}; }
    for (const [cid, opt] of Object.entries(choices)) {
      if (!(cid in cards)) { out.push(rej("choices." + cid, "closed", "Карточки «" + cid + "» сейчас нет.", "Card '" + cid + "' is not open now.")); continue; }
      if (!cards[cid].options.includes(opt)) { out.push(rej("choices." + cid, "option", "У карточки нет варианта «" + opt + "».", "The card has no option '" + opt + "'.")); continue; }
      ok_c[cid] = opt;
    }
    ok.choices = ok_c;
    return [out, ok];
  }
  decide(dec) {
    const [out, ok] = this.check(dec);
    if (!ok) return out;
    const t = this.t;
    for (const [s, o] of Object.entries(ok.orders)) {
      if (s in this.orders) { this.cash += this.orders[s].total; this.totals.purchases -= this.orders[s].total; }
      this.orders[s] = o;
      this.cash -= o.total; this.totals.purchases += o.total;
    }
    Object.assign(this.prices, ok.prices);
    if ("discounts" in ok) this.discounts = ok.discounts;
    for (let i = 0; i < ok.hire; i++) { this.staff.push({ id: "b" + this.next_id, role: "barista", start: t + this.C.staff.hire_delay_days }); this.next_id += 1; }
    if (ok.hire) { const hc = ok.hire * this.C.staff.hire_cost; this.cash -= hc; this.totals.wages += hc; }  // оформление и учебная смена
    for (let i = 0; i < ok.fire; i++) {
      const bs = this.staff.filter((s) => s.role === "barista");
      bs.sort((a, b) => (b.start - a.start) || (parseInt(b.id.slice(1), 10) - parseInt(a.id.slice(1), 10)));
      this.staff.splice(this.staff.indexOf(bs[0]), 1);
    }
    if ("schedule" in ok) this.schedule = ok.schedule;
    Object.assign(this.choices, ok.choices);
    for (const k of ok.buy) {
      const I = this.C.investments[k];
      this.cash -= I.cost; this.totals.investments += I.cost;
      this.bought[k] = t + (I.delay || 0);
    }
    this.pending_rejections = this.pending_rejections.concat(out);
    this.pending_decisions.push(dec);
    return out;
  }
  step() {
    const C = this.C, t = this.t, W = this.W;
    const D = W.days[t];
    const rep = { day: t, date: D.date, wd: D.wd, weather: D.weather, events: [], closed: false };
    let costs_ev = 0.0;
    const R0 = C.reputation;
    for (const e of W.events.concat(this.cards_extra)) {
      const k = e.kind, ch = this.choice(e), E = C.events[k] || {};
      if (k === "blogger" && e.day === t && ch === "accept") { costs_ev += E.cost; rep.events.push("blogger_shoot"); }
      if (k === "repair" && e.day === t && ch === "sign") costs_ev += E.sign_cost;
      if (k === "inspection" && ch === "clean" && !this.clean_paid.has(e.id) && (t === e.day - 1 || t === e.day)) { costs_ev += E.clean_cost; this.clean_paid.add(e.id); }
      if (k === "breakdown" && e.day + 1 === t) costs_ev += ch === "fast" ? E.fast_cost : E.slow_cost;
      if (k === "competitor" && e.day === t) {
        if (ch === "loyalty") { costs_ev += E.loyalty_cost; this.rep = clamp(this.rep + E.loyalty_rep, R0.min, R0.max); }
        else if (ch === "promo") costs_ev += E.promo_cost;
      }
      if (k === "complaint" && e.day === t) {
        if (ch === "coupons") { costs_ev += 40; this.rep = clamp(this.rep + 0.03, R0.min, R0.max); }
        else if (ch === "reply") this.rep = clamp(this.rep + 0.01, R0.min, R0.max);
        else this.rep = clamp(this.rep - 0.01, R0.min, R0.max);
      }
    }
    const closed = this.closed(t);
    rep.closed = closed;
    const delivered = {};
    const no_show = W.events.some((e) => e.kind === "no_show" && e.day === t);
    for (const [s, o] of Object.entries(this.orders)) {
      if (closed || D.weather === "blizzard" || (s === "dairy" && no_show)) {
        this.cash += o.total; this.totals.refunds += o.total;
        rep.events.push("no_delivery_" + s); continue;
      }
      for (const [it, q] of Object.entries(o.items)) {
        if (it === "milk") { const I = C.suppliers.dairy.items.milk; this.milk.push([q * I.liters, t + I.shelf_days - 1]); }
        else if (it === "beans") this.beans_g += q * C.suppliers.roaster.items.beans.grams;
        else if (it === "cups") this.cups += q * C.suppliers.roaster.items.cups.count;
        else if (it === "croissant") this.croissant += q;
      }
      delivered[s] = o.items;
    }
    this.orders = {};
    rep.delivered = delivered;
    const row = this.schedule[String(D.wd)];
    const avail_b = Math.max(0, this.headcount("barista", t) - this.sick_out(t));
    const agency = W.events.some((e) => e.kind === "sick" && e.day <= t && t <= e.day + C.events.sick.days - 1 && this.choice(e) === "agency");
    const hours_dp = C.hours.dayparts;
    const on_b = [], on_l = [], ag = [];
    for (let dp = 0; dp < DP_N; dp++) {
      const want = row.barista[dp];
      const have = Math.min(want, avail_b);
      const extra = agency ? want - have : 0;
      on_b.push(closed ? 0 : have); ag.push(closed ? 0 : extra);
      on_l.push(closed ? 0 : Math.min(row.lead[dp], this.headcount("lead", t)));
    }
    let no_latte = [false, false, false];
    for (const e of W.events) {
      if (e.kind === "breakdown") {
        if (t === e.day) no_latte[1] = no_latte[2] = true;
        if (t === e.day + 1 && this.choice(e) === "slow") no_latte[0] = no_latte[1] = true;
      }
    }
    if (this.has("machine2", t)) no_latte = [false, false, false];
    if (no_latte.some((x) => x)) rep.events.push("no_espresso");
    const [exp, notes] = this.expected_guests(t, true);
    rep.notes = notes;
    const M = C.menu;
    const I_beans = C.suppliers.roaster.items.beans;
    let revenue = 0.0, tx = 0, served_all = 0, queue = 0, stockout = 0, demand_all = 0, pastry_missing = 0;
    const by_dp = [];
    let catering = null;
    for (const e of W.events) if (e.kind === "catering" && e.day === t && this.choice(e) === "accept") catering = e;
    for (let dp = 0; dp < DP_N; dp++) {
      const g = closed ? 0 : rnd(exp[dp] * W.noise[t][dp]);
      const h = hours_dp[dp][1] - hours_dp[dp][0];
      const dph = C.drinks_per_barista_hour + (this.has("machine2", t) ? C.investments.machine2.extra_drinks_per_hour : 0);
      let cap = rnd((on_b[dp] + ag[dp] + C.lead_capacity_share * on_l[dp]) * dph * h);
      if (dp === 0) for (const e of W.events) if (e.kind === "blogger" && e.day === t && this.choice(e) === "accept") cap = rnd(cap * C.events.blogger.morning_capacity);
      const rec = { dp, demand: g, capacity: cap };
      if (dp === 0 && catering !== null && !closed) {
        const want = C.events.catering.drinks;
        const can = Math.min(want, cap, !no_latte[0] ? this.units_available("latte") : 0);
        this.consume("latte", can, t);
        revenue += can * C.events.catering.price;
        cap -= can;
        queue += want - can;
        rec.catering = can;
        rep.events.push("catering_" + can);
      }
      const served = Math.min(g, cap);
      queue += g - served; demand_all += g;
      const sp = split_lr(served, DRINKS.map((k) => M[k].share));
      const counts = {}; DRINKS.forEach((k, i) => { counts[k] = sp[i]; });
      const sold = {};
      for (const k of DRINKS) {
        const want = counts[k];
        const av = k === "latte" && no_latte[dp] ? 0 : this.units_available(k);
        const s_ = Math.min(want, av);
        this.consume(k, s_, t);
        sold[k] = s_;
        const short = want - s_;
        if (short > 0) {
          if (k === "latte") { const sw = rnd(short * C.latte_to_drip); counts.drip += sw; stockout += short - sw; }
          else stockout += short;
        }
      }
      const guests_ok = sum(Object.values(sold));
      for (const k of DRINKS) revenue += sold[k] * this.eff_price(k, dp);
      const pr = this.eff_price("croissant", dp) / M.croissant.price;
      const pm = Math.pow(pr, pr > 1 ? C.elasticity_pastry.up : C.elasticity_pastry.down);
      const pw = rnd(guests_ok * M.croissant.attach * pm);
      const ps = Math.min(pw, this.croissant);
      this.croissant -= ps;
      revenue += ps * this.eff_price("croissant", dp);
      pastry_missing += pw - ps;
      tx += guests_ok; served_all += guests_ok;
      Object.assign(rec, { served, sold, croissant: ps, croissant_missing: pw - ps });
      by_dp.push(rec);
    }
    stockout += pastry_missing;
    revenue = cents(revenue);
    const fee = tx === 0 ? 0.0 : cents(C.card_share * (revenue * (1 + C.sales_tax)) * C.card_fee_pct + C.card_fee_fixed * rnd(C.card_share * tx));
    const S = C.staff;
    let hb = 0, hl = 0, ha = 0;
    for (let dp = 0; dp < DP_N; dp++) { const h = hours_dp[dp][1] - hours_dp[dp][0]; hb += on_b[dp] * h; hl += on_l[dp] * h; ha += ag[dp] * h; }
    let wages = (hb * S.barista.wage + hl * S.lead.wage) * (1 + S.burden);
    this.week_hours.barista += hb; this.week_hours.lead += hl;
    let ot = 0.0;
    if (D.wd === 6 || t === C.days - 1) {
      for (const role of ["barista", "lead"]) {
        const over = this.week_hours[role] - S.overtime_after_h * Math.max(1, this.headcount(role, t));
        if (over > 0) ot += over * S[role].wage * (S.overtime_mult - 1) * (1 + S.burden);
      }
      rep.overtime = cents(ot);
      this.week_hours = { barista: 0.0, lead: 0.0 };
    }
    wages = cents(wages + ot);
    const agency_cost = cents(ha * S.agency_hourly);
    const expired = sum(this.milk.filter(([a, b]) => b <= t).map(([a]) => a));
    this.milk = this.milk.filter(([a, b]) => b > t && a > 1e-9).map(([a, b]) => [a, b]);
    const wo_c = this.croissant; this.croissant = 0;
    const rent = t === 0 ? cents(this.rent_day * C.days) : 0.0;
    const fixed = cents(C.fixed_month / C.days + C.supplies_pct * revenue);
    costs_ev = cents(costs_ev);
    this.cash += revenue - fee - wages - agency_cost - rent - fixed - costs_ev;
    this.cash = cents(this.cash);
    let loan_new = 0.0;
    if (this.cash < 0) { loan_new = -this.cash; this.loan += loan_new; this.cash = 0.0; }
    const T = this.totals;
    T.revenue += revenue; T.card_fees += fee; T.wages += wages; T.agency += agency_cost;
    T.rent += rent; T.fixed += fixed; T.event_costs += costs_ev;
    for (const k of Object.keys(T)) T[k] = cents(T[k]);
    const Cn = this.counts;
    Cn.stockout_guests += stockout; Cn.queue_guests += queue; Cn.guests += served_all; Cn.demand += demand_all;
    Cn.written_off_milk_l = cents(Cn.written_off_milk_l + expired); Cn.written_off_croissant += wo_c;
    for (const e of W.events) {
      if (e.kind === "inspection" && e.day === t) {
        const qrate = queue / Math.max(1, demand_all);
        const b = this.choice(e) !== "clean" && (qrate > 0.10 || e.hidden.u < C.events.inspection.b_risk);
        if (b) this.grade_b_from = t + 1;
        rep.events.push("inspection_" + (b ? "B" : "A"));
      }
    }
    const R = C.reputation;
    const unhappy = (queue + (stockout - pastry_missing) + 0.3 * pastry_missing) / Math.max(1, demand_all);
    if (!closed) this.rep = clamp(this.rep + R.drift - R.unhappy_k * unhappy, R.min, R.max);
    if (!closed && demand_all > 0 && queue / demand_all >= 0.05 && !this.cards_extra.length && t + 1 < C.days)
      this.cards_extra.push({ id: "complaint_" + t, kind: "complaint", day: t + 1, show: t + 1, deadline: t });
    Object.assign(rep, { by_dp, revenue, card_fee: fee, wages, agency: agency_cost, rent, fixed,
      event_costs: costs_ev, queue_guests: queue, stockout_guests: stockout, demand: demand_all, served: served_all,
      milk_written_off_l: cents(expired), croissant_written_off: wo_c, cash: this.cash, loan_new: cents(loan_new),
      reputation: pyround(this.rep, 4), staff_on: { barista: on_b, lead: on_l, agency: ag },
      stock: { milk_l: cents(sum(this.milk.map(([a]) => a))), beans_lb: cents(this.beans_g / I_beans.grams), cups: this.cups, croissant: wo_c },
      decisions: this.pending_decisions, rejections: this.pending_rejections });
    this.pending_rejections = [];
    this.pending_decisions = [];
    this.journal.push(rep);
    const lr = {}; for (const [k, v] of Object.entries(rep)) if (k !== "rejections") lr[k] = v;
    this.last_report = lr;
    this.t += 1;
    return rep;
  }
  units_available(k) {
    const m = this.C.menu[k];
    let lim = m.cup ? Math.floor(this.cups / m.cup) : 1e9;
    if (m.beans_g) lim = Math.min(lim, Math.floor(this.beans_g / m.beans_g + 1e-9));
    if (m.milk_l) lim = Math.min(lim, Math.floor(sum(this.milk.map(([a]) => a)) / m.milk_l + 1e-9));
    return lim;
  }
  consume(k, n, t) {
    if (n <= 0) return;
    const m = this.C.menu[k];
    this.cups -= n * m.cup;
    this.beans_g = cents(this.beans_g - n * m.beans_g);
    let need = n * m.milk_l;
    this.milk.sort((a, b) => a[1] - b[1]);
    for (const lot of this.milk) {
      if (need <= 1e-9) break;
      const take = Math.min(lot[0], need); lot[0] = cents(lot[0] - take); need -= take;
    }
  }
  score() {
    const C = this.C, T = this.totals, Cn = this.counts;
    const beans = C.suppliers.roaster.items.beans, cups = C.suppliers.roaster.items.cups;
    const left = cents(this.beans_g / beans.grams * beans.price + this.cups * cups.price / cups.count);
    const parts = {
      revenue: T.revenue, purchases: -cents(T.purchases - T.refunds), leftover_stock: left,
      wages: -cents(T.wages + T.agency), rent_fixed: -cents(T.rent + T.fixed), card_fees: -T.card_fees,
      event_costs: -T.event_costs, investments: -T.investments,
      leftover_equipment: "machine2" in this.bought ? cents(C.investments.machine2.cost * C.investments.machine2.residual) : 0.0,
      stockout_penalty: -cents(Cn.stockout_guests * C.penalty_stockout),
      queue_penalty: -cents(Cn.queue_guests * C.penalty_queue), loan_penalty: -cents(this.loan * C.loan_penalty),
    };
    const profit = cents(sum(Object.entries(parts).filter(([k]) => !k.endsWith("_penalty")).map(([, v]) => v)));
    return { score: cents(sum(Object.values(parts))), profit, parts, counts: Object.assign({}, Cn), loan: cents(this.loan), cash: cents(this.cash) };
  }
}

function replay(seed, settings, decisions, C) {
  const g = new Game(seed, settings.street, settings.money, settings.scenario, C);
  const by_day = {};
  for (const [day, dec] of decisions) (by_day[day] = by_day[day] || []).push(dec);
  while (g.t < C.days) {
    g.observe();
    for (const dec of by_day[g.t] || []) g.decide(dec);
    g.step();
  }
  return g.score();
}

const API = { Game, replay, make_world, DRINKS, DEFAULT, card_options, cents, rnd, fnv, Rng, WD_RU, WD_EN };
if (typeof module !== "undefined" && module.exports) module.exports = API;
else root.CafeSim = API;
})(typeof window !== "undefined" ? window : globalThis);

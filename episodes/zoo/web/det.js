// core/det.py на JS, один к одному: mulberry32 с подпотоками по FNV-1a, своё округление, split_lr, календарь.
// Целые операции генератора только через Math.imul и беззнаковый сдвиг: иначе 32 бита не сойдутся с Python.
(function (root) {
"use strict";

const rnd = (x) => Math.floor(x + 0.5);
const cents = (x) => Math.floor(x * 100 + 0.5) / 100;

function fnv(s) {
  let h = 2166136261 >>> 0;
  for (const ch of new TextEncoder().encode(s)) { h ^= ch; h = Math.imul(h, 16777619) >>> 0; }
  return h >>> 0;
}

class Rng {
  constructor(seed_int) { this.a = seed_int >>> 0; }
  u() {
    this.a = (this.a + 0x6D2B79F5) >>> 0;
    let t = this.a;
    t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
    t = (t ^ ((t + (Math.imul(t ^ (t >>> 7), t | 61) >>> 0)) >>> 0)) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  int(lo, hi) { return lo + Math.floor(this.u() * (hi - lo + 1)); }   // включительно
  pick_w(weights) {
    const x = this.u() * sum(weights);
    let acc = 0.0;
    for (let i = 0; i < weights.length; i++) { acc += weights[i]; if (x < acc) return i; }
    return weights.length - 1;
  }
}

const clamp = (x, lo, hi) => (x < lo ? lo : x > hi ? hi : x);
// builtins.sum Python 3.12: компенсация Нейемайера, иначе 0.4+0.25+0.05+0.2+0.1 даёт 1.0000000000000002,
// а Python даёт ровно 1.0, и доли посетителей разъезжаются на человека.
function sum(a) {
  let s = 0.0, c = 0.0;
  for (const x of a) {
    const t = s + x;
    if (Math.abs(s) >= Math.abs(x)) c += (s - t) + x;
    else c += (x - t) + s;
    s = t;
  }
  return s + c;
}

// Делит n на целые части по долям, наибольшие остатки, порядок стабилен.
function split_lr(n, shares) {
  const tot = sum(shares);
  const raw = shares.map((s) => (n * s) / tot);
  const base = raw.map((r) => Math.floor(r));
  const rest = n - sum(base);
  const order = shares.map((_, i) => i).sort((i, j) => (raw[j] - base[j]) - (raw[i] - base[i]) || i - j);
  for (const i of order.slice(0, rest)) base[i] += 1;
  return base;
}

const days_in_month = (y, m) =>
  [31, (y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0)) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1];

function weekday(y, m, d) {   // пн=0, Сакамото
  const t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4];
  const yy = m < 3 ? y - 1 : y;
  const w = (yy + Math.floor(yy / 4) - Math.floor(yy / 100) + Math.floor(yy / 400) + t[m - 1] + d) % 7;  // вс=0
  return (w + 6) % 7;
}

const API = { rnd, cents, fnv, Rng, clamp, sum, split_lr, days_in_month, weekday };
if (typeof module !== "undefined" && module.exports) module.exports = API;
else root.ZooDet = API;
})(typeof window !== "undefined" ? window : globalThis);

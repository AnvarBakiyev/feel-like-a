// Тест совпадения: те же решения в JS, сравнение наблюдений каждого вечера, полного журнала и счёта до последнего знака.
import fs from "fs"; import { createRequire } from "module";
const require = createRequire(import.meta.url);
const S = require("./sim.js");
const D = JSON.parse(fs.readFileSync(new URL("./parity_trace.json", import.meta.url)));
// ключи по алфавиту: порядок ключей у Python и JS может отличаться, значения нет
const canon = (x) => JSON.stringify(x, (k, v) => (v && typeof v === "object" && !Array.isArray(v) ? Object.fromEntries(Object.keys(v).sort().map((q) => [q, v[q]])) : v));
function firstDiff(a, b, path = "") {
  if (canon(a) === canon(b)) return null;
  if (a && b && typeof a === "object" && typeof b === "object") {
    for (const k of new Set(Object.keys(a).concat(Object.keys(b)))) { const d = firstDiff(a[k], b[k], path + "." + k); if (d) return d; }
  }
  return path + ": JS " + JSON.stringify(a) + " / Python " + JSON.stringify(b);
}
let bad = 0;
for (const tr of D.traces) {
  const s = tr.settings;
  const g = new S.Game(s.seed, s.street, s.money, s.scenario, D.city);
  let err = null;
  for (let t = 0; t < tr.steps.length && !err; t++) {
    const o = JSON.parse(JSON.stringify(g.observe()));
    if (canon(o) !== canon(tr.observe[t])) err = "вечер " + t + " наблюдение " + firstDiff(o, tr.observe[t]);
    for (const dec of tr.steps[t]) g.decide(dec);
    const rep = JSON.parse(JSON.stringify(g.step()));
    if (!err && canon(rep) !== canon(tr.journal[t])) err = "день " + t + " отчёт " + firstDiff(rep, tr.journal[t]);
  }
  const sc = JSON.parse(JSON.stringify(g.score()));
  if (!err && canon(sc) !== canon(tr.score)) err = "счёт " + firstDiff(sc, tr.score);
  const rp = S.replay(s.seed, s, tr.steps.flatMap((ds, t) => ds.map((d) => [t, d])), D.city);
  if (!err && rp.score !== tr.score.score) err = "replay " + rp.score + " / " + tr.score.score;
  if (err) { bad++; if (bad <= 5) console.log("РАСХОЖДЕНИЕ", JSON.stringify(s), err.slice(0, 400)); }
}
console.log(bad === 0 ? `ok: ${D.traces.length} трасс совпали до последнего знака (наблюдения, журнал, счёт, replay)` : `не совпало: ${bad} из ${D.traces.length}`);
process.exit(bad ? 1 : 0);

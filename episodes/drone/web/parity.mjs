// Тест совпадения: решения из Python, повтор в JS, сравнение состояния до последнего знака.
import fs from "fs"; import { createRequire } from "module";
const require = createRequire(import.meta.url);
const S = require("./sim.js");
const D = JSON.parse(fs.readFileSync(new URL("./parity_trace.json", import.meta.url)));
// repr Питона и String() JS дают одну кратчайшую запись; 1.0 у Питона против 1 у JS выравниваем
const r = (x) => { if (typeof x !== "number") return x; let s = String(x); if (Number.isInteger(x) && !s.includes("e")) s += ".0"; return s; };
const st = (g) => {
  const out = [];
  for (const d of g.drones) out.push(r(d.x), r(d.y), r(d.agl), r(d.soc), r(d.wh), d.mode, d.phase, r(d.gs));
  out.push(r(g.counts.wh), r(g.counts.late_s), g.counts.delivered, g.counts.forced, g.counts.lost, g.counts.pads);
  return out;
};
let bad = 0;
for (const tr of D.traces) {
  const w = JSON.parse(JSON.stringify(D.worlds[tr.world]));
  w.map.terrain = D.terrain[w.city];
  const g = new S.Game(w);
  let ci = 0, ok = true, si = 0;
  for (let n = 0; n < tr.n; n++) {
    if (si < tr.steps.length && tr.steps[si][0] === n) {
      for (const d of tr.steps[si][1]) {
        const rej = g.decide(d);
        if (rej.length) { console.log("ОТКАЗ В JS, А В PYTHON НЕТ", tr.city, tr.seed, tr.who, "шаг", n, JSON.stringify(d), JSON.stringify(rej)); ok = false; break; }
      }
      si++;
    }
    if (!ok) break;
    g.step();
    if (ci < tr.cps.length && tr.cps[ci][0] === n + 1) {
      const got = [n + 1].concat(st(g));
      if (JSON.stringify(got) !== JSON.stringify(tr.cps[ci])) {
        console.log("РАСХОЖДЕНИЕ", tr.city, tr.seed, tr.who, "шаг", n);
        for (let i = 0; i < Math.max(got.length, tr.cps[ci].length); i++)
          if (JSON.stringify(got[i]) !== JSON.stringify(tr.cps[ci][i])) console.log("   поле", i, "JS", got[i], "Python", tr.cps[ci][i]);
        ok = false; break;
      }
      ci++;
    }
  }
  const sc = g.score();
  if (ok) {
    const fin = st(g);
    if (JSON.stringify(fin) !== JSON.stringify(tr.final)) { console.log("ИТОГ РАЗНЫЙ", tr.city, tr.seed, tr.who, JSON.stringify(fin), JSON.stringify(tr.final)); ok = false; }
    else if (r(sc.raw) !== tr.score) { console.log("СЧЁТ РАЗНЫЙ", tr.city, tr.seed, tr.who, r(sc.raw), tr.score); ok = false; }
    else if (JSON.stringify(sc.counts) !== JSON.stringify(tr.counts)) { console.log("СВОДКА РАЗНАЯ", tr.city, tr.seed, tr.who, JSON.stringify(sc.counts), JSON.stringify(tr.counts)); ok = false; }
    else if (JSON.stringify(g.journal.slice(-3)) !== JSON.stringify(tr.journal_tail)) { console.log("ЖУРНАЛ РАЗНЫЙ", tr.city, tr.seed, tr.who, JSON.stringify(g.journal.slice(-3)), JSON.stringify(tr.journal_tail)); ok = false; }
    else if (JSON.stringify(g.events) !== JSON.stringify(tr.events)) { console.log("СОБЫТИЯ РАЗНЫЕ", tr.city, tr.seed, tr.who); ok = false; }
  }
  if (!ok) bad++;
}
console.log(bad === 0 ? `ok: ${D.traces.length} трасс совпали до последнего знака` : `не совпало: ${bad} из ${D.traces.length}`);
process.exit(bad ? 1 : 0);

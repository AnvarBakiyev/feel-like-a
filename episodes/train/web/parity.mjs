// Тест совпадения: решения из Python, повтор в JS, сравнение состояния до последнего знака.
import fs from "fs"; import { createRequire } from "module";
const require = createRequire(import.meta.url);
const S = require("./sim.js");
const D = JSON.parse(fs.readFileSync(new URL("./parity_trace.json", import.meta.url)));
// repr Python и String() JS дают одну кратчайшую запись; 1.0 у Python против 1 у JS выравниваем
const r = (x) => { let s = String(x); if (Number.isInteger(x) && !s.includes("e")) s += ".0"; return s; };
let bad = 0;
for (const tr of D.traces) {
  const g = new S.Game(D.lines[tr.line], D.trains[tr.line], tr.world);
  if (tr.pre) g.decide(tr.pre);
  let n = 0, ci = 0, ok = true;
  for (const d of tr.steps) {
    if (d) g.decide(d);
    g.step(); n++;
    if (ci < tr.cps.length && tr.cps[ci][0] === n) {
      const got = [n, r(g.x), r(g.v), r(g.E_in), r(g.E_back), r(g.t)];
      if (JSON.stringify(got) !== JSON.stringify(tr.cps[ci])) { console.log("РАСХОЖДЕНИЕ", tr.line, tr.seed, "шаг", n, got, tr.cps[ci]); ok = false; break; }
      ci++;
    }
  }
  const sc = g.score();
  const fin = [r(g.x), r(g.v), r(g.E_in), r(g.E_back), r(g.harsh_s)];
  if (ok && (JSON.stringify(fin) !== JSON.stringify(tr.final) || r(sc.score) !== tr.score)) { console.log("ИТОГ РАЗНЫЙ", tr.line, tr.seed, fin, tr.final, r(sc.score), tr.score); ok = false; }
  if (!ok) bad++;
}
console.log(bad === 0 ? `ok: ${D.traces.length} трасс совпали до последнего знака` : `не совпало: ${bad} из ${D.traces.length}`);
process.exit(bad ? 1 : 0);

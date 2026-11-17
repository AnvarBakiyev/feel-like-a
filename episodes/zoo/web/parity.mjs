// Тест совпадения: те же решения в JS, сравнение наблюдений каждого вечера, отчёта каждого шага,
// итогового счёта и результата replay с записанным в trace, до последнего знака.
import fs from "fs"; import { createRequire } from "module";
// trace весит 35 МБ и в репозиторий не кладётся: если его нет, собрать make_parity.py
const require = createRequire(import.meta.url);
const S = require("./sim.js");
// миры проверяются по очереди: у каждого свой файл трасс
const FILES = ["parity_trace.json", "parity_trace_ny2.json"]
  .map((n) => [n, new URL("./" + n, import.meta.url)]).filter(([, u]) => fs.existsSync(u));
if (!FILES.length) {
  console.log("нет файлов трасс. Собери их: python3 web/make_parity.py и python3 web/make_parity.py ny2");
  process.exit(2);
}
let TOTAL = 0, BAD = 0;
for (const [NAME, TRACE] of FILES) {
const D = JSON.parse(fs.readFileSync(TRACE));

// ключи по алфавиту: порядок ключей у Python и JS может отличаться, значения нет
const canon = (x) => JSON.stringify(x, (k, v) => (v && typeof v === "object" && !Array.isArray(v)
  ? Object.fromEntries(Object.keys(v).sort().map((q) => [q, v[q]])) : v));

function firstDiff(a, b, path = "") {
  if (canon(a) === canon(b)) return null;
  if (a && b && typeof a === "object" && typeof b === "object") {
    for (const k of new Set(Object.keys(a).concat(Object.keys(b)))) {
      const d = firstDiff(a[k], b[k], path + "." + k);
      if (d) return d;
    }
  }
  return path + ": JS " + JSON.stringify(a) + " / Python " + JSON.stringify(b);
}

let bad = 0;
for (const tr of D.traces) {
  const s = tr.settings;
  const g = new S.Game(s.seed, s.place, s.team, s.scenario, D.world);
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
  const rp = JSON.parse(JSON.stringify(S.replay(s.seed, { place: s.place, team: s.team, scenario: s.scenario },
    tr.steps.flatMap((ds, t) => ds.map((d) => [t, d])), D.world)));
  const want = { score: tr.score.score, parts: tr.score.parts, counts: tr.score.counts };
  if (!err && canon(rp) !== canon(want)) err = "replay " + firstDiff(rp, want);
  if (err) { bad++; if (bad <= 5) console.log("РАСХОЖДЕНИЕ", JSON.stringify(s), err.slice(0, 400)); }
}
// та же проверка формы, что и в test_replay.py: отказ с причиной, а не молчаливое принятие
{
  const g = new S.Game(1, "park", "mid", "heat", D.world);
  const cases = [[{ orders: { frozen: 300 } }, "orders.frozen"], [{ orders: 300 }, "orders"], [{ thaw: 12 }, "thaw"],
    [{ choices: ["a"] }, "choices"], [{ schedule: "утро" }, "schedule"]];
  for (const [dec, field] of cases) {
    const got = g.check(dec)[0].map((r) => r.field + "|" + r.code);
    if (!got.includes(field + "|form")) { bad++; console.log("ФОРМА", JSON.stringify(dec), got.join(",")); }
  }
  if (g.check(7)[0][0].code !== "form") { bad++; console.log("ФОРМА: решение не объект"); }
  if (g.check({})[0].length) { bad++; console.log("ФОРМА: пустое решение отклонено"); }
}
console.log(bad === 0
  ? `ok ${NAME}: ${D.traces.length} трасс совпали до последнего знака (наблюдения, отчёты, счёт, replay)`
  : `не совпало ${NAME}: ${bad} из ${D.traces.length}`);
TOTAL += D.traces.length; BAD += bad;
}
console.log(BAD === 0 ? `ok: всего ${TOTAL} трасс по ${FILES.length} мирам` : `не совпало: ${BAD} из ${TOTAL}`);
process.exit(BAD ? 1 : 0);

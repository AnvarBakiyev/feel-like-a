// Проверка данных страницы: решения всех соперников, проигранные sim.js, дают записанный счёт.
import { createRequire } from "module";
const require = createRequire(import.meta.url);
const S = require("./sim.js");
const fs = require("fs");
const D = JSON.parse(fs.readFileSync(new URL("./data.json", import.meta.url)));
let bad = 0, n = 0;
for (const key of Object.keys(D.worlds)) {
  const W = JSON.parse(JSON.stringify(D.worlds[key])); W.map.terrain = D.terrain[W.city];
  for (const [who, r] of Object.entries(D.rivals[key])) {
    const g = new S.Game(JSON.parse(JSON.stringify(W))); let i = 0, s = 0;
    while (!g.done()) { while (i < r.decisions.length && r.decisions[i][0] <= s) { g.decide(r.decisions[i][1]); i++; } g.step(); s++; }
    const sc = g.score().score; n++;
    if (sc !== r.score) { bad++; console.log("не совпало", key, who, sc, r.score); }
  }
}
console.log(bad ? "ошибок " + bad : "ok: " + n + " журналов, счёт в JS совпал с записанным");

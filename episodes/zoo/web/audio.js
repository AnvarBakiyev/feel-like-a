/* Звук зоопарка: всё синтезируется в браузере, файлов нет. Фон зависит от того, что на карте:
   днём птицы и гул посетителей (громче, когда людей больше), в дождь шум дождя, с наступлением вечера
   несколько секунд тихих сверчков.
   Разовые звуки привязаны к событиям сцены: монета у кассы, всплеск и лай морского льва на кормлении,
   колокол на открытии и закрытии. Включается первым нажатием на странице: браузер иначе не даёт. */
(function (root) {
  "use strict";
  var A = null, ON = true, amb = { mode: "off", crowd: 0, rain: false }, lastCoin = 0, chirpTimer = null;
  try { if (localStorage.getItem("zoo_sound") === "0") ON = false; } catch (e) {}

  function noise(ctx, sec, brown) {
    var n = Math.floor(ctx.sampleRate * sec), b = ctx.createBuffer(1, n, ctx.sampleRate), d = b.getChannelData(0), last = 0;
    for (var i = 0; i < n; i++) { var w = Math.random() * 2 - 1; if (brown) { last = (last + 0.02 * w) / 1.02; d[i] = last * 3.5; } else d[i] = w; }
    return b;
  }
  function G(v, to) { var g = A.ctx.createGain(); g.gain.value = v; if (to) g.connect(to); return g; }
  function F(type, f, q, to) { var x = A.ctx.createBiquadFilter(); x.type = type; x.frequency.value = f; if (q) x.Q.value = q; if (to) x.connect(to); return x; }
  function loop(buf, to) { var s = A.ctx.createBufferSource(); s.buffer = buf; s.loop = true; s.connect(to); s.start(); return s; }
  function ramp(p, v, t) { p.setTargetAtTime(v, A.ctx.currentTime, t || 0.25); }

  function init() {
    if (A) { if (A.ctx.state === "suspended") A.ctx.resume(); return A; }
    var AC = root.AudioContext || root.webkitAudioContext; if (!AC) return null;
    A = { ctx: new AC() };
    A.out = G(ON ? 0.8 : 0, A.ctx.destination);
    A.white = noise(A.ctx, 2.5, false); A.brown = noise(A.ctx, 3, true);
    // гул посетителей: бурый шум в полосе голоса, чуть «дышит»
    A.crowdG = G(0, A.out); var cf = F("bandpass", 520, 0.6, A.crowdG); loop(A.brown, cf);
    var lfo = A.ctx.createOscillator(); lfo.frequency.value = 0.23; var lg = G(90); lfo.connect(lg); lg.connect(cf.frequency); lfo.start();
    // дождь
    A.rainG = G(0, A.out); var rf = F("highpass", 1800, 0.4, A.rainG); loop(A.white, rf);
    // сверчки: тихо и недолго, только когда наступает вечер. Тон невысокий, без резкости.
    A.crickG = G(0, A.out); var cg = G(0.5, A.crickG), co = A.ctx.createOscillator(); co.type = "sine"; co.frequency.value = 2350; co.connect(cg); co.start();
    var cl = A.ctx.createOscillator(); cl.type = "sine"; cl.frequency.value = 11; var clg = G(0.5); cl.connect(clg); clg.connect(cg.gain); cl.start();
    applyAmb();
    return A;
  }
  function tone(type, f0, f1, dur, vol, when, filt) {
    if (!A || !ON) return; var c = A.ctx, t = c.currentTime + (when || 0), o = c.createOscillator(), g = c.createGain();
    o.type = type; o.frequency.setValueAtTime(f0, t); if (f1 && f1 !== f0) o.frequency.exponentialRampToValueAtTime(f1, t + dur);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.012); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    if (filt) { var fl = F(filt[0], filt[1], filt[2]); o.connect(fl); fl.connect(g); } else o.connect(g);
    g.connect(A.out); o.start(t); o.stop(t + dur + 0.05);
  }
  function burst(f, q, dur, vol, when, f1) {
    if (!A || !ON) return; var c = A.ctx, t = c.currentTime + (when || 0), s = c.createBufferSource(), fl = F("bandpass", f, q), g = c.createGain();
    s.buffer = A.white; s.connect(fl); fl.connect(g); g.connect(A.out);
    if (f1) fl.frequency.exponentialRampToValueAtTime(f1, t + dur);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    s.start(t); s.stop(t + dur + 0.05);
  }
  function chirp(when) {
    var base = 2300 + Math.random() * 1700, n = 1 + Math.floor(Math.random() * 3);
    for (var i = 0; i < n; i++) tone("sine", base, base * (1.25 + Math.random() * .3), 0.07, 0.035, (when || 0) + i * 0.11);
  }
  function schedule() {
    if (chirpTimer) clearTimeout(chirpTimer);
    chirpTimer = setTimeout(function () {
      if (A && ON && (amb.mode === "day" || amb.mode === "idle") && !amb.rain && root.document.visibilityState === "visible") chirp();
      schedule();
    }, 700 + Math.random() * 2600);
  }
  function applyAmb() {
    if (!A) return;
    var day = amb.mode === "day" || amb.mode === "idle";
    ramp(A.crowdG.gain, day ? 0.05 + 0.3 * Math.min(1, amb.crowd) : 0, 0.5);
    ramp(A.rainG.gain, day && amb.rain ? 0.11 : 0, 0.6);
    // сверчки звучат около трёх секунд при наступлении вечера и стихают сами
    var g = A.crickG.gain, now = A.ctx.currentTime;
    if (amb.mode === "evening" && amb.prev !== "evening") { g.cancelScheduledValues(now); g.setTargetAtTime(0.0028, now + 0.3, 0.5); g.setTargetAtTime(0, now + 3.2, 0.7); }
    else if (amb.mode !== "evening") { g.cancelScheduledValues(now); g.setTargetAtTime(0, now, 0.15); }
    amb.prev = amb.mode;
  }
  function bell(up) {
    var notes = up ? [784, 1047] : [1047, 784];
    notes.forEach(function (f, i) { tone("sine", f, f, 1.3, 0.13, i * 0.28); tone("sine", f * 2.76, f * 2.76, 0.7, 0.04, i * 0.28); tone("triangle", f * 1.5, f * 1.5, 0.9, 0.03, i * 0.28); });
  }
  var API = {
    unlock: function () { if (!init()) return; schedule(); },
    isOn: function () { return ON; },
    toggle: function () { ON = !ON; try { localStorage.setItem("zoo_sound", ON ? "1" : "0"); } catch (e) {} init(); if (A) ramp(A.out.gain, ON ? 0.8 : 0, 0.05); return ON; },
    ambience: function (a) { amb.mode = a.mode || "off"; amb.crowd = a.crowd || 0; amb.rain = !!a.rain; applyAmb(); },
    click: function () { tone("triangle", 720, 620, 0.045, 0.05); },
    pop: function () { tone("sine", 520, 820, 0.09, 0.07); },
    coin: function () { if (!A) return; var n = A.ctx.currentTime; if (n - lastCoin < 0.16) return; lastCoin = n; tone("sine", 1319, 1319, 0.22, 0.035); tone("sine", 1976, 1976, 0.3, 0.03, 0.06); },
    open: function () { bell(true); },
    close: function () { bell(false); },
    splash: function (when) { burst(1400, 0.7, 0.55, 0.22, when, 500); burst(3200, 1.2, 0.3, 0.1, (when || 0) + 0.05); },
    bark: function (when) { for (var i = 0; i < 3; i++) tone("sawtooth", 240, 150, 0.16, 0.11, (when || 0) + i * 0.24, ["bandpass", 760, 2.2]); },
    buzz: function () { tone("square", 130, 110, 0.22, 0.06, 0, ["lowpass", 500, 1]); },
    good: function () { [523, 659, 784].forEach(function (f, i) { tone("triangle", f, f, 0.22, 0.08, i * 0.09); }); },
    bad: function () { tone("triangle", 392, 392, 0.25, 0.08); tone("triangle", 311, 311, 0.4, 0.08, 0.2); },
    win: function () { [523, 659, 784, 1047, 784, 1047, 1319].forEach(function (f, i) { tone("triangle", f, f, 0.3, 0.1, i * 0.13); }); },
    animal: function (s) {
      if (s === "cats") { tone("sawtooth", 95, 70, 0.75, 0.14, 0, ["lowpass", 420, 3]); tone("sawtooth", 142, 100, 0.6, 0.06, 0.05, ["lowpass", 600, 2]); }
      else if (s === "birds") { for (var i = 0; i < 7; i++) chirp(i * 0.07 + Math.random() * 0.05); }
      else if (s === "yard") { if (!A || !ON) return; var c = A.ctx, t = c.currentTime, o = c.createOscillator(), v = c.createOscillator(), vg = c.createGain(), g = c.createGain(), fl = F("bandpass", 1150, 2.5);
        o.type = "sawtooth"; o.frequency.setValueAtTime(410, t); o.frequency.linearRampToValueAtTime(350, t + 0.55); v.frequency.value = 13; vg.gain.value = 26; v.connect(vg); vg.connect(o.frequency);
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.12, t + 0.04); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.6);
        o.connect(fl); fl.connect(g); g.connect(A.out); o.start(t); v.start(t); o.stop(t + 0.65); v.stop(t + 0.65); }
      else if (s === "tropic") { tone("sine", 480, 940, 0.2, 0.1); tone("sine", 940, 560, 0.22, 0.1, 0.2); }
      else if (s === "pool") { API.bark(0.1); API.splash(0.75); }
    }
  };
  root.ZooAudio = API;
})(typeof window !== "undefined" ? window : this);

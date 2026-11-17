// Звук эпизода «курьер дронов»: всё синтезируется в браузере, файлов нет.
//
// Переделано 14.11.2026 по замечанию: прежний звук пищал и жужжал. Правила этой версии:
// 1. Ни одного чистого тона в фоне. Винты и ветер - шум через фильтр, без пилы и квадрата.
// 2. Никакого непрерывного зуммера. Низкий заряд говорит один раз, двумя мягкими нотами.
// 3. События короткие и тихие: щелчок, глухой удар, тёплая нота с долгим спадом.
// 4. Общая громкость примерно вдвое ниже прежней; звук по умолчанию выключен.
(function (root) {
  "use strict";
  var A = null, ON = { sound: false };          // по умолчанию тихо: звук включает сам игрок
  try { if (JSON.parse(localStorage.getItem("drone_audio") || "{}").sound === true) ON.sound = true; } catch (e) {}
  function save() { try { localStorage.setItem("drone_audio", JSON.stringify(ON)); } catch (e) {} }

  function noiseBuffer(ctx, sec, brown) {
    var n = Math.floor(ctx.sampleRate * sec), b = ctx.createBuffer(1, n, ctx.sampleRate), d = b.getChannelData(0), last = 0;
    for (var i = 0; i < n; i++) {
      var w = Math.random() * 2 - 1;
      if (brown) { last = (last + 0.015 * w) / 1.015; d[i] = last * 3.2; } else d[i] = w;
    }
    return b;
  }
  function loopNoise(ctx, buf) { var s = ctx.createBufferSource(); s.buffer = buf; s.loop = true; s.start(); return s; }
  function gainNode(ctx, v, to) { var g = ctx.createGain(); g.gain.value = v; if (to) g.connect(to); return g; }
  function filt(ctx, type, f, q, to) { var x = ctx.createBiquadFilter(); x.type = type; x.frequency.value = f; if (q) x.Q.value = q; if (to) x.connect(to); return x; }
  function set(p, v, t) { if (A) p.setTargetAtTime(v, A.ctx.currentTime, t || 0.25); }

  function init() {
    if (A) { if (A.ctx.state === "suspended") A.ctx.resume(); return A; }
    var AC = root.AudioContext || root.webkitAudioContext; if (!AC) return null;
    var ctx = new AC(), out = gainNode(ctx, 0.5, ctx.destination);   // общий уровень вдвое ниже прежнего
    var sfx = gainNode(ctx, ON.sound ? 1 : 0, out);
    var white = noiseBuffer(ctx, 2.5, false), brown = noiseBuffer(ctx, 4, true);
    A = { ctx: ctx, sfx: sfx, white: white, lowSaid: false };

    // Винты: только воздух. Бурый шум через низкий фильтр, срез идёт за путевой скоростью,
    // и медленное покачивание громкости вместо тона - так слышно работу, а не сигнал.
    A.rotG = gainNode(ctx, 0, sfx);
    A.rotF = filt(ctx, "lowpass", 260, 0.9, A.rotG);
    loopNoise(ctx, brown).connect(A.rotF);
    A.rotW = gainNode(ctx, 0.3);                       // глубина покачивания
    A.rotL = ctx.createOscillator(); A.rotL.type = "sine"; A.rotL.frequency.value = 7.5;
    A.rotL.connect(A.rotW); A.rotW.connect(A.rotG.gain); A.rotL.start();

    // Ветер у склада: белый шум через низкий фильтр, без свиста полосы.
    A.windG = gainNode(ctx, 0, sfx);
    A.windF = filt(ctx, "lowpass", 600, 0.7, A.windG);
    loopNoise(ctx, white).connect(A.windF);
    return A;
  }

  // Тёплая нота: синус плюс тихая квинта сверху, мягкая атака и долгий спад.
  function note(hz, t0, len, vol) {
    var ctx = A.ctx, t = ctx.currentTime + (t0 || 0);
    var g = gainNode(ctx, 0, A.sfx), f = filt(ctx, "lowpass", hz * 2.6, 0.6, g);
    var o1 = ctx.createOscillator(), o2 = ctx.createOscillator();
    o1.type = "sine"; o2.type = "sine";
    o1.frequency.value = hz; o2.frequency.value = hz * 1.5;
    var g2 = gainNode(ctx, 0.25, f);
    o1.connect(f); o2.connect(g2);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(vol, t + 0.05);
    g.gain.exponentialRampToValueAtTime(0.0004, t + len);
    o1.start(t); o2.start(t); o1.stop(t + len + 0.05); o2.stop(t + len + 0.05);
  }

  // Глухой удар: шум через низкий фильтр с быстрым спадом, без звона.
  function thud(t0, hz, len, vol) {
    var ctx = A.ctx, t = ctx.currentTime + (t0 || 0);
    var g = gainNode(ctx, 0, A.sfx), f = filt(ctx, "lowpass", hz, 1.2, g);
    var s = ctx.createBufferSource(); s.buffer = A.white; s.connect(f);
    f.frequency.setValueAtTime(hz, t);
    f.frequency.exponentialRampToValueAtTime(Math.max(60, hz * 0.4), t + len);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(vol, t + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0004, t + len);
    s.start(t); s.stop(t + len + 0.02);
  }

  // Щелчок клавиши: очень короткий шум через полосу, тихо.
  function click(vol, hz) {
    var ctx = A.ctx, t = ctx.currentTime;
    var s = ctx.createBufferSource(); s.buffer = A.white;
    var f = filt(ctx, "bandpass", hz || 1400, 1.1), g = gainNode(ctx, 0, A.sfx);
    s.connect(f); f.connect(g);
    g.gain.setValueAtTime(vol || 0.18, t);
    g.gain.exponentialRampToValueAtTime(0.0004, t + 0.03);
    s.start(t); s.stop(t + 0.05);
  }

  var EV = {
    key: function () { click(0.16, 1500); },
    lever: function () { click(0.2, 1100); },
    send: function () { note(262, 0, 0.5, 0.07); note(392, 0.07, 0.7, 0.05); },
    reject: function () { thud(0, 320, 0.2, 0.1); note(175, 0.04, 0.5, 0.05); },
    order: function () { note(440, 0, 0.5, 0.05); },
    takeoff: function () {
      var ctx = A.ctx, t = ctx.currentTime, s = ctx.createBufferSource(); s.buffer = A.white;
      var g = gainNode(ctx, 0, A.sfx), f = filt(ctx, "lowpass", 200, 0.8, g);
      s.connect(f);
      f.frequency.setValueAtTime(180, t); f.frequency.exponentialRampToValueAtTime(700, t + 0.6);
      g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(0.08, t + 0.25);
      g.gain.exponentialRampToValueAtTime(0.0004, t + 0.9);
      s.start(t); s.stop(t + 0.95);
    },
    deliver: function () { note(392, 0, 0.5, 0.07); note(523, 0.1, 0.8, 0.05); },
    pad: function () { thud(0, 260, 0.14, 0.06); note(294, 0.05, 0.4, 0.04); },
    dock: function () { thud(0, 220, 0.16, 0.06); },
    low: function () { note(330, 0, 0.35, 0.05); note(330, 0.3, 0.45, 0.045); },   // один раз, не зуммер
    forced: function () { thud(0, 180, 0.4, 0.13); note(131, 0.08, 0.9, 0.06); },
    lost: function () { thud(0, 140, 0.6, 0.14); note(98, 0.1, 1.4, 0.07); note(65, 0.5, 1.6, 0.05); },
    done: function () { note(262, 0, 0.9, 0.06); note(392, 0.16, 1.1, 0.05); note(523, 0.32, 1.4, 0.04); }
  };

  function event(name) {
    if (!ON.sound) return;
    if (!init()) return;
    if (EV[name]) EV[name]();
  }

  // S: {air: дронов в воздухе, gs: средняя путевая, wind: м/с у склада, low: заряд ниже 20 %, run: смена идёт}
  function update(S) {
    if (!ON.sound || !A) return;
    var air = S.air || 0, gs = S.gs || 0;
    set(A.rotG.gain, air ? Math.min(0.075, 0.035 * air) : 0, 0.35);
    A.rotF.frequency.setTargetAtTime(190 + 7 * gs, A.ctx.currentTime, 0.5);
    A.rotL.frequency.setTargetAtTime(6.5 + 0.25 * gs, A.ctx.currentTime, 0.5);
    var w = S.wind || 0;
    set(A.windG.gain, Math.min(0.05, 0.0035 * w * w / 4), 0.6);
    A.windF.frequency.setTargetAtTime(420 + 22 * w, A.ctx.currentTime, 0.8);
    // низкий заряд: сказать один раз и замолчать, пока заряд не поднимется
    if (S.low && S.run && !A.lowSaid) { A.lowSaid = true; EV.low(); }
    if (!S.low) A.lowSaid = false;
  }

  function stop() { if (A) { set(A.rotG.gain, 0, 0.2); set(A.windG.gain, 0, 0.2); A.lowSaid = false; } }

  function toggle() {
    ON.sound = !ON.sound; save();
    if (ON.sound) { init(); if (A) set(A.sfx.gain, 1, 0.05); event("key"); }
    else if (A) { set(A.sfx.gain, 0, 0.05); stop(); }
    return ON.sound;
  }

  var tapped = false;   // до настоящего касания vibrate ругается в консоль, поэтому ждём касания
  try {
    root.addEventListener("pointerdown", function (e) { if (e.pointerType === "touch" || e.pointerType === "pen") tapped = true; },
      { capture: true });
  } catch (e) {}
  function buzz(ms) {
    try {
      // vibrate работает только после настоящего касания, поэтому на мыши его не зовём совсем
      var live = navigator.userActivation ? navigator.userActivation.hasBeenActive : tapped;
      if (live && tapped && navigator.maxTouchPoints > 0 && navigator.vibrate) navigator.vibrate(ms || 8);
    } catch (e) {}
  }

  root.DroneAudio = { init: init, update: update, event: event, stop: stop, toggle: toggle, buzz: buzz,
                      on: function () { return ON.sound; } };
})(this);

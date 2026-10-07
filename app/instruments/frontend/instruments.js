/* AeroSentinel instruments: engine status panel.
 *
 * Motion rule: the panel only animates when the engine (or its data) changes. Readouts tween
 * from the previous engine's values to the new ones so the difference is visible; the first
 * render fades in once. Under prefers-reduced-motion every change is applied instantly.
 */
(function () {
  const $ = (id) => document.getElementById(id);
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const DUR = REDUCED ? 0 : 0.45;
  const EASE = 'power2.out';
  const post = (type, extra) => window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type }, extra || {}), '*');

  let prev = null;          // last rendered payload
  const shown = { rul: 0 }; // tweened numeric readout

  function scaleX(v, cap) { return (Math.max(0, Math.min(cap, v)) / cap) * $('scale').clientWidth; }

  function buildScale(d) {
    const track = $('track'), scale = $('scale');
    track.innerHTML = '';
    scale.querySelectorAll('.tick').forEach((t) => t.remove());
    const edges = [0].concat(d.limits.map((l) => l.at).reverse());
    // Zones from failure (left) towards healthy; the healthy span stays untinted.
    let from = 0;
    d.limits.forEach((l) => {
      const z = document.createElement('div');
      z.className = 'zone';
      z.style.left = `${(from / d.cap) * 100}%`;
      z.style.width = `${((l.at - from) / d.cap) * 100}%`;
      z.style.background = l.color;
      z.title = `${l.label}: RUL ${l.at} or less`;
      track.appendChild(z);
      from = l.at;
    });
    edges.concat([d.cap]).forEach((v, i, all) => {
      const t = document.createElement('div');
      t.className = 'tick' + (i === 0 ? ' first' : i === all.length - 1 ? ' last' : '');
      t.style.left = `${(v / d.cap) * 100}%`;
      t.innerHTML = `<em>${v}</em>`;
      scale.appendChild(t);
    });
  }

  function place(d, animate) {
    if (d.rul == null) {
      gsap.set(['#range', '#marker'], { autoAlpha: 0 });
      return;
    }
    const lo = scaleX(d.low, d.cap), hi = scaleX(d.high, d.cap), w = $('scale').clientWidth || 1;
    const vars = { duration: animate ? DUR : 0, ease: EASE, overwrite: true };
    gsap.to('#range', Object.assign({ x: lo, scaleX: Math.max(0.004, (hi - lo) / w), autoAlpha: 0.45 }, vars));
    gsap.to('#marker', Object.assign({ x: scaleX(d.rul, d.cap), autoAlpha: 1 }, vars));
  }

  function text(id, value) { $(id).textContent = value == null ? '' : value; }

  function render(d) {
    const first = prev === null;
    const animate = !first && !REDUCED;
    const panel = $('panel');
    if (first || prev.cap !== d.cap) buildScale(d);

    // Condition: colour change is the state transition; the word swaps with a short crossfade.
    gsap.to(panel, { '--c': d.state.color, duration: animate ? DUR : 0, ease: EASE });
    if (first || prev.state.key !== d.state.key) {
      text('state', d.state.label);
      if (animate) gsap.fromTo('#state-row', { autoAlpha: 0, y: 4 }, { autoAlpha: 1, y: 0, duration: 0.24, ease: EASE });
    }
    text('unit', `Engine ${String(d.unit).padStart(3, '0')}, cycle ${d.cycle}`);
    text('reason', d.reason);

    // RUL readout tweens numerically from the previous engine's value.
    if (d.rul == null) {
      text('rul', 'n/a');
      text('rng', '');
      text('window', '');
      $('scale').setAttribute('aria-label', 'RUL unavailable');
    } else {
      gsap.to(shown, {
        rul: d.rul, duration: animate ? DUR : 0, ease: EASE, overwrite: true,
        onUpdate: () => text('rul', Math.round(shown.rul)),
      });
      text('rng', `80% range ${Math.round(d.low)} to ${Math.round(d.high)}`);
      text('window', `end of life, cycle ${d.cycle + Math.round(d.low)} to ${d.cycle + Math.round(d.high)}`);
      $('scale').setAttribute('aria-label',
        `Predicted RUL ${Math.round(d.rul)} cycles, 80 percent range ${Math.round(d.low)} to ${Math.round(d.high)} on a 0 to ${d.cap} cycle scale`);
    }
    place(d, animate);

    // Confidence
    text('conf', d.confidence);
    $('conf').className = 'conf' + (d.confidence === 'Low' || d.confidence === 'Unknown' ? ' muted' : '');
    if (d.band) {
      $('band').style.setProperty('--bandc', d.band.color);
      $('band').innerHTML = `Band <b></b>${d.probability != null ? `, ${Math.round(d.probability * 100)}% probability` : ''}`;
      $('band').querySelector('b').textContent = d.band.label;
    } else {
      $('band').textContent = 'Risk band unavailable';
    }
    $('flags').innerHTML = '';
    d.flags.forEach((f) => { const s = document.createElement('span'); s.textContent = f; $('flags').appendChild(s); });

    // Suggested action
    if (d.action) { text('act', d.action.action); text('why', d.action.why); }
    $('act-row').style.display = d.action ? '' : 'none';
    if (animate && (!prev.action || !d.action || prev.action.action !== (d.action && d.action.action))) {
      gsap.fromTo('#act-row b, #act-row .w', { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.24, ease: EASE });
    }

    if (first) gsap.to(panel, { autoAlpha: 1, duration: REDUCED ? 0 : 0.24, ease: EASE });
    prev = d;
    post('streamlit:setFrameHeight', { height: Math.ceil(panel.getBoundingClientRect().height) + 2 });
  }

  window.addEventListener('message', (e) => {
    const m = e.data;
    if (!m || m.type !== 'streamlit:render') return;
    const args = m.args || {};
    if (args.kind === 'engine_status' && args.data) {
      const key = JSON.stringify(args.data);
      if (key !== render.lastKey) { render.lastKey = key; render(args.data); }
    }
  });
  new ResizeObserver(() => {
    if (prev) { place(prev, false); post('streamlit:setFrameHeight', { height: Math.ceil($('panel').getBoundingClientRect().height) + 2 }); }
  }).observe(document.body);
  post('streamlit:componentReady', { apiVersion: 1 });
})();

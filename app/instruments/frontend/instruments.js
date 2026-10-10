/* AeroSentinel instruments: unit status panel and component schematics (gas path, cell, bearing).
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
    if (first) panel.style.display = '';  // shown before measuring the scale
    if (first || prev.cap !== d.cap) buildScale(d);

    // Condition: colour change is the state transition; the word swaps with a short crossfade.
    gsap.to(panel, { '--c': d.state.color, duration: animate ? DUR : 0, ease: EASE });
    if (first || prev.state.key !== d.state.key) {
      text('state', d.state.label);
      if (animate) gsap.fromTo('#state-row', { autoAlpha: 0, y: 4 }, { autoAlpha: 1, y: 0, duration: 0.24, ease: EASE });
    }
    const tt = (d.time_title || 'Cycle').toLowerCase();
    text('unit', `${d.label || `Engine ${String(d.unit).padStart(3, '0')}`}, ${tt} ${d.cycle}`);
    text('life-unit', d.life_unit || 'cycles');
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
      text('window', `end of life, ${tt} ${d.cycle + Math.round(d.low)} to ${d.cycle + Math.round(d.high)}`);
      $('scale').setAttribute('aria-label',
        `Predicted RUL ${Math.round(d.rul)} ${d.life_unit || 'cycles'}, 80 percent range ${Math.round(d.low)} to ${Math.round(d.high)} on a 0 to ${d.cap} scale`);
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

  /* ---------------------------------------------------------------- component schematics
   * An engineering line drawing of the component, upper half above its centre line. Each part
   * is shaded by the strongest drift among its sensors.
   *  turbofan: two-spool gas path, inlet on the left, C-MAPSS stations 2, 24, 30, 50
   *  battery:  cylindrical cell, negative end on the left, positive cap on the right
   *  bearing:  ball bearing in its housing, drive end on the left
   * Motion: part colours tween when the unit changes; flow traces drift slowly and stop under
   * prefers-reduced-motion.
   */
  const NS = 'http://www.w3.org/2000/svg';
  const NEUTRAL = { fill: '#1b1f24', stroke: '#353b43' };
  const circle = (cx, cy, r, n = 20) => Array.from({ length: n }, (_, i) => {
    const a = (i / n) * Math.PI * 2; return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`;
  }).join(' ');
  const SCHEMATICS = {
    turbofan: {
      parts: {
        byp: [{ pts: '132,52 836,60 836,84 132,88', label: 'BYPASS', lx: 470, ly: 75 }],
        fan: [{ pts: '66,34 112,34 122,204 58,204', label: 'FAN', lx: 90, ly: 128 }],
        lpc: [{ pts: '144,100 252,106 252,204 144,204', label: 'LPC', lx: 198, ly: 160 }],
        hpc: [{ pts: '264,108 444,126 444,204 264,204', label: 'HPC', lx: 354, ly: 168 }],
        comb: [{ pts: '456,120 546,120 546,204 456,204', label: 'CC', lx: 501, ly: 168 }],
        hpt: [{ pts: '558,122 616,116 616,204 558,204', label: 'HPT', lx: 587, ly: 168 }],
        lpt: [{ pts: '628,114 764,94 764,204 628,204', label: 'LPT', lx: 696, ly: 160 }],
        noz: [{ pts: '776,94 910,118 910,204 776,204', label: 'NOZ', lx: 843, ly: 164 }],
      },
      stations: [[56, 'stn 2'], [258, 'stn 24'], [450, 'stn 30'], [770, 'stn 50']],
      decor(svg) {
        el('path', { class: 'shell', d: 'M 40 40 Q 60 28 132 46 L 836 56 L 852 60' }, svg);
        el('path', { class: 'shell', d: 'M 132 92 L 770 90' }, svg);
        el('line', { x1: 96, y1: 210, x2: 700, y2: 210, class: 'shaft' }, svg);
        el('line', { x1: 300, y1: 206, x2: 590, y2: 206, class: 'shaft' }, svg);
        el('text', { x: 712, y: 213, class: 'shaft-l' }, svg).textContent = 'LP spool  Nf';
        el('text', { x: 300, y: 200, class: 'shaft-l' }, svg).textContent = 'HP spool  Nc';
      },
      flows: [['flow byp', 'M 30 70 L 860 72', 4.4], ['flow core', 'M 30 150 L 140 150 L 260 158 L 450 166 L 560 168 L 770 160 L 930 162', 3.2]],
    },
    battery: {
      parts: {
        can: [{ pts: '70,36 890,36 890,50 84,50 84,214 70,214', label: 'CAN', lx: 300, ly: 46 }],
        electrolyte: [{ pts: '92,56 882,56 882,62 92,62', label: '', lx: 0, ly: 0 },
                      { pts: '856,62 882,62 882,206 856,206', label: 'EL', lx: 869, ly: 140 }],
        stack: [{ pts: '100,68 850,68 850,122 100,122', label: 'ELECTRODE STACK', lx: 475, ly: 98 },
                { pts: '100,140 850,140 850,206 100,206', label: '', lx: 0, ly: 0 }],
        interface: [{ pts: '100,124 850,124 850,138 100,138', label: 'SEPARATOR AND SEI', lx: 475, ly: 134 }],
        terminal: [{ pts: '890,150 928,150 928,214 890,214', label: '+', lx: 909, ly: 186 },
                   { pts: '44,170 70,170 70,214 44,214', label: '-', lx: 57, ly: 196 }],
      },
      stations: [[70, 'negative'], [475, 'mid-stack'], [890, 'positive']],
      decor(svg) {
        for (let y = 74; y < 120; y += 9) el('line', { x1: 104, y1: y, x2: 846, y2: y, class: 'layer' }, svg);
        for (let y = 146; y < 204; y += 9) el('line', { x1: 104, y1: y, x2: 846, y2: y, class: 'layer' }, svg);
        el('line', { x1: 100, y1: 211, x2: 850, y2: 211, class: 'shaft' }, svg);
        el('text', { x: 104, y: 226, class: 'shaft-l' }, svg).textContent = 'mandrel';
        el('line', { x1: 850, y1: 96, x2: 900, y2: 152, class: 'tab' }, svg);
        el('line', { x1: 100, y1: 186, x2: 70, y2: 196, class: 'tab' }, svg);
      },
      flows: [['flow core', 'M 120 96 L 846 96 L 900 156', 5.0]],
    },
    bearing: {
      parts: {
        shaft: [{ pts: '40,180 920,180 920,214 40,214', label: 'SHAFT', lx: 160, ly: 202 }],
        races: [{ pts: '380,150 580,150 580,178 380,178', label: 'INNER RACE', lx: 480, ly: 170 },
                { pts: '380,62 580,62 580,90 380,90', label: 'OUTER RACE', lx: 480, ly: 80 }],
        rolling: [{ pts: circle(480, 120, 27), label: 'BALL', lx: 480, ly: 124 }],
        housing: [{ pts: '300,28 660,28 660,60 580,60 580,62 380,62 380,60 300,60', label: 'HOUSING', lx: 340, ly: 48 },
                  { pts: '600,6 644,6 644,28 600,28', label: 'acc V', lx: 622, ly: 21 }],
      },
      stations: [[120, 'drive end'], [480, 'bearing'], [840, 'free end']],
      decor(svg) {
        el('line', { x1: 444, y1: 120, x2: 516, y2: 120, class: 'layer' }, svg);
        el('text', { x: 600, y: 124, class: 'shaft-l' }, svg).textContent = 'cage';
        el('path', { class: 'load', d: 'M 700 8 L 700 25 M 693 18 L 700 26 L 707 18' }, svg);
        el('text', { x: 712, y: 21, class: 'shaft-l' }, svg).textContent = 'radial load';
      },
      flows: [['flow core', 'M 60 196 L 920 196', 2.4]],
    },
  };
  let gpPrev = null, gpComponent = null;
  let flowTweens = [];

  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([k, v]) => n.setAttribute(k, v));
    if (parent) parent.appendChild(n);
    return n;
  }

  function buildSchematic(d) {
    const sc = SCHEMATICS[d.component] || SCHEMATICS.turbofan;
    flowTweens.forEach((t) => t.kill()); flowTweens = [];
    $('gp-svg').innerHTML = '';
    const svg = el('svg', { viewBox: '0 0 960 236', role: 'img', 'aria-label': d.title || 'Component schematic' });
    el('line', { x1: 20, y1: 214, x2: 940, y2: 214, class: 'axis' }, svg);
    sc.stations.forEach(([x, name]) => {
      const g = el('g', { class: 'stn' }, svg);
      el('line', { x1: x, y1: 22, x2: x, y2: 214 }, g);
      el('text', { x: x, y: 16, 'text-anchor': 'middle' }, g).textContent = name;
    });
    sc.decor(svg);
    Object.entries(sc.parts).forEach(([key, polys]) => polys.forEach((g, i) => {
      const poly = el('polygon', { points: g.pts, class: `mod p-${key}`, fill: NEUTRAL.fill, stroke: NEUTRAL.stroke }, svg);
      poly.dataset.key = key;
      if (g.label) el('text', { x: g.lx, y: g.ly, 'text-anchor': 'middle', class: 'lbl-m' }, svg).textContent = g.label;
    }));
    sc.flows.forEach(([cls, path]) => el('path', { class: cls, d: path }, svg));
    $('gp-svg').appendChild(svg);

    const order = d.modules.map((m) => m.key);
    $('gp-chips').style.gridTemplateColumns = `repeat(${order.length}, minmax(0, 1fr))`;
    $('gp-chips').innerHTML = order.map((k) => `<div class="chip" id="c-${k}"><div class="n"><i></i><span></span></div>`
      + '<div class="v"></div><div class="s"></div></div>').join('');

    const tip = $('gp-tip');
    svg.addEventListener('mousemove', (e) => {
      const key = e.target && e.target.dataset ? e.target.dataset.key : null;
      const m = key && gpPrev ? gpPrev.modules.find((x) => x.key === key) : null;
      if (!m) { tip.style.display = 'none'; return; }
      tip.innerHTML = `<b></b>${m.sensors.length ? '' : '<div>no modelled sensor</div>'}`;
      tip.querySelector('b').textContent = m.name;
      m.sensors.forEach((s) => {
        const row = document.createElement('div');
        row.textContent = `${s.code.padEnd(6)} ${s.drift >= 0 ? '+' : ''}${s.drift.toFixed(1)} sigma  ${s.status}`;
        tip.appendChild(row);
      });
      tip.style.display = 'block';
      tip.style.left = `${Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8)}px`;
      tip.style.top = `${e.clientY + 14}px`;
    });
    svg.addEventListener('mouseleave', () => { tip.style.display = 'none'; });

    if (!REDUCED) {
      sc.flows.forEach(([cls, , secs]) => {
        flowTweens.push(gsap.to(`#gp .${cls.split(' ').join('.')}`, { strokeDashoffset: -64, duration: secs, ease: 'none', repeat: -1 }));
      });
    }
    gpComponent = d.component;
  }
  document.addEventListener('visibilitychange', () => flowTweens.forEach((t) => (document.hidden ? t.pause() : t.resume())));

  function renderGasPath(d) {
    const first = gpPrev === null;
    const box = $('gp');
    if (first) box.style.display = 'block';
    const rebuilt = first || gpComponent !== d.component;
    if (rebuilt) { buildSchematic(d); gpPrev = null; }
    const dur = rebuilt || REDUCED ? 0 : DUR;
    text('gp-title', d.title || 'Gas path, inlet to exhaust');
    text('gp-unit', `${d.label || `Engine ${String(d.unit).padStart(3, '0')}`}, ${(d.time_title || 'cycle').toLowerCase()} ${d.cycle}`);

    const oc = $('gp-oc');
    oc.className = 'oc';
    if (d.condition) {
      const c = d.condition;
      oc.innerHTML = `<em>latest reading</em> ${c.text}` + (c.corrected ? '  <em>corrected to the reference condition</em>' : '');
      if (!c.known) { oc.className = 'oc warn'; oc.innerHTML += '  condition not trained'; }
    } else {
      oc.textContent = '';
    }

    d.modules.forEach((m) => {
      const polys = document.querySelectorAll(`#gp .p-${m.key}`);
      const has = m.sensors.length > 0;
      polys.forEach((poly) => {
        poly.classList.toggle('nodata', !has);
        gsap.to(poly, { attr: { fill: m.color || NEUTRAL.fill, stroke: m.color || NEUTRAL.stroke }, fillOpacity: m.color ? 0.22 : 1,
          duration: dur, ease: EASE, overwrite: true });
      });
      const chip = $(`c-${m.key}`);
      if (!chip) return;
      chip.style.setProperty('--cc', m.color || '');
      chip.querySelector('.n span').textContent = m.name;
      chip.querySelector('.v').textContent = has ? `${m.drift >= 0 ? '+' : ''}${m.drift.toFixed(1)} sigma` : 'not modelled';
      chip.querySelector('.s').textContent = has ? `${m.status}  ${m.sensors.map((s) => s.code).join(' ')}` : '';
      if (!rebuilt && !REDUCED && gpPrev) {
        const before = gpPrev.modules.find((x) => x.key === m.key);
        if (before && before.status !== m.status) gsap.fromTo(chip, { backgroundColor: 'rgba(120,169,255,.10)' }, { backgroundColor: 'rgba(0,0,0,0)', duration: 0.8 });
      }
    });

    if (first) gsap.to(box, { autoAlpha: 1, duration: REDUCED ? 0 : 0.24, ease: EASE });
    gpPrev = d;
    post('streamlit:setFrameHeight', { height: Math.ceil(box.getBoundingClientRect().height) + 2 });
  }

  window.addEventListener('message', (e) => {
    const m = e.data;
    if (!m || m.type !== 'streamlit:render') return;
    const args = m.args || {};
    if (!args.data) return;
    const key = JSON.stringify(args.data);
    if (key === render.lastKey) return;
    render.lastKey = key;
    if (args.kind === 'engine_status') render(args.data);
    else if (args.kind === 'gas_path') renderGasPath(args.data);
  });
  new ResizeObserver(() => {
    if (prev) { place(prev, false); post('streamlit:setFrameHeight', { height: Math.ceil($('panel').getBoundingClientRect().height) + 2 }); }
    if (gpPrev) post('streamlit:setFrameHeight', { height: Math.ceil($('gp').getBoundingClientRect().height) + 2 });
  }).observe(document.body);
  post('streamlit:componentReady', { apiVersion: 1 });
})();

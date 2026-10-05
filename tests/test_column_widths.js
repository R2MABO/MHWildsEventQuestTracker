const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(require('node:path').join(__dirname, '../web/app.js'), 'utf8');
const code = source.slice(source.indexOf('function setupColumnResizing()'), source.indexOf('\nsetupColumnResizing();'));
function browser(saved = null, initialBudget = 1655) {
  let budget = initialBudget;
  let resize;
  const properties = {};
  const handles = [];
  let reset;
  const panel = { classList: { toggle() {} }, style: { setProperty(k,v) { properties[k] = v; }, removeProperty(k) { delete properties[k]; } } };
  const names = ['name', 'rank', 'area', 'reward', 'progress', 'actions'];
  const defaults = [600, 120, 120, 500, 180, 135];
  const trackWidths = () => names.map((column, i) => parseFloat(properties[`--column-${column}`] || defaults[i]));
  const cells = Object.fromEntries(names.map((column, i) => [column, {
    textContent: column, closest() { return this; },
    getBoundingClientRect() { const widths = trackWidths(); const left = widths.slice(0, i).reduce((a,b) => a+b, 0) + i*10; return { left, right: left+widths[i], width: widths[i] }; },
  }]));
  const header = { querySelector(selector) {
    // Appending resize handles means the action spacer is no longer the last child.
    if (selector === ':scope > span:last-child') return handles.length ? null : actionSpacer;
    if (selector === ':scope > span[aria-hidden="true"]') return actionSpacer;
    return cells[selector.match(/"(\w+)"/)[1]];
  }, append(node) { handles.push(node); }, get clientWidth() { return budget + 50; }, getBoundingClientRect() { return { left: 0 }; } };
  const actionSpacer = { getBoundingClientRect() { return { left: trackWidths().slice(0,5).reduce((a,b) => a+b, 0) + 50 }; } };
  let stored = saved;
  const context = vm.createContext({
    window: { innerWidth: 1800 },
    getComputedStyle() { return { gridTemplateColumns: trackWidths().map(width => `${width}px`).join(' '), columnGap: '10px', paddingLeft: '0px', paddingRight: '0px', getPropertyValue(key) { return key === '--quest-thumb-size' ? '88px' : '13px'; } }; },
    localStorage: { getItem() { return stored; }, setItem(k,v) { stored = v; } },
    document: { querySelector(selector) { return selector === '.quest-panel' ? panel : selector === '.table-head' ? header : { append(node) { reset = node; } }; }, body: { classList: { add() {}, remove() {} } } },
    ResizeObserver: class { constructor(callback) { this.callback = callback; } observe() { resize = this.callback; this.callback(); } },
    toast() {},
    el(tag, attrs) { return { ...attrs, style: {}, events: {}, captured: null, addEventListener(k,v) { this.events[k] = v; }, setAttribute(k,v) { this[k] = v; }, setPointerCapture(id) { this.captured = id; }, hasPointerCapture(id) { return this.captured === id; }, releasePointerCapture() { this.captured = null; } }; },
  });
  vm.runInContext(code + '\nsetupColumnResizing();', context);
  return { properties, handles, resize(value) { budget = value; resize(); }, get stored() { return stored; }, get reset() { return reset; } };
}
test('first use keeps CSS defaults and rejects invalid saved widths', () => {
  assert.deepEqual(browser().properties, {});
  const b = browser(JSON.stringify({ rank: -1, area: '200', reward: 6000 }));
  assert.deepEqual(b.properties, {});
  assert.deepEqual(browser('broken').properties, {});
});
test('drag updates widths, clamps them, persists on release and restores on reload', () => {
  const b = browser();
  const h = b.handles[1];
  h.events.pointerdown({ button: 0, pointerId: 1, clientX: 100, preventDefault() {} });
  h.events.pointermove({ pointerId: 1, clientX: 160 });
  assert.equal(b.properties['--column-rank'], '180px');
  assert.equal(b.stored, null);
  h.events.pointerup({ pointerId: 1 });
  assert.equal(browser(b.stored).properties['--column-rank'], '180px');
  h.events.pointerdown({ button: 0, pointerId: 2, clientX: 0, preventDefault() {} });
  h.events.pointermove({ pointerId: 2, clientX: 10000 });
  assert.equal(b.properties['--column-rank'], '580px');
  h.events.pointercancel({ pointerId: 2 });
});
test('keyboard resizing and resets restore the original responsive layout', () => {
  const b = browser(JSON.stringify({ name: 600, rank: 180, area: 150, reward: 410, progress: 180 }));
  b.handles[2].events.keydown({ key: 'ArrowLeft', shiftKey: true, preventDefault() {} });
  assert.equal(b.properties['--column-area'], '130px');
  b.handles[1].events.dblclick();
  assert.deepEqual(b.properties, {});
  b.handles[0].events.keydown({ key: 'Home', preventDefault() {} });
  assert.deepEqual(b.properties, {});
  assert.deepEqual(browser(b.stored).properties, {});
});


test('boundaries consume space to the right, preserve minimums and keep the edit column fixed', () => {
  for (const [index, column] of ['name', 'rank', 'area', 'reward'].entries()) {
    const b = browser();
    const h = b.handles[index];
    const beforeLeft = parseFloat(h.style.left);
    h.events.pointerdown({ button: 0, pointerId: 1, clientX: 100, preventDefault() {} });
    h.events.pointermove({ pointerId: 1, clientX: 140 });
    assert.equal(parseFloat(h.style.left), beforeLeft + 40);
    assert.equal(Object.values(b.properties).reduce((sum, value) => sum + parseFloat(value), 0), 1655);
    h.events.pointermove({ pointerId: 1, clientX: 10000 });
    assert.equal(Object.values(b.properties).reduce((sum, value) => sum + parseFloat(value), 0), 1655);
    for (const [key, minimum] of Object.entries({ name: 180, rank: 80, area: 80, reward: 120, progress: 140 })) {
      assert.ok(parseFloat(b.properties[`--column-${key}`]) >= minimum);
    }
    h.events.pointerup({ pointerId: 1 });
  }
});
test('stored oversized layouts and smaller viewports fit inside the available width', () => {
  const b = browser(JSON.stringify({ name: 1000, rank: 1000, area: 1000, reward: 1000, progress: 1000 }));
  const total = () => Object.values(b.properties).reduce((sum, value) => sum + parseFloat(value), 0);
  assert.ok(Math.abs(total() - 1655) < 0.01);
  b.resize(900);
  assert.ok(Math.abs(total() - 900) < 0.01);
  b.resize(1600);
  assert.ok(Math.abs(total() - 1600) < 0.01);
});


test('progress boundary moves while image/edit right edge stays fixed', () => {
  const b = browser();
  const h = b.handles[4];
  const beforeLeft = parseFloat(h.style.left);
  h.events.pointerdown({ button: 0, pointerId: 1, clientX: 100, preventDefault() {} });
  h.events.pointermove({ pointerId: 1, clientX: 60 });
  assert.equal(b.properties['--column-progress'], '140px');
  assert.equal(b.properties['--column-actions'], '175px');
  assert.equal(b.properties['--column-reward'], '500px');
  assert.equal(parseFloat(h.style.left), beforeLeft - 40);
  assert.equal(Object.values(b.properties).reduce((sum,value) => sum + parseFloat(value), 0), 1655);
  h.events.pointermove({ pointerId: 1, clientX: 10000 });
  assert.equal(b.properties['--column-progress'], '180px');
  assert.equal(b.properties['--column-actions'], '135px');
  assert.equal(parseFloat(h.style.left), beforeLeft);
  h.events.pointerup({ pointerId: 1 });
  assert.equal(browser(b.stored).properties['--column-actions'], '135px');
});

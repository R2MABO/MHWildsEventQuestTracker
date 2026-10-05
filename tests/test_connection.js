const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const connectionCode = source.slice(source.indexOf('let csrf ='), source.indexOf('const catalogLabels ='));
const apiCode = source.slice(source.indexOf('async function api('), source.indexOf('\nfunction options('));

function browser(fetch) {
  const controls = [{ inert: false, value: 'Ungespeicherter Entwurf' }];
  const notice = {
    hidden: true, open: false,
    matches() { return this.open; },
    showPopover() { this.open = true; },
    hidePopover() { this.open = false; },
  };
  const streams = [];
  const intervals = [];
  class EventSource {
    constructor(url) { this.url = url; this.events = {}; streams.push(this); }
    addEventListener(name, callback) { this.events[name] = callback; }
    close() { this.closed = true; }
  }
  const context = vm.createContext({
    fetch, AbortController, EventSource, setTimeout, clearTimeout,
    setInterval(fn) { intervals.push(fn); },
    window: { addEventListener() {} },
    document: {
      querySelector() { return { content: 'old-token' }; },
      querySelectorAll() { return controls; },
      addEventListener() {},
    },
    $() { return notice; },
  });
  vm.runInContext(connectionCode + '\n' + apiCode, context);
  return { context, controls, notice, streams, intervals,
    check: () => vm.runInContext('checkConnection()', context),
    api: () => vm.runInContext("api('/api/progress', {id: 'quest'})", context),
  };
}

function response(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

test('broken event stream keeps reachable server editable without a warning', async () => {
  const app = browser(async () => response({ ok: true, token: 'old-token' }));
  await app.streams[0].events.error();
  assert.equal(app.notice.hidden, true);
  assert.equal(app.controls[0].inert, false);
  assert.equal(app.streams.length, 1); // No repeated reconnect loop.
});

test('server from before the update is recognized through the existing state route', async () => {
  const requests = [];
  const app = browser(async url => {
    requests.push(url);
    return url === '/api/health' ? response({ error: 'Not found' }, 404) : response({ quests: [] });
  });
  await app.streams[0].events.error();
  assert.deepEqual(requests, ['/api/health', '/api/state']);
  assert.equal(app.notice.hidden, true);
  assert.equal(app.controls[0].inert, false);
});

test('server outage blocks writes and restart unlocks the preserved draft with a fresh token', async () => {
  let running = false;
  let requests = 0;
  const app = browser(async () => {
    requests++;
    if (!running) throw new TypeError('Failed to fetch');
    return response({ ok: true, token: 'new-token' });
  });
  await app.check();
  assert.equal(app.notice.hidden, false);
  assert.equal(app.controls[0].inert, true);
  const beforeWrite = requests;
  await assert.rejects(app.api(), /Server nicht erreichbar/);
  assert.equal(requests, beforeWrite);
  running = true;
  await app.intervals[0]();
  assert.equal(app.notice.hidden, true);
  assert.equal(app.controls[0].inert, false);
  assert.equal(app.controls[0].value, 'Ungespeicherter Entwurf');
  assert.equal(app.streams.at(-1).url, '/api/session?token=new-token');
});

test('failed save detects an outage even before the next periodic check', async () => {
  const app = browser(async () => { throw new TypeError('Failed to fetch'); });
  await assert.rejects(app.api(), /Server nicht erreichbar/);
  assert.equal(app.notice.hidden, false);
  assert.equal(app.controls[0].inert, true);
});

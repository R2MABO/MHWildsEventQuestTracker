const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
function section(start, end) { return source.slice(source.indexOf(start), source.indexOf(end)); }

function browser(color) {
  const fields = {
    'entity-color': {}, 'entity-color-hex': {},
    'entity-name': { value: 'Ausrüstung' },
    'entity-color-default': { checked: false },
    'entity-color-preview': { replaceChildren(node) { this.node = node; } },
  };
  const context = vm.createContext({
    entityKind: 'reward_type',
    $(id) { return fields[id]; },
    recordByName(kind, name) { return { name, color }; },
    el(tag, attrs, children = []) {
      return { tag, ...attrs, children, properties: {}, classes: new Set(),
        style: { setProperty(key, value) { this[key] = value; } },
        classList: { add(value) { this.values.add(value); }, values: new Set() },
      };
    },
  });
  vm.runInContext([
    section('function defaultRewardColor(', '\nfunction toast('),
    section('function pill(', '\nfunction filteredQuests('),
    section('function tagChecks(', '\nfunction knownMonsters('),
    section('function updateColor(', '\nfunction renderEntityIcon('),
  ].join('\n'), context);
  return { context, fields };
}

test('category colors use readable text and old categories receive vivid defaults', () => {
  for (const [color, ink] of [['#FFFFFF', '#000000'], ['#000000', '#ffffff'], ['#FF0000', '#000000']]) {
    const { context } = browser(color);
    const node = vm.runInContext("pill('Ausrüstung')", context);
    assert.equal(node.style['--reward-color'], color);
    assert.equal(node.style['--reward-ink'], ink);
  }
  const { context } = browser(null);
  const node = vm.runInContext("pill('Ausrüstung')", context);
  assert.equal(node.class, 'pill equipment');
  assert.equal(node.style['--reward-color'], '#FFB938');
});

test('only reward checkboxes receive category colors', () => {
  const { context } = browser('#123456');
  for (const kind of ['reward_type', 'tag']) {
    const container = { replaceChildren(node) { this.node = node; } };
    context.container = container;
    vm.runInContext(`tagChecks(container, ['Ausrüstung'], new Set(['Ausrüstung']), () => {}, '${kind}')`, context);
    assert.equal(container.node.style['--reward-color'], kind === 'reward_type' ? '#123456' : undefined);
    assert.equal(container.node.children[0].checked, true);
  }
});

test('color editor previews the chosen color and can restore standard styling', () => {
  const { context, fields } = browser('#123456');
  vm.runInContext("updateColor('#abcdef')", context);
  assert.equal(fields['entity-color-hex'].value, '#ABCDEF');
  assert.equal(fields['entity-color-preview'].node.style['--reward-color'], '#abcdef');
  fields['entity-color-default'].checked = true;
  vm.runInContext("updateColor('#abcdef')", context);
  assert.equal(fields['entity-color-preview'].node.style['--reward-color'], '#FFB938');
  vm.runInContext("updateColor('invalid')", context);
  assert.equal(fields['entity-color-hex'].value, '#ABCDEF');
});

test('all seven standard categories have different colors in pills and filters', () => {
  const { context } = browser(null);
  const names = ['Ausrüstung', 'Materialien', 'Artian Material', 'Rüstkugeln', 'Dekorationen', 'Jägerrang XP', 'Kochzutaten'];
  const colors = names.map(name => {
    context.name = name;
    const pill = vm.runInContext('pill(name)', context);
    const container = { replaceChildren(node) { this.node = node; } };
    context.container = container;
    vm.runInContext("tagChecks(container, [name], new Set(), () => {}, 'reward_type')", context);
    assert.equal(container.node.style['--reward-color'], pill.style['--reward-color']);
    assert.match(pill.style['--reward-color'], /^#[0-9A-F]{6}$/);
    return pill.style['--reward-color'];
  });
  assert.equal(new Set(colors).size, names.length);
});

test('renamed categories keep their default through aliases and custom identities stay stable', () => {
  const { context } = browser(null);
  context.recordByName = () => ({ name: 'Neue Ausrüstung', aliases: ['Ausrüstung'] });
  assert.equal(vm.runInContext("defaultRewardColor('Neue Ausrüstung')", context), '#FFB938');
  context.recordByName = () => ({ id: 'stable-custom-id', name: 'Spezial', aliases: [] });
  const before = vm.runInContext("defaultRewardColor('Spezial')", context);
  context.recordByName = () => ({ id: 'stable-custom-id', name: 'Umbenannt', aliases: [] });
  assert.equal(vm.runInContext("defaultRewardColor('Umbenannt')", context), before);
  assert.match(before, /^#[0-9A-F]{6}$/);
});

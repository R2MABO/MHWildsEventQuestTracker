'use strict';

// Apply the saved theme before loading quest data; initialize controls when the DOM is ready.
(() => {
  const storageKey = 'wilds-quest-tracker.theme.v1';
  const presets = {
    current: { base: '#151a17', accent: '#d8b779', secondary: '#95b897' },
    dark: { base: '#11151e', accent: '#a7b9ff', secondary: '#65d6ba' },
    light: { base: '#f4f2eb', accent: '#8a551b', secondary: '#32705a' },
  };
  const names = { current: 'Wilds Original', dark: 'Dark', light: 'Light', custom: 'Eigene Farben' };
  const root = document.documentElement;
  const validColor = value => typeof value === 'string' && /^#[\da-f]{6}$/i.test(value);
  const rgb = hex => [1, 3, 5].map(start => parseInt(hex.slice(start, start + 2), 16));
  function mix(first, second, weight) {
    const target = rgb(second);
    return '#' + rgb(first).map((channel, index) => Math.round(channel * (1 - weight) + target[index] * weight).toString(16).padStart(2, '0')).join('');
  }
  function luminance(color) {
    return rgb(color).map(channel => {
      const value = channel / 255;
      return value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4;
    }).reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
  }
  function contrast(first, second) {
    const a = luminance(first), b = luminance(second);
    return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
  }
  function readable(color, background, minimum = 4.5) {
    if (contrast(color, background) >= minimum) return color;
    const end = contrast('#ffffff', background) > contrast('#101410', background) ? '#ffffff' : '#101410';
    for (let step = 1; step <= 100; step++) {
      const candidate = mix(color, end, step / 100);
      if (contrast(candidate, background) >= minimum) return candidate;
    }
    return end;
  }
  function normalize(value) {
    if (!value || !['base', 'accent', 'secondary'].every(key => validColor(value[key]))) return { ...presets.current, preset: 'current' };
    const theme = Object.fromEntries(['base', 'accent', 'secondary'].map(key => [key, value[key].toLowerCase()]));
    theme.preset = Object.keys(presets).find(name => Object.keys(theme).every(key => theme[key] === presets[name][key])) || 'custom';
    return theme;
  }
  function palette(theme) {
    const dark = luminance(theme.base) < .4;
    const ink = dark ? '#ffffff' : '#101410';
    const surface = mix(theme.base, ink, .035);
    const raised = mix(theme.base, ink, .075);
    // Text colors are checked against the brightest/darkest regular surface.
    const text = readable(mix(theme.base, ink, .92), raised);
    const muted = readable(mix(theme.base, ink, .59), raised);
    const accent = readable(theme.accent, raised);
    const secondary = readable(theme.secondary, raised);
    return {
      bg: theme.base, surface, raised, text, muted,
      line: mix(theme.base, ink, .18), gold: accent, green: secondary,
      'gold-dark': mix(theme.base, theme.accent, .1),
      danger: readable(dark ? '#e5a097' : '#a33030', raised),
      'input-bg': mix(theme.base, ink, .01), 'sidebar-bg': mix(theme.base, ink, .02),
      'surface-soft': mix(theme.base, ink, .025), hover: mix(theme.base, ink, .11),
      'strong-line': mix(theme.base, ink, .35), 'soft-line': mix(theme.base, ink, .14),
      'secondary-text': muted, 'accent-soft': mix(theme.base, theme.accent, .13),
      'accent-line': mix(theme.base, accent, .4), 'accent-text': accent,
      'accent-hover': readable(mix(accent, ink, .14), raised),
      'on-accent': contrast('#ffffff', accent) > contrast('#101410', accent) ? '#ffffff' : '#101410',
      'success-soft': mix(theme.base, theme.secondary, .14), 'success-line': mix(theme.base, secondary, .35),
      'success-text': secondary,
      'violet-soft': mix(theme.base, '#9878c5', .14), 'violet-line': mix(theme.base, '#9878c5', .35),
      'violet-text': readable('#bfb0d8', raised),
      'blue-soft': mix(theme.base, '#459eae', .14), 'blue-line': mix(theme.base, '#459eae', .35),
      'blue-text': readable('#9fbdc1', raised),
      'danger-soft': mix(theme.base, '#ba6055', .14), 'danger-line': mix(theme.base, '#ba6055', .35),
      'danger-text': readable('#e5a097', raised),
    };
  }
  const themeProperties = Object.keys(palette(normalize(null)));
  function apply(theme) {
    themeProperties.forEach(key => root.style.removeProperty(`--${key}`));
    if (theme.preset === 'current') root.style.removeProperty('color-scheme');
    else {
      Object.entries(palette(theme)).forEach(([key, value]) => root.style.setProperty(`--${key}`, value));
      root.style.colorScheme = luminance(theme.base) < .4 ? 'dark' : 'light';
    }
    root.dataset.theme = theme.preset;
  }
  let saved = normalize(null);
  try { saved = normalize(JSON.parse(localStorage.getItem(storageKey))); } catch { /* Storage may be disabled or contain invalid data. */ }
  apply(saved);

  document.addEventListener('DOMContentLoaded', () => {
    const get = id => document.getElementById(id);
    const dialog = get('theme-dialog');
    let draft = { ...saved };
    function sync() {
      ['base', 'accent', 'secondary'].forEach(key => {
        get(`theme-${key}`).value = draft[key];
        get(`theme-${key}-hex`).value = draft[key];
      });
      preview();
    }
    function preview() {
      draft = normalize(draft);
      apply(draft);
      get('theme-name').textContent = names[draft.preset];
      document.querySelectorAll('[data-theme-preset]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.themePreset === draft.preset)));
      const colors = palette(draft);
      get('theme-shades').replaceChildren(...['bg', 'surface', 'raised', 'line', 'gold', 'green'].map(key => {
        const swatch = document.createElement('span');
        const color = getComputedStyle(root).getPropertyValue(`--${key}`).trim() || colors[key];
        swatch.style.background = color;
        swatch.style.color = contrast('#ffffff', color) > contrast('#101410', color) ? '#ffffff' : '#101410';
        swatch.textContent = color.toUpperCase();
        swatch.title = `${key}: ${color}`;
        return swatch;
      }));
    }
    get('open-theme').addEventListener('click', () => {
      draft = { ...saved };
      get('theme-storage-error').hidden = true;
      sync();
      dialog.showModal();
    });
    document.querySelectorAll('[data-theme-preset]').forEach(button => button.addEventListener('click', () => {
      draft = normalize(presets[button.dataset.themePreset]);
      sync();
    }));
    ['base', 'accent', 'secondary'].forEach(key => {
      get(`theme-${key}`).addEventListener('input', event => {
        draft[key] = event.target.value;
        get(`theme-${key}-hex`).value = event.target.value;
        preview();
      });
      get(`theme-${key}-hex`).addEventListener('input', event => {
        if (!validColor(event.target.value)) return;
        draft[key] = event.target.value;
        get(`theme-${key}`).value = event.target.value;
        preview();
      });
    });
    get('theme-form').addEventListener('submit', event => {
      event.preventDefault();
      draft = normalize(draft);
      try { localStorage.setItem(storageKey, JSON.stringify(draft)); }
      catch {
        get('theme-storage-error').textContent = 'Das Theme konnte nicht gespeichert werden. Bitte erlaube lokalen Browserspeicher. Die Vorschau bleibt bis zum Abbrechen aktiv.';
        get('theme-storage-error').hidden = false;
        return;
      }
      saved = { ...draft };
      dialog.close();
    });
    ['theme-close', 'theme-cancel'].forEach(id => get(id).addEventListener('click', () => dialog.close()));
    // Includes Escape and programmatic closes; saved changes are already committed.
    dialog.addEventListener('close', () => apply(saved));
  });
})();

'use strict';

const $ = id => document.getElementById(id);
const icons = {
  book: '<path d="M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-3H4zM20 4h-4a3 3 0 0 0-3 3v14a4 4 0 0 1 4-3h3z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  flag: '<path d="M5 21V4m0 0c4-4 9 4 14 0v10c-5 4-10-4-14 0"/>',
  gem: '<path d="m3 9 4-5h10l4 5-9 12L3 9Zm0 0h18M7 4l5 17 5-17"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 14v6h16v-6"/>',
  download: '<path d="M12 3v13m-5-5 5 5 5-5M4 14v6h16v-6"/>',
  archive: '<path d="M4 8h16v13H4zM3 3h18v5H3zM9 12h6"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  edit: '<path d="m15 4 5 5-11 11-6 1 1-6L15 4Zm-2 2 5 5"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
  chevron: '<path d="m7 9 5 5 5-5"/>',
  left: '<path d="m15 5-7 7 7 7"/>',
  right: '<path d="m9 5 7 7-7 7"/>',
  hunt: '<path d="m12 3 8 9-8 9-8-9 8-9ZM8 8l8 8m0-8-8 8"/>',
};
function icon(name) {
  const span = document.createElement('span');
  span.className = 'icon';
  span.setAttribute('aria-hidden', 'true');
  span.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${icons[name] || icons.hunt}</svg>`;
  return span;
}
document.querySelectorAll('[data-icon]').forEach(node => {
  const rendered = icon(node.dataset.icon);
  rendered.className = `icon ${node.className}`.trim();
  node.replaceWith(rendered);
});
function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
    else if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key in node && !key.startsWith('aria-') && key !== 'list') node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) if (child != null) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return node;
}

let state = { quests: [], reward_types: [], monster_types: [], ranks: [], catalogs: {} };
const questSort = { column: null, direction: 1 };
let editing = null;
let draftImages = [];
let importPreview = null;
let imageSet = null;
let toastTimer;
const expanded = new Set();
const rewardFilter = new Set();
const filterIds = ['filter-status', 'filter-rank', 'filter-stars', 'filter-hr', 'filter-monster', 'filter-type', 'filter-area', 'filter-quest-type'];
let csrf = document.querySelector('meta[name="tracker-token"]').content;
let serverOnline = true;
let checkingConnection = false;
const offlineMessage = 'Server nicht erreichbar. Bearbeitung und Speichern sind gesperrt. Starte den Tracker erneut. Deine offenen Eingaben bleiben erhalten.';
const serverControls = '#editor .dialog-body, #entity-dialog .dialog-body, #merge-dialog .dialog-body, #import-dialog .dialog-body, #save-quest, #delete-quest, #entity-save, #merge-save, #commit-import, #new-quest, #create-menu, #import-button, #export-button, #backup-button, #catalog-add, .catalog-actions, .status-cell, .quest-edit';
function updateConnectionControls() {
  document.querySelectorAll(serverControls).forEach(node => { node.inert = !serverOnline; });
}
function setServerOnline(online) {
  serverOnline = online;
  updateConnectionControls();
  const notice = $('connection-notice');
  if (online) {
    if (notice.matches(':popover-open')) notice.hidePopover();
    notice.hidden = true;
  } else {
    notice.hidden = false;
    if (!notice.matches(':popover-open')) notice.showPopover();
  }
}
async function checkConnection() {
  if (checkingConnection) return;
  checkingConnection = true;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4000);
  try {
    const requestOptions = { signal: controller.signal, cache: 'no-store' };
    let response = await fetch('/api/health', requestOptions);
    let token = csrf;
    if (response.status === 404) {
      // A server started before an update may not have the health route yet.
      response = await fetch('/api/state', requestOptions);
      if (!response.ok || !Array.isArray((await response.json()).quests)) throw new Error('Ungültige Serverantwort');
    } else {
      if (!response.ok) throw new Error('Server nicht erreichbar');
      const health = await response.json();
      if (!health.ok || typeof health.token !== 'string') throw new Error('Ungültige Serverantwort');
      token = health.token;
    }
    const changed = csrf !== token;
    csrf = token;
    if (changed) connectBrowserSession();
    setServerOnline(true);
  } catch {
    setServerOnline(false);
  } finally {
    clearTimeout(timeout);
    checkingConnection = false;
  }
}
// A persistent connection also stays alive when background-tab timers are throttled.
let browserSession;
function connectBrowserSession() {
  browserSession?.close();
  browserSession = new EventSource(`/api/session?token=${encodeURIComponent(csrf)}`);
  browserSession.addEventListener('open', () => setServerOnline(true));
  browserSession.addEventListener('error', () => {
    // A failed event stream alone does not mean that saving is unavailable.
    return checkConnection();
  });
}
connectBrowserSession();
window.addEventListener('pagehide', () => browserSession.close());
window.addEventListener('pageshow', event => { if (event.persisted) connectBrowserSession(); });
window.addEventListener('focus', checkConnection);
document.addEventListener('visibilitychange', () => { if (!document.hidden) checkConnection(); });
setInterval(checkConnection, 3000);
const catalogLabels = { monster: 'Monster', state: 'Monsterzustand', rank: 'Rang', reward_type: 'Belohnungsart', area: 'Gebiet', quest_type: 'Questtyp' };
let entityEditing = null;
let entityKind = 'monster';
let entityIcon = null;
let entityCallback = null;
let mergeSource = null;
function records(kind) { return state.catalogs[kind] || []; }
function recordById(kind, id) { return records(kind).find(r => r.id === id); }
function recordByName(kind, name) { return records(kind).find(r => r.name === name || r.aliases?.includes(name)); }
function catalogOptions(select, kind, empty = null) {
  const old = select.value;
  select.replaceChildren();
  if (empty !== null) select.append(el('option', { value: '', text: empty }));
  records(kind).forEach(record => select.append(el('option', { value: record.id, text: record.is_none ? 'Normal / ohne Zustand' : record.name })));
  if ([...select.options].some(option => option.value === old)) select.value = old;
}
function monsterGlyph(monster, status = null) {
  const frame = el('span', { class: 'monster-glyph', title: `${monster?.name || 'Monster wählen'}${status && !status.is_none ? ` · ${status.name}` : ''}` }, monster?.icon ? [el('img', { src: `/images/${monster.icon}`, alt: monster.name, loading: 'lazy' })] : [icon('hunt')]);
  if (status?.color && !status.is_none) frame.style.border = `3px solid ${status.color}`;
  return frame;
}
function statePill(status) {
  if (!status || status.is_none) return null;
  const pill = el('span', { class: 'state-pill', text: status.name });
  pill.style.backgroundColor = status.color;
  const hex = status.color.slice(1);
  const brightness = (parseInt(hex.slice(0,2),16)*299 + parseInt(hex.slice(2,4),16)*587 + parseInt(hex.slice(4,6),16)*114)/1000;
  pill.style.color = brightness > 150 ? '#142017' : '#ffffff';
  return pill;
}
function defaultRewardColor(name, kind = 'reward_type') {
  const palette = {
    'Ausrüstung': '#FFB938',
    'Materialien': '#35C9EF',
    'Artian Material': '#F15BBA',
    'Rüstkugeln': '#FF7849',
    'Dekorationen': '#A78BFA',
    'Jägerrang XP': '#B8E64C',
    'Kochzutaten': '#36D6A0',
  };
  const record = recordByName(kind, name);
  const known = kind === 'reward_type' && [record?.name, ...(record?.aliases || []), name].find(value => Object.hasOwn(palette, value));
  if (known) return palette[known];
  // Custom categories get a repeatable vivid color based on their stable identity.
  const key = record?.id || name;
  let hash = 0;
  for (const character of key) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  const hue = hash % 360 / 60;
  const channel = offset => {
    const distance = (offset + hue) % 6;
    return Math.round(255 * (.95 - .65 * Math.max(0, Math.min(distance, 4 - distance, 1)))).toString(16).padStart(2, '0');
  };
  return `#${channel(5)}${channel(3)}${channel(1)}`.toUpperCase();
}
function rewardColors(node, color) {
  if (!/^#[0-9a-f]{6}$/i.test(color || '')) return;
  const channels = [1, 3, 5].map(start => {
    const value = parseInt(color.slice(start, start + 2), 16) / 255;
    return value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4;
  });
  const luminance = channels.reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
  node.style.setProperty('--reward-color', color);
  node.style.setProperty('--reward-ink', luminance > .179 ? '#000000' : '#ffffff');
  node.classList.add('custom-reward-color');
}

function toast(message, error = false) {
  clearTimeout(toastTimer);
  $('toast').textContent = message;
  $('toast').classList.toggle('error', error);
  $('toast').setAttribute('role', error ? 'alert' : 'status');
  $('toast').hidden = false;
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, error ? 9000 : 4500);
}
async function safely(fn) {
  try { return await fn(); } catch (error) { toast(error.message || 'Ein Fehler ist aufgetreten.', true); return null; }
}
async function busy(message, fn) {
  $('loading-message').textContent = message;
  $('loading-overlay').hidden = false;
  try { return await fn(); } finally { $('loading-overlay').hidden = true; }
}
async function api(path, data, binary = false) {
  if (data !== undefined && !serverOnline) throw new Error(offlineMessage);
  let response;
  try {
    response = await fetch(path, data === undefined ? {} : {
      method: 'POST',
      headers: { 'X-Tracker-Token': csrf, 'Content-Type': binary ? 'application/zip' : 'application/json' },
      body: binary ? data : JSON.stringify(data),
    });
  } catch {
    setServerOnline(false);
    throw new Error(offlineMessage);
  }
  const body = await response.json();
  if (!response.ok) {
    if (response.status === 403) checkConnection();
    throw new Error(body.error || 'Anfrage fehlgeschlagen.');
  }
  return body;
}

function options(select, values, first = null) {
  const old = select.value;
  select.replaceChildren();
  if (first) select.append(el('option', { value: '', text: first }));
  values.forEach(value => select.append(el('option', { value, text: String(value) })));
  if ([...select.options].some(o => o.value === old)) select.value = old;
}
function tagChecks(container, values, selected, onChange, kind = null) {
  container.replaceChildren(...values.map(value => {
    const checkbox = el('input', { type: 'checkbox', value, checked: selected.has(value), onchange: e => onChange(value, e.target.checked) });
    const label = el('label', { class: 'tag-check' }, [checkbox, el('span', { text: value })]);
    if (['reward_type', 'area'].includes(kind)) rewardColors(label, recordByName(kind, value)?.color || defaultRewardColor(value, kind));
    return label;
  }));
}
function knownMonsters() {
  return records('monster').map(r => r.name).sort((a, b) => a.localeCompare(b, 'de'));
}
async function loadState() {
  state = await api('/api/state');
  for (const value of rewardFilter) if (!state.reward_types.includes(value)) rewardFilter.delete(value);
  options($('filter-rank'), state.ranks, 'Alle Ränge');
  options($('filter-type'), state.monster_types, 'Alle Arten');
  options($('filter-stars'), [...new Set(state.quests.map(q => q.stars))].sort((a, b) => a - b), 'Alle');
  options($('filter-monster'), knownMonsters(), 'Alle Monster');
  options($('filter-area'), records('area').map(r=>r.name), 'Alle Gebiete');
  options($('filter-quest-type'), records('quest_type').map(r=>r.name), 'Alle Questtypen');
  tagChecks($('reward-filters'), state.reward_types, rewardFilter, (value, checked) => {
    if (checked) rewardFilter.add(value); else rewardFilter.delete(value);
    render();
  }, 'reward_type');
  refreshEditorCatalogs();
  if ($('catalog-dialog').open) renderCatalogs();
  render();
}
function refreshEditorCatalogs() {
  catalogOptions($('quest-rank'), 'rank');
  catalogOptions($('quest-area'), 'area', 'Keine Angabe');
  catalogOptions($('quest-type'), 'quest_type', 'Keine Angabe');
  for (const row of $('target-rows').children) {
    catalogOptions(row.querySelector('.target-kind'), 'state');
    row.querySelector('.target-monster').updatePreview?.();
  }
  for (const [container, kind] of [['editor-reward-types', 'reward_type']]) {
    const checked = new Set([...$(container).querySelectorAll('input:checked')].map(input=>input.value));
    tagChecks($(container), records(kind).map(r=>r.name), checked, ()=>{}, kind);
  }
}

function targetText(target) {
  return `${target.count > 1 ? `${target.count} × ` : ''}${target.type !== 'Normal' ? `${target.type} · ` : ''}${target.monster}`;
}
function rankText(q) { return `${q.stars} ★ · ${q.rank} · ${q.hr == null ? 'JR offen' : `JR ${q.hr}+`}`; }
function rewardText(q) { return q.rewards.map(r => `${r.name}${r.required ? ` (${r.required} benötigt)` : ''}`).join(', '); }
function targetsNode(q) {
  const node = el('div', { class: 'quest-targets' });
  q.targets.forEach((t, index) => {
    const monster = recordById('monster', t.monster_id) || recordByName('monster', t.monster);
    const status = recordById('state', t.type_id) || recordByName('state', t.type);
    node.append(el('span', { class: 'target-display' }, [monsterGlyph(monster, status), el('span', { class: 'target-info' }, [el('span', { class:'target-name', text: `${t.count > 1 ? `${t.count} × ` : ''}${t.monster}` })])]));
  });
  return node;
}
function pill(value, color = undefined, kind = 'reward_type') {
  let style = '';
  if (kind === 'reward_type') {
    if (value === 'Ausrüstung') style = ' equipment';
    else if (value === 'Dekorationen') style = ' deco';
    else if (value.includes('Material')) style = ' material';
  }
  const node = el('span', { class: `pill${style}`, text: value });
  rewardColors(node, (color === undefined ? recordByName(kind, value)?.color : color) || defaultRewardColor(value, kind));
  return node;
}
function filteredQuests() {
  const query = $('search').value.trim().toLocaleLowerCase('de');
  const status = $('filter-status').value;
  const rank = $('filter-rank').value;
  const stars = $('filter-stars').value;
  const hr = $('filter-hr').value;
  const monster = $('filter-monster').value;
  const kind = $('filter-type').value;
  const result = state.quests.filter(q => {
    const searchable = [q.name, ...q.targets.map(t => t.monster), ...q.rewards.map(r => r.name)].join(' ').toLocaleLowerCase('de');
    if (query && !searchable.includes(query)) return false;
    if (status === 'open' && q.progress.all_rewards) return false;
    if (status === 'uncleared' && q.progress.first_clear) return false;
    if (status === 'cleared' && !q.progress.first_clear) return false;
    if (status === 'complete' && !q.progress.all_rewards) return false;
    if (rank && q.rank !== rank) return false;
    if (stars && q.stars !== Number(stars)) return false;
    if (hr !== '' && q.hr != null && q.hr > Number(hr)) return false;
    if ((monster || kind) && !q.targets.some(t => (!monster || t.monster === monster) && (!kind || t.type === kind))) return false;
    if (rewardFilter.size && !q.reward_types.some(t => rewardFilter.has(t))) return false;
    if ($('filter-area').value && q.area !== $('filter-area').value) return false;
    if ($('filter-quest-type').value && q.quest_type !== $('filter-quest-type').value) return false;
    return true;
  });
  const compareText = (a, b) => a.localeCompare(b, 'de', { numeric: true, sensitivity: 'base' });
  const comparators = {
    name: (a, b) => compareText(a.name, b.name),
    rank: (a, b) => a.stars - b.stars || (a.hr ?? 0) - (b.hr ?? 0) || compareText(a.rank, b.rank),
    progress: (a, b) => Number(a.progress.all_rewards) - Number(b.progress.all_rewards) || Number(a.progress.first_clear) - Number(b.progress.first_clear),
  };
  if (['reward', 'area'].includes(questSort.column)) {
    const values = q => questSort.column === 'area' ? (q.area ? [q.area] : []) : q.reward_types;
    const tags = new Map(result.map(q => [q, [...values(q)].sort((a, b) => questSort.direction * compareText(a, b))]));
    result.sort((a, b) => {
      const aTags = tags.get(a), bTags = tags.get(b);
      // Untagged quests stay last; compare the highest-priority tag first.
      if (!aTags.length || !bTags.length) return Number(!aTags.length) - Number(!bTags.length);
      for (let index = 0; index < Math.min(aTags.length, bTags.length); index++) {
        const comparison = questSort.direction * compareText(aTags[index], bTags[index]);
        if (comparison) return comparison;
      }
      // A single tag precedes the same tag plus additional tags in either direction.
      return aTags.length - bTags.length;
    });
  } else if (questSort.column) {
    result.sort((a, b) => questSort.direction * comparators[questSort.column](a, b));
  }
  return result;
}
function renderSortHeaders() {
  document.querySelectorAll('[data-sort-column]').forEach(button => {
    const active = button.dataset.sortColumn === questSort.column;
    button.classList.toggle('is-sorted', active);
    button.querySelector('.sort-indicator').textContent = active ? (questSort.direction === 1 ? '↑' : '↓') : '↕';
    const label = button.querySelector('.sort-caption').textContent;
    const nextDirection = active && questSort.direction === 1 ? 'absteigend' : 'aufsteigend';
    button.setAttribute('aria-label', `${label}${active ? `, ${questSort.direction === 1 ? 'aufsteigend' : 'absteigend'} sortiert` : ''}. ${nextDirection} sortieren`);
    button.title = `${label}: ${nextDirection} sortieren`;
  });
}
function renderActiveFilters() {
  const pills = [];
  const add = (label, clear, color = null) => {
    const node = el('button', { type: 'button', class: 'active-pill', onclick: () => { clear(); render(); }, 'aria-label': `Filter entfernen: ${label}` }, [label, icon('close')]);
    rewardColors(node, color);
    pills.push(node);
  };
  filterIds.forEach(id => {
    const input = $(id);
    if (!input.value) return;
    const label = id === 'filter-hr' ? `JR bis ${input.value}` : input.selectedOptions[0].text;
    const kind = id === 'filter-area' ? 'area' : null;
    add(label, () => { input.value = ''; }, kind ? recordByName(kind, input.value)?.color || defaultRewardColor(input.value, kind) : null);
  });
  if ($('search').value.trim()) add(`Suche: ${$('search').value.trim()}`, () => { $('search').value = ''; });
  rewardFilter.forEach(value => add(value, () => {
    rewardFilter.delete(value);
    [...$('reward-filters').querySelectorAll('input')].find(i => i.value === value).checked = false;
  }, recordByName('reward_type', value)?.color || defaultRewardColor(value)));
  $('active-filters').replaceChildren(...pills);
  $('active-filters').hidden = !pills.length;
}
function updateExpandToggle() {
  const allExpanded = state.quests.length > 0 && state.quests.every(q => expanded.has(q.id));
  const button = $('toggle-all-quests');
  const label = allExpanded ? 'Alle Quests einklappen' : 'Alle Quests ausklappen';
  button.setAttribute('aria-expanded', String(allExpanded));
  button.setAttribute('aria-label', label);
  button.title = label;
  button.disabled = !state.quests.length;
}
function render() {
  renderSortHeaders();
  const total = state.quests.length;
  const cleared = state.quests.filter(q => q.progress.first_clear).length;
  const rewarded = state.quests.filter(q => q.progress.all_rewards).length;
  $('nav-count').textContent = total;
  $('stat-total').textContent = total;
  $('stat-clear').replaceChildren(String(cleared), el('span', { text: `/ ${total}` }));
  $('stat-rewards').replaceChildren(String(rewarded), el('span', { text: `/ ${total}` }));
  $('clear-bar').style.width = `${total ? cleared / total * 100 : 0}%`;
  $('rewards-bar').style.width = `${total ? rewarded / total * 100 : 0}%`;
  const quests = filteredQuests();
  $('result-count').textContent = `${quests.length} von ${total} Quests`;
  renderActiveFilters();
  $('quest-list').replaceChildren(...quests.map(questNode));
  updateExpandToggle();
  if (!quests.length) {
    $('quest-list').append(el('div', { class: 'empty-state' }, [icon('hunt'),
      el('h3', { text: total ? 'Keine passenden Quests' : 'Deine nächste Jagd beginnt hier' }),
      el('p', { text: total ? 'Passe deine Filter an oder suche nach einem anderen Begriff.' : 'Lege eine Quest an oder importiere eine Questliste als ZIP.' }),
      el('button', { class: 'button', onclick: total ? resetFilters : () => openEditor() }, [total ? 'Filter zurücksetzen' : 'Erste Quest anlegen'])]));
  }
  updateConnectionControls();
}
function questNode(q) {
  const hasImages = q.images.length > 0;
  const thumb = hasImages ? el('button', { class: 'quest-thumb' }, [el('img', { src: `/images/${q.images[0]}`, alt: `Belohnung: ${q.name}`, loading: 'lazy' })]) : null;
  if (hasImages) {
    thumb.title = 'Belohnungsbilder ansehen';
    thumb.setAttribute('aria-label', `Belohnungsbilder für ${q.name} ansehen`);
    thumb.addEventListener('click', () => showImage(q));
    if (q.images.length > 1) thumb.append(el('span', { class: 'image-count', text: q.images.length }));
  }
  const title = el('button', { class: 'quest-title', 'aria-expanded': String(expanded.has(q.id)), onclick: () => {
    if (expanded.has(q.id)) expanded.delete(q.id); else expanded.add(q.id);
    const isOpen = expanded.has(q.id);
    title.setAttribute('aria-expanded', String(isOpen));
    updateExpandToggle();
    if (isOpen) item.append(detailNode(q)); else item.querySelector('.quest-details')?.remove();
  } }, [q.name, icon('chevron')]);
  const metadata = el('div', { class: 'quest-metadata' });
  if (q.area) {
    const area = pill(q.area, undefined, 'area');
    area.classList.add('area-pill');
    area.title = `Gebiet: ${q.area}`;
    metadata.append(area);
  }
  const text = el('div', { class: 'quest-text' }, [title, targetsNode(q)]);
  const main = el('div', { class: 'quest-main' }, [text]);
  const rank = el('div', { class: 'quest-rank' }, [el('strong', { text: `${q.stars} ★` }), el('small', { text: q.rank }), el('small', { text: q.hr == null ? 'JR: keine Angabe' : `JR ${q.hr}+` })]);
  const rewardText = el('div', { class: 'quest-reward-text' }, [el('div', { class: 'reward-pills' }, q.reward_types.map(value => pill(value)))]);
  if (q.rewards.length) {
    const first = q.rewards[0];
    rewardText.append(el('div', { class: 'reward-name', text: first.name }), el('div', { class: 'reward-needed', text: `${first.required ? `${first.required} benötigt` : ''}${q.rewards.length > 1 ? ` · +${q.rewards.length - 1} weitere` : ''}` }));
  }
  const reward = el('div', { class: 'quest-reward' }, [rewardText]);
  const progress = el('div', { class: 'status-cell' }, [progressControl(q, 'first_clear', 'Erster Abschluss'), progressControl(q, 'all_rewards', 'Alle Belohnungen')]);
  const edit = el('button', { class: 'icon-button quest-edit', title: 'Quest bearbeiten', 'aria-label': `${q.name} bearbeiten`, onclick: () => openEditor(q) }, [icon('edit')]);
  const actions = el('div', { class: 'quest-actions' }, thumb ? [thumb, edit] : [edit]);
  const item = el('article', { class: `quest-item${q.progress.all_rewards ? ' completed' : ''}` }, [el('div', { class: 'quest-row' }, [main, rank, metadata, reward, progress, actions])]);
  if (expanded.has(q.id)) item.append(detailNode(q));
  return item;
}
function progressControl(q, key, label) {
  const check = el('input', { type: 'checkbox', checked: q.progress[key], 'aria-label': `${label}: ${q.name}` });
  check.addEventListener('change', () => safely(async () => {
    const desired = { ...q.progress, [key]: check.checked };
    if (key === 'all_rewards' && check.checked) desired.first_clear = true;
    if (key === 'first_clear' && !check.checked) desired.all_rewards = false;
    const controls = check.closest('.status-cell').querySelectorAll('input');
    controls.forEach(input => { input.disabled = true; });
    try {
      q.progress = await api('/api/progress', { id: q.id, progress: desired });
      render();
    } catch (error) {
      check.checked = q.progress[key];
      throw error;
    } finally { controls.forEach(input => { input.disabled = false; }); }
  }));
  return el('label', { class: `progress-label${q.progress[key] ? ' done' : ''}` }, [check, label]);
}
function detailNode(q) {
  const first = el('div', {}, [el('h3', { class: 'detail-title', text: 'JAGD & BELOHNUNGEN' })]);
  q.targets.forEach(t => first.append(el('p', { class: 'detail-line', text: targetText(t) })));
  first.append(el('p', { class: 'detail-line', text: rankText(q) }));
  if (q.area || q.quest_type) first.append(el('p', { class:'detail-line', text:[q.area, q.quest_type].filter(Boolean).join(' · ') }));
  q.rewards.forEach(r => first.append(el('p', { class: 'detail-line', text: `${r.name}${r.required ? ` · ${r.required} benötigt` : ''}` })));
  if (q.notes) first.append(el('h3', { class: 'detail-title', text: 'NOTIZEN' }), el('p', { class: 'detail-notes', text: q.notes }));
  const second = el('div', {}, [el('h3', { class: 'detail-title', text: `BELOHNUNGSBILDER${q.images.length ? ` · ${q.images.length}` : ''}` })]);
  second.append(q.images.length ? el('div', { class: 'detail-gallery' }, q.images.map((key, index) => el('button', { onclick: () => showImage(q, index), 'aria-label': `Bild ${index + 1} für ${q.name}` }, [el('img', { src: `/images/${key}`, loading: 'lazy', alt: `Belohnung ${index + 1}` })]))) : el('p', { class: 'detail-line', text: 'Noch keine Bilder angehängt.' }));
  return el('div', { class: 'quest-details' }, [first, second]);
}
function resetFilters() {
  filterIds.forEach(id => { $(id).value = ''; });
  $('search').value = '';
  rewardFilter.clear();
  $('reward-filters').querySelectorAll('input').forEach(input => { input.checked = false; });
  render();
}

let rowCounter = 0;
function labeledInput(label, input) {
  const control = input.matches('input,select,textarea') ? input : input.querySelector('select,summary') || input;
  control.id = `dynamic-field-${++rowCounter}`;
  return el('div', {}, [el('div', { class: 'row-caption' }, [el('label', { htmlFor: control.id, text: label })]), input]);
}
function addTarget(target = { count: 1, monster: '', type: 'Normal' }) {
  if ($('target-rows').children.length >= 30) { toast('Maximal 30 Jagdziele.', true); return; }
  const count = el('input', { type: 'number', min: 1, max: 100, value: target.count, required: true, class: 'target-count' });
  const kind = el('select', { class: 'target-kind' });
  catalogOptions(kind, 'state'); kind.value = target.type_id || recordByName('state', target.type)?.id || records('state').find(s=>s.is_none)?.id || '';
  const monster = el('input', { type:'hidden', value: target.monster_id || recordByName('monster', target.monster)?.id || '', class:'target-monster' });
  const picker = el('details', { class:'monster-picker' });
  const summary = el('summary', { 'aria-label':'Monster auswählen' });
  const search = el('input', { type:'search', placeholder:'Monster suchen …', 'aria-label':'Monsterliste durchsuchen' });
  const choices = el('div', { class:'monster-choices' });
  function updatePreview() {
    const selected = recordById('monster', monster.value);
    summary.replaceChildren(monsterGlyph(selected, recordById('state', kind.value)), el('span', {text:selected?.name || 'Monster wählen'}), icon('chevron'));
    summary.setAttribute('aria-label', `Monster auswählen: ${selected?.name || 'Keine Auswahl'}`);
  }
  monster.updatePreview = updatePreview;
  function updateChoices() {
    const query = search.value.toLocaleLowerCase('de');
    const matches = records('monster').filter(r=>[r.name, ...r.aliases].some(n=>n.toLocaleLowerCase('de').includes(query))).sort((a,b)=>a.name.localeCompare(b.name,'de'));
    choices.replaceChildren(...matches.map(r=>el('button', {type:'button', class:'monster-choice', 'aria-label':r.name, onclick:()=>{monster.value=r.id; picker.open=false; updatePreview(); summary.focus();}}, [monsterGlyph(r), r.name])));
    if (!matches.length) choices.append(el('p', {class:'field-help', text:'Kein Monster gefunden. Über + kannst du eines anlegen.'}));
  }
  picker.addEventListener('toggle', ()=>{ if(picker.open){search.value='';updateChoices();search.focus();} });
  search.addEventListener('input', updateChoices);
  kind.addEventListener('change', updatePreview);
  picker.append(summary, el('div', {class:'monster-popover'}, [search, choices]), monster);
  updatePreview();
  const monsterAdd = el('button', {type:'button', class:'icon-button', 'aria-label':'Monster hinzufügen', onclick:()=>openEntity('monster', null, record=>{monster.value=record.id; updatePreview();})}, [icon('plus')]);
  const stateAdd = el('button', {type:'button', class:'icon-button', 'aria-label':'Monsterzustand hinzufügen', onclick:()=>openEntity('state', null, record=>{kind.value=record.id; updatePreview();})}, [icon('plus')]);
  const remove = el('button', { type: 'button', class: 'icon-button remove-target', 'aria-label': 'Jagdziel entfernen', onclick: () => { row.remove(); updateTargetButtons(); } }, [icon('close')]);
  const row = el('div', { class: 'dynamic-row target-row' }, [labeledInput('Anzahl', count), labeledInput('Monster', el('div', {class:'select-add'}, [picker, monsterAdd])), labeledInput('Zustand', el('div', {class:'select-add'}, [kind, stateAdd])), remove]);
  $('target-rows').append(row);
  updateTargetButtons();
}
function updateTargetButtons() { $('target-rows').querySelectorAll('.remove-target').forEach(button => { button.disabled = $('target-rows').children.length <= 1; }); }
function addReward(reward = { name: '', required: '' }) {
  if ($('reward-rows').children.length >= 30) { toast('Maximal 30 Belohnungen.', true); return; }
  const name = el('input', { value: reward.name, maxLength: 300, required: true, placeholder: 'z. B. Ernte-Ticket', class: 'reward-input' });
  const needed = el('input', { value: reward.required, maxLength: 200, placeholder: 'z. B. 13+', class: 'required-input' });
  const remove = el('button', { type: 'button', class: 'icon-button', 'aria-label': 'Belohnung entfernen', onclick: () => row.remove() }, [icon('close')]);
  const row = el('div', { class: 'dynamic-row reward-row' }, [labeledInput('Belohnungsname', name), labeledInput('Benötigte Anzahl', needed), remove]);
  $('reward-rows').append(row);
}
function openEditor(q = null) {
  if (!serverOnline) { setServerOnline(false); return; }
  editing = q;
  draftImages = q ? [...q.images] : [];
  $('quest-form').reset();
  $('editor-title').textContent = q ? 'Quest bearbeiten' : 'Quest anlegen';
  $('delete-quest').hidden = !q;
  $('quest-name').value = q?.name || '';
  $('quest-stars').value = q?.stars || 4;
  $('quest-rank').value = q?.rank_id || recordByName('rank', q?.rank || 'High-Rank')?.id || '';
  $('quest-hr').value = q?.hr ?? '';
  $('quest-notes').value = q?.notes || '';
  $('quest-area').value = q?.area_id || '';
  $('quest-type').value = q?.quest_type_id || '';
  $('target-rows').replaceChildren();
  (q?.targets || [{ count: 1, monster: '', type: 'Normal' }]).forEach(addTarget);
  $('reward-rows').replaceChildren();
  (q?.rewards || []).forEach(addReward);
  tagChecks($('editor-reward-types'), state.reward_types, new Set(q?.reward_types || []), () => {}, 'reward_type');
  renderDraftImages();
  $('editor').showModal();
  $('quest-name').focus();
}
function renderDraftImages() {
  $('editor-images').replaceChildren(...draftImages.map((key, index) => el('div', { class: 'editor-image' }, [el('img', { src: `/images/${key}`, alt: `Angehängtes Bild ${index + 1}` }), el('button', { type: 'button', class: 'icon-button', 'aria-label': `Bild ${index + 1} entfernen`, onclick: () => { draftImages.splice(index, 1); renderDraftImages(); } }, [icon('close')])])));
}
async function saveQuest(event) {
  event.preventDefault();
  await safely(async () => {
    const q = {
      id: editing?.id,
      name: $('quest-name').value.trim(),
      targets: [...$('target-rows').children].map(row => {
        const monster = recordById('monster', row.querySelector('.target-monster').value);
        const status = recordById('state', row.querySelector('.target-kind').value);
        if (!monster || !status) throw new Error('Für jedes Jagdziel bitte Monster und Zustand auswählen.');
        return {count:Number(row.querySelector('.target-count').value), monster:monster.name, monster_id:monster.id, type:status.name, type_id:status.id};
      }),
      rank: recordById('rank', $('quest-rank').value)?.name,
      rank_id: $('quest-rank').value,
      stars: Number($('quest-stars').value),
      hr: $('quest-hr').value === '' ? null : Number($('quest-hr').value),
      reward_types: [...$('editor-reward-types').querySelectorAll('input:checked')].map(input => input.value),
      reward_type_ids: [...$('editor-reward-types').querySelectorAll('input:checked')].map(input => recordByName('reward_type', input.value).id),
      area: recordById('area',$('quest-area').value)?.name || '', area_id: $('quest-area').value || null,
      quest_type: recordById('quest_type',$('quest-type').value)?.name || '', quest_type_id: $('quest-type').value || null,
      rewards: [...$('reward-rows').children].map(row => ({ name: row.querySelector('.reward-input').value.trim(), required: row.querySelector('.required-input').value.trim() })),
      images: [...draftImages], notes: $('quest-notes').value.trim(),
    };
    $('save-quest').disabled = true;
    try {
      await api(editing ? '/api/quest/save' : '/api/quest/create', q);
      $('editor').close();
      await loadState();
      toast('Quest gespeichert.');
    } finally { $('save-quest').disabled = false; }
  });
}
function confirmAction(title, message, buttonText = 'Bestätigen') {
  $('confirm-title').textContent = title;
  $('confirm-text').textContent = message;
  $('confirm-ok').textContent = buttonText;
  $('confirm-dialog').showModal();
  return new Promise(resolve => {
    const finish = answer => { $('confirm-dialog').close(); resolve(answer); };
    $('confirm-ok').onclick = () => finish(true);
    $('confirm-cancel').onclick = () => finish(false);
    $('confirm-dialog').oncancel = event => { event.preventDefault(); finish(false); };
  });
}
async function uploadImages() {
  const files = [...$('image-input').files];
  $('image-input').value = '';
  if (draftImages.length + files.length > 50) { toast('Maximal 50 Bilder pro Quest.', true); return; }
  await safely(() => busy('Bilder werden lokal gespeichert …', async () => {
    for (const file of files) {
      if (file.size > 20 * 1024 * 1024) throw new Error(`${file.name}: größer als 20 MB.`);
      const encoded = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.onerror = () => reject(new Error('Bild konnte nicht gelesen werden.'));
        reader.readAsDataURL(file);
      });
      const result = await api('/api/image', { data: encoded });
      if (!draftImages.includes(result.key)) draftImages.push(result.key);
      renderDraftImages();
    }
  }));
}

function showImage(q, index = 0) {
  imageSet = { images: q.images, title: q.name, index };
  updateImage();
  $('image-dialog').showModal();
}
function updateImage() {
  $('large-image').src = `/images/${imageSet.images[imageSet.index]}`;
  $('large-image').alt = `Belohnungsbild für ${imageSet.title}`;
  $('image-caption').textContent = imageSet.title;
  $('image-position').textContent = `${imageSet.index + 1} / ${imageSet.images.length}`;
  $('previous-image').disabled = imageSet.images.length <= 1;
  $('next-image').disabled = imageSet.images.length <= 1;
}
function moveImage(delta) {
  if (!imageSet) return;
  imageSet.index = (imageSet.index + delta + imageSet.images.length) % imageSet.images.length;
  updateImage();
}
async function downloadPackage(privateBackup = false) {
  if (privateBackup && !await confirmAction('Privates Backup', 'Dieses Backup enthält Questliste, Bilder und deinen persönlichen Fortschritt. Zum Teilen ohne Nutzerdaten verwende „Questliste teilen“.', 'Backup herunterladen')) return;
  await safely(() => busy(privateBackup ? 'Privates Backup wird erstellt …' : 'Questliste und Bilder werden verpackt …', async () => {
    const response = await fetch(privateBackup ? '/api/export/backup' : '/api/export/catalog');
    if (!response.ok) { const body = await response.json(); throw new Error(body.error || 'Export fehlgeschlagen.'); }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = el('a', { href: url, download: privateBackup ? 'wilds-privates-backup.zip' : 'wilds-questliste.zip' });
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    toast(privateBackup ? 'Privates Backup heruntergeladen.' : 'Questliste exportiert – ohne persönlichen Fortschritt.');
  }));
}
async function previewImport() {
  const file = $('import-input').files[0];
  $('import-input').value = '';
  if (!file) return;
  if (file.size > 120 * 1024 * 1024) { toast('ZIP darf höchstens 120 MB groß sein.', true); return; }
  await safely(() => busy('Questliste wird geprüft …', async () => {
    importPreview = await api('/api/import/preview', await file.arrayBuffer(), true);
    $('import-summary').textContent = `${file.name} · ${importPreview.rows.length} Quests · ${importPreview.catalog_count} Stammdateneinträge · ${importPreview.source}`;
    $('update-catalogs').checked = false;
    $('restore-option').hidden = !importPreview.has_progress;
    $('restore-progress').checked = false;
    $('import-warnings').hidden = !importPreview.warnings.length;
    $('import-warnings').textContent = importPreview.warnings.join('\n');
    $('import-rows').replaceChildren(...importPreview.rows.map(importRow));
    updateImportCounts();
    $('import-dialog').showModal();
  }));
}
function comparison(q, heading) {
  const data = [['Quest', q.name], ['Jagdziel', q.targets.map(targetText).join(' + ')], ['Rang', rankText(q)], ['Arten', q.reward_types.join(', ') || '–'], ['Belohnung', rewardText(q) || '–'], ['Bilder', String(q.images.length)], ['Notizen', q.notes || '–']];
  return el('div', {}, [el('h4', { text: heading }), el('dl', {}, data.flatMap(([label, value]) => [el('dt', { text: label }), el('dd', { text: value })]))]);
}
function importRow(row) {
  const select = el('select', { class: 'import-choice', 'data-quest-id': row.quest.id, 'aria-label': `Importentscheidung für ${row.quest.name}`, onchange: () => { updateImportCounts(); updateComparison(); } });
  select.append(el('option', { value: 'add', text: 'Als separate Quest übernehmen' }), el('option', { value: 'skip', text: 'Überspringen' }));
  const candidates = row.candidates.map(q => ({ value: `update:${q.id}`, text: `Aktualisieren: ${q.name}` }));
  candidates.forEach(candidate => select.append(el('option', candidate)));
  // Manual assignment also supports renamed/translated quests beyond suggested matches.
  const other = state.quests.filter(q => !row.candidates.some(c => c.id === q.id));
  if (other.length) {
    const group = el('optgroup', { label: 'Andere lokale Quest zuordnen' });
    other.forEach(q => group.append(el('option', { value: `update:${q.id}`, text: q.name })));
    select.append(group);
  }
  select.value = row.default;
  const hint = row.exact ? 'Bekannte Quest-ID · persönlicher Fortschritt bleibt erhalten' : row.candidates.length ? 'Mögliches Duplikat · bitte Zuordnung auswählen' : 'Neue Quest · noch keine passende ID bekannt';
  const compare = el('div', { class: 'import-comparison' });
  function updateComparison() {
    const local = select.value.startsWith('update:') ? state.quests.find(q => q.id === select.value.slice(7)) : row.candidates[0];
    compare.replaceChildren(comparison(row.quest, 'Aus der ZIP'), local ? comparison(local, 'Bisher lokal') : el('div', {}, [el('h4', { text: 'Bisher lokal' }), 'Keine Zuordnung ausgewählt.']));
  }
  updateComparison();
  return el('article', { class: 'import-row' }, [el('div', { class: 'import-row-top' }, [el('div', {}, [el('strong', { text: row.quest.name }), el('p', { text: hint })]), select]), el('details', {}, [el('summary', { text: 'Questdetails vergleichen' }), compare])]);
}
function importChoices() { return Object.fromEntries([...$('import-rows').querySelectorAll('select.import-choice')].map(input => [input.dataset.questId, input.value])); }
function updateImportCounts() {
  const values = Object.values(importChoices());
  $('import-counts').textContent = `${values.filter(v => v === 'add').length} neu · ${values.filter(v => v.startsWith('update:')).length} aktualisieren · ${values.filter(v => v === 'skip').length} überspringen`;
}
async function commitImport() {
  await safely(() => busy('Questliste wird übernommen …', async () => {
    const result = await api('/api/import/commit', { token: importPreview.token, choices: importChoices(), restore_progress: $('restore-progress').checked, update_catalogs:$('update-catalogs').checked });
    $('import-dialog').close();
    await loadState();
    toast(`${result.added} Quests hinzugefügt, ${result.updated} aktualisiert, ${result.skipped} übersprungen.`);
  }));
}

function toggleCreateMenu() {
  const menu = $('create-menu');
  menu.hidden = !menu.hidden;
  $('new-quest').setAttribute('aria-expanded', String(!menu.hidden));
  if (!menu.hidden) menu.querySelector('button')?.focus();
}
function closeCreateMenu() { $('create-menu').hidden = true; $('new-quest').setAttribute('aria-expanded','false'); }
function openCatalogs(kind = 'monster') {
  $('catalog-kind').value = kind;
  $('catalog-search').value = '';
  renderCatalogs(); $('catalog-dialog').showModal();
}
function usesRecord(r) {
  return state.quests.filter(q => r.kind === 'monster' ? q.targets.some(t=>t.monster_id===r.id) : r.kind === 'state' ? q.targets.some(t=>t.type_id===r.id) : r.kind === 'reward_type' ? q.reward_type_ids.includes(r.id) : q[`${r.kind}_id`]===r.id).length;
}
function renderCatalogs() {
  const kind = $('catalog-kind').value;
  const term = $('catalog-search').value.trim().toLocaleLowerCase('de');
  const rows = records(kind).filter(r=>[r.name,...r.aliases].some(n=>n.toLocaleLowerCase('de').includes(term)));
  $('catalog-list').replaceChildren(...rows.map(r=> {
    const preview = kind === 'monster' ? monsterGlyph(r) : kind === 'state' ? statePill(r) : ['reward_type','area'].includes(kind) ? pill(r.name, undefined, kind) : null;
    const info = el('div', {class:'catalog-info'}, [el('strong',{text:r.name}),el('small',{text:`${usesRecord(r)} Quests${r.aliases.length ? ` · Auch bekannt als: ${r.aliases.join(', ')}` : ''}`})]);
    const actions = el('div',{class:'catalog-actions'});
    if (!r.is_none) {
      actions.append(el('button',{class:'button subtle',text:'Bearbeiten',onclick:()=>openEntity(kind,r)}));
      if (records(kind).length>1) actions.append(el('button',{class:'text-button',text:'Zusammenführen',onclick:()=>openMerge(r)}));
    }
    return el('div',{class:'catalog-row'},[preview,info,actions]);
  }));
  if (!rows.length) $('catalog-list').append(el('p',{class:'field-help',text:'Noch keine passenden Einträge. Mit „+ Eintrag“ kannst du einen anlegen.'}));
  updateConnectionControls();
}
function updateColor(value) {
  if (!/^#[0-9a-f]{6}$/i.test(value)) return;
  $('entity-color').value=value; $('entity-color-hex').value=value.toUpperCase();
  const name = $('entity-name').value || 'Vorschau';
  const preview = ['reward_type','area'].includes(entityKind) ? pill(name, $('entity-color-default').checked ? null : value, entityKind) : statePill({name,color:value});
  $('entity-color-preview').replaceChildren(preview);
}
function renderEntityIcon() {
  $('entity-icon-preview').replaceChildren(monsterGlyph({name:$('entity-name').value || 'Monster',icon:entityIcon}));
  $('entity-icon-remove').hidden = !entityIcon;
}
function openEntity(kind, record=null, callback=null) {
  if (!serverOnline) { setServerOnline(false); return; }
  entityKind=kind; entityEditing=record; entityCallback=callback; entityIcon=record?.icon || null;
  $('entity-form').reset();
  $('entity-title').textContent=`${catalogLabels[kind]} ${record ? 'bearbeiten' : 'anlegen'}`;
  $('entity-name').value=record?.name || '';
  const categoryColor = ['reward_type','area'].includes(kind);
  $('entity-color-fields').hidden=!categoryColor && kind!=='state';
  $('entity-color-label').textContent=categoryColor ? 'Kategoriefarbe' : 'Zustandsfarbe';
  $('entity-color-help').textContent=categoryColor ? 'Diese Farbe kennzeichnet den Eintrag in der Questliste und bei der Auswahl.' : 'Diese Farbe umrandet ausschließlich das Icon des jeweiligen Monsters. Normal/ohne Zustand hat keine Umrandung.';
  $('entity-color-default-label').hidden=!categoryColor;
  $('entity-color-default').checked=!record?.color;
  $('entity-color-hex').required=categoryColor || kind==='state';
  $('entity-monster-fields').hidden=kind!=='monster';
  $('entity-rank-fields').hidden=kind!=='rank';
  $('entity-stars-min').value=record?.stars_min ?? '';
  $('entity-stars-max').value=record?.stars_max ?? '';
  updateColor(record?.color || (categoryColor ? defaultRewardColor(record?.name || '', kind) : '#7837FC')); renderEntityIcon();
  $('entity-dialog').showModal(); $('entity-name').focus();
}
async function saveEntity(event) {
  event.preventDefault();
  await safely(async()=> {
    const raw={...(entityEditing || {}),kind:entityKind,name:$('entity-name').value.trim()};
    if (entityKind==='state') raw.color=$('entity-color-hex').value;
    if (['reward_type','area'].includes(entityKind)) raw.color=$('entity-color-default').checked ? null : $('entity-color-hex').value;
    if (entityKind==='monster') raw.icon=entityIcon;
    if (entityKind==='rank') { raw.stars_min=$('entity-stars-min').value ? Number($('entity-stars-min').value) : null; raw.stars_max=$('entity-stars-max').value ? Number($('entity-stars-max').value) : null; }
    $('entity-save').disabled=true;
    try {
      const result=await api(entityEditing ? '/api/catalog/save' : '/api/catalog/create',raw);
      $('entity-dialog').close(); await loadState();
      entityCallback?.(result); toast(`${catalogLabels[entityKind]} gespeichert.`);
    } finally { $('entity-save').disabled=false; }
  });
}
function openMerge(record) {
  if (!serverOnline) { setServerOnline(false); return; }
  mergeSource=record;
  $('merge-source-label').textContent=`„${record.name}“ wird in den gewählten Eintrag übernommen.`;
  $('merge-target').replaceChildren(...records(record.kind).filter(r=>r.id!==record.id && !r.is_none).map(r=>el('option',{value:r.id,text:r.name})));
  $('merge-dialog').showModal();
}
async function uploadEntityIcon() {
  const file=$('entity-icon-input').files[0]; $('entity-icon-input').value='';
  if (!file) return;
  await safely(()=>busy('Monster-Icon wird gespeichert …',async()=>{
    if(file.size>20*1024*1024) throw new Error('Das Icon darf höchstens 20 MB groß sein.');
    const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(new Error('Icon konnte nicht gelesen werden.'));reader.readAsDataURL(file);});
    entityIcon=(await api('/api/image',{data:encoded})).key; renderEntityIcon();
  }));
}
Object.entries(catalogLabels).forEach(([kind,label])=>$('catalog-kind').append(el('option',{value:kind,text:label})));
$('create-menu').append(el('button',{role:'menuitem',text:'Neue Quest',onclick:()=>{closeCreateMenu();openEditor();}}));
Object.entries(catalogLabels).forEach(([kind,label])=>$('create-menu').append(el('button',{role:'menuitem',text:`${label} anlegen`,onclick:()=>{closeCreateMenu();openEntity(kind);}})));
$('create-menu').append(el('button',{role:'menuitem',text:'Stammdaten verwalten',onclick:()=>{closeCreateMenu();openCatalogs();}}));
document.addEventListener('click',event=>{if(!event.target.closest('.create-actions'))closeCreateMenu();});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('create-menu').hidden){closeCreateMenu();$('new-quest').focus();}});
$('manage-catalogs').addEventListener('click',()=>openCatalogs());
$('catalog-kind').addEventListener('change',renderCatalogs);
$('catalog-search').addEventListener('input',renderCatalogs);
$('catalog-add').addEventListener('click',()=>openEntity($('catalog-kind').value));
$('entity-form').addEventListener('submit',saveEntity);
$('entity-color').addEventListener('input',()=>{ $('entity-color-default').checked=false; updateColor($('entity-color').value); });
$('entity-color-hex').addEventListener('input',()=>{ $('entity-color-default').checked=false; updateColor($('entity-color-hex').value); });
$('entity-color-default').addEventListener('change',()=>updateColor($('entity-color').value));
$('entity-name').addEventListener('input',()=>updateColor($('entity-color').value));
$('entity-icon-input').addEventListener('change',uploadEntityIcon);
$('entity-icon-remove').addEventListener('click',()=>{entityIcon=null;renderEntityIcon();});
document.querySelectorAll('[data-add-kind]').forEach(button=>button.addEventListener('click',()=>openEntity(button.dataset.addKind,null,r=>{
  if(button.dataset.addSelect) $(button.dataset.addSelect).value=r.id;
  if(r.kind==='reward_type') { const container=$('editor-reward-types'); [...container.querySelectorAll('input')].find(input=>input.value===r.name).checked=true; }
})));
$('merge-form').addEventListener('submit',event=>{event.preventDefault();safely(async()=>{
  $('merge-save').disabled=true;
  try {await api('/api/catalog/merge',{source_id:mergeSource.id,target_id:$('merge-target').value});$('merge-dialog').close();await loadState();toast('Einträge zusammengeführt.');}
  finally {$('merge-save').disabled=false;}
});});

document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => $(button.dataset.close).close()));
filterIds.forEach(id => $(id).addEventListener(id === 'filter-hr' ? 'input' : 'change', render));
$('search').addEventListener('input', render);
function setupColumnResizing() {
  const storageKey = 'wilds-column-widths-v2';
  const columns = ['name', 'rank', 'area', 'reward', 'progress'];
  const layoutColumns = [...columns, 'actions'];
  const minimums = { name: 180, rank: 80, area: 80, reward: 120, progress: 140 };
  const panel = document.querySelector('.quest-panel');
  const header = document.querySelector('.table-head');
  const actionMinimum = () => {
    const style = getComputedStyle(header);
    return parseFloat(style.getPropertyValue('--quest-thumb-size')) + parseFloat(style.getPropertyValue('--quest-action-gap')) + 34;
  };
  minimums.actions = actionMinimum();
  const widths = {};
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    for (const column of layoutColumns) {
      if (Number.isFinite(saved?.[column]) && saved[column] >= minimums[column] && saved[column] <= 5000) widths[column] = saved[column];
    }
  } catch { /* Keep the default layout when storage is unavailable. */ }
  if (columns.every(column => widths[column]) && !widths.actions) widths.actions = minimums.actions;
  if (!layoutColumns.every(column => widths[column])) {
    for (const column of layoutColumns) delete widths[column];
  }
  const save = () => {
    try { localStorage.setItem(storageKey, JSON.stringify(widths)); }
    catch { toast('Spaltenbreiten gelten für diese Sitzung. Der Browser erlaubt keine Speicherung.'); }
  };
  const apply = () => {
    panel.classList.toggle('custom-columns', window.innerWidth > 1100 && layoutColumns.every(column => widths[column]));
    for (const column of layoutColumns) {
      if (widths[column]) panel.style.setProperty(`--column-${column}`, `${widths[column]}px`);
      else panel.style.removeProperty(`--column-${column}`);
    }
  };
  const handles = columns.map(column => {
    const cell = header.querySelector(`[data-sort-column="${column}"]`).closest(column === 'area' ? '.metadata-sorts' : 'button');
    const label = cell.textContent.replace('↕', '').trim();
    const handle = el('div', { class: 'column-resizer', role: 'separator', tabIndex: 0,
      'aria-orientation': 'vertical', 'aria-label': `${label}: Spaltenbreite ändern`,
      'aria-valuemin': minimums[column],
      title: `${label} breiter/schmaler ziehen · Doppelklick für Standardaufteilung` });
    const setWidth = value => {
      const following = layoutColumns.slice(layoutColumns.indexOf(column) + 1);
      const available = following.reduce((sum, next) => sum + widths[next] - minimums[next], 0);
      const target = Math.max(minimums[column], Math.min(widths[column] + available, Math.round(value)));
      let change = target - widths[column];
      widths[column] = target;
      if (change < 0) widths[following[0]] -= change;
      else for (const next of following) {
        const taken = Math.min(change, widths[next] - minimums[next]);
        widths[next] -= taken;
        change -= taken;
      }
      apply();
      position();
    };
    let drag = null;
    const finish = event => {
      if (!drag || event.pointerId !== drag.id) return;
      drag = null;
      document.body.classList.remove('resizing-columns');
      if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
      save();
    };
    handle.addEventListener('pointerdown', event => {
      if (event.button !== 0) return;
      event.preventDefault();
      freezeWidths();
      drag = { id: event.pointerId, x: event.clientX, width: widths[column] };
      handle.setPointerCapture(event.pointerId);
      document.body.classList.add('resizing-columns');
    });
    handle.addEventListener('pointermove', event => {
      if (drag && event.pointerId === drag.id) setWidth(drag.width + event.clientX - drag.x);
    });
    for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) handle.addEventListener(event, finish);
    handle.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home'].includes(event.key)) return;
      event.preventDefault();
      if (event.key === 'Home') { resetWidths(); }
      else { freezeWidths(); setWidth(widths[column] + (event.key === 'ArrowRight' ? 1 : -1) * (event.shiftKey ? 20 : 5)); }
      save();
    });
    handle.addEventListener('dblclick', () => { resetWidths(); save(); });
    header.append(handle);
    return { cell, handle, column };
  });
  function freezeWidths() {
    if (layoutColumns.every(column => widths[column])) return;
    const tracks = getComputedStyle(header).gridTemplateColumns.split(' ').map(parseFloat);
    layoutColumns.forEach((column, index) => { widths[column] = tracks[index]; });
    fitWidths();
    apply();
  }
  function resetWidths() {
    for (const column of layoutColumns) delete widths[column];
    apply(); position();
  }
  function position() {
    const bounds = header.getBoundingClientRect();
    const tracks = getComputedStyle(header).gridTemplateColumns.split(' ').map(parseFloat);
    const gap = parseFloat(getComputedStyle(header).columnGap) || 0;
    for (let index = 0; index < handles.length; index++) {
      const { handle, cell } = handles[index];
      const nextColumn = columns[index + 1];
      const nextCell = nextColumn
        ? header.querySelector(`[data-sort-column="${nextColumn}"]`).closest(nextColumn === 'area' ? '.metadata-sorts' : 'button')
        : header.querySelector(':scope > span[aria-hidden="true"]');
      handle.style.left = `${nextCell.getBoundingClientRect().left - bounds.left - gap / 2}px`;
      handle.setAttribute('aria-valuenow', String(Math.round(tracks[index] || cell.getBoundingClientRect().width)));
      if (layoutColumns.every(column => widths[column])) {
        const following = layoutColumns.slice(index + 1);
        handle.setAttribute('aria-valuemax', String(Math.floor(widths[columns[index]] + following.reduce((sum, column) => sum + widths[column] - minimums[column], 0))));
      }
    }
  }
  function fitWidths() {
    if (window.innerWidth <= 1100) { apply(); return; }
    if (!layoutColumns.every(column => widths[column])) { apply(); return; }
    minimums.actions = actionMinimum();
    for (const column of layoutColumns) widths[column] = Math.max(minimums[column], widths[column]);
    const style = getComputedStyle(header);
    const budget = header.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)
      - 5 * parseFloat(style.columnGap);
    const minimumTotal = layoutColumns.reduce((sum, column) => sum + minimums[column], 0);
    const total = layoutColumns.reduce((sum, column) => sum + widths[column], 0);
    if (budget < minimumTotal || !Number.isFinite(budget)) { resetWidths(); return; }
    if (Math.abs(total - budget) < 0.5) return;
    if (total < budget) widths.progress += budget - total;
    else {
      const scale = (budget - minimumTotal) / (total - minimumTotal);
      for (const column of layoutColumns) widths[column] = minimums[column] + (widths[column] - minimums[column]) * scale;
    }
    apply();
  }
  apply();
  new ResizeObserver(() => { fitWidths(); position(); }).observe(header);
  position();
}
setupColumnResizing();

$('toggle-all-quests').addEventListener('click', () => {
  const collapse = state.quests.length > 0 && state.quests.every(q => expanded.has(q.id));
  for (const quest of state.quests) {
    if (collapse) expanded.delete(quest.id);
    else expanded.add(quest.id);
  }
  render();
});

document.querySelectorAll('[data-sort-column]').forEach(button => button.addEventListener('click', () => {
  const column = button.dataset.sortColumn;
  questSort.direction = questSort.column === column ? -questSort.direction : 1;
  questSort.column = column;
  render();
}));
$('reset-filters').addEventListener('click', resetFilters);
$('new-quest').addEventListener('click', toggleCreateMenu);
$('add-target').addEventListener('click', () => addTarget());
$('add-reward').addEventListener('click', () => addReward());
$('quest-form').addEventListener('submit', saveQuest);
$('quest-stars').addEventListener('input', () => {
  const stars = Number($('quest-stars').value);
  const rank = records('rank').find(r=>r.stars_min != null && stars>=r.stars_min && (r.stars_max == null || stars<=r.stars_max));
  if (rank) $('quest-rank').value = rank.id;
});
$('image-input').addEventListener('change', uploadImages);
$('delete-quest').addEventListener('click', () => safely(async () => {
  const quest = editing;
  if (!await confirmAction('Quest löschen?', `„${quest.name}“ und der zugehörige persönliche Fortschritt werden gelöscht.`, 'Quest löschen')) return;
  await api('/api/quest/delete', { id: quest.id });
  expanded.delete(quest.id);
  $('editor').close();
  await loadState(); toast('Quest gelöscht.');
}));
$('previous-image').addEventListener('click', () => moveImage(-1));
$('next-image').addEventListener('click', () => moveImage(1));
$('export-button').addEventListener('click', () => downloadPackage());
$('backup-button').addEventListener('click', () => downloadPackage(true));
$('import-button').addEventListener('click', () => $('import-input').click());
$('import-input').addEventListener('change', previewImport);
$('commit-import').addEventListener('click', commitImport);
$('import-new').addEventListener('click', () => {
  const noCandidates = new Set(importPreview.rows.filter(row => !row.candidates.length).map(row => row.quest.id));
  $('import-rows').querySelectorAll('select.import-choice').forEach(input => { if (noCandidates.has(input.dataset.questId)) input.value = 'add'; });
  updateImportCounts();
});
document.addEventListener('keydown', event => {
  if ($('image-dialog').open && ['ArrowLeft', 'ArrowRight'].includes(event.key)) { event.preventDefault(); moveImage(event.key === 'ArrowLeft' ? -1 : 1); }
  if (event.key === '/' && !document.querySelector('dialog[open]') && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) { event.preventDefault(); $('search').focus(); }
});
safely(async () => {
  try { await loadState(); } catch (error) {
    $('result-count').textContent = 'Verbindung unterbrochen';
    $('quest-list').replaceChildren(el('div', { class: 'empty-state' }, [el('h3', { text: 'Tracker nicht erreichbar' }), el('p', { text: error.message }), el('button', { class: 'button', text: 'Erneut versuchen', onclick: () => safely(loadState) })]));
    throw error;
  }
});

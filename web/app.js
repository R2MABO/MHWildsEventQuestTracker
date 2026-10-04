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

let state = { quests: [], reward_types: [], monster_types: [], ranks: [] };
let editing = null;
let draftImages = [];
let importPreview = null;
let imageSet = null;
let toastTimer;
const expanded = new Set();
const rewardFilter = new Set();
const filterIds = ['filter-status', 'filter-rank', 'filter-stars', 'filter-hr', 'filter-monster', 'filter-type'];
const csrf = document.querySelector('meta[name="tracker-token"]').content;

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
  let response;
  try {
    response = await fetch(path, data === undefined ? {} : {
      method: 'POST',
      headers: { 'X-Tracker-Token': csrf, 'Content-Type': binary ? 'application/zip' : 'application/json' },
      body: binary ? data : JSON.stringify(data),
    });
  } catch {
    throw new Error('Der lokale Tracker ist nicht erreichbar. Prüfe, ob das Startfenster noch geöffnet ist.');
  }
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'Anfrage fehlgeschlagen.');
  return body;
}

function options(select, values, first = null) {
  const old = select.value;
  select.replaceChildren();
  if (first) select.append(el('option', { value: '', text: first }));
  values.forEach(value => select.append(el('option', { value, text: String(value) })));
  if ([...select.options].some(o => o.value === old)) select.value = old;
}
function tagChecks(container, values, selected, onChange) {
  container.replaceChildren(...values.map(value => {
    const checkbox = el('input', { type: 'checkbox', value, checked: selected.has(value), onchange: e => onChange(value, e.target.checked) });
    return el('label', { class: 'tag-check' }, [checkbox, el('span', { text: value })]);
  }));
}
function knownMonsters() {
  return [...new Set(state.quests.flatMap(q => q.targets.map(t => t.monster)))].sort((a, b) => a.localeCompare(b, 'de'));
}
async function loadState() {
  state = await api('/api/state');
  options($('filter-rank'), state.ranks, 'Alle Ränge');
  options($('filter-type'), state.monster_types, 'Alle Arten');
  options($('filter-stars'), [...new Set(state.quests.map(q => q.stars))].sort((a, b) => a - b), 'Alle');
  options($('filter-monster'), knownMonsters(), 'Alle Monster');
  $('monster-suggestions').replaceChildren(...knownMonsters().map(monster => el('option', { value: monster })));
  tagChecks($('reward-filters'), state.reward_types, rewardFilter, (value, checked) => {
    if (checked) rewardFilter.add(value); else rewardFilter.delete(value);
    render();
  });
  options($('quest-rank'), state.ranks);
  render();
}

function targetText(target) {
  return `${target.count > 1 ? `${target.count} × ` : ''}${target.type !== 'Normal' ? `${target.type} · ` : ''}${target.monster}`;
}
function rankText(q) { return `${q.stars} ★ · ${q.rank} · ${q.hr == null ? 'JR offen' : `JR ${q.hr}+`}`; }
function rewardText(q) { return q.rewards.map(r => `${r.name}${r.required ? ` (${r.required} benötigt)` : ''}`).join(', '); }
function targetsNode(q) {
  const node = el('div', { class: 'quest-targets' });
  q.targets.forEach((t, index) => {
    if (index) node.append(' + ');
    if (t.count > 1) node.append(`${t.count} × `);
    if (t.type !== 'Normal') node.append(el('span', { class: `monster-kind ${t.type.toLowerCase()}`, text: `${t.type} ` }));
    node.append(t.monster);
  });
  return node;
}
function pill(value) {
  let style = '';
  if (value === 'Ausrüstung') style = ' equipment';
  else if (value === 'Dekorationen') style = ' deco';
  else if (value.includes('Material')) style = ' material';
  return el('span', { class: `pill${style}`, text: value });
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
    return true;
  });
  const sort = $('sort').value;
  if (sort === 'name') result.sort((a, b) => a.name.localeCompare(b.name, 'de'));
  if (sort === 'stars-desc') result.sort((a, b) => b.stars - a.stars);
  if (sort === 'stars-asc') result.sort((a, b) => a.stars - b.stars);
  if (sort === 'open') result.sort((a, b) => Number(a.progress.all_rewards) - Number(b.progress.all_rewards));
  if (sort === 'hr') result.sort((a, b) => (a.hr || 0) - (b.hr || 0));
  return result;
}
function renderActiveFilters() {
  const pills = [];
  const add = (label, clear) => pills.push(el('button', { type: 'button', class: 'active-pill', onclick: () => { clear(); render(); }, 'aria-label': `Filter entfernen: ${label}` }, [label, icon('close')]));
  filterIds.forEach(id => {
    const input = $(id);
    if (!input.value) return;
    const label = id === 'filter-hr' ? `JR bis ${input.value}` : input.selectedOptions[0].text;
    add(label, () => { input.value = ''; });
  });
  if ($('search').value.trim()) add(`Suche: ${$('search').value.trim()}`, () => { $('search').value = ''; });
  rewardFilter.forEach(value => add(value, () => {
    rewardFilter.delete(value);
    [...$('reward-filters').querySelectorAll('input')].find(i => i.value === value).checked = false;
  }));
  $('active-filters').replaceChildren(...pills);
  $('active-filters').hidden = !pills.length;
}
function render() {
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
  if (!quests.length) {
    $('quest-list').append(el('div', { class: 'empty-state' }, [icon('hunt'),
      el('h3', { text: total ? 'Keine passenden Quests' : 'Deine nächste Jagd beginnt hier' }),
      el('p', { text: total ? 'Passe deine Filter an oder suche nach einem anderen Begriff.' : 'Lege eine Quest an oder importiere eine Questliste als ZIP.' }),
      el('button', { class: 'button', onclick: total ? resetFilters : () => openEditor() }, [total ? 'Filter zurücksetzen' : 'Erste Quest anlegen'])]));
  }
}
function questNode(q) {
  const hasImages = q.images.length > 0;
  const thumb = el(hasImages ? 'button' : 'div', { class: 'quest-thumb' }, hasImages ? [el('img', { src: `/images/${q.images[0]}`, alt: `Belohnung: ${q.name}`, loading: 'lazy' })] : [icon('hunt')]);
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
    if (isOpen) item.append(detailNode(q)); else item.querySelector('.quest-details')?.remove();
  } }, [q.name, icon('chevron')]);
  const main = el('div', { class: 'quest-main' }, [thumb, el('div', { class: 'quest-text' }, [title, targetsNode(q)])]);
  const rank = el('div', { class: 'quest-rank' }, [el('strong', { text: `${q.stars} ★` }), el('small', { text: q.rank }), el('small', { text: q.hr == null ? 'JR: keine Angabe' : `JR ${q.hr}+` })]);
  const reward = el('div', { class: 'quest-reward' }, [el('div', { class: 'reward-pills' }, q.reward_types.map(pill))]);
  if (q.rewards.length) {
    const first = q.rewards[0];
    reward.append(el('div', { class: 'reward-name', text: first.name }), el('div', { class: 'reward-needed', text: `${first.required ? `${first.required} benötigt` : ''}${q.rewards.length > 1 ? ` · +${q.rewards.length - 1} weitere` : ''}` }));
  }
  const progress = el('div', { class: 'status-cell' }, [progressControl(q, 'first_clear', 'Erster Abschluss'), progressControl(q, 'all_rewards', 'Alle Belohnungen')]);
  const edit = el('button', { class: 'icon-button', title: 'Quest bearbeiten', 'aria-label': `${q.name} bearbeiten`, onclick: () => openEditor(q) }, [icon('edit')]);
  const item = el('article', { class: `quest-item${q.progress.all_rewards ? ' completed' : ''}` }, [el('div', { class: 'quest-row' }, [main, rank, reward, progress, edit])]);
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
  input.id = `dynamic-field-${++rowCounter}`;
  return el('div', {}, [el('div', { class: 'row-caption' }, [el('label', { htmlFor: input.id, text: label })]), input]);
}
function addTarget(target = { count: 1, monster: '', type: 'Normal' }) {
  if ($('target-rows').children.length >= 30) { toast('Maximal 30 Jagdziele.', true); return; }
  const count = el('input', { type: 'number', min: 1, max: 100, value: target.count, required: true, class: 'target-count' });
  const monster = el('input', { value: target.monster, required: true, maxLength: 200, list: 'monster-suggestions', placeholder: 'Monstername', class: 'target-monster' });
  const kind = el('select', { class: 'target-kind' });
  options(kind, state.monster_types); kind.value = target.type;
  const remove = el('button', { type: 'button', class: 'icon-button remove-target', 'aria-label': 'Jagdziel entfernen', onclick: () => { row.remove(); updateTargetButtons(); } }, [icon('close')]);
  const row = el('div', { class: 'dynamic-row target-row' }, [labeledInput('Anzahl', count), labeledInput('Monster', monster), labeledInput('Monsterart', kind), remove]);
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
  editing = q;
  draftImages = q ? [...q.images] : [];
  $('quest-form').reset();
  $('editor-title').textContent = q ? 'Quest bearbeiten' : 'Quest anlegen';
  $('delete-quest').hidden = !q;
  $('quest-name').value = q?.name || '';
  $('quest-stars').value = q?.stars || 4;
  $('quest-rank').value = q?.rank || 'High-Rank';
  $('quest-hr').value = q?.hr ?? '';
  $('quest-notes').value = q?.notes || '';
  $('target-rows').replaceChildren();
  (q?.targets || [{ count: 1, monster: '', type: 'Normal' }]).forEach(addTarget);
  $('reward-rows').replaceChildren();
  (q?.rewards || []).forEach(addReward);
  tagChecks($('editor-reward-types'), state.reward_types, new Set(q?.reward_types || []), () => {});
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
      targets: [...$('target-rows').children].map(row => ({ count: Number(row.querySelector('.target-count').value), monster: row.querySelector('.target-monster').value.trim(), type: row.querySelector('.target-kind').value })),
      rank: $('quest-rank').value,
      stars: Number($('quest-stars').value),
      hr: $('quest-hr').value === '' ? null : Number($('quest-hr').value),
      reward_types: [...$('editor-reward-types').querySelectorAll('input:checked')].map(input => input.value),
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
    $('import-summary').textContent = `${file.name} · ${importPreview.rows.length} Quests · ${importPreview.source}`;
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
    const result = await api('/api/import/commit', { token: importPreview.token, choices: importChoices(), restore_progress: $('restore-progress').checked });
    $('import-dialog').close();
    await loadState();
    toast(`${result.added} Quests hinzugefügt, ${result.updated} aktualisiert, ${result.skipped} übersprungen.`);
  }));
}

document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => $(button.dataset.close).close()));
filterIds.forEach(id => $(id).addEventListener(id === 'filter-hr' ? 'input' : 'change', render));
$('search').addEventListener('input', render);
$('sort').addEventListener('change', render);
$('reset-filters').addEventListener('click', resetFilters);
$('new-quest').addEventListener('click', () => openEditor());
$('add-target').addEventListener('click', () => addTarget());
$('add-reward').addEventListener('click', () => addReward());
$('quest-form').addEventListener('submit', saveQuest);
$('quest-stars').addEventListener('input', () => {
  const stars = Number($('quest-stars').value);
  if (stars >= 1) $('quest-rank').value = stars <= 3 ? 'Low-Rank' : stars <= 10 ? 'High-Rank' : 'Master-Rank';
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

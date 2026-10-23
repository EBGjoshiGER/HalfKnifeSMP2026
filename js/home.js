(() => {
  'use strict';
  const C = window.HalfKnifeStats;
  const $ = id => document.getElementById(id);
  const BASE = 'https://raw.githubusercontent.com/EBGjoshiGER/HalfKnifeSMP2026/main/';
  const local = ['localhost', '127.0.0.1', ''].includes(location.hostname);
  const esc = escapeHtml;
  const avatar = player => `<span class="home-avatar" aria-hidden="true"><span>${esc(player.name.slice(0, 2).toUpperCase())}</span><img src="https://mc-heads.net/avatar/${encodeURIComponent(player.uuid || player.name)}/64" width="64" height="64" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()"></span>`;
  let roster = [];
  let onlineCount = null;
  let busy = false;

  async function json(path) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`${local ? '' : BASE}${path}?v=${Date.now()}`, { cache: 'no-store', signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } finally { clearTimeout(timer); }
  }
  function seasonLabel() {
    const started = Date.now() >= serverStartDate.getTime();
    $('season-countdown-title').textContent = started ? 'Season 2026 · Gemeinsam unterwegs' : 'Samstag, 24. Oktober · 14 Uhr';
    document.querySelector('.launch-strip .eyebrow').textContent = started ? 'UNSER ABENTEUER HAT BEGONNEN' : 'DAS ABENTEUER BEGINNT';
    $('hero-online-count').textContent = onlineCount === null ? '' : `· ${onlineCount} online`;
  }
  function renderStatus(data) {
    if (!data || typeof data.online !== 'boolean' || !Array.isArray(data.players)) throw new Error('Ungültiger Serverstatus');
    const names = data.players.filter(name => typeof name === 'string' && /^[A-Za-z0-9_]{1,16}$/.test(name));
    onlineCount = data.online ? (Number.isSafeInteger(data.onlineCount) && data.onlineCount >= 0 ? data.onlineCount : names.length) : 0;
    $('home-server-status').textContent = data.online ? `${onlineCount} online · Server online` : 'Server offline';
    $('home-server-status').dataset.online = String(data.online);
    const players = names.map(name => roster.find(p => p.name.toLowerCase() === name.toLowerCase()) || { name });
    $('home-online-list').innerHTML = data.online && players.length ? players.map(player => `<a class="online-player" href="stats.html?player=${encodeURIComponent(player.uuid || player.name)}">${avatar(player)}<span>${esc(player.name)}</span></a>`).join('')
      : `<p class="world-empty">${!data.online ? 'Die Welt macht gerade eine Pause.' : onlineCount > 0 ? 'Die Spielerliste ist gerade nicht verfügbar.' : 'Gerade ist es ruhig. Das nächste Abenteuer wartet.'}</p>`;
    seasonLabel();
  }
  function renderStats(snapshot, whitelist) {
    if (snapshot.schema !== 1 || !Array.isArray(snapshot.players) || !snapshot.players.every(C.validPlayer)) throw new Error('Ungültige Statistikdaten');
    roster = C.reconcileWhitelist(snapshot.players, whitelist);
    const totals = C.totals(roster, snapshot.activeMode);
    $('home-total-players').textContent = C.integer.format(roster.length);
    $('home-total-time').textContent = C.duration(totals.activeSeconds);
    $('home-total-blocks').textContent = C.integer.format(totals.blocksMined);
    const top = snapshot.activeMode === 'active' ? C.leaderboard(roster, 'activeSeconds', 3) : [];
    $('home-top-three').innerHTML = top.length ? top.map((player, index) => `<li class="podium-player"><a href="stats.html?player=${encodeURIComponent(player.uuid)}">${avatar(player)}<span class="podium-name"><strong>${esc(player.name)}</strong><small>${esc(C.duration(player.summary.activeSeconds))}</small></span><span class="podium-place">#${index + 1}</span></a></li>`).join('')
      : '<li class="world-empty">Noch ist hier alles offen. Wer setzt sich an die Spitze?</li>';
  }
  function renderGoal(data) {
    const labels = { not_started: 'Startet gemeinsam mit der Community', active: 'Das Nether-Projekt läuft', paused: 'Das Projekt pausiert', completed: 'Der Nether ist freigeschaltet' };
    if (!data || data.schemaVersion !== 1 || !Object.hasOwn(labels, data.status)) throw new Error('Ungültiges Projekt');
    // Only fresh exports can support a progress claim; older files stay a project teaser.
    const stamp = Date.parse(data.syncedAt);
    const fresh = Number.isFinite(stamp) && Date.now() - stamp < 30 * 60 * 1000 && stamp <= Date.now() + 60000;
    $('home-goal-status').textContent = fresh ? labels[data.status] : 'Gemeinsam den Nether freischalten';
    const resources = data.resources;
    const valid = fresh && Array.isArray(resources) && resources.length > 0 && resources.every(r => Number.isFinite(r.required) && r.required > 0 && Number.isFinite(r.donated) && r.donated >= 0);
    $('home-goal-progress').hidden = !valid;
    if (valid) {
      const percent = resources.reduce((sum, r) => sum + Math.min(1, r.donated / r.required), 0) / resources.length * 100;
      $('home-goal-meter').value = percent;
      $('home-goal-percent').textContent = `${C.number.format(percent)} %`;
    }
  }
  async function refresh() {
    if (busy) return;
    busy = true;
    // Features fail independently: a project export must never block online players.
    const results = await Promise.allSettled([
      Promise.all([json('data/statistics.json'), json('data/whitelist.json')]).then(([snapshot, whitelist]) => renderStats(snapshot, whitelist)),
      json('data/server-status.json'),
      json('nether-project.json').then(renderGoal)
    ]);
    if (results[0].status === 'rejected' && !roster.length) $('home-top-three').innerHTML = '<li class="world-empty">Die Statistiken sind gerade nicht verfügbar. Schau gleich noch einmal vorbei.</li>';
    if (results[1].status === 'fulfilled') {
      try { renderStatus(results[1].value); } catch { statusUnavailable(); }
    } else { statusUnavailable(); }
    busy = false;
  }
  function statusUnavailable() {
    onlineCount = null;
    $('home-server-status').textContent = 'Status momentan unbekannt';
    delete $('home-server-status').dataset.online;
    $('home-online-list').innerHTML = '<p class="world-empty">Die Online-Spielerliste ist gerade nicht verfügbar.</p>';
    seasonLabel();
  }
  $('home-copy').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText('halfknife2026.serverminer.com');
      $('home-copy-message').textContent = 'Serveradresse kopiert. Wir sehen uns ingame!';
    } catch {
      $('home-copy-message').textContent = 'Serveradresse: halfknife2026.serverminer.com';
    }
  });
  document.addEventListener('DOMContentLoaded', () => {
    seasonLabel();
    setInterval(seasonLabel, 1000);
    refresh();
    setInterval(() => { if (!document.hidden) refresh(); }, 60000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  });
})();

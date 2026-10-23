(function () {
  "use strict";
  const C = window.HalfKnifeStats;
  const BASE = "https://raw.githubusercontent.com/EBGjoshiGER/HalfKnifeSMP2026/main/data/";
  const $ = id => document.getElementById(id);
  const escape = value => String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const href = player => `stats.html?player=${encodeURIComponent(player.uuid)}`;
  // UUIDs keep heads associated with the player even after a name change.
  // The initials remain behind the image while loading or if the image fails.
  const avatar = (player, profile = false) => `<span class="stats-avatar" aria-hidden="true"><span>${escape(player.name.slice(0, 2).toUpperCase())}</span><img src="https://mc-heads.net/avatar/${encodeURIComponent(player.uuid)}/128" alt="" width="128" height="128" loading="${profile ? "eager" : "lazy"}" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()"></span>`;
  let data;
  let players = [];
  let online = null;
  let selected = null;
  let category = "all";
  let loading = false;

  function onlineBadge(player) {
    if (online === null) return "";
    const active = online.has(player.name.toLowerCase());
    return `<span class="stats-online ${active ? "is-online" : ""}">${active ? "Online" : "Offline"}</span>`;
  }
  function tile(label, value, extra = "") {
    return `<div class="stats-total"><span class="stats-total-label">${escape(label)}</span><strong>${escape(value)}</strong>${extra ? `<small>${escape(extra)}</small>` : ""}</div>`;
  }
  function timestamp(value) {
    const date = new Date(value);
    return value && Number.isFinite(date.getTime()) ? date.toLocaleString("de-DE", { timeZone: "Europe/Berlin", dateStyle: "medium", timeStyle: "short" }) : "unbekannt";
  }
  function renderOverview() {
    const totals = C.totals(players, data.activeMode);
    $("stats-totals").innerHTML = [
      tile("Aktive Spielzeit", C.duration(totals.activeSeconds), "Ohne AFK-Zeit"),
      tile("Tode", C.integer.format(totals.deaths), "Neue Chancen inklusive"),
      tile("Blöcke abgebaut", C.integer.format(totals.blocksMined)),
      tile("Mobs besiegt", C.integer.format(totals.mobKills)),
      tile("Strecke zurückgelegt", C.distance(totals.distanceCm)),
      tile("Spieler mit erfassten Werten", C.integer.format(totals.players))
    ].join("");
    $("stats-leaderboards").innerHTML = C.metrics.map(metric => {
      const entries = C.leaderboard(players, metric.key);
      return `<article class="stats-board"><div class="stats-board-heading"><span class="stats-board-icon" aria-hidden="true">${metric.icon}</span><div><h3>${metric.title}</h3><p>${metric.caption}</p></div></div>${entries.length
        ? `<ol class="stats-ranking">${entries.map((player, index) => `<li><span class="stats-rank stats-place-${index + 1}" aria-label="Platz ${index + 1}">${index + 1}</span><a href="${href(player)}">${escape(player.name)}</a><strong>${escape(metric.format(player.summary[metric.key]))}</strong></li>`).join("")}</ol>`
        : `<p class="stats-empty">${metric.key === "activeSeconds" && data.activeMode !== "active" ? "Wartet auf die Aktivierung des Aktivzählers." : "Hier schreibt ihr bald die ersten Zahlen."}</p>`}</article>`;
    }).join("");
    $("stats-player-count").textContent = `${players.length} freigeschaltet`;
    renderPlayers();
  }
  function renderPlayers() {
    const matches = C.sortPlayers(players, $("stats-player-search").value, $("stats-player-sort").value);
    $("stats-player-result").textContent = `${matches.length} von ${players.length} Spielern`;
    $("stats-player-grid").innerHTML = matches.length ? matches.map(player => `<a class="stats-player-card" href="${href(player)}">${avatar(player)}<span class="stats-player-info"><strong>${escape(player.name)}</strong><span>${player.pendingStats ? "Statistiken folgen" : `${escape(C.duration(player.summary.activeSeconds))} aktiv`}</span>${onlineBadge(player)}</span><span class="stats-card-arrow" aria-hidden="true">↗</span></a>`).join("")
      : '<p class="stats-empty">Kein Spieler passt zu deiner Suche.</p>';
  }
  function renderProfile(player) {
    $("stats-title").textContent = player.name;
    $("stats-intro").textContent = "Ein Spieler. Seine ganze Season.";
    document.title = `${player.name} · Statistiken · HalfKnife SMP 2026`;
    const position = C.leaderboard(players, "activeSeconds", players.length).findIndex(entry => entry.uuid === player.uuid);
    $("profile-card").innerHTML = `${avatar(player, true)}<div><span class="stats-kicker">Spielerprofil</span><h2 id="profile-name">${escape(player.name)}</h2>${onlineBadge(player)}</div><div class="stats-profile-rank"><span>Aktive Spielzeit</span><strong>${position < 0 ? "Noch ohne Platzierung" : `Platz #${position + 1}`}</strong></div>`;
    $("profile-totals").innerHTML = [
      tile("Aktive Spielzeit", C.duration(player.summary.activeSeconds), "Ohne AFK-Zeit"),
      tile("Tode", C.integer.format(player.summary.deaths)),
      tile("Blöcke abgebaut", C.integer.format(player.summary.blocksMined)),
      tile("Mobs besiegt", C.integer.format(player.summary.mobKills)),
      tile("Strecke zurückgelegt", C.distance(player.summary.distanceCm)),
      tile("Diamanterz abgebaut", C.integer.format(player.summary.diamondsMined), "Erzblöcke, kein Inventarbestand")
    ].join("");
    const count = C.statRows(player).length;
    $("profile-stat-count").textContent = `${C.integer.format(count)} gespeicherte Werte`;
    const groups = Object.keys(player.stats).filter(key => Object.keys(player.stats[key]).length);
    if (category !== "all" && !groups.includes(category)) category = "all";
    $("profile-categories").innerHTML = `<button type="button" data-category="all" aria-pressed="${category === "all"}">Alle <span>${count}</span></button>` + groups.map(group => `<button type="button" data-category="${escape(group)}" aria-pressed="${category === group}">${escape(C.categoryName(group))} <span>${Object.keys(player.stats[group]).length}</span></button>`).join("");
    renderDetails();
  }
  function renderDetails() {
    if (!selected) return;
    const query = $("stats-detail-search").value;
    const rows = C.statRows(selected, query, category, $("stats-detail-sort").value);
    $("profile-search-result").textContent = `${C.integer.format(rows.length)} passende Werte`;
    if (!rows.length) {
      $("profile-details").innerHTML = `<p class="stats-empty">${C.statRows(selected).length ? "Keine Statistik passt zu diesem Filter." : "Für diesen Spieler sind noch keine Minecraft-Statistiken gespeichert. Neue Werte erscheinen nach dem nächsten Datenabruf."}</p>`;
      return;
    }
    const groups = new Map();
    for (const row of rows) {
      if (!groups.has(row.category)) groups.set(row.category, []);
      groups.get(row.category).push(row);
    }
    $("profile-details").innerHTML = Array.from(groups, ([group, entries]) => `<section class="stats-detail-group"><h3>${escape(C.categoryName(group))}<span>${entries.length}</span></h3><div class="stats-detail-table-wrap"><table class="stats-detail-table"><caption class="stats-sr-only">${escape(C.categoryName(group))}: Statistik und Wert</caption><thead><tr><th scope="col">Statistik</th><th scope="col">Wert</th></tr></thead><tbody>${entries.map(row => `<tr><th scope="row">${escape(row.label)}<small>${escape(row.key)}</small></th><td>${escape(row.formatted)}</td></tr>`).join("")}</tbody></table></div></section>`).join("");
  }
  async function json(url) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(url, { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } finally { window.clearTimeout(timeout); }
  }
  async function load(background = false) {
    if (loading) return;
    loading = true;
    $("stats-refresh").disabled = true;
    $("stats-refresh").textContent = "Wird geladen…";
    const silent = background === true && Boolean(data);
    $("stats-retry").hidden = true;
    if (!silent) {
      $("stats-message").hidden = false;
      $("stats-message").textContent = "Die Serverstatistiken werden geladen…";
    }
    try {
      const token = Date.now();
      const [snapshot, status, whitelist] = await Promise.all([
        json(`${BASE}statistics.json?v=${token}`),
        json(`${BASE}server-status.json?v=${token}`).catch(() => null),
        json(`${BASE}whitelist.json?v=${token}`)
      ]);
      if (snapshot.schema !== 1 || !Array.isArray(snapshot.players) || !snapshot.players.every(C.validPlayer)) throw new Error("Ungültige Statistikdaten");
      data = snapshot;
      C.setTranslations(data.labels);
      players = C.reconcileWhitelist(data.players, whitelist);
      online = status && status.online && Array.isArray(status.players) ? new Set(status.players.filter(p => typeof p === "string").map(p => p.toLowerCase())) : status && status.online === false ? new Set() : null;
      const age = Date.now() - new Date(data.updatedAt).getTime();
      $("stats-status").textContent = `Datenstand: ${timestamp(data.updatedAt)} Uhr${age > 30 * 60 * 1000 ? " · Aktualisierung verzögert" : ""}`;
      $("stats-active-status").textContent = data.activeMode === "active"
        ? `Aktive Spielzeit: Datenstand ${timestamp(data.activeUpdatedAt)} Uhr.`
        : "Die aktive Spielzeit wartet noch auf den Serverneustart mit der neuen AFK-Erkennung. Bis dahin wird keine Gesamtspielzeit als aktive Zeit ausgegeben.";
      const lookup = new URLSearchParams(window.location.search).get("player");
      selected = lookup ? players.find(p => p.uuid.toLowerCase() === lookup.toLowerCase() || p.name.toLowerCase() === lookup.toLowerCase()) : null;
      if (lookup && !selected) {
        $("stats-message").hidden = false;
        $("stats-overview").hidden = true;
        $("stats-profile").hidden = true;
        $("stats-message").innerHTML = 'Dieser Spieler ist nicht in der aktuellen Whitelist enthalten. <a href="stats.html">Zur Statistikübersicht</a>';
        $("stats-title").textContent = "Spieler nicht gefunden";
        return;
      }
      $("stats-message").hidden = true;
      $("stats-overview").hidden = Boolean(selected);
      $("stats-profile").hidden = !selected;
      $("stats-explanation").hidden = false;
      if (selected) renderProfile(selected); else renderOverview();
    } catch (error) {
      if (silent) {
        $("stats-status").textContent = `Datenstand: ${timestamp(data.updatedAt)} Uhr · Aktualisierung gerade nicht möglich`;
        return;
      }
      $("stats-message").textContent = "Die Statistiken sind gerade nicht verfügbar. Bitte versuche es gleich noch einmal.";
      $("stats-status").textContent = "Datenabruf gerade nicht möglich";
      $("stats-retry").hidden = false;
    } finally {
      loading = false;
      $("stats-refresh").disabled = false;
      $("stats-refresh").textContent = "Daten aktualisieren";
    }
  }
  document.addEventListener("DOMContentLoaded", () => {
    $("stats-refresh").addEventListener("click", () => load(true));
    $("stats-retry").addEventListener("click", load);
    $("stats-player-search").addEventListener("input", renderPlayers);
    $("stats-player-sort").addEventListener("change", renderPlayers);
    $("stats-detail-search").addEventListener("input", renderDetails);
    $("stats-detail-sort").addEventListener("change", renderDetails);
    $("profile-categories").addEventListener("click", event => {
      const button = event.target.closest("button[data-category]");
      if (!button) return;
      category = button.dataset.category;
      for (const item of $("profile-categories").querySelectorAll("button")) item.setAttribute("aria-pressed", String(item === button));
      renderDetails();
    });
    load();
    window.setInterval(() => { if (!document.hidden) load(true); }, 60 * 1000);
  });
})();

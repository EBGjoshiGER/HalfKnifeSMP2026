(() => {
  "use strict";
  const root = document.getElementById("nether-project");
  if (!root) return;
  const byId = id => document.getElementById(id);
  const format = new Intl.NumberFormat("de-DE");
  const statusLabels = {
    not_started: "Noch nicht gestartet",
    active: "Projekt aktiv",
    paused: "Projekt pausiert",
    completed: "Projekt abgeschlossen"
  };
  const local = ["localhost", "127.0.0.1", ""].includes(location.hostname);
  // Raw repository data updates independently of the GitHub Pages build.
  const endpoint = local ? "data/nether-project.json" : root.dataset.source;
  let current = null;
  let busy = false;
  let failed = false;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function validate(data) {
    const integer = n => Number.isSafeInteger(n) && n >= 0;
    if (!data || data.schemaVersion !== 1 || !Object.hasOwn(statusLabels, data.status) ||
        !Number.isFinite(Date.parse(data.syncedAt)) || !Array.isArray(data.resources) ||
        !data.resources.length || !Array.isArray(data.leaderboard)) throw Error("Ungültige Projektdaten");
    for (const resource of data.resources) {
      if (typeof resource.name !== "string" || !integer(resource.donated) ||
          !integer(resource.required) || resource.required === 0) throw Error("Ungültige Ressourcen");
    }
    for (const player of data.leaderboard) {
      if (typeof player.name !== "string" || !integer(player.points) ||
          !integer(player.rank) || player.rank === 0) throw Error("Ungültige Rangliste");
    }
    return data;
  }

  function showSyncState() {
    const message = byId("nether-sync");
    if (!current) {
      message.textContent = failed ? "Projektdaten gerade nicht verfügbar. Wir versuchen es automatisch erneut." : "Projektstand wird geladen …";
      message.dataset.warning = String(failed);
      return;
    }
    const stale = Date.now() - Date.parse(current.syncedAt) > 30 * 60 * 1000;
    const stamp = new Date(current.syncedAt).toLocaleString("de-DE");
    message.textContent = `${failed ? "Aktualisierung fehlgeschlagen · Letzter bekannter Stand" : stale ? "Älterer Datenstand · Zuletzt synchronisiert" : "Zuletzt synchronisiert"}: ${stamp}`;
    message.dataset.warning = String(stale || failed);
  }

  function render(data) {
    const status = byId("nether-status");
    status.textContent = statusLabels[data.status];
    status.dataset.state = data.status;
    const done = data.resources.filter(item => item.donated >= item.required).length;
    byId("nether-goals").textContent = `${done} / ${data.resources.length} Ressourcenziele erfüllt`;
    byId("nether-donors").textContent = `${format.format(data.leaderboard.length)} Mitwirkende`;
    const resources = document.createDocumentFragment();
    for (const item of data.resources) {
      const card = node("div", "nether-resource");
      const heading = node("div", "nether-resource-heading");
      heading.append(node("span", "", item.name), node("strong", "", `${format.format(item.donated)} / ${format.format(item.required)}`));
      const progress = node("progress", "nether-meter");
      progress.max = item.required;
      progress.value = Math.min(item.donated, item.required);
      progress.setAttribute("aria-label", `${item.name}: ${format.format(item.donated)} von ${format.format(item.required)}`);
      const percent = Math.min(100, item.donated / item.required * 100);
      const label = percent >= 100 ? "Ziel erreicht" : `${format.format(Math.floor(percent * 10) / 10)} % · ${format.format(Math.max(0, item.required - item.donated))} fehlen`;
      card.dataset.complete = String(item.donated >= item.required);
      card.append(heading, progress, node("span", "nether-resource-note", label));
      resources.append(card);
    }
    byId("nether-resources").replaceChildren(resources);
    const rows = document.createDocumentFragment();
    for (const player of data.leaderboard) {
      const row = node("tr");
      row.dataset.rank = String(player.rank);
      row.append(node("td", "nether-rank", String(player.rank)), node("td", "nether-player", player.name), node("td", "nether-points", format.format(player.points)));
      rows.append(row);
    }
    byId("nether-leaderboard-body").replaceChildren(rows);
    byId("nether-leaderboard-table").hidden = data.leaderboard.length === 0;
    byId("nether-empty").hidden = data.leaderboard.length !== 0;
    byId("nether-empty").textContent = "Noch keine Einzahlungen. Die ersten Beiträge erscheinen hier nach der nächsten Synchronisierung.";
  }

  async function refresh() {
    if (busy) return;
    busy = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const url = new URL(endpoint, location.href);
      url.searchParams.set("v", String(Date.now()));
      const response = await fetch(url, { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      const next = validate(await response.json());
      render(next);
      current = next;
      failed = false;
    } catch (error) {
      failed = true;
      if (!current) {
        byId("nether-status").textContent = "Status nicht verfügbar";
        byId("nether-goals").textContent = "Fortschritt nicht verfügbar";
        byId("nether-resources").replaceChildren(node("p", "nether-empty", "Der Ressourcenstand ist gerade nicht verfügbar."));
        byId("nether-empty").textContent = "Die Rangliste ist gerade nicht verfügbar.";
      }
      console.warn("Nether-Projekt konnte nicht aktualisiert werden:", error);
    } finally {
      clearTimeout(timeout);
      busy = false;
      showSyncState();
    }
  }

  refresh();
  setInterval(() => {
    showSyncState();
    if (!document.hidden) refresh();
  }, 60000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
})();

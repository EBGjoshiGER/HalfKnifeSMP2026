const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const C = require("../js/stats-core.js");
const ids = ["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"];
const alice = { uuid: ids[0], name: "Alice", hasStats: true,
  summary: { activeSeconds: 3600, totalSeconds: 7200, deaths: 3, blocksMined: 105, mobKills: 5, distanceCm: 300000, diamondsMined: 5, totemsUsed: 2, itemsCrafted: 8, elytraCm: 0 },
  stats: { "minecraft:custom": { "minecraft:play_time": 144000, "minecraft:damage_dealt": 50, "minecraft:walk_one_cm": 100000, "ras:levels_gained": 12 }, "minecraft:mined": { "minecraft:stone": 100, "minecraft:diamond_ore": 3 } } };
const bob = { uuid: ids[1], name: "Bob", hasStats: false, summary: { ...alice.summary, activeSeconds: 0, deaths: 0, blocksMined: 0, mobKills: 0, distanceCm: 0, diamondsMined: 0 }, stats: {} };
assert(C.validPlayer(alice));
assert.deepEqual(C.leaderboard([bob, alice], "activeSeconds").map(p => p.name), ["Alice"]);
assert.deepEqual(C.leaderboard([{ ...alice, summary: { activeSeconds: null } }], "activeSeconds"), []);
assert.equal(C.totals([alice, bob], "active").activeSeconds, 3600);
assert.equal(C.totals([alice, bob], "pending").activeSeconds, null);
assert.equal(C.rawValue("minecraft:custom", "minecraft:play_time", 144000), "2 Std. 0 Min.");
assert.equal(C.rawValue("minecraft:custom", "minecraft:walk_one_cm", 100000), "1 km");
assert.equal(C.rawValue("minecraft:custom", "minecraft:damage_dealt", 50), "5 LP");
assert.equal(C.statRows(alice, "Diamant").length, 1);
assert.equal(C.statRows(alice, "ras:")[0].key, "ras:levels_gained");
assert.equal(C.statRows(alice, "", "minecraft:mined").length, 2);
assert.equal(C.sortPlayers([alice, bob], "BO", "name")[0].name, "Bob");

async function mount(search = "", fail = false, whitelist = [alice, bob]) {
  const markup = fs.readFileSync(require.resolve("../stats.html"), "utf8");
  const elements = {};
  for (const match of markup.matchAll(/id="([^"]+)"/g)) elements[match[1]] = {
    value: "", hidden: false, textContent: "", innerHTML: "", handlers: {},
    addEventListener(name, callback) { this.handlers[name] = callback; }, querySelectorAll() { return []; }
  };
  elements["stats-player-sort"].value = "activeSeconds";
  elements["stats-detail-sort"].value = "value";
  const document = { title: "", getElementById: id => elements[id], addEventListener(name, callback) { this.ready = callback; } };
  const snapshot = { schema: 1, updatedAt: new Date().toISOString(), activeMode: "active", activeUpdatedAt: new Date().toISOString(), players: [alice, bob] };
  const window = { HalfKnifeStats: C, location: { search }, setTimeout, clearTimeout, setInterval() {} };
  const context = { window, document, Date, URLSearchParams, AbortController, console,
    fetch: async url => ({ ok: !fail, status: fail ? 503 : 200, json: async () => url.includes("whitelist") ? whitelist : url.includes("server-status") ? { online: true, players: ["Alice"] } : snapshot }) };
  vm.runInNewContext(fs.readFileSync(require.resolve("../js/stats.js"), "utf8"), context);
  document.ready();
  await new Promise(resolve => setImmediate(resolve));
  return { elements, document };
}
(async () => {
  let { elements: e } = await mount();
  assert.equal(e["stats-overview"].hidden, false);
  assert(e["stats-leaderboards"].innerHTML.includes(`stats.html?player=${ids[0]}`));
  assert(e["stats-player-grid"].innerHTML.includes("Online"));
  e["stats-player-search"].value = "BOB"; e["stats-player-search"].handlers.input();
  assert(e["stats-player-grid"].innerHTML.includes("Bob"));
  assert(!e["stats-player-grid"].innerHTML.includes("Alice"));
  const profile = await mount(`?player=${ids[0]}`); e = profile.elements;
  assert.equal(e["stats-profile"].hidden, false);
  assert(profile.document.title.startsWith("Alice"));
  assert(e["profile-details"].innerHTML.includes("ras:levels_gained"));
  e["stats-detail-search"].value = "Diamant"; e["stats-detail-search"].handlers.input();
  assert(e["profile-details"].innerHTML.includes("minecraft:diamond_ore"));
  assert(!e["profile-details"].innerHTML.includes("minecraft:play_time"));
  const emptyProfile = await mount("?player=Bob");
  assert(emptyProfile.elements["profile-details"].innerHTML.includes("noch keine Minecraft-Statistiken"));
  const unknown = await mount("?player=Unknown");
  assert.equal(unknown.elements["stats-title"].textContent, "Spieler nicht gefunden");
  const added = { uuid: "00000000-0000-0000-0000-000000000003", name: "NewPlayer" };
  const testAccount = { uuid: "2f4bd5e2-e184-43af-8ab5-df7670dbc530", name: "FuturePending" };
  const roster = C.reconcileWhitelist([alice, bob], [alice, added, testAccount]);
  assert.deepEqual(roster.map(p => p.name), ["Alice", "NewPlayer"]);
  assert.equal(roster[0].stats, alice.stats);
  assert.equal(roster[1].pendingStats, true);
  assert.equal(C.totals(roster, "active").activeSeconds, 3600);
  assert.deepEqual(C.leaderboard(roster, "activeSeconds").map(p => p.name), ["Alice"]);
  assert.equal(C.reconcileWhitelist([alice], [{ ...alice, name: "Renamed" }])[0].name, "Renamed");
  assert.throws(() => C.reconcileWhitelist([alice], {}));
  const newProfile = await mount("?player=NewPlayer", false, [alice, added, testAccount]);
  assert.equal(newProfile.elements["stats-profile"].hidden, false);
  assert(newProfile.document.title.startsWith("NewPlayer"));
  assert(newProfile.elements["profile-details"].innerHTML.includes("noch keine Minecraft-Statistiken"));
  const fresh = await mount("", false, [alice]);
  assert(!fresh.elements["stats-player-grid"].innerHTML.includes("Bob"));
  await fresh.elements["stats-refresh"].handlers.click();
  assert.equal(fresh.elements["stats-refresh"].disabled, false);
  const failed = await mount("", true);
  assert.equal(failed.elements["stats-retry"].hidden, false);
  assert(failed.elements["stats-message"].textContent.includes("nicht verfügbar"));
  console.log("Stats: active-only rankings, units, category/search filters, overview, profile deep links, empty profiles and fetch errors passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });

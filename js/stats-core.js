(function (root) {
  "use strict";
  const number = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 });
  const integer = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });
  const categories = {
    "minecraft:custom": "Allgemein", "minecraft:mined": "Blöcke abgebaut",
    "minecraft:crafted": "Hergestellt", "minecraft:used": "Benutzt",
    "minecraft:broken": "Zerbrochen", "minecraft:picked_up": "Aufgesammelt",
    "minecraft:dropped": "Fallen gelassen", "minecraft:killed": "Kreaturen besiegt",
    "minecraft:killed_by": "Getötet durch"
  };
  const labels = {
    play_time: "Gesamte Spielzeit · inklusive AFK", play_one_minute: "Gesamte Spielzeit · inklusive AFK",
    total_world_time: "Zeit in der Welt", time_since_death: "Zeit seit dem letzten Tod",
    time_since_rest: "Zeit seit dem letzten Schlaf", sneak_time: "Zeit geschlichen",
    deaths: "Tode", mob_kills: "Mobs besiegt", player_kills: "Spieler besiegt", jump: "Sprünge",
    damage_dealt: "Schaden ausgeteilt", damage_taken: "Schaden erlitten",
    damage_blocked_by_shield: "Schaden mit Schild geblockt", damage_absorbed: "Schaden absorbiert",
    damage_resisted: "Schaden widerstanden", damage_dealt_absorbed: "Absorbierter Schaden ausgeteilt",
    damage_dealt_resisted: "Widerstandener Schaden ausgeteilt", animals_bred: "Tiere gezüchtet",
    fish_caught: "Fische gefangen", talked_to_villager: "Mit Dorfbewohnern gesprochen",
    traded_with_villager: "Mit Dorfbewohnern gehandelt", leave_game: "Spiel verlassen",
    sleep_in_bed: "Im Bett geschlafen", enchant_item: "Gegenstände verzaubert",
    eat_cake_slice: "Kuchenstücke gegessen", open_chest: "Truhen geöffnet",
    open_enderchest: "Endertruhen geöffnet", open_barrel: "Fässer geöffnet",
    open_shulker_box: "Shulkerkisten geöffnet", inspect_dispenser: "Werfer geöffnet",
    inspect_dropper: "Spender geöffnet", inspect_hopper: "Trichter geöffnet",
    interact_with_crafting_table: "Werkbank benutzt", interact_with_furnace: "Ofen benutzt",
    interact_with_blast_furnace: "Schmelzofen benutzt", interact_with_smoker: "Räucherofen benutzt",
    interact_with_anvil: "Amboss benutzt", interact_with_beacon: "Leuchtfeuer benutzt",
    interact_with_brewingstand: "Braustand benutzt", interact_with_grindstone: "Schleifstein benutzt",
    interact_with_smithing_table: "Schmiedetisch benutzt", interact_with_stonecutter: "Steinsäge benutzt",
    interact_with_loom: "Webstuhl benutzt", interact_with_cartography_table: "Kartentisch benutzt",
    walk_one_cm: "Zu Fuß", sprint_one_cm: "Gesprintet", crouch_one_cm: "Geschlichen",
    swim_one_cm: "Geschwommen", fall_one_cm: "Gefallen", climb_one_cm: "Geklettert",
    fly_one_cm: "Geflogen", aviate_one_cm: "Mit Elytra geflogen", boat_one_cm: "Mit Boot gefahren",
    minecart_one_cm: "Mit Lore gefahren", horse_one_cm: "Auf Pferden geritten",
    pig_one_cm: "Auf Schweinen geritten", strider_one_cm: "Auf Schreitschreitern geritten",
    walk_on_water_one_cm: "Auf dem Wasser bewegt", walk_under_water_one_cm: "Unter Wasser bewegt",
    drop: "Gegenstände fallen gelassen", bell_ring: "Glocke geläutet", raid_trigger: "Überfälle ausgelöst",
    raid_win: "Überfälle gewonnen", target_hit: "Zielblöcke getroffen", pot_flower: "Blumen eingetopft",
    clean_armor: "Lederrüstung gewaschen", clean_banner: "Banner gewaschen", fill_cauldron: "Kessel gefüllt",
    use_cauldron: "Kessel benutzt", play_record: "Schallplatten abgespielt", trigger_trapped_chest: "Redstone-Truhen geöffnet",
    stone: "Stein", cobblestone: "Bruchstein", deepslate: "Tiefenschiefer", dirt: "Erde", grass_block: "Grasblock",
    sand: "Sand", gravel: "Kies", netherrack: "Netherrack", end_stone: "Endstein", obsidian: "Obsidian",
    oak_log: "Eichenstamm", spruce_log: "Fichtenstamm", birch_log: "Birkenstamm", bamboo: "Bambus",
    diamond: "Diamant", diamond_ore: "Diamanterz", deepslate_diamond_ore: "Tiefenschiefer-Diamanterz",
    iron_ore: "Eisenerz", deepslate_iron_ore: "Tiefenschiefer-Eisenerz", coal_ore: "Steinkohle",
    gold_ore: "Golderz", copper_ore: "Kupfererz", emerald_ore: "Smaragderz", ancient_debris: "Antiker Schrott",
    totem_of_undying: "Totem der Unsterblichkeit", elytra: "Elytra", bread: "Brot", cooked_beef: "Steak",
    cooked_porkchop: "Gebratenes Schweinefleisch", golden_carrot: "Goldene Karotte", apple: "Apfel",
    diamond_pickaxe: "Diamantspitzhacke", netherite_pickaxe: "Netheritspitzhacke", iron_pickaxe: "Eisenspitzhacke",
    diamond_sword: "Diamantschwert", netherite_sword: "Netheritschwert", torch: "Fackel", stick: "Stock",
    zombie: "Zombie", skeleton: "Skelett", creeper: "Creeper", spider: "Spinne", enderman: "Enderman",
    ender_dragon: "Enderdrache", wither: "Wither", warden: "Wärter", piglin: "Piglin", blaze: "Lohe",
    ghast: "Ghast", slime: "Schleim", cow: "Kuh", sheep: "Schaf", chicken: "Huhn", pig: "Schwein",
    villager: "Dorfbewohner", iron_golem: "Eisengolem", player: "Spieler", drowned: "Ertrunkener"
  };
  const timeStats = new Set(["play_time", "play_one_minute", "total_world_time", "time_since_death", "time_since_rest", "sneak_time"]);
  let translations = {};
  function setTranslations(values) {
    translations = values && typeof values === "object" ? values : {};
  }
  function duration(seconds) {
    if (!Number.isFinite(seconds)) return "–";
    const minutes = Math.floor(seconds / 60);
    if (seconds > 0 && minutes === 0) return "< 1 Min.";
    return `${integer.format(Math.floor(minutes / 60))} Std. ${minutes % 60} Min.`;
  }
  function distance(cm) {
    return cm >= 100000 ? `${number.format(cm / 100000)} km` : `${number.format(cm / 100)} m`;
  }
  function readable(id) {
    const name = id.split(":").pop();
    const translated = typeof translations[id] === "string" ? translations[id] : null;
    const text = (id.startsWith("minecraft:") ? labels[name] : null) || translated || name.replaceAll("_", " ").replaceAll("/", " · ");
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
  function categoryName(id) { return categories[id] || readable(id); }
  function rawValue(category, key, value) {
    const name = key.split(":").pop();
    if (category === "minecraft:custom" && key.startsWith("minecraft:")) {
      if (timeStats.has(name)) return duration(value / 20);
      if (name.endsWith("_one_cm")) return distance(value);
      if (name.startsWith("damage_")) return `${number.format(value / 10)} LP`;
    }
    return integer.format(value);
  }
  const metrics = [
    { key: "activeSeconds", title: "Dauerzocker", caption: "Aktive Spielzeit · ohne AFK", icon: "◷", format: duration },
    { key: "deaths", title: "Respawn-Stammgäste", caption: "Die meisten Tode", icon: "☠", format: v => integer.format(v) },
    { key: "blocksMined", title: "Abrisskommando", caption: "Die meisten Blöcke abgebaut", icon: "⛏", format: v => integer.format(v) },
    { key: "mobKills", title: "Auf der Jagd", caption: "Die meisten Mobs besiegt", icon: "⚔", format: v => integer.format(v) },
    { key: "distanceCm", title: "Immer unterwegs", caption: "Zurückgelegte Strecke", icon: "↗", format: distance },
    { key: "diamondsMined", title: "Glück unter Tage", caption: "Diamanterz-Blöcke abgebaut", icon: "◆", format: v => integer.format(v) },
    { key: "totemsUsed", title: "Noch ein Leben", caption: "Totems der Unsterblichkeit benutzt", icon: "✦", format: v => integer.format(v) },
    { key: "itemsCrafted", title: "Werkbank-Crew", caption: "Gegenstände hergestellt", icon: "▦", format: v => integer.format(v) },
    { key: "elytraCm", title: "Überflieger", caption: "Strecke mit der Elytra", icon: "⌁", format: distance }
  ];
  function validPlayer(player) {
    return player && /^[A-Za-z0-9_]{1,16}$/.test(player.name) && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(player.uuid)
      && player.summary && player.stats && typeof player.stats === "object";
  }
  function leaderboard(players, key, limit = 10) {
    return players.filter(player => Number.isFinite(player.summary[key]) && player.summary[key] > 0)
      .slice().sort((a, b) => b.summary[key] - a.summary[key] || a.name.localeCompare(b.name, "de"))
      .slice(0, limit);
  }
  function sortPlayers(players, query, sort) {
    const filtered = players.filter(player => player.name.toLowerCase().includes(query.trim().toLowerCase()));
    if (sort === "name") return filtered.sort((a, b) => a.name.localeCompare(b.name, "de"));
    return filtered.sort((a, b) => (b.summary[sort] ?? -1) - (a.summary[sort] ?? -1) || a.name.localeCompare(b.name, "de"));
  }
  function statRows(player, query = "", category = "all", sort = "value") {
    const term = query.trim().toLowerCase();
    const rows = [];
    for (const [group, entries] of Object.entries(player.stats)) {
      if (category !== "all" && category !== group) continue;
      for (const [key, value] of Object.entries(entries)) {
        if (!Number.isFinite(value) || value < 0) continue;
        const label = readable(key);
        if (term && !`${label} ${key} ${categoryName(group)} ${group}`.toLowerCase().includes(term)) continue;
        rows.push({ category: group, key, value, label, formatted: rawValue(group, key, value) });
      }
    }
    return rows.sort((a, b) => a.category.localeCompare(b.category) ||
      (sort === "name" ? a.label.localeCompare(b.label, "de") : b.value - a.value || a.label.localeCompare(b.label, "de")));
  }
  function totals(players, activeMode) {
    const result = { players: players.filter(p => p.hasStats || (p.summary.activeSeconds ?? 0) > 0).length };
    for (const key of ["activeSeconds", "deaths", "blocksMined", "mobKills", "distanceCm"])
      result[key] = key === "activeSeconds" && activeMode !== "active" ? null : players.reduce((sum, p) => sum + (p.summary[key] ?? 0), 0);
    return result;
  }
  const api = { metrics, categories, categoryName, duration, distance, readable, rawValue, validPlayer, leaderboard, sortPlayers, statRows, totals, integer, number, setTranslations };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.HalfKnifeStats = api;
})(typeof window !== "undefined" ? window : globalThis);

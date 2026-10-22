package de.halfknife.playtime;

import com.google.gson.*;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.scores.ScoreHolder;
import de.halfknife.playtime.mixin.PlayerListAccessor;

import java.lang.reflect.*;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

/** Explicit adapters for the installed versions. No player NBT or RAS state is written. */
final class ConsoleReset {
    private static final Gson JSON = new GsonBuilder().setPrettyPrinting().create();
    private static final Set<String> DUMMY_STATS = Set.of("hk.active_ticks", "playtime", "playtime_hours", "deaths", "kills", "tab_info");
    private static boolean busy;

    static void register() {
        CommandRegistrationCallback.EVENT.register((dispatcher, registry, environment) -> {
            var all = Commands.literal("all").executes(ctx -> run(ctx.getSource(), false))
                .then(Commands.literal("confirm").executes(ctx -> run(ctx.getSource(), true)));
            dispatcher.register(Commands.literal("halfknife")
                .requires(source -> source.source == source.getServer())
                .then(Commands.literal("reset").then(all)));
        });
    }

    private static int run(CommandSourceStack source, boolean confirm) {
        if (busy) { source.sendFailure(Component.literal("Ein Reset laeuft bereits.")); return 0; }
        busy = true;
        try {
            MinecraftServer server = source.getServer();
            if (!server.getPlayerList().getPlayers().isEmpty())
                throw new IllegalStateException("Bitte zuerst alle Spieler ausloggen lassen.");
            Plan plan = prepare(server);
            if (!confirm) {
                source.sendSuccess(() -> Component.literal("RESET-VORSCHAU: " + plan.files.size() + " Dateien; " + plan.scores.size()
                    + " Scorewerte. Alle gespeicherten Spieler, auch ausserhalb der Whitelist. Vanilla-/Mod-Statistiken, Fortschritte ausser RAS, Aktiv/AFK, Playtime Rewards und Quiz; persoenliche Nether/End-Beitraege. RAS, Inventare, Welt, Projekt-Gesamtfortschritt und Statuen bleiben. Ausfuehren: halfknife reset all confirm"), false);
                return 1;
            }
            Path backup = plan.execute();
            // Leaderboards pull from the new sources on their normal 30-second refresh.
            source.sendSuccess(() -> Component.literal("HALFKNIFE RESET OK. Sicherung: " + backup
                + ". RAS unveraendert. Spielzeit-Raenge: 0; verwaltete LuckPerms-Raenge werden beim naechsten Login abgeglichen. Website folgt beim naechsten Sync."), false);
            return 1;
        } catch (Exception error) {
            source.sendFailure(Component.literal("RESET ABGEBROCHEN: " + error.getMessage()));
            org.slf4j.LoggerFactory.getLogger("HalfKnife Reset").error("Console reset failed", error);
            return 0;
        } finally { busy = false; }
    }

    private static Plan prepare(MinecraftServer server) throws Exception {
        Path world = server.getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();
        Plan p = new Plan(server, world);
        Path activePath = world.resolve("config/halfknife-active-playtime/playtime.json");
        if (Files.exists(activePath.resolveSibling("reset-request.json")))
            throw new IllegalStateException("Ein GitHub-Reset wartet noch. Diesen zuerst abschliessen.");
        Object active = entrypoint("de.halfknife.playtime.ActivePlaytimeMod");
        if (get(active, "output") == null) throw new IllegalStateException("Aktivzeit noch nicht geladen.");
        JsonObject activeData = object(activePath);
        for (JsonElement e : activeData.getAsJsonArray("players")) {
            e.getAsJsonObject().addProperty("activeMillis", 0);
            e.getAsJsonObject().addProperty("afkMillis", 0);
        }
        activeData.addProperty("updatedAt", Instant.now().toString());
        p.json(activePath, activeData);
        for (Object record : map(active, "totals").values()) {
            p.field(record, "activeMillis", 0L); p.field(record, "afkMillis", 0L);
        }
        if (!map(active, "sessions").isEmpty()) throw new IllegalStateException("Aktive Sitzungen vorhanden.");

        // Read and transform every player, not just @a / the whitelist. Preserve RAS namespaces.
        for (String folder : List.of("stats", "players/stats", "advancements", "players/advancements")) {
            Path dir = world.resolve(folder);
            if (!Files.exists(dir)) continue;
            try (var paths = Files.list(dir)) {
                for (Path file : paths.filter(f -> f.toString().endsWith(".json")).sorted().toList()) {
                    UUID.fromString(file.getFileName().toString().replace(".json", ""));
                    JsonObject data = object(file);
                    if (folder.endsWith("stats")) {
                        JsonObject stats = data.getAsJsonObject("stats");
                        if (stats != null) for (String type : new ArrayList<>(stats.keySet())) {
                            if (ras(type)) continue;
                            JsonObject values = stats.getAsJsonObject(type);
                            for (String key : new ArrayList<>(values.keySet())) if (!ras(key)) values.addProperty(key, 0);
                        }
                    } else {
                        for (String key : new ArrayList<>(data.keySet()))
                            if (!key.equals("DataVersion") && !ras(key)) data.remove(key);
                    }
                    p.json(file, data);
                }
            }
        }
        p.clearMap(((PlayerListAccessor)server.getPlayerList()).halfknife$getStats());
        p.clearMap(((PlayerListAccessor)server.getPlayerList()).halfknife$getAdvancements());
        var scoreboard = server.getScoreboard();
        for (var objective : scoreboard.getObjectives()) {
            String name = objective.getName();
            String criterion = objective.getCriteria().getName();
            if (ras(name) || ras(criterion)) continue;
            if (!(DUMMY_STATS.contains(name) || criterion.startsWith("minecraft.")
                    || Set.of("deathCount", "playerKillCount", "totalKillCount").contains(criterion))) continue;
            for (ScoreHolder holder : new ArrayList<>(scoreboard.getTrackedPlayers())) {
                if (holder.getScoreboardName().startsWith("#")) continue; // Tab's divisor/mode constants
                var score = scoreboard.getPlayerScoreInfo(holder, objective);
                if (score != null) {
                    int old = score.value();
                    p.scores.add(Map.of("holder", holder.getScoreboardName(), "objective", name, "value", old));
                    p.change(() -> scoreboard.getOrCreatePlayerScore(holder, objective).set(0),
                             () -> scoreboard.getOrCreatePlayerScore(holder, objective).set(old));
                }
            }
        }
        if (installed("playtime_rewards", "1.7.3")) {
            Object rewards = entrypoint("com.sovern.playtimerewards.PlaytimeRewardsMod");
            Path dir = (Path)get(rewards, "dataDirectory");
            if (dir == null) throw new IllegalStateException("Playtime Rewards noch nicht geladen.");
            StringBuilder tsv = new StringBuilder("# uuid\\tname\\tseconds\\trankIndex\\timportedVanilla\\tclaimedRewards\n");
            for (Object record : map(rewards, "records").values()) {
                p.field(record, "seconds", 0L); p.field(record, "rankIndex", -1); p.field(record, "importedVanilla", true);
                p.clearSet((Set<?>)get(record, "claimedRewards"));
                String name = get(record, "name").toString().replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n");
                tsv.append(get(record, "uuid")).append('\t').append(name).append("\t0\t-1\ttrue\t\n");
            }
            p.put(dir.resolve("players.tsv"), tsv.toString());
        }
        if (installed("halfknifequiz", "1.0.0")) {
            Class<?> mod = Class.forName("de.halfknife.quiz.HalfKnifeQuizMod");
            Object manager = mod.getMethod("quizManager").invoke(null);
            if ((boolean)manager.getClass().getMethod("hasActiveSession").invoke(manager))
                throw new IllegalStateException("Bitte zuerst das laufende Quiz beenden.");
            Class<?> stats = Class.forName("de.halfknife.quiz.manager.QuizStatsManager");
            p.clearMap((Map<?,?>)field(stats, "PLAYERS").get(null));
            Path file = server.getWorldPath(LevelResource.DATA).resolve("halfknifequiz/stats.json");
            JsonObject data = object(file);
            data.add("players", new JsonObject());
            p.json(file, data);
        }
        project(p, "netherproject", "2.3.0", "de.halfknife.netherproject", "NetherProjectMod");
        project(p, "endproject", "1.0.0", "de.halfknife.endproject", "EndProjectMod");
        return p;
    }

    private static void project(Plan p, String id, String version, String pkg, String main) throws Exception {
        if (!installed(id, version)) return;
        Object state = field(Class.forName(pkg + "." + main), "STATE").get(null);
        Path file = (Path)Class.forName(pkg + ".ProjectConfig").getMethod("progressFile").invoke(null);
        JsonObject data = JSON.toJsonTree(state).getAsJsonObject();
        for (String name : List.of("playerTotals", "playerPoints", "playerNames")) {
            p.clearMap(map(state, name)); data.add(name, new JsonObject());
        }
        // This is a statistics reset, not a reset of the community unlock event.
        p.json(file, data);
    }

    private static boolean installed(String id, String version) {
        var mod = FabricLoader.getInstance().getModContainer(id);
        if (mod.isEmpty()) return false;
        String actual = mod.get().getMetadata().getVersion().getFriendlyString();
        if (!actual.equals(version)) throw new IllegalStateException(id + " Version " + actual + " nicht geprueft; erwartet " + version);
        return true;
    }
    private static boolean ras(String name) {
        String key = name.toLowerCase(Locale.ROOT);
        return key.contains("rpg_attribute") || key.equals("ras") || key.startsWith("ras_") || key.startsWith("ras:") || key.startsWith("ras.");
    }
    private static Object entrypoint(String name) {
        return FabricLoader.getInstance().getEntrypoints("main", ModInitializer.class).stream()
            .filter(o -> o.getClass().getName().equals(name)).findFirst().orElseThrow(() -> new IllegalStateException("Mod fehlt: " + name));
    }
    private static Field field(Class<?> type, String name) throws Exception { Field f = type.getDeclaredField(name); f.setAccessible(true); return f; }
    private static Object get(Object obj, String name) throws Exception { return field(obj.getClass(), name).get(obj); }
    private static Map<?,?> map(Object obj, String name) throws Exception { return (Map<?,?>)get(obj, name); }
    private static JsonObject object(Path path) throws Exception {
        if (Files.isSymbolicLink(path)) throw new IllegalStateException("Symlink nicht erlaubt: " + path);
        return JsonParser.parseString(Files.readString(path)).getAsJsonObject();
    }
    @FunctionalInterface private interface Action { void run() throws Exception; }
    private record Change(Action apply, Action undo) {}
    private static final class Plan {
        final MinecraftServer server;
        final Path world;
        final Map<Path, String> files = new LinkedHashMap<>();
        final List<Change> changes = new ArrayList<>();
        final List<Map<String,Object>> scores = new ArrayList<>();
        Plan(MinecraftServer server, Path world) { this.server = server; this.world = world; }
        void put(Path file, String data) throws Exception {
            Path absolute = file.toAbsolutePath().normalize();
            Path game = FabricLoader.getInstance().getGameDir().toAbsolutePath().normalize();
            if (!absolute.startsWith(game)) throw new IllegalStateException("Datei ausserhalb Server: " + absolute);
            for (Path parent = absolute; parent != null && parent.startsWith(game); parent = parent.getParent())
                if (Files.isSymbolicLink(parent)) throw new IllegalStateException("Symlink im Reset-Pfad: " + parent);
            files.put(absolute, data);
        }
        void json(Path file, JsonObject data) throws Exception { put(file, JSON.toJson(data) + "\n"); }
        void change(Action apply, Action undo) { changes.add(new Change(apply, undo)); }
        void field(Object target, String name, Object value) throws Exception {
            Field f = ConsoleReset.field(target.getClass(), name); Object old = f.get(target);
            change(() -> f.set(target, value), () -> f.set(target, old));
        }
        @SuppressWarnings({"rawtypes", "unchecked"}) void clearMap(Map map) {
            Map copy = new LinkedHashMap(map); change(map::clear, () -> { map.clear(); map.putAll(copy); });
        }
        @SuppressWarnings({"rawtypes", "unchecked"}) void clearSet(Set set) {
            Set copy = new HashSet(set); change(set::clear, () -> { set.clear(); set.addAll(copy); });
        }
        Path execute() throws Exception {
            Path backup = world.resolve("config/halfknife-active-playtime/reset-backups/console-" + UUID.randomUUID());
            Files.createDirectories(backup);
            Map<Path,byte[]> originals = new LinkedHashMap<>();
            Map<String,String> manifest = new LinkedHashMap<>();
            int index = 0;
            // Finish ALL backups before changing any counter or source file.
            for (Path path : files.keySet()) {
                byte[] original = Files.exists(path) ? Files.readAllBytes(path) : null;
                originals.put(path, original);
                String filename = String.format("%04d.backup", index++);
                if (original != null) Files.write(backup.resolve(filename), original);
                manifest.put(path.toString(), original == null ? "ABSENT" : filename);
            }
            Files.writeString(backup.resolve("manifest.json"), JSON.toJson(manifest));
            Files.writeString(backup.resolve("scoreboard-values.json"), JSON.toJson(scores));
            Files.writeString(backup.resolve("status.txt"), "PREPARED\n");
            List<Change> applied = new ArrayList<>();
            try {
                for (var entry : files.entrySet()) atomic(entry.getKey(), entry.getValue().getBytes(java.nio.charset.StandardCharsets.UTF_8));
                for (Change change : changes) { applied.add(change); change.apply.run(); }
                server.saveEverything(false, true, true);
                for (var entry : files.entrySet())
                    if (!Files.readString(entry.getKey()).equals(entry.getValue())) throw new IllegalStateException("Reset-Datei wurde unerwartet veraendert: " + entry.getKey());
                Files.writeString(backup.resolve("status.txt"), "COMPLETED\nRAS/player NBT untouched.\n");
                return backup;
            } catch (Exception error) {
                Collections.reverse(applied);
                for (Change change : applied) try { change.undo.run(); } catch (Exception e) { error.addSuppressed(e); }
                for (var entry : originals.entrySet()) try {
                    if (entry.getValue() == null) Files.deleteIfExists(entry.getKey()); else atomic(entry.getKey(), entry.getValue());
                } catch (Exception e) { error.addSuppressed(e); }
                try { server.saveEverything(false, true, true); } catch (Exception e) { error.addSuppressed(e); }
                Files.writeString(backup.resolve("status.txt"), "FAILED; rollback attempted; check server log.\n");
                throw new IllegalStateException("Fehler; Wiederherstellung versucht. Sicherung: " + backup, error);
            }
        }
    }
    private static void atomic(Path target, byte[] data) throws Exception {
        Files.createDirectories(target.getParent());
        Path temporary = Files.createTempFile(target.getParent(), ".halfknife-reset-", ".tmp");
        try {
            Files.write(temporary, data);
            try { Files.move(temporary, target, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING); }
            catch (AtomicMoveNotSupportedException e) { Files.move(temporary, target, StandardCopyOption.REPLACE_EXISTING); }
        } finally { Files.deleteIfExists(temporary); }
    }
}

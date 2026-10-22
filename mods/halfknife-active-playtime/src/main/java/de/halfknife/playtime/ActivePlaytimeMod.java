package de.halfknife.playtime;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.event.player.*;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.scores.ScoreHolder;
import net.minecraft.world.scores.criteria.ObjectiveCriteria;
import de.halfknife.playtime.mixin.PlayerListAccessor;
import de.halfknife.playtime.mixin.StatsCounterAccessor;
import com.google.gson.JsonParser;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

public final class ActivePlaytimeMod implements ModInitializer {
    private static final Logger LOG = LoggerFactory.getLogger("HalfKnife Active Playtime");
    private static final Gson JSON = new GsonBuilder().setPrettyPrinting().create();
    private static ActivePlaytimeMod instance;
    private final Map<UUID, Totals> totals = new HashMap<>();
    private final Map<UUID, ActiveClock> sessions = new HashMap<>();
    private Path output;
    private long lastSave;
    public static final String ACTIVE_OBJECTIVE = "hk.active_ticks";
    private MinecraftServer activeServer;
    private Map<UUID, String> whitelistNames = Map.of();
    private long whitelistChecked;
    private long resetChecked;
    private final Set<String> processedResetIds = new LinkedHashSet<>();

    private static final class Totals {
        String uuid;
        String name;
        long activeMillis;
        long afkMillis;
        Totals(UUID id, String name) { this.uuid = id.toString(); this.name = name; }
    }
    private static final class Store {
        int schema = 1;
        int resetProtocol = 1;
        String mode = "active";
        int afkTimeoutSeconds = 300;
        String startedAt;
        String updatedAt;
        List<Totals> players = new ArrayList<>();
        Set<String> processedResetIds = new LinkedHashSet<>();
    }
    private String startedAt;
    private static long now() { return System.nanoTime() / 1_000_000L; }

    @Override public void onInitialize() {
        instance = this;
        RewardsReset.register();
        ServerLifecycleEvents.SERVER_STARTED.register(this::start);
        ServerLifecycleEvents.SERVER_STOPPING.register(server -> save());
        ServerPlayConnectionEvents.JOIN.register((handler, sender, server) -> {
            ServerPlayer player = handler.player;
            UUID id = player.getUUID();
            totals.computeIfAbsent(id, key -> new Totals(key, player.getScoreboardName())).name = player.getScoreboardName();
            sessions.put(id, new ActiveClock(now()));
            save();
        });
        ServerPlayConnectionEvents.DISCONNECT.register((handler, server) -> {
            flush(handler.player.getUUID(), now());
            sessions.remove(handler.player.getUUID());
            save();
        });
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            long current = now();
            if (current - resetChecked >= 1000) {
                resetChecked = current;
                processResetRequest();
            }
            for (UUID id : sessions.keySet()) flush(id, current);
            for (ServerPlayer player : server.getPlayerList().getPlayers()) {
                publishScore(server, player.getScoreboardName(), activeSeconds(player.getUUID()));
            }
            if (current - lastSave >= 60_000) save();
        });
        UseBlockCallback.EVENT.register((player, world, hand, hit) -> { if (player instanceof ServerPlayer p) activity(p); return InteractionResult.PASS; });
        UseItemCallback.EVENT.register((player, world, hand) -> { if (player instanceof ServerPlayer p) activity(p); return InteractionResult.PASS; });
        UseEntityCallback.EVENT.register((player, world, hand, entity, hit) -> { if (player instanceof ServerPlayer p) activity(p); return InteractionResult.PASS; });
        AttackEntityCallback.EVENT.register((player, world, hand, entity, hit) -> { if (player instanceof ServerPlayer p) activity(p); return InteractionResult.PASS; });
    }

    private void start(MinecraftServer server) {
        activeServer = server;
        try {
            Class.forName("net.minecraft.server.network.ServerGamePacketListenerImpl", true, getClass().getClassLoader());
        } catch (ClassNotFoundException error) {
            throw new IllegalStateException("Could not initialize activity packet hooks", error);
        }
        output = server.getWorldPath(LevelResource.ROOT).resolve("config/halfknife-active-playtime/playtime.json");
        startedAt = Instant.now().toString();
        if (Files.exists(output)) {
            try {
                Store stored = JSON.fromJson(Files.readString(output), Store.class);
                if (stored == null || stored.schema != 1 || !"active".equals(stored.mode) || stored.players == null)
                    throw new IOException("Invalid active playtime storage");
                for (Totals value : stored.players) {
                    if (value == null || value.activeMillis < 0 || value.afkMillis < 0 || value.name == null)
                        throw new IOException("Invalid active playtime entry");
                    totals.put(UUID.fromString(value.uuid), value);
                }
                startedAt = stored.startedAt == null ? startedAt : stored.startedAt;
                if (stored.processedResetIds != null) processedResetIds.addAll(stored.processedResetIds);
            } catch (Exception error) {
                output = null; // Never overwrite a damaged save with an empty ranking.
                throw new IllegalStateException("Cannot load active playtime. Restore its playtime.json.bak before restarting.", error);
            }
        }
        save();
        refreshWhitelist();
        publishScore(server, "#initial", 0);
        if (Boolean.getBoolean("halfknife.playtime.integration-test")) IntegrationCheck.run(server);
        LOG.info("Active playtime enabled; AFK timeout: 300 seconds. No AFK kicks.");
    }

    public record ActiveEntry(UUID uuid, String name, long seconds) {}

    public static long activeSeconds(UUID uuid) {
        if (instance == null) return 0;
        instance.flush(uuid, now());
        Totals value = instance.totals.get(uuid);
        return value == null ? 0 : value.activeMillis / 1000;
    }

    private void refreshWhitelist() {
        if (now() - whitelistChecked < 60_000 && !whitelistNames.isEmpty()) return;
        whitelistChecked = now();
        try {
            Map<UUID, String> names = new HashMap<>();
            Path file = FabricLoader.getInstance().getGameDir().resolve("whitelist.json");
            for (var element : JsonParser.parseString(Files.readString(file)).getAsJsonArray()) {
                var entry = element.getAsJsonObject();
                String name = entry.get("name").getAsString();
                if (name.matches("[A-Za-z0-9_]{1,16}")) names.put(UUID.fromString(entry.get("uuid").getAsString()), name);
            }
            whitelistNames = names;
        } catch (Exception error) {
            LOG.error("Could not refresh active-playtime leaderboard whitelist", error);
        }
    }

    public static List<ActiveEntry> activeRanking() {
        if (instance == null || instance.output == null) return List.of();
        instance.refreshWhitelist();
        List<ActiveEntry> entries = new ArrayList<>();
        for (var entry : instance.whitelistNames.entrySet()) {
            if (StatsExclusions.excluded(entry.getKey())) continue;
            long seconds = activeSeconds(entry.getKey());
            if (seconds > 0) entries.add(new ActiveEntry(entry.getKey(), entry.getValue(), seconds));
        }
        entries.sort(Comparator.comparingLong(ActiveEntry::seconds).reversed().thenComparing(ActiveEntry::name, String.CASE_INSENSITIVE_ORDER));
        return entries;
    }

    public static void publishScore(MinecraftServer server, String name, long seconds) {
        var scoreboard = server.getScoreboard();
        var objective = scoreboard.getObjective(ACTIVE_OBJECTIVE);
        if (objective == null) objective = scoreboard.addObjective(ACTIVE_OBJECTIVE, ObjectiveCriteria.DUMMY,
                Component.literal("Aktive Spielzeit"), ObjectiveCriteria.RenderType.INTEGER, false, null);
        int ticks = (int) Math.min(Integer.MAX_VALUE, Math.max(0L, seconds) * 20L);
        scoreboard.getOrCreatePlayerScore(ScoreHolder.forNameOnly(name), objective).set(ticks);
    }

    private void flush(UUID id, long current) {
        ActiveClock clock = sessions.get(id);
        Totals value = totals.get(id);
        if (clock == null || value == null) return;
        clock.update(current);
        value.activeMillis += clock.takeActive();
        value.afkMillis += clock.takeAfk();
    }

    public static void activity(ServerPlayer player) {
        if (instance == null) return;
        MinecraftServer server = player.level().getServer();
        if (server == null) return;
        server.execute(() -> {
            ActiveClock clock = instance.sessions.get(player.getUUID());
            if (clock != null) clock.activity(now());
        });
    }

    public static void input(ServerPlayer player, boolean moving) {
        if (instance == null) return;
        MinecraftServer server = player.level().getServer();
        if (server == null) return;
        server.execute(() -> {
            ActiveClock clock = instance.sessions.get(player.getUUID());
            if (clock != null) clock.input(moving, now());
        });
    }

    private boolean save() {
        if (output == null) return false;
        long current = now();
        for (UUID id : sessions.keySet()) flush(id, current);
        Store stored = new Store();
        stored.startedAt = startedAt;
        stored.updatedAt = Instant.now().toString();
        stored.players.addAll(totals.values());
        stored.processedResetIds.addAll(processedResetIds);
        stored.players.sort(Comparator.comparing(value -> value.uuid));
        try {
            Files.createDirectories(output.getParent());
            Path temporary = output.resolveSibling("playtime.json.tmp");
            Files.writeString(temporary, JSON.toJson(stored) + "\n", StandardCharsets.UTF_8);
            if (Files.exists(output)) Files.copy(output, output.resolveSibling("playtime.json.bak"), StandardCopyOption.REPLACE_EXISTING);
            try { Files.move(temporary, output, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE); }
            catch (AtomicMoveNotSupportedException error) { Files.move(temporary, output, StandardCopyOption.REPLACE_EXISTING); }
            lastSave = current;
            return true;
        } catch (IOException error) {
            lastSave = current;
            LOG.error("Could not save active playtime; in-memory counters retained", error);
            return false;
        }
    }

    /** Runs on the server thread: disk-only edits cannot reset an in-memory clock. */
    private void processResetRequest() {
        if (output == null) return;
        Path request = output.resolveSibling("reset-request.json");
        if (!Files.exists(request)) return;
        String id = null;
        try {
            var data = JsonParser.parseString(Files.readString(request)).getAsJsonObject();
            id = UUID.fromString(data.get("id").getAsString()).toString();
            if (processedResetIds.contains(id)) {
                writeResetResult(id, true, "Already applied; counters were not reset again.");
                Files.deleteIfExists(request);
                return;
            }
            if (!Instant.parse(data.get("expiresAt").getAsString()).isAfter(Instant.now()))
                throw new IOException("Reset request expired; start a new workflow");
            String scope = data.get("scope").getAsString();
            if (!scope.equals("active") && !scope.equals("all")) throw new IOException("Unknown reset scope");
            String target = data.get("target").getAsString();
            whitelistChecked = 0;
            refreshWhitelist();
            Set<UUID> selected = new LinkedHashSet<>();
            if (target.equals("ALL")) selected.addAll(whitelistNames.keySet());
            else {
                UUID uuid = UUID.fromString(target);
                if (!whitelistNames.containsKey(uuid)) throw new IOException("Player is not whitelisted");
                selected.add(uuid);
            }
            if (selected.isEmpty()) throw new IOException("No whitelisted players selected");
            if (!save()) throw new IOException("Cannot save current counters before backup");
            Path backup = output.getParent().resolve("reset-backups").resolve(id);
            Files.createDirectories(backup);
            // Never replace the original backup when a failed request is retried.
            if (!Files.exists(backup.resolve("playtime.json"))) Files.copy(output, backup.resolve("playtime.json"));
            Path world = activeServer.getWorldPath(LevelResource.ROOT);
            if (scope.equals("all")) {
                for (UUID uuid : selected) {
                    ServerPlayer online = activeServer.getPlayerList().getPlayer(uuid);
                    if (online != null) online.getStats().save();
                    for (String directory : List.of("stats", "players/stats")) {
                        Path source = world.resolve(directory).resolve(uuid + ".json");
                        Path destination = backup.resolve(directory).resolve(uuid + ".json");
                        if (Files.exists(source) && !Files.exists(destination)) {
                            Files.createDirectories(destination.getParent());
                            Files.copy(source, destination);
                        }
                    }
                }
            }
            for (UUID uuid : selected) {
                String name = whitelistNames.get(uuid);
                totals.put(uuid, new Totals(uuid, name));
                if (sessions.containsKey(uuid)) sessions.put(uuid, new ActiveClock(now()));
                publishScore(activeServer, name, 0);
                if (scope.equals("all")) {
                    ServerPlayer player = activeServer.getPlayerList().getPlayer(uuid);
                    if (player != null) {
                        var counter = player.getStats();
                        for (var stat : new ArrayList<>(((StatsCounterAccessor) counter).halfknife$getStats().keySet()))
                            counter.setValue(player, stat, 0);
                        counter.save();
                    } else {
                        ((PlayerListAccessor) activeServer.getPlayerList()).halfknife$getStats().remove(uuid);
                        for (String directory : List.of("stats", "players/stats"))
                            Files.deleteIfExists(world.resolve(directory).resolve(uuid + ".json"));
                    }
                }
            }
            processedResetIds.add(id);
            if (!save()) {
                processedResetIds.remove(id);
                throw new IOException("Reset could not be persisted");
            }
            writeResetResult(id, true, "Reset " + selected.size() + " player(s); scope=" + scope);
            Files.deleteIfExists(request);
            LOG.info("Stats reset {} completed: {} player(s), scope={}", id, selected.size(), scope);
        } catch (Exception error) {
            LOG.error("Stats reset failed", error);
            try {
                writeResetResult(id, false, error.getClass().getSimpleName() + ": " + error.getMessage());
                // A failure is explicit; never keep retrying a partially applied reset each tick.
                Files.deleteIfExists(request);
            } catch (IOException writeError) { LOG.error("Cannot acknowledge reset failure", writeError); }
        }
    }

    private void writeResetResult(String id, boolean success, String message) throws IOException {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", id);
        result.put("success", success);
        result.put("message", message);
        result.put("updatedAt", Instant.now().toString());
        Path temporary = output.resolveSibling("reset-result.json.tmp");
        Files.writeString(temporary, JSON.toJson(result) + "\n", StandardCharsets.UTF_8);
        Files.move(temporary, output.resolveSibling("reset-result.json"), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    }
}

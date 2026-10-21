package de.halfknife.playtime;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.event.player.*;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.level.storage.LevelResource;
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

    private static final class Totals {
        String uuid;
        String name;
        long activeMillis;
        long afkMillis;
        Totals(UUID id, String name) { this.uuid = id.toString(); this.name = name; }
    }
    private static final class Store {
        int schema = 1;
        String mode = "active";
        int afkTimeoutSeconds = 300;
        String startedAt;
        String updatedAt;
        List<Totals> players = new ArrayList<>();
    }
    private String startedAt;
    private static long now() { return System.nanoTime() / 1_000_000L; }

    @Override public void onInitialize() {
        instance = this;
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
            for (UUID id : sessions.keySet()) flush(id, current);
            if (current - lastSave >= 60_000) save();
        });
        UseBlockCallback.EVENT.register((player, world, hand, hit) -> { if (player instanceof ServerPlayer p) activity(p); return InteractionResult.PASS; });
        UseItemCallback.EVENT.register((player, world, hand) -> { if (player instanceof ServerPlayer p) activity(p); return InteractionResult.PASS; });
        UseEntityCallback.EVENT.register((player, world, hand, entity, hit) -> { if (player instanceof ServerPlayer p) activity(p); return InteractionResult.PASS; });
        AttackEntityCallback.EVENT.register((player, world, hand, entity, hit) -> { if (player instanceof ServerPlayer p) activity(p); return InteractionResult.PASS; });
    }

    private void start(MinecraftServer server) {
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
            } catch (Exception error) {
                output = null; // Never overwrite a damaged save with an empty ranking.
                throw new IllegalStateException("Cannot load active playtime. Restore its playtime.json.bak before restarting.", error);
            }
        }
        save();
        LOG.info("Active playtime enabled; AFK timeout: 300 seconds. No AFK kicks.");
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

    private void save() {
        if (output == null) return;
        long current = now();
        for (UUID id : sessions.keySet()) flush(id, current);
        Store stored = new Store();
        stored.startedAt = startedAt;
        stored.updatedAt = Instant.now().toString();
        stored.players.addAll(totals.values());
        stored.players.sort(Comparator.comparing(value -> value.uuid));
        try {
            Files.createDirectories(output.getParent());
            Path temporary = output.resolveSibling("playtime.json.tmp");
            Files.writeString(temporary, JSON.toJson(stored) + "\n", StandardCharsets.UTF_8);
            if (Files.exists(output)) Files.copy(output, output.resolveSibling("playtime.json.bak"), StandardCopyOption.REPLACE_EXISTING);
            try { Files.move(temporary, output, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE); }
            catch (AtomicMoveNotSupportedException error) { Files.move(temporary, output, StandardCopyOption.REPLACE_EXISTING); }
            lastSave = current;
        } catch (IOException error) {
            lastSave = current;
            LOG.error("Could not save active playtime; in-memory counters retained", error);
        }
    }
}

package de.halfknife.playtime;

import com.google.gson.*;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.commands.Commands;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.stats.Stats;
import net.minecraft.world.level.storage.LevelResource;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Reset only Playtime Rewards, including offline records. Vanilla and RAS are never written. */
public final class RewardsReset {
    private static final Gson JSON = new GsonBuilder().setPrettyPrinting().create();
    private static Map<String, Long> baselines = new HashMap<>();
    private static Path baselineFile;
    static void register() {
        ServerLifecycleEvents.SERVER_STARTING.register(server -> {
            baselineFile = server.getWorldPath(LevelResource.ROOT).resolve("config/playtime-rewards/reset-baselines.json");
            baselines = new HashMap<>();
            if (Files.exists(baselineFile)) try {
                var data = JsonParser.parseString(Files.readString(baselineFile)).getAsJsonObject();
                for (var e : data.entrySet()) {
                    UUID.fromString(e.getKey());
                    long value = e.getValue().getAsLong();
                    if (value < 0) throw new IllegalStateException("Negative baseline");
                    baselines.put(e.getKey(), value);
                }
            } catch (Exception error) { throw new IllegalStateException("Cannot load rewards reset baselines", error); }
        });
        CommandRegistrationCallback.EVENT.register((dispatcher, registry, environment) ->
            dispatcher.register(Commands.literal("hkrewards").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                .then(Commands.literal("reset").then(Commands.argument("target", StringArgumentType.word())
                    .executes(ctx -> run(ctx.getSource(), StringArgumentType.getString(ctx, "target"), false))
                    .then(Commands.literal("confirm").executes(ctx -> run(ctx.getSource(), StringArgumentType.getString(ctx, "target"), true)))))));
    }
    public static long adjusted(UUID id, long vanilla) {
        return Math.max(0, vanilla - baselines.getOrDefault(id.toString(), 0L));
    }
    private static Field field(Object object, String name) throws Exception {
        Field f = object.getClass().getDeclaredField(name); f.setAccessible(true); return f;
    }
    private static Object get(Object object, String name) throws Exception { return field(object, name).get(object); }
    private static Object mod() {
        for (ModInitializer m : FabricLoader.getInstance().getEntrypoints("main", ModInitializer.class))
            if (m.getClass().getName().equals("com.sovern.playtimerewards.PlaytimeRewardsMod")) return m;
        throw new IllegalStateException("Playtime Rewards fehlt");
    }
    private static String escape(String value) { return value.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n"); }
    private static void write(Path file, String text) throws Exception {
        Files.createDirectories(file.getParent());
        Path tmp = file.resolveSibling(file.getFileName() + ".hk-reset.tmp");
        Files.writeString(tmp, text);
        Files.move(tmp, file, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }
    private static long vanilla(MinecraftServer server, UUID id) throws Exception {
        ServerPlayer online = server.getPlayerList().getPlayer(id);
        if (online != null) return Math.max(0, (long)online.getStats().getValue(Stats.CUSTOM.get(Stats.PLAY_TIME)) / 20);
        Path world = server.getWorldPath(LevelResource.ROOT);
        for (String dir : List.of("players/stats", "stats")) {
            Path file = world.resolve(dir).resolve(id + ".json");
            if (Files.exists(file)) {
                var root = JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                var stats = root.getAsJsonObject("stats");
                var custom = stats == null ? null : stats.getAsJsonObject("minecraft:custom");
                return custom == null || !custom.has("minecraft:play_time") ? 0 : Math.max(0, custom.get("minecraft:play_time").getAsLong() / 20);
            }
        }
        return 0;
    }
    @SuppressWarnings("unchecked")
    private static int run(CommandSourceStack source, String target, boolean confirm) {
        try {
            Object mod = mod();
            Map<UUID, Object> records = (Map<UUID, Object>)get(mod, "records");
            List<UUID> selected = new ArrayList<>();
            for (var entry : records.entrySet()) if (target.equalsIgnoreCase("all") || target.equalsIgnoreCase(entry.getKey().toString())
                    || target.equalsIgnoreCase((String)get(entry.getValue(), "name"))) selected.add(entry.getKey());
            if (selected.isEmpty()) throw new IllegalArgumentException("Kein gespeicherter Spieler gefunden");
            if (!target.equalsIgnoreCase("all") && selected.size() != 1) throw new IllegalArgumentException("Name nicht eindeutig; UUID verwenden");
            if (!confirm) {
                source.sendSuccess(() -> Component.literal("Vorschau: " + selected.size() + " Playtime-Rewards-Spieler: Zeit, Rang und abgeholte Belohnungen auf 0. Ausfuehren: hkrewards reset " + target + " confirm"), false);
                return selected.size();
            }
            if (baselineFile == null) throw new IllegalStateException("Server noch nicht bereit");
            Path directory = (Path)get(mod, "dataDirectory");
            if (directory == null) throw new IllegalStateException("Playtime Rewards noch nicht geladen");
            Map<String, Long> next = new HashMap<>(baselines);
            for (UUID id : selected) next.put(id.toString(), vanilla(source.getServer(), id));
            StringBuilder before = new StringBuilder("# uuid\tname\tseconds\trankIndex\timportedVanilla\tclaimedRewards\n");
            StringBuilder after = new StringBuilder(before);
            // Validate every reflected field before any write; snapshot current memory, not an outdated disk file.
            for (var e : records.entrySet()) {
                Object rec = e.getValue();
                long seconds = field(rec, "seconds").getLong(rec);
                int rank = field(rec, "rankIndex").getInt(rec);
                boolean imported = field(rec, "importedVanilla").getBoolean(rec);
                Set<String> claims = (Set<String>)get(rec, "claimedRewards");
                String prefix = e.getKey() + "\t" + escape((String)get(rec, "name")) + "\t";
                String old = prefix + seconds + "\t" + rank + "\t" + imported + "\t" + String.join(",", new TreeSet<>(claims)) + "\n";
                before.append(old);
                after.append(selected.contains(e.getKey()) ? prefix + "0\t-1\ttrue\t\n" : old);
            }
            Path backup = directory.resolve("reset-backups").resolve(UUID.randomUUID().toString());
            Files.createDirectories(backup);
            Files.writeString(backup.resolve("players.tsv"), before);
            Files.writeString(backup.resolve("reset-baselines.json"), JSON.toJson(baselines));
            try {
                write(baselineFile, JSON.toJson(next));
                write(directory.resolve("players.tsv"), after.toString());
            } catch (Exception failure) {
                write(baselineFile, JSON.toJson(baselines));
                write(directory.resolve("players.tsv"), before.toString());
                throw failure;
            }
            baselines = next;
            for (UUID id : selected) {
                Object rec = records.get(id);
                field(rec, "seconds").setLong(rec, 0);
                field(rec, "rankIndex").setInt(rec, -1);
                field(rec, "importedVanilla").setBoolean(rec, true);
                ((Set<?>)get(rec, "claimedRewards")).clear();
            }
            source.sendSuccess(() -> Component.literal("Playtime Rewards zurueckgesetzt: " + selected.size() + " Spieler. Sicherung: " + backup + ". RAS, Vanilla-Statistiken und aktive Spielzeit unveraendert. Raenge werden beim naechsten Login/Tick abgeglichen."), false);
            return selected.size();
        } catch (Exception error) {
            source.sendFailure(Component.literal("Playtime-Rewards-Reset fehlgeschlagen: " + error.getMessage()));
            org.slf4j.LoggerFactory.getLogger("HalfKnife Rewards Reset").error("Rewards reset failed", error);
            return 0;
        }
    }
}

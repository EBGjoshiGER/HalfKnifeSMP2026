package de.halfknife.endproject;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.minecraft.server.level.ServerPlayer;

import java.io.Reader;
import java.io.Writer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

public final class ProjectState {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    public Map<String, Integer> donated = new LinkedHashMap<>();
    public Map<String, Integer> playerTotals = new HashMap<>();
    public Map<String, Integer> playerPoints = new HashMap<>();
    public Map<String, String> playerNames = new HashMap<>();
    public boolean active = false;
    public boolean paused = false;
    public boolean completed = false;
    public boolean completionCommandsExecuted = false;
    public int highestMilestoneAnnounced = 0;

    public static ProjectState load(ProjectConfig config) {
        Path file = ProjectConfig.progressFile();
        try {
            if (Files.notExists(file)) {
                ProjectState state = fresh(config);
                state.save();
                return state;
            }
            try (Reader reader = Files.newBufferedReader(file)) {
                ProjectState state = GSON.fromJson(reader, ProjectState.class);
                if (state == null) state = fresh(config);
                if (state.donated == null) state.donated = new LinkedHashMap<>();
                if (state.playerTotals == null) state.playerTotals = new HashMap<>();
                if (state.playerPoints == null) state.playerPoints = new HashMap<>();
                if (state.playerNames == null) state.playerNames = new HashMap<>();
                // Quartz's real registry ID is minecraft:quartz. Preserve legacy counts.
                if (config.requirements.containsKey("minecraft:quartz")) {
                    Integer legacyQuartz = state.donated.remove("minecraft:nether_quartz");
                    if (legacyQuartz != null) state.donated.merge("minecraft:quartz", legacyQuartz, Integer::sum);
                }
                for (String id : config.requirements.keySet()) state.donated.putIfAbsent(id, 0);
                state.completed = state.isComplete(config);
                return state;
            }
        } catch (Exception e) {
            EndProjectMod.LOGGER.error("Could not load End Project progress", e);
            return fresh(config);
        }
    }

    public static ProjectState fresh(ProjectConfig config) {
        ProjectState state = new ProjectState();
        for (String id : config.requirements.keySet()) state.donated.put(id, 0);
        return state;
    }

    public synchronized DonationResult donate(ServerPlayer player, String itemId, int amount, ProjectConfig config) {
        return donate(player.getUUID(), player.getName().getString(), itemId, amount, config);
    }

    synchronized DonationResult donate(UUID playerId, String playerName, String itemId, int amount, ProjectConfig config) {
        if (!active || paused || completed || amount <= 0) return new DonationResult(0, 0);
        if (!currentRequirements(config).containsKey(itemId)) return new DonationResult(0, 0);
        Integer target = config.requirements.get(itemId);
        if (target == null) return new DonationResult(0, 0);
        int current = donated.getOrDefault(itemId, 0);
        int accepted = Math.min(amount, Math.max(0, target - current));
        if (accepted <= 0) return new DonationResult(0, 0);

        donated.put(itemId, current + accepted);
        String uuid = playerId.toString();
        playerTotals.merge(uuid, accepted, Integer::sum);
        int weight = Math.max(0, config.contributionWeights.getOrDefault(itemId, 1));
        int points = accepted * weight;
        playerPoints.merge(uuid, points, Integer::sum);
        playerNames.put(uuid, playerName);
        save();
        return new DonationResult(accepted, points);
    }

    // Derive the current stage from the original counters: no reset or new progress format.
    public int currentStage(ProjectConfig config) {
        List<List<String>> stages = config.stageItems();
        for (int stage = 0; stage < stages.size(); stage++) {
            for (String id : stages.get(stage)) {
                if (donated.getOrDefault(id, 0) < config.requirements.get(id)) return stage;
            }
        }
        return stages.size();
    }

    public Map<String, Integer> currentRequirements(ProjectConfig config) {
        List<List<String>> stages = config.stageItems();
        int stage = currentStage(config);
        Map<String, Integer> result = new LinkedHashMap<>();
        if (stage < stages.size()) for (String id : stages.get(stage)) result.put(id, config.requirements.get(id));
        return result;
    }

    public float stageProgress(ProjectConfig config) {
        Map<String, Integer> current = currentRequirements(config);
        if (current.isEmpty()) return 1.0f;
        double sum = 0;
        for (Map.Entry<String, Integer> entry : current.entrySet()) {
            sum += Math.min(1.0, Math.max(0, donated.getOrDefault(entry.getKey(), 0)) / (double) Math.max(1, entry.getValue()));
        }
        return (float) (sum / current.size());
    }

    public boolean isComplete(ProjectConfig config) {
        for (Map.Entry<String, Integer> entry : config.requirements.entrySet()) {
            if (donated.getOrDefault(entry.getKey(), 0) < entry.getValue()) return false;
        }
        return true;
    }

    // Jede Materialkategorie zählt gleich viel zum Gesamtfortschritt.
    public float progress(ProjectConfig config) {
        if (config.requirements.isEmpty()) return 1.0f;
        double sum = 0.0;
        for (Map.Entry<String, Integer> entry : config.requirements.entrySet()) {
            int target = Math.max(1, entry.getValue());
            int current = Math.max(0, donated.getOrDefault(entry.getKey(), 0));
            sum += Math.min(1.0, (double) current / (double) target);
        }
        return (float) Math.min(1.0, sum / config.requirements.size());
    }

    public int playerTotal(UUID uuid) {
        return playerTotals.getOrDefault(uuid.toString(), 0);
    }

    public int playerPoints(UUID uuid) {
        return playerPoints.getOrDefault(uuid.toString(), 0);
    }

    public List<LeaderboardEntry> leaderboard(int limit) {
        return playerPoints.entrySet().stream()
                .sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
                .limit(limit)
                .map(e -> new LeaderboardEntry(playerNames.getOrDefault(e.getKey(), "Unbekannt"), e.getValue()))
                .toList();
    }

    public synchronized void save() {
        try {
            Path file = ProjectConfig.progressFile();
            Files.createDirectories(file.getParent());
            try (Writer writer = Files.newBufferedWriter(file)) {
                GSON.toJson(this, writer);
            }
        } catch (Exception e) {
            EndProjectMod.LOGGER.error("Could not save End Project progress", e);
        }
    }

    public record DonationResult(int items, int points) {}
    public record LeaderboardEntry(String name, int points) {}
}

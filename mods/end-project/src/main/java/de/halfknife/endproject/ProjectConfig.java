package de.halfknife.endproject;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.fabricmc.loader.api.FabricLoader;

import java.io.IOException;
import java.io.Reader;
import java.io.Writer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.List;
import java.util.Map;

public final class ProjectConfig {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static final Path DIR = FabricLoader.getInstance().getConfigDir().resolve("endproject");
    private static final Path FILE = DIR.resolve("config.json");

    public int configVersion = 3;
    public String guiTitle = "End-Gemeinschaftsprojekt";
    public boolean broadcastDonations = true;
    public boolean joinReminderEnabled = true;
    public int completionDelaySeconds = 60;
    public boolean lockEndWhileInactive = true;

    public Map<String, Integer> requirements = defaultRequirements();
    public List<List<String>> stages = List.of(
            List.of("minecraft:netherrack", "minecraft:blackstone", "minecraft:soul_sand"),
            List.of("minecraft:nether_wart", "minecraft:quartz", "minecraft:glowstone_dust"),
            List.of("minecraft:blaze_rod", "minecraft:ender_pearl", "minecraft:magma_cream"),
            List.of("minecraft:crying_obsidian", "minecraft:ghast_tear", "minecraft:ancient_debris"));

    // Keep custom requirements and quantities. Every configured resource occurs once.
    public List<List<String>> stageItems() {
        List<List<String>> result = new ArrayList<>();
        Set<String> remaining = new LinkedHashSet<>(requirements.keySet());
        if (stages != null) for (List<String> group : stages) {
            if (group == null) continue;
            List<String> items = new ArrayList<>();
            for (String id : group) if (remaining.remove(id)) items.add(id);
            if (!items.isEmpty()) result.add(List.copyOf(items));
        }
        if (!remaining.isEmpty()) result.add(List.copyOf(remaining));
        return List.copyOf(result);
    }

    public Map<String, Integer> contributionWeights = defaultWeights();

    // Ohne führenden Slash. Wird nach manuell gestartetem Countdown einmalig ausgeführt.
    public List<String> completionCommands = List.of("DimensionDaddy enable end");

    // Ohne führenden Slash. Wird bei Reset und optional beim Serverstart im inaktiven Zustand ausgeführt.
    public List<String> lockCommands = List.of("DimensionDaddy disable end");

    public static ProjectConfig load() {
        try {
            Files.createDirectories(DIR);
            if (Files.notExists(FILE)) {
                ProjectConfig config = new ProjectConfig();
                save(config);
                if (config.configVersion < 3) {
                    // Only add the stage structure; never alter amounts or donation history.
                    config.configVersion = 3;
                    save(config);
                }
                return config;
            }
            try (Reader reader = Files.newBufferedReader(FILE)) {
                ProjectConfig config = GSON.fromJson(reader, ProjectConfig.class);
                if (config == null) config = new ProjectConfig();
                if (config.requirements == null || config.requirements.isEmpty()) config.requirements = defaultRequirements();
                if (config.contributionWeights == null || config.contributionWeights.isEmpty()) config.contributionWeights = defaultWeights();
                if (config.completionCommands == null || config.completionCommands.isEmpty()) config.completionCommands = List.of("DimensionDaddy enable end");
                if (config.lockCommands == null || config.lockCommands.isEmpty()) config.lockCommands = List.of("DimensionDaddy disable end");
                if (config.configVersion < 2) {
                    // Apply the explicitly approved new targets exactly once, preserving
                    // command lists, reminders, delay, custom weights and all progress.
                    config.requirements = defaultRequirements();
                    Integer legacyQuartzWeight = config.contributionWeights.remove("minecraft:nether_quartz");
                    if (legacyQuartzWeight != null) config.contributionWeights.putIfAbsent("minecraft:quartz", legacyQuartzWeight);
                    defaultWeights().forEach(config.contributionWeights::putIfAbsent);
                    config.configVersion = 2;
                    save(config);
                    EndProjectMod.LOGGER.info("Migrated End Project to the approved twelve resource goals; progress retained.");
                }
                if (config.configVersion < 3) {
                    // Only add the stage structure; never alter amounts or donation history.
                    config.configVersion = 3;
                    save(config);
                }
                return config;
            }
        } catch (Exception e) {
            EndProjectMod.LOGGER.error("Could not load End Project config", e);
            return new ProjectConfig();
        }
    }

    public static void save(ProjectConfig config) throws IOException {
        Files.createDirectories(DIR);
        try (Writer writer = Files.newBufferedWriter(FILE)) {
            GSON.toJson(config, writer);
        }
    }

    public static Path progressFile() {
        return DIR.resolve("progress.json");
    }

    private static Map<String, Integer> defaultRequirements() {
        Map<String, Integer> result = new LinkedHashMap<>();
        // Approved HalfKnife community targets, 2026-10-26.
        result.put("minecraft:netherrack", 73728);
        result.put("minecraft:blackstone", 18432);
        result.put("minecraft:soul_sand", 6144);
        result.put("minecraft:nether_wart", 3584);
        result.put("minecraft:quartz", 11520);
        result.put("minecraft:glowstone_dust", 9216);
        result.put("minecraft:blaze_rod", 1408);
        result.put("minecraft:ender_pearl", 1664);
        result.put("minecraft:magma_cream", 896);
        result.put("minecraft:crying_obsidian", 704);
        result.put("minecraft:ghast_tear", 80);
        result.put("minecraft:ancient_debris", 56);
        return result;
    }

    private static Map<String, Integer> defaultWeights() {
        Map<String, Integer> result = new LinkedHashMap<>();
        result.put("minecraft:netherrack", 1);
        result.put("minecraft:blackstone", 1);
        result.put("minecraft:soul_sand", 1);
        result.put("minecraft:nether_wart", 1);
        result.put("minecraft:quartz", 1);
        result.put("minecraft:glowstone_dust", 1);
        result.put("minecraft:magma_cream", 2);
        result.put("minecraft:ender_pearl", 3);
        result.put("minecraft:blaze_rod", 4);
        result.put("minecraft:crying_obsidian", 5);
        result.put("minecraft:ghast_tear", 8);
        result.put("minecraft:ancient_debris", 15);
        return result;
    }
}

package de.halfknife.netherproject;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.fabricmc.loader.api.FabricLoader;

import java.io.IOException;
import java.io.Reader;
import java.io.Writer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class ProjectConfig {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static final Path DIR = FabricLoader.getInstance().getConfigDir().resolve("netherproject");
    private static final Path FILE = DIR.resolve("config.json");

    public int configVersion = 3;
    public String guiTitle = "Nether-Gemeinschaftsprojekt";
    public boolean broadcastDonations = true;
    public boolean joinReminderEnabled = true;
    public int completionDelaySeconds = 60;
    public boolean lockNetherWhileInactive = true;

    public Map<String, Integer> requirements = defaultRequirements();
    public Map<String, Integer> contributionWeights = defaultWeights();

    // Ohne führenden Slash. Wird nach manuell gestartetem Countdown einmalig ausgeführt.
    public List<String> completionCommands = List.of("DimensionDaddy enable nether");

    // Ohne führenden Slash. Wird bei Reset und optional beim Serverstart im inaktiven Zustand ausgeführt.
    public List<String> lockCommands = List.of("DimensionDaddy disable nether");

    public static ProjectConfig load() {
        try {
            Files.createDirectories(DIR);
            if (Files.notExists(FILE)) {
                ProjectConfig config = new ProjectConfig();
                save(config);
                return config;
            }
            try (Reader reader = Files.newBufferedReader(FILE)) {
                ProjectConfig config = GSON.fromJson(reader, ProjectConfig.class);
                if (config == null) config = new ProjectConfig();
                if (config.requirements == null || config.requirements.isEmpty()) config.requirements = defaultRequirements();
                if (config.contributionWeights == null || config.contributionWeights.isEmpty()) config.contributionWeights = defaultWeights();
                if (config.completionCommands == null || config.completionCommands.isEmpty()) config.completionCommands = List.of("DimensionDaddy enable nether");
                if (config.lockCommands == null || config.lockCommands.isEmpty()) config.lockCommands = List.of("DimensionDaddy disable nether");

                // Migration älterer Konfigurationen. Eigene angepasste Mengen
                // werden bewusst nicht überschrieben.
                if (config.configVersion < 3) {
                    if (matchesLegacyRequirements(config.requirements)) {
                        config.requirements = defaultRequirements();
                        NetherProjectMod.LOGGER.info("Migrated legacy Nether Project requirements to the 20-player defaults.");
                    }
                    config.configVersion = 3;
                    save(config);
                }
                return config;
            }
        } catch (Exception e) {
            NetherProjectMod.LOGGER.error("Could not load Nether Project config", e);
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

    private static boolean matchesLegacyRequirements(Map<String, Integer> requirements) {
        if (requirements == null || requirements.size() != 6) return false;
        return requirements.getOrDefault("minecraft:obsidian", -1) == 256
                && requirements.getOrDefault("minecraft:iron_ingot", -1) == 1024
                && requirements.getOrDefault("minecraft:gold_ingot", -1) == 256
                && requirements.getOrDefault("minecraft:diamond", -1) == 64
                && requirements.getOrDefault("minecraft:redstone", -1) == 1024
                && requirements.getOrDefault("minecraft:lapis_lazuli", -1) == 512;
    }

    private static Map<String, Integer> defaultRequirements() {
        Map<String, Integer> result = new LinkedHashMap<>();
        result.put("minecraft:obsidian", 768);
        result.put("minecraft:iron_ingot", 5120);
        result.put("minecraft:gold_ingot", 1280);
        result.put("minecraft:diamond", 400);
        result.put("minecraft:redstone", 5120);
        result.put("minecraft:lapis_lazuli", 2560);
        return result;
    }

    private static Map<String, Integer> defaultWeights() {
        Map<String, Integer> result = new LinkedHashMap<>();
        result.put("minecraft:obsidian", 5);
        result.put("minecraft:iron_ingot", 1);
        result.put("minecraft:gold_ingot", 3);
        result.put("minecraft:diamond", 10);
        result.put("minecraft:redstone", 1);
        result.put("minecraft:lapis_lazuli", 1);
        return result;
    }
}

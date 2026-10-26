package de.halfknife.endproject;

import com.mojang.brigadier.Command;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.minecraft.commands.Commands;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.Permissions;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.Map;

public final class EndProjectMod implements ModInitializer {
    public static final String MOD_ID = "endproject";
    public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

    public static ProjectConfig CONFIG;
    public static ProjectState STATE;
    private static MinecraftServer SERVER;
    private static int completionTicksRemaining = -1;

    @Override
    public void onInitialize() {
        CONFIG = ProjectConfig.load();
        STATE = ProjectState.load(CONFIG);

        CommandRegistrationCallback.EVENT.register((dispatcher, registryAccess, environment) -> {
            dispatcher.register(Commands.literal("endproject")
                    .executes(ctx -> {
                        ServerPlayer player = ctx.getSource().getPlayer();
                        if (player == null) {
                            ctx.getSource().sendFailure(Component.literal("Dieser Befehl kann nur von einem Spieler genutzt werden."));
                            return 0;
                        }
                        ProjectGui.open(player);
                        return Command.SINGLE_SUCCESS;
                    })
                    .then(Commands.literal("status").executes(ctx -> {
                        ServerPlayer player = ctx.getSource().getPlayer();
                        if (player != null) sendStatus(player);
                        else ctx.getSource().sendSuccess(() -> Component.literal(statusLine()), false);
                        return Command.SINGLE_SUCCESS;
                    }))
                    .then(Commands.literal("top").executes(ctx -> {
                        ServerPlayer player = ctx.getSource().getPlayer();
                        if (player != null) sendLeaderboard(player);
                        return Command.SINGLE_SUCCESS;
                    }))
                    .then(Commands.literal("start")
                            .requires(src -> src.permissions().hasPermission(Permissions.COMMANDS_ADMIN))
                            .executes(ctx -> {
                                if (STATE.completed) {
                                    ctx.getSource().sendFailure(Component.literal("Das Projekt ist bereits abgeschlossen. Nutze zuerst /endproject reset."));
                                    return 0;
                                }
                                STATE.active = true;
                                STATE.paused = false;
                                STATE.save();
                                runLockCommands();
                                broadcast("§5§lDas End-Gemeinschaftsprojekt wurde gestartet! §r§7Mit §e/endproject §7könnt ihr Ressourcen einzahlen.");
                                return Command.SINGLE_SUCCESS;
                            }))
                    .then(Commands.literal("pause")
                            .requires(src -> src.permissions().hasPermission(Permissions.COMMANDS_ADMIN))
                            .executes(ctx -> {
                                if (!STATE.active || STATE.completed) {
                                    ctx.getSource().sendFailure(Component.literal("Das Projekt ist aktuell nicht aktiv."));
                                    return 0;
                                }
                                STATE.paused = true;
                                STATE.save();
                                broadcast("§eDas End-Projekt wurde vorübergehend pausiert.");
                                return Command.SINGLE_SUCCESS;
                            }))
                    .then(Commands.literal("resume")
                            .requires(src -> src.permissions().hasPermission(Permissions.COMMANDS_ADMIN))
                            .executes(ctx -> {
                                if (!STATE.active || !STATE.paused || STATE.completed) {
                                    ctx.getSource().sendFailure(Component.literal("Das Projekt ist nicht pausiert."));
                                    return 0;
                                }
                                STATE.paused = false;
                                STATE.save();
                                broadcast("§aDas End-Projekt läuft weiter! §7Mit §e/endproject §7könnt ihr wieder einzahlen.");
                                return Command.SINGLE_SUCCESS;
                            }))
                    .then(Commands.literal("reload")
                            .requires(src -> src.permissions().hasPermission(Permissions.COMMANDS_ADMIN))
                            .executes(ctx -> {
                                completionTicksRemaining = -1;
                                CONFIG = ProjectConfig.load();
                                STATE = ProjectState.load(CONFIG);
                                ctx.getSource().sendSuccess(() -> Component.literal("End Project neu geladen."), true);
                                return Command.SINGLE_SUCCESS;
                            }))
                    .then(Commands.literal("forcecomplete")
                            .requires(src -> src.permissions().hasPermission(Permissions.COMMANDS_ADMIN))
                            .executes(ctx -> {
                                if (STATE.completionCommandsExecuted || completionTicksRemaining >= 0) {
                                    ctx.getSource().sendFailure(Component.literal("Das End ist bereits aktiviert oder die Freischaltung läuft."));
                                    return 0;
                                }
                                for (Map.Entry<String, Integer> entry : CONFIG.requirements.entrySet()) {
                                    STATE.donated.put(entry.getKey(), entry.getValue());
                                }
                                STATE.active = true;
                                STATE.paused = false;

                                STATE.save();
                                afterProgressChanged();
                                ctx.getSource().sendSuccess(() -> Component.literal("Sammelziel erreicht. Zum Öffnen /endproject activate nutzen."), true);
                                return Command.SINGLE_SUCCESS;
                            }))
                    .then(Commands.literal("lockend")
                            .requires(src -> src.permissions().hasPermission(Permissions.COMMANDS_ADMIN))
                            .executes(ctx -> {
                                completionTicksRemaining = -1;
                                if (!runConfiguredCommands(CONFIG.lockCommands, "lock")) return 0;
                                STATE.completionCommandsExecuted = false;
                                STATE.save();
                                ctx.getSource().sendSuccess(() -> Component.literal("End wurde über DimensionDaddy gesperrt."), true);
                                return Command.SINGLE_SUCCESS;
                            }))
                    .then(Commands.literal("activate")
                            .requires(src -> src.permissions().hasPermission(Permissions.COMMANDS_ADMIN))
                            .executes(ctx -> activate(ctx.getSource())))
                    .then(Commands.literal("unlockend")
                            .requires(src -> src.permissions().hasPermission(Permissions.COMMANDS_ADMIN))
                            .executes(ctx -> activate(ctx.getSource())))
                    .then(Commands.literal("reset")
                            .requires(src -> src.permissions().hasPermission(Permissions.COMMANDS_ADMIN))
                            .executes(ctx -> {
                                STATE = ProjectState.fresh(CONFIG);
                                STATE.save();
                                completionTicksRemaining = -1;
                                runLockCommands();
                                ctx.getSource().sendSuccess(() -> Component.literal("End Project wurde zurückgesetzt, deaktiviert und das End gesperrt."), true);
                                return Command.SINGLE_SUCCESS;
                            }))
            );
        });

        ServerLifecycleEvents.SERVER_STARTED.register(server -> {
            SERVER = server;
            if (CONFIG.lockEndWhileInactive && !STATE.active && !STATE.completed) {
                runLockCommands();
            }
            if (Boolean.getBoolean("halfknife.endproject.test")) IntegrationCheck.run();
            // A pending project never starts a countdown on restart.
            completionTicksRemaining = -1;
        });

        ServerLifecycleEvents.SERVER_STOPPING.register(server -> {
            STATE.save();
            SERVER = null;
        });

        ServerPlayConnectionEvents.JOIN.register((handler, sender, server) -> {
            ServerPlayer player = handler.getPlayer();
            if (CONFIG.joinReminderEnabled && STATE.completed && !STATE.completionCommandsExecuted) {
                player.sendSystemMessage(Component.literal("§6End-Sammelziel erreicht! §7Das End bleibt bis zur gemeinsamen Freischaltung durch einen Admin gesperrt."));
            }
            if (CONFIG.joinReminderEnabled && STATE.active && !STATE.paused && !STATE.completed) {
                int percent = Math.round(STATE.progress(CONFIG) * 100.0f);
                player.sendSystemMessage(Component.literal("§5End-Projekt aktiv! §7Aktueller Fortschritt: §e" + percent + "%§7. §e/endproject §7zum Einzahlen."));
            }
        });

        ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (completionTicksRemaining > 0) {
                completionTicksRemaining--;
                if (completionTicksRemaining == 0) {
                    completionTicksRemaining = -1;
                    runCompletionCommandsIfNeeded();
                }
            }
        });

        LOGGER.info("End Project V1.1 initialized for Minecraft 26.2");
    }

    public static void broadcastDonation(ServerPlayer player, int acceptedTotal, int points) {
        broadcast("§6" + player.getName().getString() + " §7hat §e" + acceptedTotal + " Items §7(§d" + points + " Punkte§7) zum End-Projekt beigetragen.");
    }

    public static void afterProgressChanged() {
        boolean wasCompleted = STATE.completed;
        STATE.completed = STATE.isComplete(CONFIG);
        announceMilestoneIfNeeded();
        STATE.save();

        if (STATE.completed && !wasCompleted) {
            broadcast("§6§lDas Sammelziel ist erreicht! §r§eDas End bleibt bis zur manuellen Freischaltung durch einen Admin gesperrt.");
            sendFinalLeaderboard();

        }
    }

    public static void sendStatus(ServerPlayer player) {
        String stateText = STATE.completed ? (STATE.completionCommandsExecuted ? "§aEnd freigeschaltet" : "§eZiel erreicht – wartet auf Freischaltung") : !STATE.active ? "§7Noch nicht gestartet" : STATE.paused ? "§ePausiert" : "§aAktiv";
        player.sendSystemMessage(Component.literal("§5§lEnd-Gemeinschaftsprojekt §r§8- " + stateText));
        for (Map.Entry<String, Integer> entry : CONFIG.requirements.entrySet()) {
            int current = STATE.donated.getOrDefault(entry.getKey(), 0);
            player.sendSystemMessage(Component.literal("§7" + pretty(entry.getKey()) + ": §e" + current + "§7/§e" + entry.getValue()));
        }
        player.sendSystemMessage(Component.literal("§7Gesamt: §d" + Math.round(STATE.progress(CONFIG) * 100.0f) + "% §8| §7Deine Items: §e" + STATE.playerTotal(player.getUUID()) + " §8| §7Punkte: §d" + STATE.playerPoints(player.getUUID())));
    }

    private static void sendLeaderboard(ServerPlayer player) {
        player.sendSystemMessage(Component.literal("§5§lTop-Spender"));
        List<ProjectState.LeaderboardEntry> top = STATE.leaderboard(10);
        if (top.isEmpty()) {
            player.sendSystemMessage(Component.literal("§7Noch keine Beiträge."));
            return;
        }
        for (int i = 0; i < top.size(); i++) {
            ProjectState.LeaderboardEntry entry = top.get(i);
            player.sendSystemMessage(Component.literal("§e" + (i + 1) + ". §f" + entry.name() + " §8- §d" + entry.points() + " Punkte"));
        }
    }

    private static void sendFinalLeaderboard() {
        List<ProjectState.LeaderboardEntry> top = STATE.leaderboard(3);
        if (top.isEmpty()) return;
        broadcast("§5§lDie größten Unterstützer des Projekts:");
        for (int i = 0; i < top.size(); i++) {
            ProjectState.LeaderboardEntry e = top.get(i);
            broadcast("§e" + (i + 1) + ". §f" + e.name() + " §8- §d" + e.points() + " Punkte");
        }
    }

    private static String statusLine() {
        String state = STATE.completed ? (STATE.completionCommandsExecuted ? "End freigeschaltet" : "Ziel erreicht – wartet auf Freischaltung") : !STATE.active ? "nicht gestartet" : STATE.paused ? "pausiert" : "aktiv";
        return "End Project: " + Math.round(STATE.progress(CONFIG) * 100.0f) + "% (" + state + ")";
    }

    private static String pretty(String id) {
        int colon = id.indexOf(':');
        String s = colon >= 0 ? id.substring(colon + 1) : id;
        return switch (s) {
            case "netherrack" -> "Netherrack";
            case "blackstone" -> "Schwarzstein";
            case "soul_sand" -> "Seelensand";
            case "nether_wart" -> "Netherwarzen";
            case "quartz", "nether_quartz" -> "Netherquarz";
            case "blaze_rod" -> "Lohenruten";
            case "ender_pearl" -> "Enderperlen";
            case "glowstone_dust" -> "Glowstonestaub";
            case "magma_cream" -> "Magmacreme";
            case "crying_obsidian" -> "Weinender Obsidian";
            case "ghast_tear" -> "Ghasttränen";
            case "ancient_debris" -> "Antiker Schrott";
            default -> {
                String[] parts = s.split("_");
                StringBuilder out = new StringBuilder();
                for (String part : parts) {
                    if (!out.isEmpty()) out.append(' ');
                    if (!part.isEmpty()) out.append(Character.toUpperCase(part.charAt(0))).append(part.substring(1));
                }
                yield out.toString();
            }
        };
    }

    private static void announceMilestoneIfNeeded() {
        if (!STATE.active || STATE.completed) return;
        int percent = Math.round(STATE.progress(CONFIG) * 100.0f);
        int reached = percent >= 75 ? 75 : percent >= 50 ? 50 : percent >= 25 ? 25 : 0;
        if (reached > STATE.highestMilestoneAnnounced) {
            STATE.highestMilestoneAnnounced = reached;
            broadcast("§5§lEnd-Projekt: §r§e" + reached + "% §7erreicht!");
        }
    }

    private static int activate(CommandSourceStack source) {
        if (!STATE.completed || !STATE.isComplete(CONFIG)) {
            source.sendFailure(Component.literal("Das Sammelziel ist noch nicht erreicht."));
            return 0;
        }
        if (STATE.completionCommandsExecuted || completionTicksRemaining >= 0) {
            source.sendFailure(Component.literal("Das End ist bereits aktiviert oder die Freischaltung läuft."));
            return 0;
        }
        scheduleCompletion();
        return Command.SINGLE_SUCCESS;
    }

    private static void scheduleCompletion() {
        if (STATE.completionCommandsExecuted || completionTicksRemaining >= 0) return;
        int seconds = Math.max(0, CONFIG.completionDelaySeconds);
        if (seconds == 0) {
            runCompletionCommandsIfNeeded();
            return;
        }
        completionTicksRemaining = seconds * 20;
        broadcast("§7Die End-Freischaltung erfolgt in §e" + seconds + " Sekunden§7.");
    }

    private static void runCompletionCommandsIfNeeded() {
        if (SERVER == null || !STATE.completed || STATE.completionCommandsExecuted) return;
        if (CONFIG.completionCommands.isEmpty()) {
            LOGGER.warn("End Project is complete, but no completionCommands are configured.");
            broadcast("§eDas Projekt ist fertig, aber es ist noch kein Freischaltungsbefehl konfiguriert.");
            return;
        }

        if (!runConfiguredCommands(CONFIG.completionCommands, "completion")) return;
        STATE.completionCommandsExecuted = true;
        STATE.save();
        broadcast("§5§lDas Endportal wurde aktiviert!");
    }

    private static void runLockCommands() {
        if (SERVER == null) return;
        if (CONFIG.lockCommands == null || CONFIG.lockCommands.isEmpty()) {
            LOGGER.warn("No lockCommands configured; End was not locked.");
            return;
        }
        runConfiguredCommands(CONFIG.lockCommands, "lock");
    }

    private static boolean runConfiguredCommands(List<String> commands, String purpose) {
        if (SERVER == null || commands == null) return false;
        boolean executed = false;
        for (String raw : commands) {
            if (raw == null || raw.isBlank()) continue;
            String command = raw.startsWith("/") ? raw.substring(1) : raw;
            try {
                int result = SERVER.getCommands().getDispatcher().execute(command, SERVER.createCommandSourceStack());
                if (result <= 0) {
                    LOGGER.error("{} command reported failure: {}", purpose, command);
                    return false;
                }
                executed = true;
                LOGGER.info("Executed {} command: {}", purpose, command);
            } catch (Exception e) {
                LOGGER.error("{} command failed: {}", purpose, command, e);
                return false;
            }
        }
        return executed;
    }

    private static void broadcast(String text) {
        if (SERVER == null) return;
        SERVER.getPlayerList().broadcastSystemMessage(Component.literal(text), false);
    }

}


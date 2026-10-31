package de.halfknife.endproject;

import net.minecraft.core.registries.BuiltInRegistries;
import java.util.Set;
import java.util.UUID;
import java.util.List;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.stream.Collectors;

/** Runs exclusively on the isolated test server when its JVM flag is set. */
final class IntegrationCheck {
    static void run() {
        Set<String> available = BuiltInRegistries.ITEM.keySet().stream().map(Object::toString).collect(Collectors.toSet());
        for (String item : EndProjectMod.CONFIG.requirements.keySet()) {
            if (!available.contains(item)) throw new AssertionError("Unobtainable item ID in project: " + item);
        }
        testStages();
        EndProjectMod.STATE.save();
        System.out.println("END ITEM REGISTRY PASS: all configured donation materials exist in Minecraft.");
    }
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static void testStages() {
        ProjectConfig config = new ProjectConfig();
        config.requirements.replaceAll((id, ignored) -> 2);
        ProjectState state = ProjectState.fresh(config);
        UUID donor = UUID.fromString("00000000-0000-0000-0000-000000000001");
        check(state.currentStage(config) == 0, "initial stage");
        check(state.currentRequirements(config).size() == 3, "hidden future goals");
        check(state.donate(donor, "Test", "minecraft:netherrack", 1, config).items() == 0, "inactive donation");
        state.active = true;
        for (int stage = 0; stage < 4; stage++) {
            check(state.currentStage(config) == stage, "stage order");
            if (stage < 3) {
                String future = config.stageItems().get(stage + 1).getFirst();
                check(!state.currentRequirements(config).containsKey(future), "future item exposed");
                check(state.donate(donor, "Test", future, 64, config).items() == 0, "future donation accepted");
            }
            List<String> items = config.stageItems().get(stage);
            state.paused = true;
            check(state.donate(donor, "Test", items.getFirst(), 1, config).items() == 0, "paused donation");
            state.paused = false;
            for (int i = 0; i < items.size(); i++) {
                String id = items.get(i);
                check(state.donate(donor, "Test", id, 1, config).items() == 1, "partial donation rejected");
                check(state.currentStage(config) == stage, "advanced prematurely");
                check(state.donate(donor, "Test", id, 64, config).items() == 1, "overflow not capped");
                if (i < items.size() - 1) check(state.currentStage(config) == stage, "stage incomplete");
            }
            check(state.donate(donor, "Test", items.getFirst(), 1, config).items() == 0, "old stage accepted");
        }
        check(state.isComplete(config) && state.currentRequirements(config).isEmpty(), "final stage not completed");
        check(!state.completionCommandsExecuted, "stage completion activated End");
        check(state.playerTotal(donor) == 24, "donation history wrong");
        ProjectState legacy = ProjectState.fresh(config);
        legacy.donated.put("minecraft:ancient_debris", 2);
        check(legacy.currentStage(config) == 0, "legacy future counts skipped earlier stage");
        for (String id : config.stageItems().getFirst()) legacy.donated.put(id, 2);
        check(legacy.currentStage(config) == 1 && legacy.donated.get("minecraft:ancient_debris") == 2, "legacy progress lost");
        config.stages = List.of(List.of("minecraft:netherrack", "minecraft:netherrack", "missing:item"));
        check(config.stageItems().stream().mapToInt(List::size).sum() == config.requirements.size(), "custom requirements lost/duplicated");
        System.out.println("END STAGES PASS: sequential goals, hidden/blocked future items, capped donations, pause, legacy counters and history.");
    }
}

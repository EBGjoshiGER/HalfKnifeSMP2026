package de.halfknife.endproject;

import net.minecraft.core.registries.BuiltInRegistries;
import java.util.Set;
import java.util.stream.Collectors;

/** Runs exclusively on the isolated test server when its JVM flag is set. */
final class IntegrationCheck {
    static void run() {
        Set<String> available = BuiltInRegistries.ITEM.keySet().stream().map(Object::toString).collect(Collectors.toSet());
        for (String item : EndProjectMod.CONFIG.requirements.keySet()) {
            if (!available.contains(item)) throw new AssertionError("Unobtainable item ID in project: " + item);
        }
        System.out.println("END ITEM REGISTRY PASS: all configured donation materials exist in Minecraft.");
    }
}

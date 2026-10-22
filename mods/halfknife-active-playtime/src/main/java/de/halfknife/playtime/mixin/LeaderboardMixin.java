package de.halfknife.playtime.mixin;

import de.halfknife.playtime.ActivePlaytimeMod;
import de.halfknife.playtime.StatsExclusions;
import org.spongepowered.asm.mixin.injection.Redirect;
import java.util.*;
import com.google.gson.JsonObject;
import net.minecraft.server.MinecraftServer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import java.util.ArrayList;
import java.util.List;

/** Override only the playtime board; levels, projects and quiz boards stay unchanged. */
@Pseudo
@Mixin(targets = "de.halfknife.leaderboards.HalfKnifeLeaderboards", remap = false)
public abstract class LeaderboardMixin {
    @Inject(method = "playtime", at = @At("HEAD"), cancellable = true, remap = false)
    private static void halfknife$activeRows(MinecraftServer server, CallbackInfoReturnable<List<?>> cir) {
        try {
            Class<?> rowType = Class.forName("de.halfknife.leaderboards.HalfKnifeLeaderboards$Row");
            var constructor = rowType.getDeclaredConstructor(String.class, long.class);
            constructor.setAccessible(true);
            List<Object> rows = new ArrayList<>();
            for (var entry : ActivePlaytimeMod.activeRanking().stream().limit(3).toList())
                rows.add(constructor.newInstance(entry.name(), entry.seconds()));
            cir.setReturnValue(rows);
        } catch (ReflectiveOperationException error) {
            throw new IllegalStateException("Cannot connect lobby playtime board to active time", error);
        }
    }

    @Redirect(method = "levels", at = @At(value = "INVOKE", target = "Ljava/util/Map;values()Ljava/util/Collection;"), remap = false)
    private static Collection<?> halfknife$levels(Map<?, ?> map) { return StatsExclusions.values(map); }

    @Redirect(method = "quiz", at = @At(value = "INVOKE", target = "Lcom/google/gson/JsonObject;entrySet()Ljava/util/Set;"), remap = false)
    private static Set<?> halfknife$quiz(JsonObject object) {
        Set<Object> result = new LinkedHashSet<>();
        for (var entry : object.entrySet()) if (!StatsExclusions.excluded(entry.getKey())) result.add(entry);
        return result;
    }
}

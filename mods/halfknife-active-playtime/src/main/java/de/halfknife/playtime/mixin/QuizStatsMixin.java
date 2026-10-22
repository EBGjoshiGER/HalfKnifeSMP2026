package de.halfknife.playtime.mixin;
import de.halfknife.playtime.StatsExclusions;
import java.util.*;
import org.spongepowered.asm.mixin.*;
import org.spongepowered.asm.mixin.injection.*;
@Pseudo
@Mixin(targets = "de.halfknife.quiz.manager.QuizStatsManager", remap = false)
public abstract class QuizStatsMixin {
    @Redirect(method = {"leaderboard", "findByName"}, at = @At(value = "INVOKE", target = "Ljava/util/Map;values()Ljava/util/Collection;"), remap = false)
    private static Collection<?> halfknife$values(Map<?, ?> map) { return StatsExclusions.values(map); }
}

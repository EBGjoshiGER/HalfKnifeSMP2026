package de.halfknife.playtime.mixin;
import de.halfknife.playtime.StatsExclusions;
import java.util.*;
import org.spongepowered.asm.mixin.*;
import org.spongepowered.asm.mixin.injection.*;
@Pseudo
@Mixin(targets = "de.halfknife.netherproject.ProjectState", remap = false)
public abstract class NetherStatsMixin {
    @Redirect(method = "leaderboard", at = @At(value = "INVOKE", target = "Ljava/util/Map;entrySet()Ljava/util/Set;"), remap = false)
    private Set<?> halfknife$entries(Map<?, ?> map) { return StatsExclusions.entries(map); }
}

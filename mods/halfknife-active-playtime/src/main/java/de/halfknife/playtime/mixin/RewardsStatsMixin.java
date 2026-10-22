package de.halfknife.playtime.mixin;
import de.halfknife.playtime.StatsExclusions;
import java.util.*;
import org.spongepowered.asm.mixin.*;
import org.spongepowered.asm.mixin.injection.*;
@Pseudo
@Mixin(targets = "com.sovern.playtimerewards.PlaytimeRewardsMod", remap = false)
public abstract class RewardsStatsMixin {
    @Redirect(method = "sortedLeaderboard(Lcom/sovern/playtimerewards/PlaytimeRewardsMod$LeaderboardSort;)Ljava/util/List;", at = @At(value = "INVOKE", target = "Ljava/util/Map;values()Ljava/util/Collection;"), remap = false)
    private Collection<?> halfknife$values(Map<?, ?> map) { return StatsExclusions.values(map); }
}

package de.halfknife.playtime.mixin;

import java.util.Map;
import java.util.UUID;
import net.minecraft.server.players.PlayerList;
import net.minecraft.stats.ServerStatsCounter;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

@Mixin(PlayerList.class)
public interface PlayerListAccessor {
    @Accessor("stats") Map<UUID, ServerStatsCounter> halfknife$getStats();
}

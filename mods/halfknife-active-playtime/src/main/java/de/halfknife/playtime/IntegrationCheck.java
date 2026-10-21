package de.halfknife.playtime;

import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.scores.ScoreHolder;

/** Isolated-CI check, enabled only through the test JVM flag. */
final class IntegrationCheck {
    static void run(MinecraftServer server) {
        var ranking = ActivePlaytimeMod.activeRanking();
        if (ranking.size() != 2 || !ranking.get(0).name().equals("ActiveAlice") || ranking.get(0).seconds() != 21600
                || ranking.get(1).seconds() != 7200) throw new AssertionError("Unexpected active ranking: " + ranking);
        ActivePlaytimeMod.publishScore(server, "ActiveAlice", ranking.get(0).seconds());
        var score = server.getScoreboard().getPlayerScoreInfo(ScoreHolder.forNameOnly("ActiveAlice"), server.getScoreboard().getObjective(ActivePlaytimeMod.ACTIVE_OBJECTIVE));
        if (score == null || score.value() != 432000) throw new AssertionError("Tab score must be active ticks");
        if (FabricLoader.getInstance().isModLoaded("halfknife_leaderboards")) {
            try {
                var method = Class.forName("de.halfknife.leaderboards.HalfKnifeLeaderboards").getDeclaredMethod("playtime", MinecraftServer.class);
                method.setAccessible(true);
                var rows = (java.util.List<?>) method.invoke(null, server);
                if (rows.size() != 2) throw new AssertionError("Lobby must use active ranking, not legacy rewards");
                var value = rows.get(0).getClass().getDeclaredMethod("value");
                value.setAccessible(true);
                if (((Long) value.invoke(rows.get(0))) != 21600L) throw new AssertionError("Wrong active lobby value");
            } catch (ReflectiveOperationException error) { throw new AssertionError(error); }
        } else throw new AssertionError("Lobby mod missing from integration server");
        System.out.println("HALFKNIFE INTEGRATION PASSED: active ranking, Tab ticks and lobby rows agree; AFK and non-whitelisted data excluded.");
    }
}

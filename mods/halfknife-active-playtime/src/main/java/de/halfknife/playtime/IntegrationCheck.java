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
        checkExclusions(server);
        System.out.println("HALFKNIFE INTEGRATION PASSED: active ranking, Tab ticks and lobby rows agree; AFK and non-whitelisted data excluded.");
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static void checkExclusions(MinecraftServer server) {
        try {
            // Exercise the installed project mixins before top-N truncation, preserving all saved points.
            for (String pkg : java.util.List.of("netherproject", "endproject")) {
                Class<?> type = Class.forName("de.halfknife." + pkg + ".ProjectState");
                Object state = type.getConstructor().newInstance();
                java.util.Map points = (java.util.Map)type.getField("playerPoints").get(state);
                java.util.Map names = (java.util.Map)type.getField("playerNames").get(state);
                points.put(StatsExclusions.TEST_ACCOUNT.toString(), 999);
                names.put(StatsExclusions.TEST_ACCOUNT.toString(), "RenamedTestAccount");
                points.put("00000000-0000-0000-0000-000000000001", 10);
                names.put("00000000-0000-0000-0000-000000000001", "ActiveAlice");
                var rows = (java.util.List<?>)type.getMethod("leaderboard", int.class).invoke(state, 1);
                if (rows.size() != 1 || !rows.get(0).getClass().getMethod("name").invoke(rows.get(0)).equals("ActiveAlice"))
                    throw new AssertionError("Project exclusion failed: " + pkg);
                if (points.size() != 2) throw new AssertionError("Filtering changed project data");
            }
            Class<?> boards = Class.forName("de.halfknife.leaderboards.HalfKnifeLeaderboards");
            var field = boards.getDeclaredField("data"); field.setAccessible(true);
            Object data = field.get(null);
            var levelsField = data.getClass().getDeclaredField("levels"); levelsField.setAccessible(true);
            java.util.Map levels = (java.util.Map)levelsField.get(data);
            java.util.Map original = new java.util.HashMap(levels);
            try {
                levels.clear();
                var ctor = Class.forName("de.halfknife.leaderboards.HalfKnifeLeaderboards$LevelEntry").getDeclaredConstructor(String.class, int.class);
                ctor.setAccessible(true);
                levels.put(StatsExclusions.TEST_ACCOUNT.toString(), ctor.newInstance("RenamedTestAccount", 999));
                levels.put("00000000-0000-0000-0000-000000000001", ctor.newInstance("ActiveAlice", 10));
                var method = boards.getDeclaredMethod("levels"); method.setAccessible(true);
                if (((java.util.List<?>)method.invoke(null)).size() != 1) throw new AssertionError("Level exclusion failed");
                if (levels.size() != 2) throw new AssertionError("Filtering changed levels");
            } finally { levels.clear(); levels.putAll(original); }
            System.out.println("UUID EXCLUSION PASSED: renamed test account filtered before project/level ranking; source data retained.");
        } catch (ReflectiveOperationException error) { throw new AssertionError(error); }
    }
}

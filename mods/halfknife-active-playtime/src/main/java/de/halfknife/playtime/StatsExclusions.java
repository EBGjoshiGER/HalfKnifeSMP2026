package de.halfknife.playtime;
import java.util.*;
/** Presentation-only exclusion: source saves and RAS remain available for testing. */
public final class StatsExclusions {
    public static final UUID TEST_ACCOUNT = UUID.fromString("2f4bd5e2-e184-43af-8ab5-df7670dbc530");
    public static boolean excluded(Object id) { return TEST_ACCOUNT.toString().equalsIgnoreCase(String.valueOf(id)); }
    public static Collection<?> values(Map<?, ?> source) {
        return source.entrySet().stream().filter(e -> !excluded(e.getKey())).map(Map.Entry::getValue).toList();
    }
    public static Set<?> entries(Map<?, ?> source) {
        Set<Object> result = new LinkedHashSet<>();
        for (var entry : source.entrySet()) if (!excluded(entry.getKey())) result.add(entry);
        return result;
    }
}

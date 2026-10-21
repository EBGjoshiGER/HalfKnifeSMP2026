package de.halfknife.playtime;

public final class ActiveClockTest {
    private static void equal(long actual, long expected) {
        if (actual != expected) throw new AssertionError(actual + " != " + expected);
    }
    public static void main(String[] args) {
        ActiveClock clock = new ActiveClock(0);
        clock.update(600_000);
        equal(clock.takeActive(), 300_000);
        equal(clock.takeAfk(), 300_000);
        clock.activity(600_000);
        clock.update(660_000);
        equal(clock.takeActive(), 60_000);
        equal(clock.takeAfk(), 0);
        clock.input(true, 660_000);
        clock.update(1_260_000);
        equal(clock.takeActive(), 600_000);
        clock.input(false, 1_260_000);
        clock.update(1_620_000);
        equal(clock.takeActive(), 300_000);
        equal(clock.takeAfk(), 60_000);
        clock.update(1_620_000);
        equal(clock.takeActive(), 0);
        // A new session must never count the time spent offline.
        ActiveClock nextSession = new ActiveClock(10_000_000);
        nextSession.update(10_001_000);
        equal(nextSession.takeActive(), 1_000);
        equal(nextSession.takeAfk(), 0);
        System.out.println("Active clock: timeout, resuming, held movement, release, boundaries and reconnect passed.");
    }
}

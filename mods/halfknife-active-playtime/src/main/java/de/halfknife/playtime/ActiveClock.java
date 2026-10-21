package de.halfknife.playtime;

/** Monotonic session clock; all arguments and counters are milliseconds. */
public final class ActiveClock {
    public static final long TIMEOUT = 300_000;
    private long lastUpdate;
    private long lastActivity;
    private boolean moving;
    private long active;
    private long afk;

    public ActiveClock(long now) { lastUpdate = now; lastActivity = now; }
    public void activity(long now) { update(now); lastActivity = now; }
    public void input(boolean moving, long now) {
        update(now);
        this.moving = moving;
        if (moving) lastActivity = now;
    }
    public void update(long now) {
        if (now <= lastUpdate) return;
        long elapsed = now - lastUpdate;
        long counted = moving ? elapsed : Math.max(0, Math.min(now, lastActivity + TIMEOUT) - lastUpdate);
        active += counted;
        afk += elapsed - counted;
        if (moving) lastActivity = now;
        lastUpdate = now;
    }
    public long takeActive() { long result = active; active = 0; return result; }
    public long takeAfk() { long result = afk; afk = 0; return result; }
}

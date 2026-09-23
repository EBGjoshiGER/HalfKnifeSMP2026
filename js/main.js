document.addEventListener("DOMContentLoaded", () => {
  renderNavigation();

  updateCountdown();

  if (document.getElementById("countdown")) {
    window.setInterval(updateCountdown, 1000);
  }

  if (document.getElementById("live-player-list")) {
    updateMinecraftServerStatus();

    window.setInterval(
      updateMinecraftServerStatus,
      minecraftStatusRefreshMs
    );
  }

  if (document.getElementById("whitelist-player-list")) {
    loadWhitelistPlayers();
  }
});


/* =========================================================
   NAVIGATION
   ========================================================= */

function renderNavigation() {
  const nav = document.getElementById("main-nav");

  if (!nav) {
    return;
  }

  const navigationItems = [
    ["index.html", "Startseite"],
    ["mods.html", "Mods"],
    ["install.html", "Installation"],
    ["players.html", "Spieler"],
    ["rules.html", "Regeln"],
    ["events.html", "Events"],
    ["discord.html", "Discord"]
  ];

  const currentPage =
    window.location.pathname.split("/").pop() || "index.html";

  nav.innerHTML = navigationItems
    .map(([href, label]) => {
      const activeClass =
        currentPage === href ? "active" : "";

      return `
        <a
          href="${href}"
          class="${activeClass}"
        >
          ${label}
        </a>
      `;
    })
    .join("");
}


/* =========================================================
   COUNTDOWN
   ========================================================= */

const serverStartDate =
  new Date("2026-10-24T14:00:00+02:00");

function updateCountdown() {
  const countdown = document.getElementById("countdown");

  if (!countdown) {
    return;
  }

  const now = new Date();
  const distance =
    serverStartDate.getTime() - now.getTime();

  if (distance <= 0) {
    countdown.textContent =
      "HalfKnife SMP 2026 ist gestartet!";

    return;
  }

  const days = Math.floor(
    distance / (1000 * 60 * 60 * 24)
  );

  const hours = Math.floor(
    (distance % (1000 * 60 * 60 * 24)) /
    (1000 * 60 * 60)
  );

  const minutes = Math.floor(
    (distance % (1000 * 60 * 60)) /
    (1000 * 60)
  );

  const seconds = Math.floor(
    (distance % (1000 * 60)) /
    1000
  );

  countdown.textContent =
    `${days} Tage, ` +
    `${hours} Stunden, ` +
    `${minutes} Minuten, ` +
    `${seconds} Sekunden`;
}


/* =========================================================
   SERVER-IP KOPIEREN
   ========================================================= */

function copyIP() {
  const serverIP =
    "halfknife2026.serverminer.com";

  navigator.clipboard
    .writeText(serverIP)
    .then(() => {
      const button =
        document.getElementById("copy-ip-button");

      if (!button) {
        return;
      }

      const originalText =
        button.textContent;

      button.textContent =
        "IP kopiert!";

      window.setTimeout(() => {
        button.textContent =
          originalText;
      }, 2000);
    })
    .catch(error => {
      console.error(
        "Server-IP konnte nicht kopiert werden:",
        error
      );
    });
}


/* =========================================================
   LIVE SERVERSTATUS
   ========================================================= */

const minecraftStatusRefreshMs =
  60 * 1000;

async function updateMinecraftServerStatus() {
  const playerList =
    document.getElementById(
      "live-player-list"
    );

  const statusDot =
    document.getElementById(
      "server-status-dot"
    );

  const statusLabel =
    document.getElementById(
      "server-status-label"
    );

  const playerCounter =
    document.getElementById(
      "live-player-counter"
    );

  const statusText =
    document.getElementById(
      "server-status-text"
    );

  const onlineCount =
    document.getElementById(
      "online-player-count"
    );

  const statusNote =
    document.getElementById(
      "live-status-note"
    );

  if (!playerList) {
    return;
  }

  try {
    const response = await fetch(
      `data/server-status.json?v=${Date.now()}`,
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error(
        `Serverstatus konnte nicht geladen werden: ${response.status}`
      );
    }

    const data =
      await response.json();

    const isOnline =
      Boolean(data.online);

    const players =
      Array.isArray(data.players)
        ? data.players
        : [];

    const currentPlayers =
      Number(
        data.onlineCount ??
        players.length
      );

    const maxPlayers =
      Number(
        data.maxPlayers ??
        25
      );


    /* -------------------------
       Statuspunkt
       ------------------------- */

    if (statusDot) {
      statusDot.classList.toggle(
        "online",
        isOnline
      );

      statusDot.classList.toggle(
        "offline",
        !isOnline
      );
    }


    /* -------------------------
       Statusbeschriftung
       ------------------------- */

    if (statusLabel) {
      statusLabel.textContent =
        isOnline
          ? "Server online"
          : "Server offline";
    }


    /* -------------------------
       Spielerzähler
       ------------------------- */

    if (playerCounter) {
      playerCounter.textContent =
        `${currentPlayers} / ${maxPlayers}`;
    }

    if (onlineCount) {
      onlineCount.textContent =
        currentPlayers;
    }


    /* -------------------------
       Statustext
       ------------------------- */

    if (statusText) {
      if (isOnline) {
        if (currentPlayers === 1) {
          statusText.textContent =
            "1 Spieler online";
        } else {
          statusText.textContent =
            `${currentPlayers} Spieler online`;
        }
      } else {
        statusText.textContent =
          "Server offline";
      }
    }


    /* -------------------------
       Letzte Aktualisierung
       ------------------------- */

    if (statusNote) {
      if (data.updatedAt) {
        const updated =
          new Date(
            data.updatedAt
          );

        statusNote.textContent =
          `Letzte Aktualisierung: ${updated.toLocaleString(
            "de-DE"
          )}`;
      } else {
        statusNote.textContent =
          "Serverstatus automatisch aktualisiert";
      }
    }


    /* -------------------------
       Server offline
       ------------------------- */

    if (!isOnline) {
      playerList.innerHTML = `
        <div class="feature">
          <h3>Server offline</h3>
          <p>
            Aktuell ist der Minecraft-Server
            nicht erreichbar.
          </p>
        </div>
      `;

      return;
    }


    /* -------------------------
       Niemand online
       ------------------------- */

    if (players.length === 0) {
      playerList.innerHTML = `
        <div class="feature">
          <h3>Niemand online</h3>
          <p>
            Aktuell ist kein Spieler
            auf dem Server.
          </p>
        </div>
      `;

      return;
    }


    /* -------------------------
       Spieler anzeigen
       ------------------------- */

    playerList.innerHTML =
      players
        .map(
          player => `
            <div class="feature">
              <h3>
                ${escapeHtml(player)}
              </h3>
            </div>
          `
        )
        .join("");

  } catch (error) {
    console.error(
      "Fehler beim Laden des Serverstatus:",
      error
    );

    if (statusDot) {
      statusDot.classList.remove(
        "online"
      );

      statusDot.classList.add(
        "offline"
      );
    }

    if (statusLabel) {
      statusLabel.textContent =
        "Status unbekannt";
    }

    if (statusText) {
      statusText.textContent =
        "Serverstatus konnte nicht geladen werden";
    }

    if (statusNote) {
      statusNote.textContent =
        "Fehler beim Aktualisieren des Live-Status";
    }

    if (playerCounter) {
      playerCounter.textContent =
        "– / 25";
    }

    if (onlineCount) {
      onlineCount.textContent =
        "–";
    }

    playerList.innerHTML = `
      <div class="feature">
        <h3>Status nicht verfügbar</h3>
        <p>
          Die Serverdaten konnten
          gerade nicht geladen werden.
        </p>
      </div>
    `;
  }
}


/* =========================================================
   WHITELIST
   ========================================================= */

async function loadWhitelistPlayers() {
  const playerList =
    document.getElementById(
      "whitelist-player-list"
    );

  const playerCount =
    document.getElementById(
      "whitelist-player-count"
    );

  const slotsCount =
    document.getElementById(
      "whitelist-slots-count"
    );

  if (!playerList) {
    return;
  }

  try {
    const response = await fetch(
      `data/whitelist.json?v=${Date.now()}`,
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error(
        `Whitelist konnte nicht geladen werden: ${response.status}`
      );
    }

    const whitelist =
      await response.json();

    const players =
      Array.isArray(whitelist)
        ? whitelist
            .filter(
              player =>
                player &&
                typeof player.name ===
                  "string"
            )
            .sort(
              (a, b) =>
                a.name.localeCompare(
                  b.name,
                  "de",
                  {
                    sensitivity: "base"
                  }
                )
            )
        : [];


    /* -------------------------
       Spieleranzahl
       ------------------------- */

    if (playerCount) {
      playerCount.textContent =
        `${players.length} freigeschaltet`;
    }


    /* -------------------------
       Spielerplätze
       ------------------------- */

    if (slotsCount) {
      slotsCount.textContent =
        `${players.length} / 25`;
    }


    /* -------------------------
       Leere Whitelist
       ------------------------- */

    if (players.length === 0) {
      playerList.innerHTML = `
        <div class="feature">
          <h3>
            Noch keine Spieler
          </h3>
          <p>
            Die Whitelist ist aktuell leer.
          </p>
        </div>
      `;

      return;
    }


    /* -------------------------
       Spieler anzeigen
       ------------------------- */

    playerList.innerHTML =
      players
        .map(
          player => `
            <div class="feature">
              <h3>
                ${escapeHtml(
                  player.name
                )}
              </h3>
            </div>
          `
        )
        .join("");

  } catch (error) {
    console.error(
      "Fehler beim Laden der Whitelist:",
      error
    );

    if (playerCount) {
      playerCount.textContent =
        "Nicht verfügbar";
    }

    if (slotsCount) {
      slotsCount.textContent =
        "– / 25";
    }

    playerList.innerHTML = `
      <div class="feature">
        <h3>
          Whitelist nicht verfügbar
        </h3>
        <p>
          Die Spielerliste konnte
          gerade nicht geladen werden.
        </p>
      </div>
    `;
  }
}


/* =========================================================
   HTML ESCAPING
   ========================================================= */

function escapeHtml(value) {
  return String(value)
    .replace(
      /&/g,
      "&amp;"
    )
    .replace(
      /</g,
      "&lt;"
    )
    .replace(
      />/g,
      "&gt;"
    )
    .replace(
      /"/g,
      "&quot;"
    )
    .replace(
      /'/g,
      "&#039;"
    );
}

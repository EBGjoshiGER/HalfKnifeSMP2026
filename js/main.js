// HalfKnife SMP 2026 – gemeinsame Website-Funktionen

document.addEventListener("DOMContentLoaded", () => {
  renderNavigation();
  updateCountdown();

  if (document.getElementById("countdown")) {
    window.setInterval(updateCountdown, 1000);
  }

  if (document.getElementById("live-player-list")) {
    updateMinecraftServerStatus();
    window.setInterval(updateMinecraftServerStatus, minecraftStatusRefreshMs);
  }

  if (document.getElementById("whitelist-player-list")) {
    loadWhitelistPlayers();
  }
});


// =========================================================
// NAVIGATION
// =========================================================

function renderNavigation() {
  const nav = document.getElementById("main-nav");

  if (!nav) {
    return;
  }

  const current =
    (window.location.pathname.split("/").pop() || "index.html")
      .toLowerCase();

  const items = [
    ["index.html", "Startseite"],
    ["mods.html", "Mods"],
    ["install.html", "Installation"],
    ["players.html", "Spieler"],
    ["rules.html", "Regeln"],
    ["events.html", "Events"],
    ["discord.html", "Discord"]
  ];

  nav.innerHTML = items
    .map(([href, label]) => {
      const active =
        current === href
          ? ' class="active"'
          : "";

      return `
        <a href="${href}"${active}>
          ${label}
        </a>
      `;
    })
    .join("");
}


// =========================================================
// COUNTDOWN
// =========================================================

const startDate =
  new Date("2026-10-24T14:00:00+02:00");


function updateCountdown() {
  const countdown =
    document.getElementById("countdown");

  if (!countdown) {
    return;
  }

  const diff =
    startDate.getTime() - Date.now();


  if (diff <= 0) {
    countdown.innerHTML =
      "🟢 Der Server ist jetzt ONLINE!";

    return;
  }


  const days =
    Math.floor(
      diff / (1000 * 60 * 60 * 24)
    );


  const hours =
    Math.floor(
      (diff / (1000 * 60 * 60)) % 24
    );


  const minutes =
    Math.floor(
      (diff / (1000 * 60)) % 60
    );


  const seconds =
    Math.floor(
      (diff / 1000) % 60
    );


  countdown.innerHTML =
    `${days} Tage · ${hours} Std · ${minutes} Min · ${seconds} Sek`;
}


// =========================================================
// SERVER-IP KOPIEREN
// =========================================================

function copyIP() {
  const ipElement =
    document.getElementById("server-ip");

  if (!ipElement) {
    return;
  }


  navigator.clipboard.writeText(
    ipElement.innerText
  );


  const button =
    document.querySelector(".copy-button");

  if (!button) {
    return;
  }


  const oldText =
    button.innerHTML;


  button.innerHTML =
    "✓";


  window.setTimeout(() => {
    button.innerHTML = oldText;
  }, 1500);
}


// =========================================================
// LIVE MINECRAFT SERVERSTATUS
// =========================================================

const minecraftServerAddress =
  "halfknife2026.serverminer.com";


const minecraftStatusApi =
  `https://api.mcsrvstat.us/3/${encodeURIComponent(
    minecraftServerAddress
  )}`;


const minecraftStatusRefreshMs =
  60 * 1000;


async function updateMinecraftServerStatus() {
  const list =
    document.getElementById(
      "live-player-list"
    );


  if (!list) {
    return;
  }


  const dot =
    document.getElementById(
      "server-status-dot"
    );


  const label =
    document.getElementById(
      "server-status-label"
    );


  const counter =
    document.getElementById(
      "live-player-counter"
    );


  const summary =
    document.getElementById(
      "server-status-text"
    );


  const countCard =
    document.getElementById(
      "online-player-count"
    );


  const note =
    document.getElementById(
      "live-status-note"
    );


  try {
    const response =
      await fetch(
        minecraftStatusApi,
        {
          method: "GET",
          mode: "cors",
          cache: "no-store"
        }
      );


    if (!response.ok) {
      throw new Error(
        `Status-API HTTP ${response.status}`
      );
    }


    const data =
      await response.json();


    // -----------------------------------------------------
    // SERVER OFFLINE
    // -----------------------------------------------------

    if (!data.online) {
      dot?.classList.remove(
        "loading",
        "online"
      );


      dot?.classList.add(
        "offline"
      );


      if (label) {
        label.textContent =
          "Server offline";
      }


      if (counter) {
        counter.textContent =
          "0 / –";
      }


      if (summary) {
        summary.textContent =
          "Der Server ist aktuell nicht erreichbar.";
      }


      if (countCard) {
        countCard.textContent =
          "0 online";
      }


      list.innerHTML = `
        <div class="live-player-empty">
          Aktuell ist niemand auf dem Server.
        </div>
      `;


      return;
    }


    // -----------------------------------------------------
    // SERVER ONLINE
    // -----------------------------------------------------

    const online =
      Number(
        data.players?.online ?? 0
      );


    const max =
      Number(
        data.players?.max ?? 0
      );


    const players =
      Array.isArray(
        data.players?.list
      )
        ? data.players.list
        : [];


    dot?.classList.remove(
      "loading",
      "offline"
    );


    dot?.classList.add(
      "online"
    );


    if (label) {
      label.textContent =
        "Server online";
    }


    if (counter) {
      counter.textContent =
        `${online} / ${max || "–"}`;
    }


    if (summary) {
      summary.textContent =
        online === 1
          ? "Aktuell ist 1 Spieler online."
          : `Aktuell sind ${online} Spieler online.`;
    }


    if (countCard) {
      countCard.textContent =
        `${online} online`;
    }


    // -----------------------------------------------------
    // KEIN SPIELER ONLINE
    // -----------------------------------------------------

    if (online === 0) {
      list.innerHTML = `
        <div class="live-player-empty">
          Aktuell ist niemand auf dem Server.
        </div>
      `;


      if (note) {
        note.textContent = "";
      }


      return;
    }


    // -----------------------------------------------------
    // SPIELER ONLINE, ABER KEINE NAMEN
    // -----------------------------------------------------

    if (players.length === 0) {
      list.innerHTML = `
        <div class="live-player-empty">
          ${online} Spieler online –
          die Namen werden vom Serverstatus
          derzeit nicht übertragen.
        </div>
      `;


      if (note) {
        note.textContent =
          "Die Anzahl der Online-Spieler ist verfügbar, die Namen werden vom Statusdienst momentan jedoch nicht vollständig übertragen.";
      }


      return;
    }


    // -----------------------------------------------------
    // SPIELERNAMEN ANZEIGEN
    // -----------------------------------------------------

    list.innerHTML =
      players
        .map(player => `
          <div class="live-player">
            ${escapeHtml(
              player.name ||
              "Unbekannt"
            )}
          </div>
        `)
        .join("");


    if (
      players.length < online &&
      note
    ) {
      note.textContent =
        `${online} Spieler online, aber nur ${players.length} Namen wurden übermittelt.`;
    } else if (note) {
      note.textContent =
        "Der Serverstatus wird automatisch aktualisiert.";
    }

  } catch (error) {
    console.error(
      "Minecraft-Serverstatus konnte nicht geladen werden:",
      error
    );


    dot?.classList.remove(
      "loading",
      "online"
    );


    dot?.classList.add(
      "offline"
    );


    if (label) {
      label.textContent =
        "Status nicht verfügbar";
    }


    if (counter) {
      counter.textContent =
        "– / –";
    }


    if (summary) {
      summary.textContent =
        "Der Live-Status konnte gerade nicht geladen werden.";
    }


    if (countCard) {
      countCard.textContent =
        "–";
    }


    list.innerHTML = `
      <div class="live-player-error">
        Live-Spielerliste momentan nicht verfügbar.
        Bitte später erneut versuchen.
      </div>
    `;


    if (note) {
      note.textContent =
        "";
    }
  }
}


// =========================================================
// WHITELIST / FREIGESCHALTETE SPIELER
// =========================================================

async function loadWhitelistPlayers() {
  const container =
    document.getElementById(
      "whitelist-player-list"
    );


  if (!container) {
    return;
  }


  const whitelistCount =
    document.getElementById(
      "whitelist-player-count"
    );


  const slotsCount =
    document.getElementById(
      "whitelist-slots-count"
    );


  try {
    const response =
      await fetch(
        `data/whitelist.json?v=${Date.now()}`,
        {
          method: "GET",
          cache: "no-store"
        }
      );


    if (!response.ok) {
      throw new Error(
        `Whitelist HTTP ${response.status}`
      );
    }


    const data =
      await response.json();


    const players =
      Array.isArray(data)
        ? data
            .filter(
              player =>
                player &&
                typeof player.name === "string" &&
                player.name.trim()
            )
            .sort(
              (a, b) =>
                a.name.localeCompare(
                  b.name,
                  "de",
                  {
                    sensitivity:
                      "base"
                  }
                )
            )
        : [];


    const count =
      players.length;


    // -----------------------------------------------------
    // ANZAHL FREIGESCHALTETER SPIELER
    // -----------------------------------------------------

    if (whitelistCount) {
      whitelistCount.textContent =
        `${count} freigeschaltet`;
    }


    // -----------------------------------------------------
    // SPIELERPLÄTZE
    // -----------------------------------------------------

    if (slotsCount) {
      slotsCount.textContent =
        `${count} / 25`;
    }


    // -----------------------------------------------------
    // KEINE SPIELER
    // -----------------------------------------------------

    if (count === 0) {
      container.innerHTML = `
        <div class="feature">
          <h3>
            Noch keine Spieler freigeschaltet
          </h3>

          <p>
            Die Whitelist ist aktuell leer.
          </p>
        </div>
      `;


      return;
    }


    // -----------------------------------------------------
    // SPIELERKARTEN ERZEUGEN
    // -----------------------------------------------------

    container.innerHTML =
      players
        .map(player => `
          <div class="feature">
            <h3>
              ${escapeHtml(player.name)}
            </h3>
          </div>
        `)
        .join("");

  } catch (error) {
    console.error(
      "Whitelist konnte nicht geladen werden:",
      error
    );


    if (whitelistCount) {
      whitelistCount.textContent =
        "Nicht verfügbar";
    }


    if (slotsCount) {
      slotsCount.textContent =
        "– / 25";
    }


    container.innerHTML = `
      <div class="feature">

        <h3>
          Whitelist momentan nicht verfügbar
        </h3>

        <p>
          Die Spielerliste konnte gerade
          nicht geladen werden.
        </p>

      </div>
    `;
  }
}


// =========================================================
// HTML SICHER AUSGEBEN
// =========================================================

function escapeHtml(value) {
  return String(value)

    .replaceAll(
      "&",
      "&amp;"
    )

    .replaceAll(
      "<",
      "&lt;"
    )

    .replaceAll(
      ">",
      "&gt;"
    )

    .replaceAll(
      '"',
      "&quot;"
    )

    .replaceAll(
      "'",
      "&#039;"
    );
}

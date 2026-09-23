// =========================================================
// HALFKNIFE SMP 2026
// Gemeinsame Website-Funktionen
// =========================================================


document.addEventListener(
  "DOMContentLoaded",
  () => {

    renderNavigation();


    // =====================================================
    // COUNTDOWN
    // =====================================================

    if (
      document.getElementById(
        "countdown"
      )
    ) {

      updateCountdown();

      window.setInterval(
        updateCountdown,
        1000
      );

    }


    // =====================================================
    // LIVE SERVERSTATUS
    // =====================================================

    if (
      document.getElementById(
        "live-player-list"
      )
    ) {

      updateMinecraftServerStatus();

      window.setInterval(
        updateMinecraftServerStatus,
        minecraftStatusRefreshMs
      );

    }


    // =====================================================
    // WHITELIST
    // =====================================================

    if (
      document.getElementById(
        "whitelist-player-list"
      )
    ) {

      loadWhitelistPlayers();

    }

  }
);


// =========================================================
// NAVIGATION
// =========================================================

function renderNavigation() {

  const nav =
    document.getElementById(
      "main-nav"
    );


  if (!nav) {
    return;
  }


  const navigationItems = [

    [
      "index.html",
      "Startseite"
    ],

    [
      "mods.html",
      "Mods"
    ],

    [
      "install.html",
      "Installation"
    ],

    [
      "players.html",
      "Spieler"
    ],

    [
      "rules.html",
      "Regeln"
    ],

    [
      "events.html",
      "Events"
    ],

    [
      "discord.html",
      "Discord"
    ]

  ];


  const currentPage =
    window.location.pathname
      .split("/")
      .pop()
      .toLowerCase()
      ||
      "index.html";


  nav.innerHTML =
    navigationItems

      .map(
        ([href, label]) => {

          const activeClass =
            currentPage === href
              ? "active"
              : "";


          return `
            <a
              href="${href}"
              class="${activeClass}"
            >
              ${label}
            </a>
          `;

        }
      )

      .join("");

}


// =========================================================
// COUNTDOWN
// =========================================================

const serverStartDate =
  new Date(
    "2026-10-24T14:00:00+02:00"
  );


function updateCountdown() {

  const countdown =
    document.getElementById(
      "countdown"
    );


  if (!countdown) {
    return;
  }


  const daysElement =
    document.getElementById(
      "countdown-days"
    );


  const hoursElement =
    document.getElementById(
      "countdown-hours"
    );


  const minutesElement =
    document.getElementById(
      "countdown-minutes"
    );


  const secondsElement =
    document.getElementById(
      "countdown-seconds"
    );


  const onlineElement =
    document.getElementById(
      "countdown-online"
    );


  const now =
    new Date();


  const distance =
    serverStartDate.getTime()
    -
    now.getTime();


  // =======================================================
  // SERVERSTART ERREICHT
  // =======================================================

  if (distance <= 0) {

    countdown.hidden = true;


    if (onlineElement) {
      onlineElement.hidden = false;
    }


    return;

  }


  countdown.hidden = false;


  if (onlineElement) {
    onlineElement.hidden = true;
  }


  if (
    !daysElement
    ||
    !hoursElement
    ||
    !minutesElement
    ||
    !secondsElement
  ) {

    return;

  }


  const days =
    Math.floor(
      distance
      /
      (
        1000
        *
        60
        *
        60
        *
        24
      )
    );


  const hours =
    Math.floor(
      (
        distance
        %
        (
          1000
          *
          60
          *
          60
          *
          24
        )
      )
      /
      (
        1000
        *
        60
        *
        60
      )
    );


  const minutes =
    Math.floor(
      (
        distance
        %
        (
          1000
          *
          60
          *
          60
        )
      )
      /
      (
        1000
        *
        60
      )
    );


  const seconds =
    Math.floor(
      (
        distance
        %
        (
          1000
          *
          60
        )
      )
      /
      1000
    );


  daysElement.textContent =
    String(days)
      .padStart(
        2,
        "0"
      );


  hoursElement.textContent =
    String(hours)
      .padStart(
        2,
        "0"
      );


  minutesElement.textContent =
    String(minutes)
      .padStart(
        2,
        "0"
      );


  secondsElement.textContent =
    String(seconds)
      .padStart(
        2,
        "0"
      );

}


// =========================================================
// SERVER-IP KOPIEREN
// =========================================================

function copyIP() {

  const ipElement =
    document.getElementById(
      "server-ip"
    );


  if (!ipElement) {
    return;
  }


  const serverIP =
    ipElement.innerText.trim();


  navigator.clipboard
    .writeText(
      serverIP
    )

    .then(
      () => {

        const button =
          document.querySelector(
            ".copy-button"
          );


        if (!button) {
          return;
        }


        const originalText =
          button.innerHTML;


        button.innerHTML =
          "✓";


        window.setTimeout(
          () => {

            button.innerHTML =
              originalText;

          },
          1500
        );

      }
    )

    .catch(
      error => {

        console.error(
          "Server-IP konnte nicht kopiert werden:",
          error
        );

      }
    );

}


// =========================================================
// LIVE SERVERSTATUS
// =========================================================

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

    const response =
      await fetch(
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
      Boolean(
        data.online
      );


    const players =
      Array.isArray(
        data.players
      )
        ? data.players
        : [];


    const currentPlayers =
      Number(
        data.onlineCount
        ??
        players.length
      );


    const maxPlayers =
      Number(
        data.maxPlayers
        ??
        25
      );


    // =====================================================
    // STATUSPUNKT
    // =====================================================

    if (statusDot) {

      statusDot.classList.remove(
        "loading",
        "online",
        "offline"
      );


      statusDot.classList.add(
        isOnline
          ? "online"
          : "offline"
      );

    }


    // =====================================================
    // STATUSLABEL
    // =====================================================

    if (statusLabel) {

      statusLabel.textContent =
        isOnline
          ? "Server online"
          : "Server offline";

    }


    // =====================================================
    // SPIELERZÄHLER
    // =====================================================

    if (playerCounter) {

      playerCounter.textContent =
        `${currentPlayers} / ${maxPlayers}`;

    }


    if (onlineCount) {

      onlineCount.textContent =
        currentPlayers === 1
          ? "1 online"
          : `${currentPlayers} online`;

    }


    // =====================================================
    // STATUSTEXT
    // =====================================================

    if (statusText) {

      if (!isOnline) {

        statusText.textContent =
          "Der Server ist aktuell offline.";

      }

      else if (
        currentPlayers === 0
      ) {

        statusText.textContent =
          "Der Server ist online. Aktuell ist niemand verbunden.";

      }

      else if (
        currentPlayers === 1
      ) {

        statusText.textContent =
          "Aktuell ist 1 Spieler online.";

      }

      else {

        statusText.textContent =
          `Aktuell sind ${currentPlayers} Spieler online.`;

      }

    }


    // =====================================================
    // LETZTE AKTUALISIERUNG
    // =====================================================

    if (statusNote) {

      if (data.updatedAt) {

        const updated =
          new Date(
            data.updatedAt
          );


        statusNote.textContent =
          `Letzte Statusänderung: ${updated.toLocaleString(
            "de-DE"
          )}`;

      }

      else {

        statusNote.textContent =
          "Serverstatus wird automatisch aktualisiert.";

      }

    }


    // =====================================================
    // SERVER OFFLINE
    // =====================================================

    if (!isOnline) {

      playerList.innerHTML = `
        <div class="live-player-empty">
          Der Minecraft-Server ist aktuell offline.
        </div>
      `;


      return;

    }


    // =====================================================
    // SERVER ONLINE, ABER NIEMAND DRAUF
    // =====================================================

    if (
      players.length === 0
    ) {

      playerList.innerHTML = `
        <div class="live-player-empty">
          Aktuell ist niemand auf dem Server.
        </div>
      `;


      return;

    }


    // =====================================================
    // SPIELER ANZEIGEN
    // =====================================================

    playerList.innerHTML =
      players

        .map(
          player => `
            <div class="live-player">
              ${escapeHtml(player)}
            </div>
          `
        )

        .join("");

  }

  catch (error) {

    console.error(
      "Fehler beim Laden des Serverstatus:",
      error
    );


    if (statusDot) {

      statusDot.classList.remove(
        "loading",
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
        "Der Serverstatus konnte gerade nicht geladen werden.";

    }


    if (statusNote) {

      statusNote.textContent =
        "Fehler beim Aktualisieren des Serverstatus.";

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
      <div class="live-player-error">
        Live-Spielerliste momentan nicht verfügbar.
      </div>
    `;

  }

}


// =========================================================
// WHITELIST
// =========================================================

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

    const response =
      await fetch(
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
      Array.isArray(
        whitelist
      )

        ? whitelist

            .filter(
              player =>
                player
                &&
                typeof player.name
                  === "string"
                &&
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


    // =====================================================
    // FREIGESCHALTETE SPIELER
    // =====================================================

    if (playerCount) {

      playerCount.textContent =
        `${players.length} freigeschaltet`;

    }


    // =====================================================
    // SPIELERPLÄTZE
    // =====================================================

    if (slotsCount) {

      slotsCount.textContent =
        `${players.length} / 25`;

    }


    // =====================================================
    // LEERE WHITELIST
    // =====================================================

    if (
      players.length === 0
    ) {

      playerList.innerHTML = `
        <div class="feature">
          <h3>
            Noch keine Spieler freigeschaltet
          </h3>
        </div>
      `;


      return;

    }


    // =====================================================
    // SPIELER ANZEIGEN
    // =====================================================

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

  }

  catch (error) {

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


// =========================================================
// HTML ESCAPING
// =========================================================

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

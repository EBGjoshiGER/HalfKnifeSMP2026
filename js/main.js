// HalfKnife SMP 2026 – gemeinsame Website-Funktionen

document.addEventListener("DOMContentLoaded", () => {
  renderNavigation();
  updateCountdown();

  if (document.getElementById("countdown")) {
    window.setInterval(updateCountdown, 1000);
  }
});

function renderNavigation() {
  const nav = document.getElementById("main-nav");
  if (!nav) return;

  const current = (window.location.pathname.split("/").pop() || "index.html").toLowerCase();
  const items = [
    ["index.html", "Startseite"],
    ["mods.html", "Mods"],
    ["install.html", "Installation"],
    ["players.html", "Spieler"],
    ["rules.html", "Regeln"],
    ["events.html", "Events"],
    ["discord.html", "Discord"]
  ];

  nav.innerHTML = items.map(([href, label]) => {
    const active = current === href ? ' class="active"' : "";
    return `<a href="${href}"${active}>${label}</a>`;
  }).join("");
}

const startDate = new Date("2026-10-24T14:00:00+02:00");

function updateCountdown() {
  const countdown = document.getElementById("countdown");
  if (!countdown) return;

  const diff = startDate.getTime() - Date.now();
  if (diff <= 0) {
    countdown.innerHTML = "🟢 Der Server ist jetzt ONLINE!";
    return;
  }

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
  const minutes = Math.floor((diff / (1000 * 60)) % 60);
  const seconds = Math.floor((diff / 1000) % 60);
  countdown.innerHTML = `${days} Tage · ${hours} Std · ${minutes} Min · ${seconds} Sek`;
}

function copyIP() {
  const ipElement = document.getElementById("server-ip");
  if (!ipElement) return;

  navigator.clipboard.writeText(ipElement.innerText);
  const button = document.querySelector(".copy-button");
  if (!button) return;

  const oldText = button.innerHTML;
  button.innerHTML = "✓";
  window.setTimeout(() => { button.innerHTML = oldText; }, 1500);
}

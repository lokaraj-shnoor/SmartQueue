// The wall board is the one screen nobody touches, so it keeps itself current:
// a ticking clock, and a full reload on the interval the server asked for.
// Reloading beats polling here — the page is small, and a stale board is worse
// than a blink.
(() => {
  const body = document.body;
  const seconds = Number(body.dataset.refresh) || 15;

  const clock = document.querySelector("[data-clock]");
  if (clock) {
    const tick = () => {
      const now = new Date();
      clock.textContent =
        String(now.getHours()).padStart(2, "0") + ":" + String(now.getMinutes()).padStart(2, "0");
    };
    tick();
    setInterval(tick, 10000);
  }

  // Don't reload a board nobody is looking at; catch up when it comes back.
  let due = Date.now() + seconds * 1000;
  setInterval(() => {
    if (document.hidden || Date.now() < due) {
      return;
    }
    window.location.reload();
  }, 1000);

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      due = Date.now();
    }
  });
})();

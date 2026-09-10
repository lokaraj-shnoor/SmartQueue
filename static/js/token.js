// The visitor's page watches its own token so nobody has to sit refreshing.
//
// Deliberately a poll rather than web push: push needs a service worker, VAPID
// keys and a subscription stored per device, and it still cannot reach a phone
// whose browser has been swiped away. A poll is honest about what it does —
// it works while the page is open, including in a background tab, which is
// exactly how somebody waits in a room with their phone in their hand.
(() => {
  const page = document.querySelector("[data-token-watch]");
  if (!page) {
    return;
  }

  const endpoint = page.dataset.tokenWatch;
  const askButton = document.querySelector("[data-notify-ask]");
  const numberEl = document.querySelector("[data-token-code]");
  const aheadEl = document.querySelector("[data-token-ahead]");
  const etaEl = document.querySelector("[data-token-eta]");
  const counterEl = document.querySelector("[data-token-counter]");
  const labelEl = document.querySelector("[data-token-label]");

  const supported = "Notification" in window;
  let worker = null;

  // Chrome refuses `new Notification(...)` from a page and insists the alert
  // comes from a service worker registration. Register one up front so it is
  // ready by the time a number is called.
  async function readyWorker() {
    if (worker || !("serviceWorker" in navigator)) {
      return worker;
    }
    try {
      await navigator.serviceWorker.register("/sw.js");
      worker = await navigator.serviceWorker.ready;
    } catch (err) {
      console.warn("Smart Queue: service worker unavailable, falling back.", err);
    }
    return worker;
  }
  let lastStatus = page.dataset.tokenStatus || "";
  let notified = lastStatus === "called" || lastStatus === "serving";
  let stopped = false;

  function paintPermission() {
    if (!askButton) {
      return;
    }
    if (!supported) {
      askButton.hidden = true;
      return;
    }
    const state = Notification.permission;
    askButton.hidden = state === "granted";
    askButton.textContent =
      state === "denied" ? "Alerts blocked in your browser" : "Alert me when I'm called";
    askButton.disabled = state === "denied";
  }

  if (askButton && supported) {
    askButton.addEventListener("click", async () => {
      // Chrome throws rather than resolving when the call is not from a
      // gesture, and Safari still wants the callback form.
      let state;
      try {
        state = await Notification.requestPermission();
      } catch (err) {
        state = await new Promise((resolve) => Notification.requestPermission(resolve));
      }
      paintPermission();
      if (state === "granted") {
        await readyWorker();
        // Prove the whole path works at the moment permission is given,
        // rather than leaving someone to discover it failed when it mattered.
        show("Alerts are on", {
          body: "We will tell you the moment your number is called.",
          tag: "smart-queue-ready",
        });
      }
    });
  }
  paintPermission();
  if (supported && Notification.permission === "granted") {
    readyWorker();
  }

  // One way in for every alert: the registration when there is one, the page
  // constructor otherwise, and a loud console line when neither works.
  async function show(title, options) {
    if (!supported || Notification.permission !== "granted") {
      return false;
    }
    const registration = await readyWorker();
    try {
      if (registration) {
        await registration.showNotification(title, options);
        return true;
      }
      new Notification(title, options);
      return true;
    } catch (err) {
      console.warn("Smart Queue: could not show the alert.", err);
      return false;
    }
  }

  function announce(data) {
    const where = data.counter ? "Counter " + data.counter : "the counter";
    const body = data.counter_name
      ? where + " (" + data.counter_name + ") is ready for you."
      : "Please go to " + where + ".";

    show(data.code + " - it's your turn", {
      body,
      tag: "smart-queue-" + data.entry_id, // one alert per token, not one per poll
      requireInteraction: true,
      icon: page.dataset.notifyIcon || undefined,
      badge: page.dataset.notifyIcon || undefined,
      vibrate: [200, 100, 200],
      data: { url: window.location.pathname },
    });

    // The page itself says so too, for anyone who declined notifications or
    // is looking straight at it.
    document.title = "Your turn — " + data.code;
    page.classList.add("is-called");
  }

  function paint(data) {
    if (!data.holding) {
      // The token was served, skipped or given up: the page is out of date.
      window.location.reload();
      return;
    }
    if (numberEl) numberEl.textContent = data.code;
    if (aheadEl) aheadEl.textContent = data.ahead;
    if (etaEl) etaEl.textContent = data.eta_minutes ? data.eta_minutes + " min" : "Any moment";
    if (counterEl) counterEl.textContent = data.counter || "Not assigned";
    if (labelEl) labelEl.textContent = data.status_label;

    if (data.is_up && !notified) {
      notified = true;
      announce(data);
    }
    if (!data.is_up) {
      notified = false;
      page.classList.remove("is-called");
    }
    lastStatus = data.status;
  }

  async function check() {
    if (stopped) {
      return;
    }
    try {
      const response = await fetch(endpoint, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "fetch" },
      });
      if (response.status === 403 || response.status === 302) {
        stopped = true; // signed out in another tab
        return;
      }
      paint(await response.json());
    } catch (err) {
      console.warn("Smart Queue: status check failed.", err);
      // A dropped connection is normal on a phone moving between cells.
      // Stay quiet and try again on the next tick.
    }
  }

  // Every 10s while the tab is visible, backing off to 30s when it is not, so
  // a page left open all afternoon is not hammering the server.
  let timer = null;
  function schedule() {
    clearInterval(timer);
    timer = setInterval(check, document.hidden ? 30000 : 10000);
  }
  document.addEventListener("visibilitychange", () => {
    schedule();
    if (!document.hidden) {
      check();
    }
  });
  schedule();
  check();
})();

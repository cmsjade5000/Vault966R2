(() => {
  const DEFAULT_TIMEOUT_MS = 20 * 60 * 1000;
  const ACTIVITY_KEY = "vault966:lastActivity";
  const ACTIVITY_EVENTS = [
    "pointerdown",
    "pointermove",
    "keydown",
    "touchstart",
    "scroll",
  ];

  const createController = ({
    documentLike,
    windowLike,
    storageLike,
    now = () => Date.now(),
    setTimer = window.setTimeout.bind(window),
    clearTimer = window.clearTimeout.bind(window),
    lock = null,
  }) => {
    const root = documentLike.body;
    if (!root?.hasAttribute("data-vault-auto-lock")) return null;

    const configuredTimeout = Number(
      root.getAttribute("data-vault-auto-lock-ms"),
    );
    const timeoutMs =
      Number.isFinite(configuredTimeout) && configuredTimeout > 0
        ? configuredTimeout
        : DEFAULT_TIMEOUT_MS;

    let timerId = null;
    let lastActivity = now();
    let locked = false;

    const readStoredActivity = () => {
      try {
        const stored = Number(storageLike?.getItem(ACTIVITY_KEY));
        return Number.isFinite(stored) && stored > 0 ? stored : null;
      } catch (error) {
        console.warn("Failed to read auto-lock activity", error);
        return null;
      }
    };

    const writeStoredActivity = (timestamp) => {
      try {
        storageLike?.setItem(ACTIVITY_KEY, String(timestamp));
      } catch (error) {
        console.warn("Failed to persist auto-lock activity", error);
      }
    };

    const submitLogout = () => {
      const form = documentLike.createElement("form");
      form.method = "post";
      form.action = "/logout";
      form.hidden = true;
      documentLike.body.appendChild(form);
      form.submit();
    };

    const lockVault = () => {
      if (locked) return;
      locked = true;
      if (timerId !== null) clearTimer(timerId);
      try {
        storageLike?.removeItem(ACTIVITY_KEY);
      } catch (error) {
        console.warn("Failed to clear auto-lock activity", error);
      }
      (lock || submitLogout)();
    };

    const schedule = () => {
      if (locked) return;
      if (timerId !== null) clearTimer(timerId);
      const storedActivity = readStoredActivity();
      if (storedActivity && storedActivity > lastActivity) {
        lastActivity = storedActivity;
      }
      const remaining = timeoutMs - (now() - lastActivity);
      if (remaining <= 0) {
        lockVault();
        return;
      }
      timerId = setTimer(lockVault, remaining);
    };

    const markActivity = () => {
      if (locked) return;
      const timestamp = now();
      if (timestamp - lastActivity < 1000) return;
      lastActivity = timestamp;
      writeStoredActivity(lastActivity);
      schedule();
    };

    const checkElapsed = () => {
      if (documentLike.visibilityState === "hidden") return;
      schedule();
    };

    const syncFromStorage = (event) => {
      if (event.key !== ACTIVITY_KEY || !event.newValue) return;
      const timestamp = Number(event.newValue);
      if (!Number.isFinite(timestamp) || timestamp <= lastActivity) return;
      lastActivity = timestamp;
      schedule();
    };

    ACTIVITY_EVENTS.forEach((eventName) => {
      documentLike.addEventListener(eventName, markActivity, {
        capture: true,
        passive: true,
      });
    });
    documentLike.addEventListener("visibilitychange", checkElapsed);
    windowLike.addEventListener("focus", checkElapsed);
    windowLike.addEventListener("pageshow", checkElapsed);
    windowLike.addEventListener("storage", syncFromStorage);

    writeStoredActivity(lastActivity);
    schedule();

    return {
      activityKey: ACTIVITY_KEY,
      checkElapsed,
      getLastActivity: () => lastActivity,
      getRemainingMs: () => Math.max(0, timeoutMs - (now() - lastActivity)),
      lockNow: lockVault,
      markActivity,
      timeoutMs,
    };
  };

  const init = () => {
    const controller = createController({
      documentLike: document,
      windowLike: window,
      storageLike: window.localStorage,
    });
    window.VaultAutoLock = controller;
    if (controller) {
      document.body.setAttribute("data-vault-auto-lock-ready", "");
    }
  };

  window.VaultAutoLockSupport = {
    ACTIVITY_KEY,
    DEFAULT_TIMEOUT_MS,
    createController,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();

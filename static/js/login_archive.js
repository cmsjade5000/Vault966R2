(() => {
  const initArchive = () => {
    const dataEl = document.getElementById("login-archive-data");
    if (!dataEl) return;
    let posterUrls = [];
    try {
      const data = JSON.parse(dataEl.textContent || "{}");
      posterUrls = Array.isArray(data.posters) ? data.posters : [];
    } catch (error) {
      console.warn("Failed to parse login archive data", error);
      return;
    }

    const slots = Array.from(
      document.querySelectorAll(".login-archive__poster"),
    );
    if (!slots.length || posterUrls.length < 2) return;

    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (prefersReduced) return;

    const shuffle = (arr) => {
      const copy = [...arr];
      for (let i = copy.length - 1; i > 0; i -= 1) {
        const j = Math.floor(Math.random() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
      }
      return copy;
    };

    let pool = shuffle(posterUrls);
    let pointer = slots.length;

    const nextUrl = () => {
      if (pool.length === 0) return "";
      if (pointer >= pool.length) {
        pool = shuffle(posterUrls);
        pointer = 0;
      }
      const url = pool[pointer] || "";
      pointer += 1;
      return url;
    };

    const applySlot = (slot, url) => {
      if (!slot || !url) return;
      let img = slot.querySelector("img");
      if (!img) {
        img = document.createElement("img");
        img.alt = "";
        img.loading = "lazy";
        img.decoding = "async";
        img.setAttribute("data-archive-img", "");
        slot.appendChild(img);
      }
      img.src = url;
    };

    const isUnlocked = () =>
      document.body.classList.contains("auth-page--unlocked");
    let stopped = false;
    const timers = new Set();

    const trackTimeout = (fn, delay) => {
      const id = window.setTimeout(() => {
        timers.delete(id);
        fn();
      }, delay);
      timers.add(id);
    };

    const stopRotation = () => {
      if (stopped) return;
      stopped = true;
      timers.forEach((id) => window.clearTimeout(id));
      timers.clear();
      slots.forEach((slot) => slot.classList.remove("is-dim"));
    };

    document.addEventListener("vault:unlocked", stopRotation);
    if (isUnlocked()) {
      stopRotation();
      return;
    }

    const cycleSlot = (slot) => {
      if (isUnlocked() || stopped) return;
      slot.classList.add("is-dim");
      trackTimeout(() => {
        if (isUnlocked() || stopped) return;
        applySlot(slot, nextUrl());
        trackTimeout(() => {
          slot.classList.remove("is-dim");
        }, 240);
      }, 1600);
    };

    let lastSlot = null;
    const scheduleNext = () => {
      if (isUnlocked() || stopped) return;
      const delay = 12000 + Math.floor(Math.random() * 8000);
      trackTimeout(() => {
        if (isUnlocked() || stopped) return;
        let slot = slots[Math.floor(Math.random() * slots.length)];
        if (slot === lastSlot && slots.length > 1) {
          slot = slots[(slots.indexOf(slot) + 1) % slots.length];
        }
        lastSlot = slot;
        cycleSlot(slot);
        scheduleNext();
      }, delay);
    };
    scheduleNext();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initArchive, { once: true });
  } else {
    initArchive();
  }
})();

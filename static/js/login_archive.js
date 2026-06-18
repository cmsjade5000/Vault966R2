(() => {
  const IMAGE_FADE_MS = 1300;

  const markImageReady = async (img) => {
    if (!img) return false;
    try {
      if (!img.complete) {
        await new Promise((resolve, reject) => {
          img.addEventListener("load", resolve, { once: true });
          img.addEventListener("error", reject, { once: true });
        });
      }
      if (!img.naturalWidth) return false;
      if (typeof img.decode === "function") {
        await img.decode().catch(() => {});
      }
      window.requestAnimationFrame(() => {
        img.classList.add("is-loaded");
      });
      return true;
    } catch (error) {
      img.classList.add("is-unavailable");
      return false;
    }
  };

  const preloadImage = async (url) => {
    const img = new Image();
    img.alt = "";
    img.decoding = "async";
    img.draggable = false;
    img.src = url;
    const ready = await markImageReady(img);
    return ready ? img : null;
  };

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
    if (!slots.length) return;

    slots.forEach((slot) => {
      markImageReady(slot.querySelector("img"));
    });
    if (posterUrls.length < 2) return;

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
      slots.forEach((slot) => {
        slot.querySelectorAll(".is-leaving").forEach((img) => img.remove());
        slot.classList.remove("is-swapping");
      });
    };

    document.addEventListener("vault:unlocked", stopRotation);
    if (isUnlocked()) {
      stopRotation();
      return;
    }

    const cycleSlot = async (slot) => {
      if (isUnlocked() || stopped) return;
      const url = nextUrl();
      if (!url) return;
      const nextImage = await preloadImage(url);
      if (!nextImage || isUnlocked() || stopped) return;

      const currentImage = slot.querySelector("img:not(.is-leaving)");
      nextImage.loading = "eager";
      nextImage.setAttribute("data-archive-img", "");
      nextImage.classList.add("login-archive__poster-next");
      slot.classList.add("is-swapping");
      slot.appendChild(nextImage);

      window.requestAnimationFrame(() => {
        nextImage.classList.remove("login-archive__poster-next");
        nextImage.classList.add("is-loaded");
        currentImage?.classList.add("is-leaving");
      });

      trackTimeout(() => {
        currentImage?.remove();
        slot.classList.remove("is-swapping");
      }, IMAGE_FADE_MS);
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

  window.VaultLoginArchiveSupport = {
    IMAGE_FADE_MS,
    markImageReady,
    preloadImage,
  };
})();

(() => {
  const IMAGE_FADE_MS = 1300;

  const IMAGE_LOAD_TIMEOUT_MS = 8000;

  const markImageReady = async (img, signal) => {
    if (!img) return false;
    img.classList.add("is-pending");
    try {
      await new Promise((resolve, reject) => {
        let finished = false;
        const cleanup = () => {
          window.clearTimeout(timeout);
          img.removeEventListener?.("load", loaded);
          img.removeEventListener?.("error", failed);
          signal?.removeEventListener("abort", failed);
        };
        const finish = (error) => {
          if (finished) return;
          finished = true;
          cleanup();
          if (error) reject(error);
          else resolve();
        };
        const failed = () => finish(new Error("Poster unavailable"));
        const loaded = async () => {
          if (!img.naturalWidth) return failed();
          if (typeof img.decode === "function") {
            await img.decode().catch(() => {});
          }
          finish();
        };
        const timeout = window.setTimeout(failed, IMAGE_LOAD_TIMEOUT_MS);
        signal?.addEventListener("abort", failed, { once: true });
        if (signal?.aborted) failed();
        else if (img.complete) loaded();
        else {
          img.addEventListener("load", loaded, { once: true });
          img.addEventListener("error", failed, { once: true });
        }
      });
      if (signal?.aborted) throw new Error("Poster unavailable");
      img.classList.remove("is-pending", "is-unavailable");
      img.classList.add("is-loaded");
      return true;
    } catch (error) {
      img.classList.remove("is-pending");
      img.classList.add("is-unavailable");
      return false;
    }
  };

  const preloadImage = async (url, signal) => {
    const img = new Image();
    img.alt = "";
    img.decoding = "async";
    img.draggable = false;
    img.src = url;
    const ready = await markImageReady(img, signal);
    return ready ? img : null;
  };

  const VISIT_STORAGE_KEY = "vault-login-archive-lineup";

  const shuffle = (arr) => {
    const copy = [...arr];
    for (let i = copy.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
  };

  const selectLineup = (urls, count, previous = []) => {
    const prior = new Set(previous);
    const lineup = [
      ...shuffle(urls.filter((url) => !prior.has(url))),
      ...shuffle(urls.filter((url) => prior.has(url))),
    ].slice(0, count);
    if (
      lineup.length > 1 &&
      lineup.every((url, index) => url === previous[index])
    ) {
      lineup.push(lineup.shift());
    }
    return lineup;
  };

  const initArchive = () => {
    const dataEl = document.getElementById("login-archive-data");
    if (!dataEl) return;
    let posterUrls = [];
    try {
      const data = JSON.parse(dataEl.textContent || "{}");
      posterUrls = Array.isArray(data.posters)
        ? [
            ...new Set(
              data.posters.filter(
                (url) =>
                  typeof url === "string" &&
                  url.startsWith(
                    window.location.origin +
                      "/static/img/login-posters/poster-",
                  ),
              ),
            ),
          ]
        : [];
    } catch (error) {
      console.warn("Failed to parse login archive data", error);
      return;
    }

    const slots = Array.from(
      document.querySelectorAll(".login-archive__poster"),
    );
    if (!slots.length) return;

    slots.forEach((slot) => {
      if (window.getComputedStyle(slot).display !== "none") {
        markImageReady(slot.querySelector("img"));
      }
    });
    if (posterUrls.length < 2) return;

    const motionPreference = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    );

    let pool = shuffle(posterUrls);
    let pointer = 0;
    let visitGeneration = 0;
    let visitController;
    let visitPending = false;
    let previousLineup = slots.map((slot) => slot.querySelector("img")?.src);
    try {
      const stored = JSON.parse(
        window.sessionStorage.getItem(VISIT_STORAGE_KEY),
      );
      if (Array.isArray(stored)) previousLineup = stored;
    } catch (error) {
      // Storage may be disabled; the current markup still supplies a fallback.
    }

    const nextUrl = () => {
      if (pool.length === 0) pool = shuffle(posterUrls);
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
        slot
          .querySelectorAll(".is-leaving, .login-archive__poster-next")
          .forEach((img) => img.remove());
        slot.classList.remove("is-swapping");
      });
    };

    const suspendVisit = () => {
      visitGeneration += 1;
      visitController?.abort();
      stopRotation();
    };
    document.addEventListener("vault:unlocked", suspendVisit);
    window.addEventListener("pagehide", () => {
      suspendVisit();
    });
    motionPreference.addEventListener?.("change", (event) => {
      if (event.matches) stopRotation();
    });
    if (isUnlocked()) {
      stopRotation();
      return;
    }

    const cycleSlot = async (slot) => {
      if (
        isUnlocked() ||
        stopped ||
        motionPreference.matches ||
        document.hidden
      )
        return;
      const url = nextUrl();
      if (!url) return;
      const currentImage = slot.querySelector("img:not(.is-leaving)");
      if (currentImage?.src === url) return;
      const generation = visitGeneration;
      const nextImage = await preloadImage(url, visitController?.signal);
      if (
        !nextImage ||
        generation !== visitGeneration ||
        isUnlocked() ||
        stopped ||
        motionPreference.matches ||
        document.hidden
      )
        return;

      nextImage.loading = "eager";
      nextImage.setAttribute("data-archive-img", "");
      nextImage.classList.add("login-archive__poster-next");
      slot.classList.add("is-swapping");
      slot.appendChild(nextImage);

      window.requestAnimationFrame(() => {
        if (generation !== visitGeneration || stopped) return;
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
      if (isUnlocked() || stopped || motionPreference.matches) return;
      const delay = 12000 + Math.floor(Math.random() * 8000);
      trackTimeout(() => {
        if (isUnlocked() || stopped || motionPreference.matches) return;
        const visibleSlots = slots.filter(
          (slot) => window.getComputedStyle(slot).display !== "none",
        );
        if (!document.hidden && visibleSlots.length) {
          let slot =
            visibleSlots[Math.floor(Math.random() * visibleSlots.length)];
          if (slot === lastSlot && visibleSlots.length > 1) {
            slot =
              visibleSlots[
                (visibleSlots.indexOf(slot) + 1) % visibleSlots.length
              ];
          }
          lastSlot = slot;
          cycleSlot(slot);
        }
        scheduleNext();
      }, delay);
    };
    const replaceVisitLineup = async () => {
      visitPending = false;
      const generation = ++visitGeneration;
      visitController?.abort();
      visitController = new AbortController();
      const visibleSlots = slots.filter(
        (slot) => window.getComputedStyle(slot).display !== "none",
      );
      const lineup = selectLineup(
        posterUrls,
        visibleSlots.length,
        previousLineup,
      );
      const images = await Promise.all(
        lineup.map((url) => preloadImage(url, visitController.signal)),
      );
      if (
        generation !== visitGeneration ||
        stopped ||
        isUnlocked() ||
        images.some((img) => !img)
      )
        return;
      images.forEach((img, index) => {
        img.loading = "eager";
        img.setAttribute("data-archive-img", "");
        const current = visibleSlots[index].querySelector("img");
        if (current) visibleSlots[index].replaceChild(img, current);
      });
      previousLineup = lineup;
      try {
        window.sessionStorage.setItem(
          VISIT_STORAGE_KEY,
          JSON.stringify(lineup),
        );
      } catch (error) {
        // Visit variety remains available when storage is disabled.
      }
      pool = shuffle(posterUrls.filter((url) => !lineup.includes(url)));
      pointer = 0;
    };

    const startVisit = () => {
      if (isUnlocked()) return;
      stopRotation();
      stopped = false;
      visitPending = true;
      if (!document.hidden) replaceVisitLineup();
      scheduleNext();
    };
    window.addEventListener("pageshow", (event) => {
      if (event.persisted) startVisit();
    });
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && visitPending && !stopped) replaceVisitLineup();
    });
    startVisit();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initArchive, { once: true });
  } else {
    initArchive();
  }

  window.VaultLoginArchiveSupport = {
    IMAGE_FADE_MS,
    IMAGE_LOAD_TIMEOUT_MS,
    markImageReady,
    preloadImage,
    selectLineup,
  };
})();

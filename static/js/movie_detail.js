(function () {
  document.addEventListener("DOMContentLoaded", () => {
    const posterFocusButton = document.querySelector("[data-poster-focus]");
    const posterFocusBackdrop = document.querySelector(
      "[data-poster-focus-backdrop]",
    );

    if (posterFocusButton && posterFocusBackdrop) {
      const movieTitle = posterFocusButton.dataset.movieTitle || "movie";

      const setPosterFocused = (focused) => {
        posterFocusButton.classList.toggle("is-poster-focused", focused);
        posterFocusBackdrop.hidden = !focused;
        posterFocusBackdrop.classList.toggle("is-visible", focused);
        document.body.classList.toggle("poster-focus-open", focused);
        posterFocusButton.setAttribute(
          "aria-pressed",
          focused ? "true" : "false",
        );
        posterFocusButton.setAttribute(
          "aria-label",
          `${focused ? "Reduce" : "Enlarge"} ${movieTitle} poster`,
        );
      };

      posterFocusButton.addEventListener("click", () => {
        setPosterFocused(
          !posterFocusButton.classList.contains("is-poster-focused"),
        );
      });

      posterFocusBackdrop.addEventListener("click", () => {
        setPosterFocused(false);
        posterFocusButton.focus();
      });

      document.addEventListener("keydown", (event) => {
        if (
          event.key === "Escape" &&
          posterFocusButton.classList.contains("is-poster-focused")
        ) {
          event.preventDefault();
          setPosterFocused(false);
          posterFocusButton.focus();
        }
      });
    }

    const vaultCopyButton = document.querySelector("[data-copy-vault]");
    if (vaultCopyButton) {
      const triggerVaultReaction = () => {
        vaultCopyButton.classList.remove("is-vault-burst");
        void vaultCopyButton.offsetWidth;
        vaultCopyButton.classList.add("is-vault-burst");
        window.setTimeout(() => {
          vaultCopyButton.classList.remove("is-vault-burst");
        }, 560);
      };

      vaultCopyButton.addEventListener("click", async () => {
        const vaultId = vaultCopyButton.dataset.vaultId || "";
        triggerVaultReaction();
        if (!vaultId) return;
        try {
          if (typeof navigator.clipboard?.writeText !== "function") {
            throw new Error("Clipboard unavailable");
          }
          await navigator.clipboard.writeText(vaultId);
          window.showToast?.("Copied Vault ID.");
        } catch (error) {
          return;
        }
      });
    }

    const trailerAction = document.querySelector("[data-trailer-action]");
    const trailerButton = document.querySelector("[data-trailer-button]");
    const trailerModal = document.querySelector("[data-trailer-modal]");
    const trailerFrame = document.querySelector("[data-trailer-frame]");
    const trailerTitle = document.querySelector("[data-trailer-title]");
    const trailerClose = document.querySelector("[data-trailer-close]");
    let trailerPayload = null;
    let trailerReturnFocus = null;

    const trailerEmbedUrl = (value) => {
      if (!value) return null;
      try {
        const url = new URL(value);
        if (url.origin !== "https://www.youtube-nocookie.com") return null;
        if (!url.pathname.startsWith("/embed/")) return null;
        url.searchParams.set("autoplay", "1");
        url.searchParams.set("rel", "0");
        return url.toString();
      } catch (error) {
        return null;
      }
    };

    const applyTrailerPayload = (payload) => {
      if (!payload || payload.site !== "youtube") return false;
      const embedUrl = trailerEmbedUrl(payload.embed_url);
      if (!embedUrl || !trailerButton || !trailerAction) return false;
      trailerPayload = {
        name: payload.name || "Trailer",
        embedUrl,
      };
      trailerButton.dataset.trailerName = trailerPayload.name;
      trailerButton.dataset.trailerEmbedUrl = trailerPayload.embedUrl;
      trailerAction.hidden = false;
      return true;
    };

    const fetchTrailer = async () => {
      const movieId = trailerAction?.dataset.movieId;
      if (!movieId) return null;
      const response = await fetch(`/movies/${movieId}/trailer`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return null;
      return response.json();
    };

    const closeTrailer = () => {
      if (!trailerModal) return;
      trailerModal.hidden = true;
      document.body.classList.remove("trailer-open");
      if (trailerFrame) {
        trailerFrame.replaceChildren();
      }
      trailerReturnFocus?.focus?.();
      trailerReturnFocus = null;
    };

    const openTrailer = async () => {
      if (!trailerButton || !trailerModal || !trailerFrame) return;
      let embedUrl = trailerEmbedUrl(trailerButton.dataset.trailerEmbedUrl);
      let trailerName = trailerButton.dataset.trailerName || "Trailer";
      if (!embedUrl) {
        try {
          const payload = await fetchTrailer();
          if (!applyTrailerPayload(payload)) {
            window.showToast?.("Trailer unavailable.");
            return;
          }
          embedUrl = trailerPayload.embedUrl;
          trailerName = trailerPayload.name;
        } catch (error) {
          window.showToast?.("Trailer unavailable.");
          return;
        }
      }

      if (trailerTitle) trailerTitle.textContent = trailerName;
      const iframe = document.createElement("iframe");
      iframe.src = embedUrl;
      iframe.title = trailerName;
      iframe.allow =
        "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
      iframe.allowFullscreen = true;
      iframe.referrerPolicy = "strict-origin-when-cross-origin";
      trailerFrame.replaceChildren(iframe);
      trailerReturnFocus = document.activeElement;
      trailerModal.hidden = false;
      document.body.classList.add("trailer-open");
      trailerClose?.focus();
    };

    if (trailerAction && trailerButton) {
      if (trailerButton.dataset.trailerEmbedUrl) {
        applyTrailerPayload({
          site: "youtube",
          name: trailerButton.dataset.trailerName || "Trailer",
          embed_url: trailerButton.dataset.trailerEmbedUrl,
        });
      } else {
        fetchTrailer()
          .then((payload) => {
            applyTrailerPayload(payload);
          })
          .catch(() => {});
      }

      trailerButton.addEventListener("click", () => {
        openTrailer();
      });
      trailerClose?.addEventListener("click", closeTrailer);
      trailerModal?.addEventListener("click", (event) => {
        if (event.target === trailerModal) closeTrailer();
      });
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && trailerModal && !trailerModal.hidden) {
          event.preventDefault();
          closeTrailer();
        }
      });
    }

    const parseErrorDetail = async (response) => {
      if (!response || typeof response.json !== "function") return null;
      try {
        const payload = await response.json();
        if (payload && typeof payload.detail === "string") {
          return payload.detail;
        }
      } catch (error) {
        return null;
      }
      return null;
    };

    const flagDialog = document.querySelector("[data-flag-dialog]");
    const flagForm = document.querySelector("[data-flag-form]");
    const flagReason = document.querySelector("[data-flag-reason]");
    const flagNotes = document.querySelector("[data-flag-notes]");
    const flagStatus = document.querySelector("[data-flag-status]");
    const flagStatusTitle = document.querySelector("[data-flag-status-title]");
    const flagStatusNotes = document.querySelector("[data-flag-status-notes]");
    const flagDialogStatus = document.querySelector(
      "[data-flag-dialog-status]",
    );
    const flagDialogTitle = document.getElementById("flag-dialog-title");
    const flagSave = document.querySelector("[data-flag-save]");
    const flagResolve = document.querySelector("[data-flag-resolve]");
    const flagButtons = document.querySelectorAll("[data-flag-button]");
    const movieId = flagButtons[0]?.dataset.movieId;
    const flagMode = flagForm?.dataset.flagMode || "manage";
    const canManageFlags = flagMode === "manage";
    let resolveArmed = false;

    const flagDialogController = window.VaultDialog?.bind(flagDialog, {
      closeSelector: "[data-flag-close]",
      initialFocus: "[data-flag-reason]",
      onClose: () => {
        resolveArmed = false;
        if (flagResolve) flagResolve.textContent = "Resolve flag";
        if (flagDialogStatus) flagDialogStatus.textContent = "";
      },
    });

    const setFlagPending = (pending) => {
      flagSave?.toggleAttribute("disabled", pending);
      flagResolve?.toggleAttribute("disabled", pending);
      flagForm?.toggleAttribute("aria-busy", pending);
    };

    const updateFlagView = ({ flagged, reason = "", notes = "" }) => {
      if (flagStatus) {
        flagStatus.hidden = !flagged;
        flagStatus.classList.toggle("is-visible", flagged);
      }
      if (flagStatusTitle) {
        flagStatusTitle.textContent = flagged
          ? `Needs review${reason ? ` · ${reason}` : ""}`
          : "";
      }
      if (flagStatusNotes) {
        flagStatusNotes.textContent = notes || "No notes were added.";
      }
      if (flagDialogTitle) {
        flagDialogTitle.textContent = canManageFlags
          ? flagged
            ? "Manage review flag"
            : "Flag for review"
          : "Report issue";
      }
      if (flagResolve) flagResolve.hidden = !flagged;
      flagButtons.forEach((button) => {
        const inStatus = Boolean(button.closest("[data-flag-status]"));
        button.textContent = canManageFlags
          ? flagged
            ? "Manage flag"
            : inStatus
              ? "Manage flag"
              : "Flag for review"
          : "Report issue";
        button.setAttribute(
          "aria-label",
          canManageFlags
            ? flagged
              ? "Manage review flag"
              : "Flag for review"
            : "Report issue",
        );
      });
    };

    flagButtons.forEach((button) => {
      button.addEventListener("click", () => {
        flagDialogController?.open(button);
      });
    });

    flagForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!movieId || !flagReason) return;
      setFlagPending(true);
      if (flagDialogStatus) {
        flagDialogStatus.classList.remove("is-error");
        flagDialogStatus.textContent = canManageFlags
          ? "Saving flag…"
          : "Sending report…";
      }
      try {
        const response = await fetch(
          canManageFlags
            ? `/ui/movies/${movieId}/flag`
            : `/movies/${movieId}/flag/report`,
          {
            method: canManageFlags ? "PUT" : "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json",
            },
            body: JSON.stringify({
              reason: flagReason.value,
              notes: flagNotes?.value.trim() || null,
            }),
          },
        );
        if (!response.ok) {
          throw new Error(
            (await parseErrorDetail(response)) ||
              (canManageFlags
                ? "Could not save that flag."
                : "Could not send that report."),
          );
        }
        const savedFlag = await response.json();
        updateFlagView({
          flagged: true,
          reason: savedFlag.reason,
          notes: savedFlag.notes,
        });
        flagDialogController?.close();
        window.showToast?.(canManageFlags ? "Flag saved." : "Report sent.");
      } catch (error) {
        if (flagDialogStatus) {
          flagDialogStatus.textContent =
            error?.message ||
            (canManageFlags
              ? "Could not save that flag."
              : "Could not send that report.");
          flagDialogStatus.classList.add("is-error");
        }
      } finally {
        setFlagPending(false);
      }
    });

    flagResolve?.addEventListener("click", async () => {
      if (!movieId) return;
      if (!resolveArmed) {
        resolveArmed = true;
        flagResolve.textContent = "Confirm resolve";
        if (flagDialogStatus) {
          flagDialogStatus.textContent =
            "Select Confirm resolve again to remove this item from Flags.";
        }
        return;
      }

      setFlagPending(true);
      if (flagDialogStatus) {
        flagDialogStatus.classList.remove("is-error");
        flagDialogStatus.textContent = "Resolving flag…";
      }
      try {
        const response = await fetch(`/ui/movies/${movieId}/flag`, {
          method: "DELETE",
          headers: { Accept: "application/json" },
        });
        if (!response.ok && response.status !== 204) {
          throw new Error(
            (await parseErrorDetail(response)) ||
              "Could not resolve that flag.",
          );
        }
        updateFlagView({ flagged: false });
        flagDialogController?.close();
        window.showToast?.("Flag resolved.");
      } catch (error) {
        if (flagDialogStatus) {
          flagDialogStatus.textContent =
            error?.message || "Could not resolve that flag.";
          flagDialogStatus.classList.add("is-error");
        }
      } finally {
        setFlagPending(false);
      }
    });

    const rail = document.querySelector("[data-similar-rail]");
    const prevButton = document.querySelector('[data-scroll="prev"]');
    const nextButton = document.querySelector('[data-scroll="next"]');
    if (!rail || !prevButton || !nextButton) {
      return;
    }

    const updateButtons = () => {
      const maxScroll = rail.scrollWidth - rail.clientWidth;
      const current = rail.scrollLeft;
      prevButton.disabled = current <= 4;
      nextButton.disabled = current >= maxScroll - 4;
    };

    const scrollAmount = () => rail.clientWidth * 0.8;

    prevButton.addEventListener("click", () => {
      rail.scrollBy({ left: -scrollAmount(), behavior: "smooth" });
      setTimeout(updateButtons, 300);
    });

    nextButton.addEventListener("click", () => {
      rail.scrollBy({ left: scrollAmount(), behavior: "smooth" });
      setTimeout(updateButtons, 300);
    });

    rail.addEventListener("scroll", updateButtons);
    window.addEventListener("resize", updateButtons);

    updateButtons();
  });
})();

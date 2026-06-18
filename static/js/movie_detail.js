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
        flagReason?.focus();
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

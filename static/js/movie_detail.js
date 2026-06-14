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

    const getAdminToken = () =>
      window.localStorage?.getItem("adminToken") || "";
    const promptForAdminToken = (message) => {
      const token = window.prompt(message || "Enter admin token");
      if (token && window.localStorage) {
        window.localStorage.setItem("adminToken", token);
      }
      return token || "";
    };

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

    const FLAG_REASONS = [
      "Metadata cleanup",
      "Poster/backdrop issue",
      "Missing poster",
      "Broken link",
      "Movie mismatch",
      "Wrong runtime/year",
      "Needs runtime",
      "Other",
    ];

    const openFlagDialog = (defaultReason) =>
      new Promise((resolve) => {
        const overlay = document.createElement("dialog");
        overlay.className = "flag-dialog-overlay";
        overlay.setAttribute("aria-hidden", "true");
        const dialog = document.createElement("section");
        dialog.className = "flag-dialog";
        const heading = document.createElement("h3");
        heading.textContent = "Flag this movie";
        const reasonLabel = document.createElement("label");
        reasonLabel.htmlFor = "flag-reason";
        reasonLabel.textContent = "Reason";
        const reasonSelect = document.createElement("select");
        reasonSelect.id = "flag-reason";
        FLAG_REASONS.forEach((reason) => {
          const option = document.createElement("option");
          option.value = reason;
          option.textContent = reason;
          option.selected = reason === defaultReason;
          reasonSelect.append(option);
        });
        const notesLabel = document.createElement("label");
        notesLabel.htmlFor = "flag-notes";
        notesLabel.textContent = "Notes (optional)";
        const notesInput = document.createElement("textarea");
        notesInput.id = "flag-notes";
        notesInput.maxLength = 500;
        notesInput.placeholder = "What needs a fix?";
        const actions = document.createElement("div");
        actions.className = "flag-dialog__actions";
        const cancelButton = document.createElement("button");
        cancelButton.type = "button";
        cancelButton.className = "button-ghost";
        cancelButton.dataset.flagCancel = "";
        cancelButton.textContent = "Cancel";
        const saveButton = document.createElement("button");
        saveButton.type = "button";
        saveButton.className = "button-primary";
        saveButton.dataset.flagSave = "";
        saveButton.textContent = "Save";
        actions.append(cancelButton, saveButton);
        dialog.append(
          heading,
          reasonLabel,
          reasonSelect,
          notesLabel,
          notesInput,
          actions,
        );
        overlay.append(dialog);
        document.body.append(overlay);

        let result = null;
        const controller = window.VaultDialog?.bind(overlay, {
          closeSelector: "[data-flag-cancel]",
          onClose: () => {
            overlay.remove();
            resolve(result);
          },
        });
        const close = (value) => {
          result = value;
          controller?.close();
        };

        saveButton.addEventListener("click", () => {
          close({
            reason: reasonSelect.value,
            notes: notesInput.value.trim() || null,
          });
        });
        controller?.open();
        reasonSelect.focus();
      });

    const updateFlagButton = (button, flagged) => {
      button.dataset.flagged = flagged ? "true" : "false";
      button.classList.toggle("is-flagged", flagged);
      button.textContent = flagged ? "Resolve flag" : "Flag";
      button.setAttribute("aria-pressed", flagged ? "true" : "false");
      if (window.showToast) {
        window.showToast(flagged ? "Flag saved." : "Flag cleared.");
      }
    };

    const handleFlagClick = async (event) => {
      const button = event.target.closest("[data-flag-button]");
      if (!button) return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      const movieId = button.dataset.movieId;
      if (!movieId || button.dataset.flagBusy === "true") return;
      button.dataset.flagHandlerAttached = "true";
      button.dataset.flagDetailAttached = "true";
      const currentlyFlagged = button.dataset.flagged === "true";
      const baseHeaders = {
        "Content-Type": "application/json",
        Accept: "application/json",
      };
      const withAuth = (token) =>
        token
          ? { ...baseHeaders, Authorization: `Bearer ${token}` }
          : baseHeaders;
      button.dataset.flagBusy = "true";
      try {
        if (currentlyFlagged) {
          let resp = await fetch(`/movies/${movieId}/flag`, {
            method: "DELETE",
            headers: withAuth(getAdminToken()),
          });
          if (resp.status === 401) {
            const token = promptForAdminToken(
              "Admin token required to update flags.",
            );
            if (!token) return;
            resp = await fetch(`/movies/${movieId}/flag`, {
              method: "DELETE",
              headers: withAuth(token),
            });
          }
          if (!resp.ok && resp.status !== 204) {
            const detail =
              (await parseErrorDetail(resp)) || "Failed to clear flag";
            throw new Error(detail);
          }
          updateFlagButton(button, false);
        } else {
          const defaultReason =
            button.dataset.flagDefault || "Metadata cleanup";
          const dialogResult = await openFlagDialog(defaultReason);
          if (!dialogResult) return;
          const { reason, notes } = dialogResult;
          const cleanReason = reason ? reason.trim() : "";
          let resp = await fetch(`/movies/${movieId}/flag`, {
            method: "POST",
            headers: withAuth(getAdminToken()),
            body: JSON.stringify({
              reason: cleanReason || null,
              notes: notes || null,
            }),
          });
          if (resp.status === 401) {
            const token = promptForAdminToken(
              "Admin token required to manage flags.",
            );
            if (!token) return;
            resp = await fetch(`/movies/${movieId}/flag`, {
              method: "POST",
              headers: withAuth(token),
              body: JSON.stringify({
                reason: cleanReason || null,
                notes: notes || null,
              }),
            });
          }
          if (!resp.ok) {
            const detail =
              (await parseErrorDetail(resp)) || "Failed to flag movie";
            throw new Error(detail);
          }
          updateFlagButton(button, true);
        }
      } catch (error) {
        console.error("Flag toggle failed", error);
        if (window.showToast) {
          window.showToast(
            error && error.message
              ? error.message
              : "Could not update that flag—try again soon?",
          );
        }
      } finally {
        delete button.dataset.flagBusy;
      }
    };

    document.addEventListener("click", handleFlagClick, true);

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

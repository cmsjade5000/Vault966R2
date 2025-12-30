(function () {
  document.addEventListener("DOMContentLoaded", () => {
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
        const overlay = document.createElement("div");
        overlay.className = "flag-dialog-overlay";
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-modal", "true");
        const dialog = document.createElement("div");
        dialog.className = "flag-dialog";
        dialog.innerHTML = `
          <h3>Flag this movie</h3>
          <label for="flag-reason">Reason</label>
          <select id="flag-reason">
            ${FLAG_REASONS.map((reason) => {
              const selected = reason === defaultReason ? "selected" : "";
              return `<option value="${reason}" ${selected}>${reason}</option>`;
            }).join("")}
          </select>
          <label for="flag-notes">Notes (optional)</label>
          <textarea id="flag-notes" maxlength="500" placeholder="What needs a fix?"></textarea>
          <div class="flag-dialog__actions">
            <button type="button" class="button-ghost" data-flag-cancel>Cancel</button>
            <button type="button" class="button-primary" data-flag-save>Save</button>
          </div>
        `;
        overlay.append(dialog);
        document.body.append(overlay);

        const cleanup = () => overlay.remove();
        const close = (value) => {
          cleanup();
          resolve(value);
        };

        overlay.addEventListener("click", (event) => {
          if (event.target === overlay) {
            close(null);
          }
        });
        overlay.addEventListener("keydown", (event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            close(null);
          }
        });
        dialog
          .querySelector("[data-flag-cancel]")
          ?.addEventListener("click", () => close(null));
        dialog
          .querySelector("[data-flag-save]")
          ?.addEventListener("click", () => {
            const reason = dialog.querySelector("#flag-reason")?.value || "";
            const notes =
              dialog.querySelector("#flag-notes")?.value.trim() || null;
            close({ reason, notes });
          });
        setTimeout(() => {
          dialog.querySelector("#flag-reason")?.focus();
        }, 0);
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

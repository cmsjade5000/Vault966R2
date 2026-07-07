(function () {
  const HOLD_DELAY_MS = 550;
  const MOVE_TOLERANCE_PX = 12;

  const movedBeyondTolerance = (startX, startY, currentX, currentY) =>
    Math.hypot(currentX - startX, currentY - startY) > MOVE_TOLERANCE_PX;

  const enableKeyboardAccess = (button) => {
    if (!button) return;
    button.removeAttribute("aria-hidden");
    if (button.getAttribute("tabindex") === "-1") {
      button.removeAttribute("tabindex");
    }
  };

  window.VaultCardReviewFlagSupport = {
    HOLD_DELAY_MS,
    MOVE_TOLERANCE_PX,
    enableKeyboardAccess,
    movedBeyondTolerance,
  };

  document.addEventListener("DOMContentLoaded", () => {
    const cards = document.querySelectorAll(".library-page [data-movie-card]");
    if (!cards.length) return;

    let holdTimer = null;
    let holdCard = null;
    let startX = 0;
    let startY = 0;
    let suppressLinkCard = null;

    const concealCardAction = (card) => {
      if (!card) return;
      card.classList.remove("is-review-action-visible");
      const button = card.querySelector("[data-review-flag-button]");
      if (!button) return;
      enableKeyboardAccess(button);
    };

    const concealOtherActions = (activeCard = null) => {
      cards.forEach((card) => {
        if (card !== activeCard) concealCardAction(card);
      });
    };

    const revealCardAction = (card) => {
      const button = card?.querySelector("[data-review-flag-button]");
      if (!card || !button) return;
      concealOtherActions(card);
      card.classList.add("is-review-action-visible");
      enableKeyboardAccess(button);
      suppressLinkCard = card;
      button.focus({ preventScroll: true });
    };

    const cancelHold = () => {
      if (holdTimer !== null) {
        window.clearTimeout(holdTimer);
      }
      holdTimer = null;
      holdCard = null;
    };

    cards.forEach((card) => {
      enableKeyboardAccess(card.querySelector("[data-review-flag-button]"));

      card.addEventListener("pointerdown", (event) => {
        if (event.pointerType === "mouse" && event.button !== 0) return;
        if (event.target.closest("button, .library-card__actions")) return;
        cancelHold();
        holdCard = card;
        startX = event.clientX;
        startY = event.clientY;
        holdTimer = window.setTimeout(() => {
          revealCardAction(card);
          holdTimer = null;
          holdCard = null;
        }, HOLD_DELAY_MS);
      });

      card.addEventListener("pointermove", (event) => {
        if (
          holdCard === card &&
          movedBeyondTolerance(startX, startY, event.clientX, event.clientY)
        ) {
          cancelHold();
        }
      });

      card.addEventListener("pointerup", cancelHold);
      card.addEventListener("pointercancel", cancelHold);
      card.addEventListener("lostpointercapture", cancelHold);
      card.addEventListener("contextmenu", (event) => {
        if (
          event.pointerType === "touch" ||
          event.sourceCapabilities?.firesTouchEvents
        ) {
          event.preventDefault();
        }
      });
    });

    document.addEventListener(
      "click",
      (event) => {
        const link = event.target.closest(".library-card__link");
        const card = link?.closest("[data-movie-card]");
        if (card && card === suppressLinkCard) {
          event.preventDefault();
          event.stopPropagation();
          suppressLinkCard = null;
          return;
        }

        if (event.target.closest("[data-review-flag-button]")) {
          suppressLinkCard = null;
          return;
        }
        suppressLinkCard = null;
        concealOtherActions();
      },
      true,
    );

    document.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-review-flag-button]");
      if (!button) return;
      event.preventDefault();
      event.stopPropagation();
      if (button.disabled) return;

      const card = button.closest("[data-movie-card]");
      const movieId = button.dataset.movieId;
      const title = button.dataset.movieTitle || "Movie";
      if (!card || !movieId) return;

      if (card.dataset.flagged === "true") {
        window.showToast?.("Flagged for review");
        return;
      }

      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      try {
        const response = await fetch(`/ui/movies/${movieId}/review-flag`, {
          method: "POST",
          headers: { Accept: "application/json" },
        });
        if (!response.ok) {
          throw new Error("Review flag update failed");
        }

        card.dataset.flagged = "true";
        card.classList.add("library-card--review");
        button.classList.add("is-active");
        button.setAttribute("aria-pressed", "true");
        button.setAttribute(
          "aria-label",
          `${title} is already flagged for review`,
        );

        const media = card.querySelector(".library-card__media");
        if (media && !media.querySelector(".library-card__status")) {
          const status = document.createElement("span");
          status.className = "library-card__status";
          status.textContent = "Needs review";
          media.appendChild(status);
        }
        window.showToast?.("Flagged for review");
      } catch (error) {
        console.warn("Could not flag movie for review", error);
        window.showToast?.("Could not flag that movie—try again.");
      } finally {
        button.disabled = false;
        button.removeAttribute("aria-busy");
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        concealOtherActions();
      }
    });
  });
})();

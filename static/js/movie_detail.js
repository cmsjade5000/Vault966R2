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

    const flagButton = document.querySelector("[data-flag-button]");
    if (flagButton && flagButton.dataset.flagHandlerAttached !== "true") {
      flagButton.dataset.flagHandlerAttached = "true";
      flagButton.addEventListener("click", async () => {
        const movieId = flagButton.dataset.movieId;
        if (!movieId) return;
        const currentlyFlagged = flagButton.dataset.flagged === "true";
        try {
          const headers = {
            "Content-Type": "application/json",
            Accept: "application/json",
            Authorization: `Bearer ${getAdminToken()}`,
          };
          if (currentlyFlagged) {
            const resp = await fetch(`/movies/${movieId}/flag`, {
              method: "DELETE",
              headers,
            });
            if (resp.status === 401) {
              const token = promptForAdminToken(
                "Admin token required to update flags.",
              );
              if (!token) return;
              await fetch(`/movies/${movieId}/flag`, {
                method: "DELETE",
                headers: { ...headers, Authorization: `Bearer ${token}` },
              });
            }
            flagButton.dataset.flagged = "false";
            flagButton.classList.remove("is-flagged");
            flagButton.textContent = "Flag";
          } else {
            const defaultReason =
              flagButton.dataset.flagDefault || "Metadata cleanup";
            const rawReason = window.prompt("What needs a fix?", defaultReason);
            if (rawReason === null) return;
            const reason = rawReason.trim();
            const resp = await fetch(`/movies/${movieId}/flag`, {
              method: "POST",
              headers,
              body: JSON.stringify({ reason: reason || null }),
            });
            if (resp.status === 401) {
              const token = promptForAdminToken(
                "Admin token required to manage flags.",
              );
              if (!token) return;
              await fetch(`/movies/${movieId}/flag`, {
                method: "POST",
                headers: { ...headers, Authorization: `Bearer ${token}` },
                body: JSON.stringify({ reason: reason || null }),
              });
            }
            flagButton.dataset.flagged = "true";
            flagButton.classList.add("is-flagged");
            flagButton.textContent = "Resolve flag";
          }
        } catch (error) {
          console.error("Flag toggle failed", error);
        }
      });
    }

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

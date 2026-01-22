(() => {
  const initProfileSwitcher = () => {
    const select = document.querySelector("[data-profile-select]");
    if (!select) return;

    select.addEventListener("change", async () => {
      const nextValue = Number.parseInt(select.value, 10);
      if (!Number.isFinite(nextValue)) return;
      try {
        const response = await fetch("/api/profiles/active", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({ profile_id: nextValue }),
        });
        if (!response.ok) {
          throw new Error("Failed to switch profile");
        }
        window.location.reload();
      } catch (error) {
        console.warn(error);
        if (typeof window.showToast === "function") {
          window.showToast("Could not switch profiles—try again.");
        }
      }
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initProfileSwitcher, {
      once: true,
    });
  } else {
    initProfileSwitcher();
  }
})();

(() => {
  document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.querySelector("[data-recommendation-refresh]");
    const recommendationText = document.querySelector("[data-recommendation-text]");
    if (!refreshButton || !recommendationText) return;

    const setBusy = (isBusy) => {
      refreshButton.classList.toggle("is-busy", isBusy);
      refreshButton.disabled = isBusy;
    };

    refreshButton.addEventListener("click", async () => {
      setBusy(true);
      const adminToken = window.localStorage?.getItem("vaultAdminToken");
      const headers = adminToken
        ? { Authorization: `Bearer ${adminToken}` }
        : {};
      try {
        const response = await fetch(
          "/api/collection-health/recommendation/refresh",
          { method: "POST", headers },
        );
        if (!response.ok) {
          if (response.status === 401) {
            throw new Error(
              "Admin token required. Set localStorage.vaultAdminToken to your ADMIN_TOKEN.",
            );
          }
          throw new Error("Failed to refresh recommendation");
        }
        const payload = await response.json();
        if (typeof payload.recommendation === "string") {
          recommendationText.textContent = payload.recommendation;
        }
      } catch (error) {
        console.warn(error);
        if (typeof window.showToast === "function") {
          window.showToast("Couldn’t refresh—try again soon?");
        }
        if (!adminToken) {
          console.warn(
            "Set localStorage.vaultAdminToken = '<ADMIN_TOKEN>' to refresh collection health.",
          );
        }
      } finally {
        setBusy(false);
      }
    });
  });
})();

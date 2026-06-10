(() => {
  document.addEventListener("DOMContentLoaded", () => {
    const updateButton = document.querySelector("[data-update-trigger]");
    const updateStatus = document.querySelector("[data-update-status]");
    const updateSteps = document.querySelector("[data-update-steps]");

    const adminToken = window.localStorage?.getItem("vaultAdminToken");
    const adminHeaders = adminToken
      ? { Authorization: `Bearer ${adminToken}` }
      : {};

    const setBusy = (isBusy) => {
      if (updateButton) {
        updateButton.classList.toggle("is-busy", isBusy);
        updateButton.disabled = isBusy;
      }
    };

    const formatTimestamp = (value) => {
      if (!value) return "Not run yet";
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return "Not run yet";
      return parsed.toLocaleString();
    };

    const renderSteps = (steps) => {
      if (!updateSteps) return;
      updateSteps.innerHTML = "";
      if (!Array.isArray(steps) || steps.length === 0) {
        updateSteps.textContent = "No recent update steps logged.";
        return;
      }
      steps.forEach((step) => {
        const chip = document.createElement("span");
        chip.className = "collection-health__update-step";
        if (step.status === "success") chip.classList.add("is-success");
        if (step.status === "failed") chip.classList.add("is-failed");
        if (step.status === "skipped") chip.classList.add("is-skipped");
        const label = `${step.name}: ${step.status}`;
        chip.textContent = label;
        updateSteps.appendChild(chip);
      });
    };

    const renderStatus = (status) => {
      if (!updateStatus) return;
      const state = status?.state || "idle";
      const lastSuccess = formatTimestamp(status?.last_success_at);
      const lastFinished = formatTimestamp(status?.last_run_finished);
      if (state === "running") {
        updateStatus.textContent = "Update running now…";
      } else if (state === "failed") {
        updateStatus.textContent = `Last attempt failed at ${lastFinished}.`;
      } else if (state === "success") {
        updateStatus.textContent = `Last success: ${lastSuccess}.`;
      } else {
        updateStatus.textContent = `Last update: ${lastFinished}.`;
      }
      renderSteps(status?.steps || []);
    };

    const fetchStatus = async () => {
      if (!updateStatus) return;
      try {
        const response = await fetch("/api/collection-health/update/status");
        if (!response.ok) return;
        const payload = await response.json();
        renderStatus(payload);
        return payload;
      } catch (error) {
        console.warn(error);
        return null;
      }
    };

    const pollUntilDone = async () => {
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts += 1;
        const payload = await fetchStatus();
        if (!payload) return;
        if (payload.state !== "running" || attempts > 20) {
          clearInterval(interval);
          setBusy(false);
        }
      }, 3000);
    };

    if (updateButton) {
      updateButton.addEventListener("click", async () => {
        setBusy(true);
        try {
          const response = await fetch("/api/collection-health/update/run", {
            method: "POST",
            headers: adminHeaders,
          });
          if (!response.ok) {
            if (response.status === 401) {
              throw new Error(
                "Admin token required. Set localStorage.vaultAdminToken to your ADMIN_TOKEN.",
              );
            }
            throw new Error("Failed to start vault update");
          }
          const payload = await response.json();
          if (payload?.status) {
            renderStatus(payload.status);
          }
          pollUntilDone();
        } catch (error) {
          console.warn(error);
          if (typeof window.showToast === "function") {
            window.showToast("Couldn’t start update—try again soon?");
          }
          setBusy(false);
        }
      });
    }

    if (updateStatus) {
      fetchStatus();
    }
  });
})();

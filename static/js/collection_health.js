(() => {
  document.addEventListener("DOMContentLoaded", () => {
    const updateButtons = Array.from(
      document.querySelectorAll("[data-update-trigger]"),
    );
    const updateStatus = document.querySelector("[data-update-status]");
    const updateSteps = document.querySelector("[data-update-steps]");
    const runHistory = document.querySelector("[data-maintenance-history]");
    const cancelButton = document.querySelector("[data-update-cancel]");
    const providerSummary = document.querySelector(
      "[data-maintenance-providers]",
    );

    const setBusy = (isBusy) => {
      updateButtons.forEach((button) => {
        button.classList.toggle("is-busy", isBusy);
        button.disabled = isBusy || button.dataset.previewBlocked === "true";
      });
      if (cancelButton) {
        cancelButton.disabled = !isBusy;
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
      updateSteps.replaceChildren();
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
        chip.textContent = step.summary ? `${label} — ${step.summary}` : label;
        updateSteps.appendChild(chip);
      });
    };

    const runLabel = (run) => {
      const task = run?.task_id || "all";
      if (task === "all") return "Full metadata maintenance";
      return `${task.charAt(0).toUpperCase()}${task.slice(1)} maintenance`;
    };

    const renderHistory = (runs) => {
      if (!runHistory) return;
      runHistory.replaceChildren();
      if (!Array.isArray(runs) || runs.length === 0) {
        runHistory.textContent = "No recent maintenance runs.";
        return;
      }
      runs.slice(0, 4).forEach((run) => {
        const item = document.createElement("div");
        item.className = "maintenance-run-history__item";

        const summary = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = `${runLabel(run)}: ${run.state || "unknown"}`;
        const time = document.createElement("span");
        time.textContent = `Finished ${formatTimestamp(run.finished_at)}`;
        summary.append(title, time);

        const reports = document.createElement("div");
        reports.className = "maintenance-run-history__reports";
        const availableReports = Array.isArray(run.reports)
          ? run.reports.filter((report) => report.exists && report.url)
          : [];
        if (availableReports.length === 0) {
          const empty = document.createElement("span");
          empty.textContent = "No report available";
          reports.appendChild(empty);
        } else {
          availableReports.forEach((report) => {
            const link = document.createElement("a");
            link.href = report.url;
            link.textContent = `${report.task_name || "Report"} CSV`;
            reports.appendChild(link);
          });
        }

        item.append(summary, reports);
        runHistory.appendChild(item);
      });
    };

    const renderTaskStatuses = (taskStatuses) => {
      const statuses =
        taskStatuses && typeof taskStatuses === "object" ? taskStatuses : {};
      Object.entries(statuses).forEach(([taskId, status]) => {
        const target = document.querySelector(
          `[data-maintenance-latest="${taskId}"]`,
        );
        if (!target) return;

        target.replaceChildren();
        target.classList.remove("is-success", "is-failed", "is-running");
        const state = status?.state || "idle";
        if (state === "success") target.classList.add("is-success");
        if (state === "failed") target.classList.add("is-failed");
        if (state === "running") target.classList.add("is-running");

        const finished = status?.finished_at
          ? formatTimestamp(status.finished_at)
          : "";
        const summary = status?.summary ? ` — ${status.summary}` : "";
        const prefix =
          state === "idle"
            ? "Latest: not run yet"
            : `Latest: ${state}${finished ? ` at ${finished}` : ""}${summary}`;
        target.append(document.createTextNode(prefix));

        const report = status?.report;
        if (report?.exists && report?.url) {
          target.append(document.createTextNode(" "));
          const link = document.createElement("a");
          link.href = report.url;
          link.textContent = "Report CSV";
          target.appendChild(link);
        }
      });
    };

    const renderStatus = (status) => {
      if (!updateStatus) return;
      const state = status?.state || "idle";
      const lastSuccess = formatTimestamp(status?.last_success_at);
      const lastFinished = formatTimestamp(status?.last_run_finished);
      if (state === "running") {
        updateStatus.textContent = "Update running now…";
        if (cancelButton) cancelButton.disabled = false;
      } else if (state === "failed") {
        updateStatus.textContent = `Last attempt failed at ${lastFinished}.`;
        if (cancelButton) cancelButton.disabled = true;
      } else if (state === "cancelled") {
        updateStatus.textContent = `Last attempt cancelled at ${lastFinished}.`;
        if (cancelButton) cancelButton.disabled = true;
      } else if (state === "success") {
        updateStatus.textContent = `Last success: ${lastSuccess}.`;
        if (cancelButton) cancelButton.disabled = true;
      } else {
        updateStatus.textContent = `Last update: ${lastFinished}.`;
        if (cancelButton) cancelButton.disabled = true;
      }
      renderSteps(status?.steps || []);
      renderHistory(status?.runs || []);
      renderTaskStatuses(status?.task_statuses || {});
    };

    const renderPreview = (payload) => {
      if (providerSummary) {
        const providers =
          payload?.providers && typeof payload.providers === "object"
            ? payload.providers
            : {};
        const tmdb = providers.tmdb ? "TMDb available" : "TMDb missing";
        const omdb = providers.omdb ? "OMDb available" : "OMDb missing";
        providerSummary.textContent = `${tmdb} · ${omdb}`;
      }

      const tasks = Array.isArray(payload?.tasks) ? payload.tasks : [];
      tasks.forEach((task) => {
        const preview = document.querySelector(
          `[data-maintenance-preview="${task.id}"]`,
        );
        const button = document.querySelector(
          `[data-maintenance-task="${task.id}"]`,
        );
        const count = Number(task.candidate_count || 0);
        const unit = task.candidate_unit || "candidate rows";
        const samples = Array.isArray(task.sample_titles)
          ? task.sample_titles
          : [];
        const sampleText = samples.length
          ? ` Examples: ${samples.join(", ")}.`
          : "";
        if (preview) {
          preview.textContent = task.ready
            ? `${count} ${unit}.${sampleText}`
            : `${count} ${unit}. ${task.blocked_reason || "Not ready"}.`;
        }
        if (button) {
          button.disabled = !task.ready;
          button.dataset.previewBlocked = task.ready ? "false" : "true";
        }
      });
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

    const fetchPreview = async () => {
      if (!updateButtons.length) return;
      try {
        const response = await fetch("/api/collection-health/update/preview");
        if (!response.ok) return;
        renderPreview(await response.json());
      } catch (error) {
        console.warn(error);
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

    updateButtons.forEach((button) => {
      button.addEventListener("click", async () => {
        const task = button.dataset.maintenanceTask || "all";
        setBusy(true);
        try {
          const response = await fetch(
            `/api/collection-health/update/run?task=${encodeURIComponent(task)}`,
            {
              method: "POST",
            },
          );
          if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
              throw new Error("Admin profile session required.");
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
    });

    if (cancelButton) {
      cancelButton.addEventListener("click", async () => {
        cancelButton.disabled = true;
        try {
          const response = await fetch("/api/collection-health/update/cancel", {
            method: "POST",
          });
          if (!response.ok) {
            throw new Error("Failed to request maintenance cancellation");
          }
          const payload = await response.json();
          if (payload?.status) {
            renderStatus(payload.status);
          }
        } catch (error) {
          console.warn(error);
          if (typeof window.showToast === "function") {
            window.showToast("Couldn’t request cancellation—try again soon?");
          }
        }
      });
    }

    if (updateStatus) {
      fetchStatus();
    }
    fetchPreview();
  });
})();

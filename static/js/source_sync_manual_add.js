(() => {
  const parseErrorMessage = async (response) => {
    try {
      const payload = await response.json();
      return payload.message || payload.detail || "Request failed.";
    } catch {
      return "Request failed.";
    }
  };

  const normalizeYear = (value) => {
    const trimmed = String(value || "").trim();
    if (!trimmed) return null;
    const parsed = Number.parseInt(trimmed, 10);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const buildPreviewSummary = (metadata) => {
    const parts = [
      metadata.year || null,
      metadata.runtime ? `${metadata.runtime} min` : null,
      Array.isArray(metadata.genres) && metadata.genres.length
        ? metadata.genres.slice(0, 3).join(", ")
        : null,
    ];
    return parts.filter(Boolean).join(" • ");
  };

  const renderPreview = (container, title, year, metadata) => {
    container.replaceChildren();

    const poster = document.createElement("div");
    poster.className = "source-sync-manual__poster";
    if (metadata.poster_url) {
      const image = document.createElement("img");
      image.src = metadata.poster_url;
      image.alt = `${metadata.title || title} poster`;
      image.loading = "lazy";
      poster.append(image);
    } else {
      poster.textContent = "No poster";
    }

    const body = document.createElement("div");
    body.className = "source-sync-manual__preview-body";

    const heading = document.createElement("strong");
    heading.textContent = metadata.title || title;

    const summary = document.createElement("span");
    summary.textContent =
      buildPreviewSummary({ ...metadata, year: metadata.year || year }) ||
      "Metadata found";

    const overview = document.createElement("p");
    overview.textContent =
      metadata.overview || "No synopsis returned for this match.";

    body.append(heading, summary, overview);
    container.append(poster, body);
    container.hidden = false;
  };

  window.VaultSourceSyncManualAddSupport = {
    buildPreviewSummary,
    normalizeYear,
  };

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-source-manual-add]");
    if (!root) return;

    const form = root.querySelector("[data-source-manual-form]");
    const status = root.querySelector("[data-source-manual-status]");
    const previewCard = root.querySelector("[data-source-manual-preview-card]");
    const previewButton = root.querySelector("[data-source-manual-preview]");
    const createButton = root.querySelector("[data-source-manual-create]");
    let pendingMetadata = null;
    let pendingTitle = "";
    let pendingYear = null;

    const setStatus = (message, isError = false) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = !message;
      status.classList.toggle("is-error", isError);
    };

    const setBusy = (busy) => {
      if (previewButton) previewButton.disabled = busy;
      if (createButton) createButton.disabled = busy || !pendingMetadata;
      root.toggleAttribute("aria-busy", busy);
    };

    const resetPreview = () => {
      pendingMetadata = null;
      if (createButton) createButton.disabled = true;
      previewCard?.replaceChildren();
      if (previewCard) previewCard.hidden = true;
    };

    const readForm = () => {
      const data = new FormData(form);
      return {
        title: String(data.get("title") || "").trim(),
        year: normalizeYear(data.get("year")),
        vudu: data.get("vudu") === "on",
      };
    };

    form?.addEventListener("input", () => {
      resetPreview();
      setStatus("");
    });

    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      resetPreview();
      const values = readForm();
      if (!values.title) {
        setStatus("Title is required.", true);
        return;
      }

      setBusy(true);
      setStatus("Finding movie metadata...");
      try {
        const response = await fetch("/ui/movies/manual-add/preview", {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ title: values.title, year: values.year }),
        });
        if (!response.ok) {
          throw new Error(await parseErrorMessage(response));
        }
        pendingMetadata = await response.json();
        pendingTitle = values.title;
        pendingYear = values.year;
        renderPreview(previewCard, pendingTitle, pendingYear, pendingMetadata);
        setStatus("Match ready. Review the poster and metadata before adding.");
      } catch (error) {
        setStatus(error.message || "Could not preview that movie.", true);
      } finally {
        setBusy(false);
      }
    });

    createButton?.addEventListener("click", async () => {
      if (!pendingMetadata) return;
      const values = readForm();
      setBusy(true);
      setStatus("Adding movie to Vault...");
      try {
        const response = await fetch("/ui/movies/manual-add", {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            title: pendingTitle,
            year: pendingYear,
            metadata: pendingMetadata,
            vudu: values.vudu,
          }),
        });
        if (!response.ok) {
          throw new Error(await parseErrorMessage(response));
        }
        const payload = await response.json();
        const label = payload.vault_id ? ` ${payload.vault_id}` : "";
        setStatus(`Added${label}: ${payload.title}.`);
        window.showToast?.(`Added ${payload.title}.`);
        resetPreview();
        form.reset();
      } catch (error) {
        setStatus(error.message || "Could not add that movie.", true);
      } finally {
        setBusy(false);
      }
    });
  });
})();

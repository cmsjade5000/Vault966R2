(function () {
  const readError = async (response) => {
    try {
      const payload = await response.json();
      return payload?.message || payload?.detail || null;
    } catch (error) {
      return null;
    }
  };

  const appendMeta = (container, label, value) => {
    const item = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = `${label}: `;
    item.appendChild(strong);
    item.appendChild(document.createTextNode(value || "Missing"));
    container.appendChild(item);
  };

  const providerLink = (label, href) => {
    const link = document.createElement("a");
    link.className = "research-link";
    link.href = href;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = label;
    return link;
  };

  const initFlagMatcher = (root) => {
    const movieId = root.dataset.movieId;
    const form = root.querySelector("[data-flag-match-search]");
    const status = root.querySelector("[data-flag-match-status]");
    const results = root.querySelector("[data-flag-match-results]");
    const submitButton = form?.querySelector('button[type="submit"]');
    if (!movieId || !form || !status || !results || !submitButton) return;

    let currentSearch = null;

    const setPending = (pending) => {
      submitButton.disabled = pending;
      submitButton.toggleAttribute("aria-busy", pending);
    };

    const setStatus = (message, isError = false) => {
      status.textContent = message;
      status.classList.toggle("is-error", isError);
    };

    const renderCandidates = (items) => {
      results.replaceChildren();
      results.hidden = false;

      items.forEach((candidate) => {
        const article = document.createElement("article");
        article.className = "flag-match-card";

        const poster = document.createElement("div");
        poster.className = "flag-match-card__poster";
        if (candidate.poster_url) {
          const image = document.createElement("img");
          image.src = candidate.poster_url;
          image.alt = `${candidate.title || "Movie"} poster`;
          image.loading = "lazy";
          poster.appendChild(image);
        } else {
          poster.textContent = "No poster";
        }

        const body = document.createElement("div");
        body.className = "flag-match-card__body";
        const heading = document.createElement("h4");
        heading.textContent = candidate.title || "Untitled";
        body.appendChild(heading);

        const summary = document.createElement("p");
        summary.className = "flag-match-card__summary";
        const provider =
          candidate.source === "omdb" ? "OMDb result" : "TMDB result";
        const year = candidate.year ? String(candidate.year) : "Year unknown";
        const runtime = candidate.runtime
          ? `${candidate.runtime} minutes`
          : "Runtime unknown";
        const confidence =
          typeof candidate.match_confidence === "number"
            ? `${Math.round(candidate.match_confidence * 100)}% title/year match`
            : "Unscored match";
        summary.textContent = `${provider} · ${year} · ${runtime} · ${confidence}`;
        body.appendChild(summary);

        const ids = document.createElement("div");
        ids.className = "flag-match-card__ids";
        appendMeta(
          ids,
          "TMDB",
          candidate.tmdb_id ? String(candidate.tmdb_id) : "",
        );
        appendMeta(ids, "IMDb", candidate.imdb_id || "");
        body.appendChild(ids);

        if (candidate.synopsis) {
          const synopsis = document.createElement("p");
          synopsis.className = "flag-match-card__synopsis";
          synopsis.textContent = candidate.synopsis;
          body.appendChild(synopsis);
        }

        const links = document.createElement("div");
        links.className = "candidate-research-links";
        if (candidate.tmdb_id) {
          links.appendChild(
            providerLink(
              "View on TMDB",
              `https://www.themoviedb.org/movie/${candidate.tmdb_id}`,
            ),
          );
        }
        if (candidate.imdb_id) {
          links.appendChild(
            providerLink(
              "View on IMDb",
              `https://www.imdb.com/title/${candidate.imdb_id}/`,
            ),
          );
        }
        body.appendChild(links);

        const actions = document.createElement("div");
        actions.className = "flag-match-card__actions";
        const choose = document.createElement("button");
        choose.type = "button";
        choose.className = "button-secondary";
        choose.textContent = "Use this match";
        choose.disabled = !candidate.tmdb_id;
        choose.addEventListener("click", async () => {
          if (!currentSearch || !candidate.tmdb_id) return;
          const confirmed = window.confirm(
            `Use ${candidate.title || "this movie"} (${candidate.year || "year unknown"}) for this Vault entry?`,
          );
          if (!confirmed) return;

          choose.disabled = true;
          choose.setAttribute("aria-busy", "true");
          setStatus("Applying the selected match…");
          try {
            const response = await fetch(
              `/ui/movies/health/review/${movieId}/matches/apply`,
              {
                method: "POST",
                headers: {
                  Accept: "application/json",
                  "Content-Type": "application/json",
                },
                body: JSON.stringify({
                  title: currentSearch.title,
                  year: currentSearch.year,
                  source: candidate.source === "omdb" ? "omdb" : "tmdb",
                  tmdb_id: candidate.tmdb_id,
                  imdb_id: candidate.imdb_id,
                }),
              },
            );
            if (!response.ok) {
              const detail = await readError(response);
              throw new Error(
                detail || `Could not apply match (${response.status})`,
              );
            }
            const payload = await response.json();
            window.persistToastMessage?.(payload.message || "Movie matched.");
            window.location.assign(
              "/ui/movies/health?view=flags#review-workbench",
            );
          } catch (error) {
            setStatus(error.message || "Could not apply that match.", true);
            choose.disabled = false;
            choose.removeAttribute("aria-busy");
          }
        });
        actions.appendChild(choose);
        article.appendChild(poster);
        article.appendChild(body);
        article.appendChild(actions);
        results.appendChild(article);
      });
    };

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const title = String(data.get("title") || "").trim();
      const yearText = String(data.get("year") || "").trim();
      const year = yearText ? Number.parseInt(yearText, 10) : null;
      if (!title) {
        setStatus("Enter a title to search.", true);
        return;
      }
      if (
        year !== null &&
        (!Number.isInteger(year) || year < 1870 || year > 2100)
      ) {
        setStatus("Year must be between 1870 and 2100, or left blank.", true);
        return;
      }

      currentSearch = { title, year };
      const params = new URLSearchParams({ title });
      if (year !== null) params.set("year", String(year));
      setPending(true);
      setStatus("Searching TMDB and OMDb…");
      results.hidden = true;
      results.replaceChildren();

      try {
        const response = await fetch(
          `/ui/movies/health/review/${movieId}/matches?${params}`,
          { headers: { Accept: "application/json" } },
        );
        if (!response.ok) {
          const detail = await readError(response);
          throw new Error(detail || `Lookup failed (${response.status})`);
        }
        const payload = await response.json();
        const items = Array.isArray(payload.items) ? payload.items : [];
        if (!items.length) {
          setStatus(
            "No matches found. Change the title or remove the year.",
            true,
          );
          return;
        }
        renderCandidates(items);
        setStatus(
          `${items.length} option${items.length === 1 ? "" : "s"} found. Review before selecting.`,
        );
      } catch (error) {
        setStatus(error.message || "Lookup failed. Try again.", true);
      } finally {
        setPending(false);
      }
    });
  };

  document.querySelectorAll("[data-flag-match]").forEach(initFlagMatcher);

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-confirm]");
    if (!button) return;
    if (!window.confirm(button.dataset.confirm)) {
      event.preventDefault();
    }
  });
})();

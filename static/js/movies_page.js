  (function () {
    document.addEventListener('DOMContentLoaded', () => {
      const pageData = window.__moviesPageData || {};
      const form = document.getElementById('filters-form');
      const heroStats = document.querySelector('[data-hero-stats]');
      const filtersDialog = document.querySelector('[data-filters-dialog]');
      const filtersOpenButton = document.querySelector('[data-filters-open]');
      const filtersCloseButton = document.querySelector('[data-filters-close]');
      const filtersApplyButton = document.querySelector('[data-filters-apply]');
      const filtersSummaryEl = document.querySelector('[data-filters-summary]');
      const editDialog = document.querySelector('[data-edit-dialog]');
      const editForm = document.getElementById('edit-form');
      const editMovieIdInput = document.getElementById('edit-movie-id');
      const editTitleInput = document.getElementById('edit-title');
      const editYearInput = document.getElementById('edit-year');
      const editRuntimeInput = document.getElementById('edit-runtime');
      const editPosterInput = document.getElementById('edit-poster');
      const editProvidersInput = document.getElementById('edit-providers');
      const editGenresInput = document.getElementById('edit-genres');
      const editPlotInput = document.getElementById('edit-plot');
      const editResolveInput = document.getElementById('edit-resolve-flag');
      const editStatusEl = document.getElementById('edit-status');
      const editSubmitButton = document.getElementById('edit-submit');
      const editCancelButton = document.querySelector('[data-edit-cancel]');
      const editCloseButton = document.querySelector('[data-edit-close]');
      const editLookupButton = document.getElementById('edit-lookup-button');
      const editLookupRetryButton = document.getElementById('edit-lookup-retry');
      const editLookupResults = document.getElementById('edit-lookup-results');
      const editLookupResultsBody = document.getElementById('edit-lookup-results-body');

      let currentEditMovieId = null;
      let currentEditDetail = null;
      let lastEditTrigger = null;
      let currentLookupCandidates = [];
      let lookupRequestToken = 0;

      const isDesktop = () => window.matchMedia('(min-width: 900px)').matches;
      let previousOverflow = document.body.style.overflow || '';

      const lockScroll = () => {
        previousOverflow = document.body.style.overflow || '';
        document.body.style.overflow = 'hidden';
      };

      const unlockScroll = () => {
        document.body.style.overflow = previousOverflow;
      };

      const closeFilters = ({ restoreFocus = false } = {}) => {
        if (!filtersDialog) return;
        if (isDesktop()) {
          filtersDialog.setAttribute('aria-hidden', 'false');
          if (filtersApplyButton) filtersApplyButton.hidden = true;
          unlockScroll();
          return;
        }
        if (!filtersDialog.classList.contains('is-open')) return;
        filtersDialog.classList.remove('is-open');
        filtersDialog.setAttribute('aria-hidden', 'true');
        if (filtersApplyButton) filtersApplyButton.hidden = true;
        unlockScroll();
        if (restoreFocus && filtersOpenButton) {
          filtersOpenButton.focus();
        }
      };

      const openFilters = () => {
        if (!filtersDialog || isDesktop()) {
          return;
        }
        filtersDialog.classList.add('is-open');
        filtersDialog.setAttribute('aria-hidden', 'false');
        if (filtersApplyButton) filtersApplyButton.hidden = false;
        lockScroll();
      };

      const syncHeroStats = () => {
        if (!heroStats) return;
        if (isDesktop()) {
          heroStats.setAttribute('open', '');
        } else {
          heroStats.removeAttribute('open');
        }
      };

      const syncDialogToViewport = () => {
        if (!filtersDialog) return;
        if (isDesktop()) {
          filtersDialog.classList.remove('is-open');
          filtersDialog.setAttribute('aria-hidden', 'false');
          if (filtersApplyButton) filtersApplyButton.hidden = true;
          unlockScroll();
        } else if (!filtersDialog.classList.contains('is-open')) {
          filtersDialog.setAttribute('aria-hidden', 'true');
        }
        syncHeroStats();
      };

      filtersOpenButton?.addEventListener('click', () => {
        openFilters();
      });

      filtersCloseButton?.addEventListener('click', () => {
        closeFilters({ restoreFocus: true });
      });

      filtersDialog?.addEventListener('click', (event) => {
        if (event.target === filtersDialog && !isDesktop()) {
          closeFilters({ restoreFocus: true });
        }
      });

      const dialogMediaQuery = window.matchMedia('(min-width: 900px)');
      dialogMediaQuery.addEventListener('change', syncDialogToViewport);
      syncDialogToViewport();
      const taglines = Array.isArray(pageData.taglines) ? pageData.taglines : [];
      let current = taglines.indexOf(pageData.initialTagline);
      if (current < 0) current = 0;
      const taglineEl = document.getElementById('tagline');
      if (taglines.length && taglineEl) {
        setInterval(() => {
          current = (current + 1) % taglines.length;
          taglineEl.textContent = taglines[current];
        }, 12000);
      }

      const total = Number(pageData.total ?? 0);
      const totalPages = Number(pageData.totalPages ?? 0);
      let currentPage = Number(pageData.page ?? 1);
      if (!Number.isFinite(currentPage) || currentPage < 1) currentPage = 1;
      const showToastMessage = (message) => {
        if (typeof window.showToast === 'function') {
          window.showToast(message);
        }
      };
      if (typeof window.showToast === 'function') {
        if (total > 0) {
          showToastMessage(`I found ${total} titles.`);
        } else {
          showToastMessage('Nothing matched—want me to widen the net?');
        }
      }

      const resetEditStatus = () => {
        if (!editStatusEl) return;
        editStatusEl.textContent = '';
        editStatusEl.hidden = true;
        editStatusEl.classList.remove('is-error');
      };

      const setEditStatus = (message, isError = false) => {
        if (!editStatusEl) return;
        editStatusEl.textContent = message;
        editStatusEl.hidden = !message;
        editStatusEl.classList.toggle('is-error', Boolean(isError));
      };

      const clearLookupResults = ({ hideRetry = false } = {}) => {
        currentLookupCandidates = [];
        if (editLookupResultsBody) {
          editLookupResultsBody.innerHTML = '';
        }
        if (editLookupResults) {
          editLookupResults.hidden = true;
        }
        if (hideRetry && editLookupRetryButton) {
          editLookupRetryButton.hidden = true;
        }
      };

      const setLookupButtonsPending = (pending) => {
        const buttons = [editLookupButton, editLookupRetryButton];
        buttons.forEach((button) => {
          if (!button) return;
          button.disabled = pending;
          if (pending) {
            button.setAttribute('aria-busy', 'true');
          } else {
            button.removeAttribute('aria-busy');
          }
        });
      };

      const applyLookupCandidate = (candidate) => {
        if (!candidate) return;
        if (editTitleInput) editTitleInput.value = candidate.title ?? '';
        if (editYearInput) editYearInput.value =
          candidate.year !== null && candidate.year !== undefined ? String(candidate.year) : '';
        if (editRuntimeInput) editRuntimeInput.value =
          candidate.runtime !== null && candidate.runtime !== undefined
            ? String(candidate.runtime)
            : '';
        if (editPosterInput) editPosterInput.value = candidate.poster_url || '';
        if (editPlotInput) editPlotInput.value = candidate.synopsis || candidate.overview || '';
        if (editGenresInput && Array.isArray(candidate.genres)) {
          editGenresInput.value = candidate.genres.join(', ');
        }
        setEditStatus(`Applied details from "${candidate.title || 'match'}".`);
      };

      const renderLookupCandidates = (candidates) => {
        if (!editLookupResultsBody || !editLookupResults) return;
        editLookupResultsBody.innerHTML = '';

        if (!Array.isArray(candidates) || !candidates.length) {
          editLookupResults.hidden = true;
          return;
        }

        candidates.forEach((candidate, index) => {
          const row = document.createElement('tr');

          const titleCell = document.createElement('td');
          const titleStrong = document.createElement('strong');
          titleStrong.textContent = candidate.title || 'Untitled';
          titleCell.appendChild(titleStrong);
          row.appendChild(titleCell);

          const yearCell = document.createElement('td');
          yearCell.textContent =
            candidate.year !== null && candidate.year !== undefined ? String(candidate.year) : '—';
          row.appendChild(yearCell);

          const runtimeCell = document.createElement('td');
          runtimeCell.textContent = candidate.runtime ? `${candidate.runtime} min` : '—';
          row.appendChild(runtimeCell);

          const idsCell = document.createElement('td');
          const ids = [];
          if (candidate.tmdb_id) ids.push(`TMDb ${candidate.tmdb_id}`);
          if (candidate.imdb_id) ids.push(`IMDb ${candidate.imdb_id}`);
          idsCell.textContent = ids.length ? ids.join(' • ') : '—';
          row.appendChild(idsCell);

          const synopsisCell = document.createElement('td');
          synopsisCell.textContent = candidate.synopsis || '—';
          row.appendChild(synopsisCell);

          const actionsCell = document.createElement('td');
          actionsCell.className = 'edit-lookup-table__actions';
          const applyButton = document.createElement('button');
          applyButton.type = 'button';
          applyButton.className = 'button-ghost';
          applyButton.textContent = 'Use';
          applyButton.addEventListener('click', () => {
            applyLookupCandidate(currentLookupCandidates[index]);
          });
          actionsCell.appendChild(applyButton);
          row.appendChild(actionsCell);

          editLookupResultsBody.appendChild(row);
        });

        editLookupResults.hidden = false;
      };

      const fetchLookupCandidates = async () => {
        if (!currentEditMovieId) return;

        const params = new URLSearchParams();
        const titleValue = editTitleInput?.value?.trim();
        if (titleValue) {
          params.set('title', titleValue);
        }
        const yearValueRaw = editYearInput?.value?.trim();
        if (yearValueRaw) {
          const parsedYear = Number.parseInt(yearValueRaw, 10);
          if (!Number.isNaN(parsedYear)) {
            params.set('year', String(parsedYear));
          }
        }
        params.set('limit', '5');

        const query = params.toString();
        const requestId = ++lookupRequestToken;

        setLookupButtonsPending(true);
        setEditStatus('Finding matches…');

        try {
          const response = await fetch(
            query ? `/movies/${currentEditMovieId}/lookup?${query}` : `/movies/${currentEditMovieId}/lookup`,
            {
              headers: { Accept: 'application/json' },
            }
          );

          if (requestId !== lookupRequestToken) {
            return;
          }

          if (response.status === 404) {
            clearLookupResults();
            setEditStatus('No matches found—try adjusting the title or year.', true);
            return;
          }

          if (response.status === 503) {
            setEditStatus('Lookup service is temporarily unavailable.', true);
            return;
          }

          if (!response.ok) {
            setEditStatus(`Lookup failed (${response.status}).`, true);
            return;
          }

          const payload = await response.json();
          const items = Array.isArray(payload?.items) ? payload.items : [];
          currentLookupCandidates = items;
          renderLookupCandidates(items);
          if (items.length) {
            setEditStatus(items.length === 1 ? 'Found 1 match.' : `Found ${items.length} matches.`);
          } else {
            clearLookupResults();
            setEditStatus('No matches found—try adjusting the title or year.', true);
          }
        } catch (error) {
          console.error('Lookup failed', error);
          if (requestId === lookupRequestToken) {
            setEditStatus('Lookup failed—check your connection and try again.', true);
          }
        } finally {
          if (requestId === lookupRequestToken) {
            setLookupButtonsPending(false);
            if (editLookupRetryButton) {
              editLookupRetryButton.hidden = false;
            }
          }
        }
      };

      const resetEditForm = () => {
        if (editTitleInput) editTitleInput.value = '';
        if (editYearInput) editYearInput.value = '';
        if (editRuntimeInput) editRuntimeInput.value = '';
        if (editPosterInput) editPosterInput.value = '';
        if (editProvidersInput) editProvidersInput.value = '';
        if (editGenresInput) editGenresInput.value = '';
        if (editPlotInput) editPlotInput.value = '';
        if (editResolveInput) editResolveInput.checked = false;
        if (editMovieIdInput) editMovieIdInput.value = '';
        resetEditStatus();
        clearLookupResults({ hideRetry: true });
        setLookupButtonsPending(false);
        lookupRequestToken += 1;
      };

      const closeEditDialog = ({ restoreFocus = false } = {}) => {
        if (!editDialog) return;
        if (editDialog.classList.contains('is-open')) {
          editDialog.classList.remove('is-open');
          editDialog.setAttribute('aria-hidden', 'true');
          unlockScroll();
        }
        resetEditForm();
        const trigger = restoreFocus && lastEditTrigger ? lastEditTrigger : null;
        currentEditMovieId = null;
        currentEditDetail = null;
        if (trigger && typeof trigger.focus === 'function') {
          trigger.focus();
        }
        lastEditTrigger = null;
      };

      const parseProvidersInput = (value) =>
        (value || '')
          .split(/\r?\n|[,;]/)
          .map((item) => item.trim())
          .filter((item) => item.length);

      const parseGenresInput = (value) =>
        (value || '')
          .split(',')
          .map((item) => item.trim())
          .filter((item) => item.length);

      const populateEditForm = (detail) => {
        if (!detail) return;
        currentEditDetail = detail;
        if (editMovieIdInput) editMovieIdInput.value = String(detail.id);
        if (editTitleInput) editTitleInput.value = detail.title || '';
        if (editYearInput) editYearInput.value = detail.year ?? '';
        if (editRuntimeInput) editRuntimeInput.value = detail.runtime ?? '';
        if (editPosterInput) editPosterInput.value = detail.poster_url || '';
        if (editPlotInput) editPlotInput.value = detail.plot || '';
        if (editProvidersInput) editProvidersInput.value = (detail.where_to_watch || []).join('\n');
        if (editGenresInput) editGenresInput.value = (detail.genres || []).join(', ');
        if (editResolveInput) editResolveInput.checked = Boolean(detail.flagged);
      };

      const openEditDialog = async (movieId) => {
        if (!editDialog || !movieId) return;
        currentEditMovieId = Number(movieId);
        resetEditForm();
        editDialog.classList.add('is-open');
        editDialog.setAttribute('aria-hidden', 'false');
        lockScroll();
        setEditStatus('Loading metadata…');
        if (editSubmitButton) {
          editSubmitButton.disabled = true;
          editSubmitButton.setAttribute('aria-busy', 'true');
        }
        try {
          const response = await fetch(`/movies/${movieId}/detail`);
          if (!response.ok) {
            throw new Error(`Failed to load detail (${response.status})`);
          }
          const detail = await response.json();
          populateEditForm(detail);
          setEditStatus('');
          if (editStatusEl) editStatusEl.hidden = true;
          if (editTitleInput) editTitleInput.focus();
          fetchLookupCandidates();
        } catch (error) {
          console.error('Failed to load movie detail', error);
          closeEditDialog();
          showToastMessage('Could not load that movie—try again?');
          return;
        } finally {
          if (editSubmitButton) {
            editSubmitButton.disabled = false;
            editSubmitButton.removeAttribute('aria-busy');
          }
        }
      };

      editCancelButton?.addEventListener('click', () => {
        closeEditDialog({ restoreFocus: true });
      });

      editCloseButton?.addEventListener('click', () => {
        closeEditDialog({ restoreFocus: true });
      });

      editDialog?.addEventListener('click', (event) => {
        if (event.target === editDialog) {
          closeEditDialog({ restoreFocus: true });
        }
      });

      editLookupButton?.addEventListener('click', () => {
        fetchLookupCandidates();
      });

      editLookupRetryButton?.addEventListener('click', () => {
        fetchLookupCandidates();
      });

      const searchInput = document.getElementById('search-q');
      const orderSelect = document.getElementById('order-by');
      const pageInput = form?.querySelector('input[name="page"]');

      const hiddenGenresInput = document.getElementById('genres-input');
      const hiddenYearMinInput = document.getElementById('year-min-input');
      const hiddenYearMaxInput = document.getElementById('year-max-input');
      const hiddenRuntimeInput = document.getElementById('runtime-max-input');
      const hiddenMoodsInput = document.getElementById('moods-input');

      const parseList = (value) =>
        (value || '')
          .split(',')
          .map((item) => item.trim())
          .filter((item) => item.length);

      const toNumber = (value) => {
        if (value === null || value === undefined || value === '') return null;
        const parsed = Number.parseInt(value, 10);
        return Number.isNaN(parsed) ? null : parsed;
      };

      let submitTimer = null;
      const scheduleSubmit = (delay = 120) => {
        if (!form) return;
        if (submitTimer) {
          clearTimeout(submitTimer);
        }
        submitTimer = window.setTimeout(() => {
          submitTimer = null;
          submitSearch();
        }, delay);
      };

      const genreChips = Array.from(document.querySelectorAll('[data-filter-group="genres"] .chip-select'));
      const genreOrder = genreChips.map((chip) => chip.dataset.filterValue).filter(Boolean);
      const moodChips = Array.from(document.querySelectorAll('[data-filter-group="moods"] .chip-select'));
      const moodOrder = moodChips.map((chip) => chip.dataset.filterValue).filter(Boolean);

      const selectedGenres = new Set(parseList(hiddenGenresInput?.value));
      const selectedMoods = new Set(parseList(hiddenMoodsInput?.value));

      const yearPills = document.querySelectorAll('[data-year-pills] .pill-button');
      const yearCustomContainer = document.getElementById('year-custom');
      const yearCustomMinInput = document.getElementById('year-custom-min');
      const yearCustomMaxInput = document.getElementById('year-custom-max');

      let yearState = {
        mode: 'any',
        min: toNumber(hiddenYearMinInput?.value),
        max: toNumber(hiddenYearMaxInput?.value),
      };
      if (yearState.min !== null || yearState.max !== null) {
        if (yearState.min !== null && yearState.max !== null) {
          const matchesPreset = Array.from(yearPills).some((button) => {
            const range = button.dataset.yearRange;
            if (!range || range === 'custom') return false;
            const [start, end] = range.split('-');
            return Number(start) === yearState.min && Number(end) === yearState.max;
          });
          yearState.mode = matchesPreset ? 'decade' : 'custom';
        } else {
          yearState.mode = 'custom';
        }
      }

      const runtimePills = document.querySelectorAll('[data-runtime-pills] .pill-button');
      const runtimeCustomContainer = document.getElementById('runtime-custom');
      const runtimeCustomInput = document.getElementById('runtime-custom-input');
      let runtimeValue = toNumber(hiddenRuntimeInput?.value);

      const orderedFromSet = (set, order) => {
        const ordered = order.filter((value) => set.has(value));
        const extras = Array.from(set).filter((value) => !order.includes(value));
        return [...ordered, ...extras];
      };

      const getFiltersSnapshot = () => {
        const genresArray = orderedFromSet(selectedGenres, genreOrder);
        const moodsArray = orderedFromSet(selectedMoods, moodOrder);
        return {
          q: searchInput?.value.trim() || null,
          genres: genresArray,
          moods: moodsArray,
          year_min: yearState.min,
          year_max: yearState.max,
          runtime_max: runtimeValue,
          order_by: orderSelect?.value || 'title_asc',
        };
      };

      const ORDER_LABELS = {
        title_asc: 'Title A→Z',
        title_desc: 'Title Z→A',
        year_desc: 'Newest first',
        runtime_asc: 'Shortest runtime',
        imdb_desc: 'Highest IMDb',
        rt_desc: 'Highest Rotten Tomatoes',
        flic: 'Flic score',
      };

      const updateFilterSummary = () => {
        if (!filtersSummaryEl) return;
        const snapshot = getFiltersSnapshot();
        const parts = [];
        const {
          genres,
          moods,
          runtime_max: runtimeMax,
          year_min: yearMin,
          year_max: yearMax,
          order_by: orderBy,
        } = snapshot;

        if (genres.length) {
          const label = genres.slice(0, 2).join(', ');
          parts.push(genres.length > 2 ? `${label}…` : label);
        }

        if (moods.length) {
          const preview = moods.slice(0, 2).join(', ');
          const label = moods.length > 2 ? `${preview}…` : preview;
          parts.push(`Moods: ${label}`);
        }

        if (typeof runtimeMax === 'number') {
          parts.push(`≤ ${runtimeMax} min`);
        }

        if (typeof yearMin === 'number' || typeof yearMax === 'number') {
          const start = typeof yearMin === 'number' ? yearMin : 'Any';
          const end = typeof yearMax === 'number' ? yearMax : 'Now';
          parts.push(`${start}–${end}`);
        }

        if (orderBy && orderBy !== 'title_asc') {
          parts.push(ORDER_LABELS[orderBy] || orderBy);
        }

        filtersSummaryEl.textContent = parts.length ? parts.join(' • ') : 'Adjust search';
      };

      const syncHiddenInputs = () => {
        if (hiddenGenresInput) {
          hiddenGenresInput.value = orderedFromSet(selectedGenres, genreOrder).join(', ');
        }
        if (hiddenMoodsInput) {
          hiddenMoodsInput.value = orderedFromSet(selectedMoods, moodOrder).join(', ');
        }
        if (hiddenYearMinInput) {
          hiddenYearMinInput.value = yearState.min ?? '';
        }
        if (hiddenYearMaxInput) {
          hiddenYearMaxInput.value = yearState.max ?? '';
        }
        if (hiddenRuntimeInput) {
          hiddenRuntimeInput.value = runtimeValue ?? '';
        }
      };

      const setChipState = (chips, selection) => {
        chips.forEach((chip) => {
          const value = chip.dataset.filterValue;
          if (!value) return;
          chip.classList.toggle('is-active', selection.has(value));
        });
      };

      const updateChipsFromState = () => {
        setChipState(genreChips, selectedGenres);
        setChipState(moodChips, selectedMoods);
      };

      const ensureYearControlsFromState = () => {
        yearPills.forEach((button) => {
          const range = button.dataset.yearRange;
          if (!range) return;
          if (range === 'custom') {
            button.classList.toggle('is-active', yearState.mode === 'custom');
          } else if (range === '') {
            button.classList.toggle('is-active', yearState.mode === 'any');
          } else if (yearState.min !== null && yearState.max !== null) {
            const [start, end] = range.split('-');
            const isMatch = Number(start) === yearState.min && Number(end) === yearState.max;
            button.classList.toggle('is-active', isMatch);
          } else {
            button.classList.remove('is-active');
          }
        });

        if (yearState.mode === 'custom') {
          yearCustomContainer?.removeAttribute('hidden');
          if (yearCustomMinInput) yearCustomMinInput.value = yearState.min ?? '';
          if (yearCustomMaxInput) yearCustomMaxInput.value = yearState.max ?? '';
        } else {
          yearCustomContainer?.setAttribute('hidden', '');
          if (yearCustomMinInput) yearCustomMinInput.value = '';
          if (yearCustomMaxInput) yearCustomMaxInput.value = '';
        }
      };

      const ensureRuntimeControlsFromState = () => {
        runtimePills.forEach((button) => {
          const raw = button.dataset.runtimeMax;
          if (raw === 'custom') {
            button.classList.toggle(
              'is-active',
              runtimeValue !== null && !Array.from(runtimePills).some((pill) => {
                const preset = pill.dataset.runtimeMax;
                if (!preset || preset === 'custom') return false;
                return Number(preset) === runtimeValue;
              })
            );
          } else if (!raw) {
            button.classList.toggle('is-active', runtimeValue === null);
          } else {
            button.classList.toggle('is-active', runtimeValue === Number(raw));
          }
        });

        const matchesPreset = runtimeValue === null
          || Array.from(runtimePills).some((button) => {
            const raw = button.dataset.runtimeMax;
            return raw && raw !== 'custom' && Number(raw) === runtimeValue;
          });

        if (runtimeValue === null || matchesPreset) {
          runtimeCustomContainer?.setAttribute('hidden', '');
          if (runtimeCustomInput) runtimeCustomInput.value = '';
        } else {
          runtimeCustomContainer?.removeAttribute('hidden');
          if (runtimeCustomInput) runtimeCustomInput.value = runtimeValue ?? '';
        }
      };

      const refreshUI = () => {
        updateChipsFromState();
        ensureYearControlsFromState();
        ensureRuntimeControlsFromState();
        syncHiddenInputs();
        updateFilterSummary();
      };

      const attachChipToggle = (chip, selection) => {
        if (!chip) return;
        const value = chip.dataset.filterValue;
        if (!value) return;
        chip.addEventListener('click', () => {
          if (selection.has(value)) {
            selection.delete(value);
          } else {
            selection.add(value);
          }
          refreshUI();
          scheduleSubmit();
        });
      };

      genreChips.forEach((chip) => attachChipToggle(chip, selectedGenres));
      moodChips.forEach((chip) => attachChipToggle(chip, selectedMoods));

      yearPills.forEach((button) => {
        const range = button.dataset.yearRange ?? '';
        button.addEventListener('click', () => {
          if (range === 'custom') {
            yearState.mode = 'custom';
            yearCustomContainer?.removeAttribute('hidden');
            yearState.min = toNumber(yearCustomMinInput?.value ?? null);
            yearState.max = toNumber(yearCustomMaxInput?.value ?? null);
            if (yearCustomMinInput && !yearCustomMinInput.value) {
              yearCustomMinInput.focus();
            }
          } else if (range === '') {
            yearState = { mode: 'any', min: null, max: null };
          } else {
            const [start, end] = range.split('-');
            yearState = {
              mode: 'decade',
              min: Number(start),
              max: Number(end),
            };
          }
          refreshUI();
          scheduleSubmit(range === 'custom' ? 240 : 0);
        });
      });

      const handleYearCustomInput = () => {
        yearState.mode = 'custom';
        yearCustomContainer?.removeAttribute('hidden');
        yearState.min = toNumber(yearCustomMinInput?.value ?? null);
        yearState.max = toNumber(yearCustomMaxInput?.value ?? null);
        refreshUI();
        scheduleSubmit(240);
      };

      yearCustomMinInput?.addEventListener('input', handleYearCustomInput);
      yearCustomMaxInput?.addEventListener('input', handleYearCustomInput);

      runtimePills.forEach((button) => {
        const raw = button.dataset.runtimeMax ?? '';
        button.addEventListener('click', () => {
          if (raw === 'custom') {
            runtimeCustomContainer?.removeAttribute('hidden');
            runtimeValue = toNumber(runtimeCustomInput?.value ?? null);
            runtimeCustomInput?.focus();
          } else if (raw === '') {
            runtimeValue = null;
          } else {
            runtimeValue = toNumber(raw);
            runtimeCustomContainer?.setAttribute('hidden', '');
            if (runtimeCustomInput) runtimeCustomInput.value = '';
          }
          refreshUI();
          scheduleSubmit(raw === 'custom' ? 240 : 0);
        });
      });

      runtimeCustomInput?.addEventListener('input', () => {
        runtimeValue = toNumber(runtimeCustomInput.value);
        runtimeCustomContainer?.removeAttribute('hidden');
        refreshUI();
        scheduleSubmit(240);
      });

      const submitSearch = ({ resetPage = true } = {}) => {
        if (!form) return;
        if (resetPage && pageInput) pageInput.value = '1';
        syncHiddenInputs();
        closeFilters();
        form.requestSubmit();
      };

      filtersApplyButton?.addEventListener('click', () => {
        submitSearch({ resetPage: false });
      });

      orderSelect?.addEventListener('change', () => {
        if (pageInput) pageInput.value = '1';
        scheduleSubmit();
      });

      const reset = () => {
        if (!form) return;
        if (searchInput) searchInput.value = '';
        selectedGenres.clear();
        selectedMoods.clear();
        yearState = { mode: 'any', min: null, max: null };
        runtimeValue = null;
        if (orderSelect) orderSelect.value = 'title_asc';
        if (pageInput) pageInput.value = '1';
        if (yearCustomMinInput) yearCustomMinInput.value = '';
        if (yearCustomMaxInput) yearCustomMaxInput.value = '';
        if (runtimeCustomInput) runtimeCustomInput.value = '';
        refreshUI();
        syncHiddenInputs();
        submitSearch();
      };

      document.getElementById('reset-filters-bottom')?.addEventListener('click', reset);
      document.getElementById('reset-empty')?.addEventListener('click', reset);

      const applyFilters = (filters) => {
        if (!form) return;
        if (searchInput) searchInput.value = filters.q || '';
        selectedGenres.clear();
        (filters.genres || []).forEach((value) => selectedGenres.add(value));
        selectedMoods.clear();
        (filters.moods || []).forEach((value) => selectedMoods.add(value));
        yearState = { mode: 'any', min: null, max: null };
      if (typeof filters.year_min === 'number' || typeof filters.year_max === 'number') {
        yearState.min = typeof filters.year_min === 'number' ? filters.year_min : null;
        yearState.max = typeof filters.year_max === 'number' ? filters.year_max : null;
        if (yearState.min !== null && yearState.max !== null) {
          const matchesPreset = Array.from(yearPills).some((button) => {
            const range = button.dataset.yearRange;
            if (!range || range === 'custom' || range === '') return false;
            const [start, end] = range.split('-');
            return Number(start) === yearState.min && Number(end) === yearState.max;
          });
          yearState.mode = matchesPreset ? 'decade' : 'custom';
        } else {
          yearState.mode = 'custom';
        }
      }
      runtimeValue = typeof filters.runtime_max === 'number' ? filters.runtime_max : null;
        if (orderSelect) {
          orderSelect.value = filters.order_by || 'title_asc';
        }
        if (pageInput) pageInput.value = '1';
        refreshUI();
        syncHiddenInputs();
        submitSearch();
      };

      const attachPresetChip = (chip) => {
        if (!chip) return;
        chip.addEventListener('click', () => {
          try {
            const raw = chip.getAttribute('data-filters');
            if (!raw) return;
            const data = JSON.parse(raw);
            applyFilters(data);
          } catch (err) {
            console.error('Failed to apply preset', err);
          }
        });
      };

      document.querySelectorAll('.chip-preset[data-filters]').forEach(attachPresetChip);

      const presetsContainer = document.querySelector('#fliclists .chip-scroll');
      const savePresetButton = document.getElementById('save-preset');
      if (savePresetButton) {
        savePresetButton.addEventListener('click', async () => {
          if (!form || savePresetButton.dataset.pending === 'true') {
            return;
          }
          const suggestedName = searchInput?.value.trim() || '';
          const rawName = window.prompt('Name this Fliclist', suggestedName);
          if (rawName === null) {
            return;
          }
          const name = rawName.trim();
          if (!name) {
            if (typeof window.showToast === 'function') {
              window.showToast('Give the preset a name first.');
            }
            return;
          }

        const snapshot = getFiltersSnapshot();
        const payload = {
          name,
          filters: {
            q: snapshot.q,
            genres: snapshot.genres,
            moods: snapshot.moods,
            year_min: snapshot.year_min,
            year_max: snapshot.year_max,
            runtime_max: snapshot.runtime_max,
            order_by: snapshot.order_by,
          },
          };

          savePresetButton.dataset.pending = 'true';
          savePresetButton.setAttribute('aria-busy', 'true');
          savePresetButton.disabled = true;

          try {
            const response = await fetch('/fliclists/', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify(payload),
            });

            if (response.status === 201) {
              const preset = await response.json();
              if (typeof window.showToast === 'function') {
                window.showToast(`Saved "${preset.name}" to Fliclists.`);
              }
              if (presetsContainer) {
                const chip = document.createElement('button');
                chip.type = 'button';
                chip.className = 'chip chip-preset';
                chip.textContent = preset.name;
                chip.setAttribute('data-filters', JSON.stringify(preset.filters));
                presetsContainer.insertBefore(chip, savePresetButton);
                attachPresetChip(chip);
              }
              return;
            }

            let detailMessage = null;
            try {
              const errorPayload = await response.json();
              detailMessage = errorPayload?.detail ?? null;
            } catch (err) {
              detailMessage = null;
            }
            if (detailMessage && typeof window.showToast === 'function') {
              window.showToast(detailMessage);
            } else if (typeof window.showToast === 'function') {
              window.showToast('I could not save that preset—try again?');
            }
          } catch (error) {
            console.error('Failed to save preset', error);
            if (typeof window.showToast === 'function') {
              window.showToast('Network hiccup—try again soon?');
            }
          } finally {
            delete savePresetButton.dataset.pending;
            savePresetButton.removeAttribute('aria-busy');
            savePresetButton.disabled = false;
          }
        });
      }

      form?.addEventListener('submit', syncHiddenInputs);

      refreshUI();

      const resultsTable = document.getElementById('results-table-table');
      const updateMovieDisplays = (movie) => {
        if (!movie || !movie.id) return;
        const title = movie.title || '';
        document
          .querySelectorAll(`[data-movie-card][data-movie-id="${movie.id}"] h2`)
          .forEach((heading) => {
            heading.textContent = title;
          });

        document
          .querySelectorAll(`[data-movie-row][data-movie-id="${movie.id}"]`)
          .forEach((row) => {
            row.dataset.title = title.toLowerCase();
            row.dataset.year = movie.year ?? '';
            row.dataset.runtime = movie.runtime ?? '';
            row.dataset.rating = movie.imdb_rating ?? '';

            const titleCell = row.querySelector('[data-label="Title"]');
            if (titleCell) {
              const link = titleCell.querySelector('a');
              if (link) link.textContent = title;
              titleCell.querySelectorAll('.table-tag--vudu').forEach((tag) => tag.remove());
              const providersRaw = movie.where_to_watch || '';
              const providers = providersRaw
                .split(';')
                .map((provider) => provider.trim())
                .filter((provider) => provider.length);
              const hasVudu = providers.some((provider) => provider.toLowerCase() === 'vudu' || provider.toLowerCase() === 'in vudu');
              if (hasVudu) {
                const tag = document.createElement('span');
                tag.className = 'table-tag table-tag--vudu';
                tag.textContent = 'In Vudu';
                titleCell.appendChild(tag);
              }
            }

            const yearCell = row.querySelector('[data-label="Year"]');
            if (yearCell) yearCell.textContent = movie.year ?? '—';

            const runtimeCell = row.querySelector('[data-label="Runtime"]');
            if (runtimeCell) runtimeCell.textContent = movie.runtime ? String(movie.runtime) : '—';

            const ratingCell = row.querySelector('[data-label="IMDb"]');
            if (ratingCell) ratingCell.textContent = movie.imdb_rating ? String(movie.imdb_rating) : '—';

            const genresCell = row.querySelector('[data-label="Genres"]');
            if (genresCell) {
              const genreNames = Array.isArray(movie.genres)
                ? movie.genres.map((genre) => (typeof genre === 'string' ? genre : genre.name)).filter(Boolean)
                : [];
              genresCell.textContent = genreNames.length ? genreNames.join(', ') : '—';
            }
          });
      };

      const updateFlagUI = (movieId, flagged) => {
        const flagValue = flagged ? 'true' : 'false';
        document
          .querySelectorAll(`[data-flag-button][data-movie-id="${movieId}"]`)
          .forEach((button) => {
            button.dataset.flagged = flagValue;
            button.classList.toggle('is-flagged', flagged);
            button.setAttribute('aria-pressed', flagValue);
            const isTableButton = button.classList.contains('flag-toggle--table');
            const buttonLabel = flagged
              ? isTableButton
                ? 'Resolve'
                : 'Resolve flag'
              : isTableButton
              ? 'Flag'
              : '🚩';
            button.textContent = buttonLabel;
            const ariaLabel = flagged ? 'Resolve flag' : 'Flag to fix';
            button.setAttribute('aria-label', ariaLabel);
          });
        document
          .querySelectorAll(`[data-movie-card][data-movie-id="${movieId}"]`)
          .forEach((card) => {
            card.dataset.flagged = flagValue;
            card.classList.toggle('card--flagged', flagged);
          });
        document
          .querySelectorAll(`[data-movie-row][data-movie-id="${movieId}"]`)
          .forEach((row) => {
            row.dataset.flagged = flagValue;
            row.classList.toggle('is-flagged', flagged);
          });
      };

      const attachFlagButtons = () => {
        document.querySelectorAll('[data-flag-button]').forEach((button) => {
          if (button.dataset.flagHandlerAttached === 'true') {
            return;
          }
          button.dataset.flagHandlerAttached = 'true';
          button.addEventListener('click', async () => {
            const movieId = button.dataset.movieId;
            if (!movieId || button.dataset.flagBusy === 'true') return;
            const currentlyFlagged = button.dataset.flagged === 'true';
            try {
              button.dataset.flagBusy = 'true';
              if (currentlyFlagged) {
                const response = await fetch(`/movies/${movieId}/flag`, {
                  method: 'DELETE',
                });
                if (!response.ok && response.status !== 204) {
                  throw new Error('Failed to clear flag');
                }
                updateFlagUI(movieId, false);
                showToastMessage('Flag cleared.');
              } else {
                const defaultReason = button.dataset.flagDefault || 'Metadata cleanup';
                const rawReason = window.prompt('What needs a fix?', defaultReason);
                if (rawReason === null) {
                  return;
                }
                const reason = rawReason.trim();
                const response = await fetch(`/movies/${movieId}/flag`, {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({ reason: reason || null }),
                });
                if (!response.ok) {
                  throw new Error('Failed to flag movie');
                }
                updateFlagUI(movieId, true);
                showToastMessage('Flag saved.');
              }
            } catch (error) {
              console.error('Flag toggle failed', error);
              showToastMessage('Could not update that flag—try again soon?');
            } finally {
              delete button.dataset.flagBusy;
            }
          });
        });
      };

      const attachEditButtons = () => {
        document.querySelectorAll('[data-edit-button]').forEach((button) => {
          if (button.dataset.editHandlerAttached === 'true') {
            return;
          }
          button.dataset.editHandlerAttached = 'true';
          button.addEventListener('click', () => {
            const movieId = button.dataset.movieId;
            if (!movieId) return;
            lastEditTrigger = button;
            openEditDialog(movieId);
          });
        });
      };

      attachFlagButtons();
      attachEditButtons();

      if (resultsTable) {
        const tableBody = resultsTable.querySelector('tbody');
        const headers = resultsTable.querySelectorAll('[data-sort-key]');
        headers.forEach((header) => {
          header.addEventListener('click', () => {
            const key = header.dataset.sortKey;
            const type = header.dataset.sortType || 'string';
            const currentDir = header.dataset.sortDirection === 'asc' ? 'asc' : 'desc';
            const nextDir = currentDir === 'asc' ? 'desc' : 'asc';

            headers.forEach((h) => {
              h.dataset.sortDirection = '';
              h.setAttribute('aria-sort', 'none');
            });

            header.dataset.sortDirection = nextDir;
            header.setAttribute('aria-sort', nextDir === 'asc' ? 'ascending' : 'descending');

            const rows = Array.from(tableBody.querySelectorAll('tr'));
            rows.sort((a, b) => {
              let aVal = a.dataset[key] || '';
              let bVal = b.dataset[key] || '';

              if (type === 'number') {
                aVal = aVal === '' ? null : Number(aVal);
                bVal = bVal === '' ? null : Number(bVal);
                if (aVal === null) aVal = nextDir === 'asc' ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
                if (bVal === null) bVal = nextDir === 'asc' ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
              } else {
                aVal = (aVal || '').toString().toLowerCase();
                bVal = (bVal || '').toString().toLowerCase();
              }

              if (aVal < bVal) return nextDir === 'asc' ? -1 : 1;
              if (aVal > bVal) return nextDir === 'asc' ? 1 : -1;
              return 0;
            });

            rows.forEach((row) => tableBody.appendChild(row));
          });
        });
      }

      attachFlagButtons();

      const manualAddForm = document.getElementById('manual-add-form');
      if (manualAddForm) {
        const titleInput = document.getElementById('manual-add-title');
        const yearInput = document.getElementById('manual-add-year');
        const statusEl = document.getElementById('manual-add-status');
        const submitButton = document.getElementById('manual-add-submit');
        const previewContainer = document.getElementById('manual-add-preview');
        const previewTitle = document.getElementById('manual-add-preview-title');
        const previewMeta = document.getElementById('manual-add-preview-meta');
        const previewOverview = document.getElementById('manual-add-preview-overview');
        const previewGenres = document.getElementById('manual-add-preview-genres');
        const previewPoster = document.getElementById('manual-add-preview-poster');
        const previewLocation = document.getElementById('manual-add-preview-location');
        const vuduInput = document.getElementById('manual-add-vudu');
        const confirmButton = document.getElementById('manual-add-confirm');
        const cancelButton = document.getElementById('manual-add-cancel');
        const confirmMinimalButton = document.getElementById('manual-add-confirm-minimal');
        const totalFact = document.querySelector('[data-total-entries]');
        const tableBody = document.querySelector('#results-table-table tbody');
        const detailsRoot = document.getElementById('manual-add');

        let currentPreview = null;
        let lastPayload = null;

        const updatePreviewLocation = (preview = null) => {
          if (!previewLocation) return;
          const labels = [];
          if (preview && Array.isArray(preview.where_to_watch)) {
            preview.where_to_watch.forEach((value) => {
              if (typeof value !== 'string') return;
              const trimmed = value.trim();
              if (!trimmed) return;
              const lower = trimmed.toLowerCase();
              const display = lower === 'vudu' || lower === 'in vudu' ? 'In Vudu' : trimmed;
              if (!labels.includes(display)) {
                labels.push(display);
              }
            });
          }
          if (vuduInput?.checked) {
            if (!labels.some((label) => label.toLowerCase() === 'in vudu')) {
              labels.push('In Vudu');
            }
          }
          previewLocation.textContent = labels.length ? labels.join(' · ') : '';
        };

        const setStatus = (message, isError = false) => {
          if (!statusEl) return;
          statusEl.textContent = message;
          statusEl.classList.toggle('is-error', Boolean(isError));
          statusEl.hidden = message === '';
        };

        const resetPreview = () => {
          currentPreview = null;
          if (previewContainer) {
            previewContainer.setAttribute('hidden', '');
          }
          if (previewTitle) previewTitle.textContent = '';
          if (previewMeta) previewMeta.textContent = '';
          if (previewOverview) previewOverview.textContent = '';
          if (previewGenres) previewGenres.textContent = '';
          if (previewPoster) previewPoster.innerHTML = '';
          if (previewLocation) previewLocation.textContent = '';
          if (confirmMinimalButton) confirmMinimalButton.hidden = true;
          if (confirmButton) {
            confirmButton.disabled = false;
            confirmButton.removeAttribute('aria-busy');
          }
        };

        const renderPreview = (preview) => {
          if (!previewContainer) return;
          previewContainer.removeAttribute('hidden');
          if (previewTitle) previewTitle.textContent = preview.title || 'Untitled';

          const metaParts = [];
          if (preview.year) metaParts.push(preview.year);
          if (preview.runtime) metaParts.push(`${preview.runtime} min`);
          if (preview.source) metaParts.push(`from ${preview.source.toUpperCase()}`);
          if (preview.release_date && !preview.year) metaParts.push(preview.release_date);
          if (previewMeta) previewMeta.textContent = metaParts.join(' · ');

          if (previewOverview) {
            previewOverview.textContent = preview.overview || 'No description available yet.';
          }

          if (previewGenres) {
            const genresLabel = (preview.genres || []).join(', ');
            previewGenres.textContent = genresLabel ? `Genres: ${genresLabel}` : '';
          }

          updatePreviewLocation(preview);

          if (previewPoster) {
            previewPoster.innerHTML = '';
            if (preview.poster_url) {
              const img = document.createElement('img');
              img.src = preview.poster_url;
              img.alt = `${preview.title || 'Movie'} poster`;
              img.className = 'manual-add-preview__poster';
              previewPoster.appendChild(img);
            }
          }
        };

        vuduInput?.addEventListener('change', () => {
          updatePreviewLocation(currentPreview);
        });

        manualAddForm.addEventListener('submit', async (event) => {
          event.preventDefault();
          if (!submitButton || !titleInput) return;

          const title = titleInput.value.trim();
          const yearRaw = yearInput?.value.trim() ?? '';
          if (!title) {
            setStatus('Add a title before saving.', true);
            titleInput.focus();
            return;
          }

          let yearValue = null;
          if (yearRaw) {
            const parsed = Number.parseInt(yearRaw, 10);
            if (Number.isNaN(parsed)) {
              setStatus('Year must be a number.', true);
              yearInput?.focus();
              return;
            }
            yearValue = parsed;
          }

          if (submitButton.dataset.pending === 'true') {
            return;
          }

          submitButton.dataset.pending = 'true';
          submitButton.disabled = true;
          submitButton.setAttribute('aria-busy', 'true');
          setStatus('Looking up info…');
          resetPreview();

          const payload = yearValue === null ? { title } : { title, year: yearValue };
          payload.vudu = Boolean(vuduInput?.checked);
          lastPayload = { ...payload };

          try {
            const response = await fetch('/ui/movies/manual-add/preview', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload),
            });
            let body = null;
            try {
              body = await response.json();
            } catch (err) {
              body = null;
            }

            if (!response.ok) {
              const detail = body?.detail ?? 'Unable to find details for that movie.';
              setStatus(detail, true);
              if (response.status === 409) {
                if (typeof window.showToast === 'function') {
                  window.showToast(detail);
                }
                currentPreview = null;
                return;
              }
              if (previewContainer && confirmMinimalButton) {
                previewContainer.removeAttribute('hidden');
                if (previewOverview) {
                  previewOverview.textContent = detail;
                  previewOverview.classList.add('manual-add-preview__body');
                }
                confirmMinimalButton.hidden = false;
              }
              if (confirmButton) {
                confirmButton.disabled = true;
              }
              currentPreview = null;
              updatePreviewLocation();
              return;
            }

            currentPreview = body;
            setStatus('Review the details before adding.');
            renderPreview(body);
            if (confirmButton) confirmButton.disabled = false;
            if (confirmButton) confirmButton.focus();
          } catch (error) {
            console.error('Manual add preview failed', error);
            setStatus('Network hiccup—try again soon?', true);
          } finally {
            submitButton.removeAttribute('aria-busy');
            submitButton.disabled = false;
            delete submitButton.dataset.pending;
          }
        });

        const addRowToTable = (moviePayload) => {
          if (!tableBody || !moviePayload) return;
          const row = document.createElement('tr');
          const lowerTitle = (moviePayload.title || '').toString().toLowerCase();
          row.dataset.title = lowerTitle;
          row.dataset.year = moviePayload.year ?? '';
          row.dataset.runtime = moviePayload.runtime ?? '';
          row.dataset.rating = '';
          row.dataset.movieRow = 'true';
          row.dataset.movieId = String(moviePayload.id);
          row.dataset.flagged = 'false';

          const titleCell = document.createElement('td');
          titleCell.setAttribute('data-label', 'Title');
          const link = document.createElement('a');
          link.href = `/ui/movies/${moviePayload.id}`;
          link.textContent = moviePayload.title;
          titleCell.appendChild(link);
          const providers = Array.isArray(moviePayload.where_to_watch)
            ? moviePayload.where_to_watch
            : [];
          const hasVudu = providers.some(
            (provider) => typeof provider === 'string' && provider.trim().toLowerCase() === 'vudu'
          );
          if (hasVudu) {
            const tag = document.createElement('span');
            tag.className = 'table-tag table-tag--vudu';
            tag.textContent = 'In Vudu';
            titleCell.appendChild(tag);
          }

          const yearCell = document.createElement('td');
          yearCell.setAttribute('data-label', 'Year');
          yearCell.textContent = moviePayload.year ?? '—';

          const runtimeCell = document.createElement('td');
          runtimeCell.setAttribute('data-label', 'Runtime');
          runtimeCell.textContent = moviePayload.runtime ? `${moviePayload.runtime}` : '—';

          const ratingCell = document.createElement('td');
          ratingCell.setAttribute('data-label', 'IMDb');
          ratingCell.textContent = '—';

          const genresCell = document.createElement('td');
          genresCell.setAttribute('data-label', 'Genres');
          const genres = moviePayload.genres || moviePayload.metadata?.genres || [];
          genresCell.textContent = genres.length ? genres.join(', ') : '—';

          const statusCell = document.createElement('td');
          statusCell.setAttribute('data-label', 'Status');
          const statusActions = document.createElement('div');
          statusActions.className = 'table-actions';

          const editButton = document.createElement('button');
          editButton.type = 'button';
          editButton.className = 'edit-toggle edit-toggle--table';
          editButton.dataset.editButton = 'true';
          editButton.dataset.movieId = String(moviePayload.id);
          editButton.textContent = 'Edit';
          editButton.setAttribute('aria-label', `Edit ${moviePayload.title}`);

          const flagButton = document.createElement('button');
          flagButton.type = 'button';
          flagButton.className = 'flag-toggle flag-toggle--table';
          flagButton.dataset.flagButton = 'true';
          flagButton.dataset.movieId = String(moviePayload.id);
          flagButton.dataset.flagged = 'false';
          flagButton.dataset.flagDefault = 'Metadata cleanup';
          flagButton.setAttribute('aria-pressed', 'false');
          flagButton.textContent = 'Flag';

          statusActions.appendChild(editButton);
          statusActions.appendChild(flagButton);
          statusCell.appendChild(statusActions);

          row.appendChild(titleCell);
          row.appendChild(yearCell);
          row.appendChild(runtimeCell);
          row.appendChild(ratingCell);
          row.appendChild(genresCell);
          row.appendChild(statusCell);

          row.classList.remove('is-flagged');

          tableBody.appendChild(row);
          attachFlagButtons();
          attachEditButtons();
        };

        const finalizeCreate = async (metadataOverride) => {
          if (!lastPayload) {
            setStatus('Start with a preview first.', true);
            return;
          }

          const payload = { ...lastPayload };
          payload.vudu = Boolean(vuduInput?.checked);
          if (metadataOverride !== undefined) {
            if (metadataOverride !== null) {
              payload.metadata = metadataOverride;
            }
          } else if (currentPreview) {
            payload.metadata = currentPreview;
          }

          if (confirmButton) {
            confirmButton.dataset.pending = 'true';
            confirmButton.disabled = true;
            confirmButton.setAttribute('aria-busy', 'true');
          }
          if (confirmMinimalButton) {
            confirmMinimalButton.disabled = true;
            confirmMinimalButton.setAttribute('aria-busy', 'true');
          }
          setStatus('Saving…');

          try {
            const response = await fetch('/ui/movies/manual-add', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload),
            });
            let body = null;
            try {
              body = await response.json();
            } catch (err) {
              body = null;
            }

            if (!response.ok) {
              const detail = body?.detail ?? 'Unable to add that movie right now';
              setStatus(detail, true);
              if (typeof window.showToast === 'function') {
                window.showToast(detail);
              }
              return;
            }

            if (titleInput) titleInput.value = '';
            if (yearInput) yearInput.value = '';
            setStatus('Added to your library.');
            if (typeof window.showToast === 'function') {
              window.showToast(`Added "${body.title}".`);
            }

            if (totalFact) {
              const current = Number.parseInt(totalFact.textContent.replace(/[^0-9]/g, ''), 10);
              if (!Number.isNaN(current)) {
                totalFact.textContent = String(current + 1);
              }
            }

            addRowToTable(body);
            if (vuduInput) vuduInput.checked = false;
            resetPreview();
            lastPayload = null;
            if (detailsRoot) {
              detailsRoot.removeAttribute('open');
            }
          } catch (error) {
            console.error('Manual add failed', error);
            setStatus('Network hiccup—try again soon?', true);
          } finally {
            if (confirmButton) {
              confirmButton.removeAttribute('aria-busy');
              confirmButton.disabled = false;
              delete confirmButton.dataset.pending;
            }
            if (confirmMinimalButton) {
              confirmMinimalButton.removeAttribute('aria-busy');
              confirmMinimalButton.disabled = false;
            }
          }
        };

        confirmButton?.addEventListener('click', () => {
          finalizeCreate();
        });

        confirmMinimalButton?.addEventListener('click', () => {
          finalizeCreate({ source: 'manual' });
        });

        cancelButton?.addEventListener('click', () => {
          resetPreview();
          setStatus('Cancelled. Adjust the title or year to try again.');
        });
      }

      const arraysEqualCI = (a, b) => {
        if (!Array.isArray(a) || !Array.isArray(b)) return false;
        if (a.length !== b.length) return false;
        const normalize = (items) => items.map((item) => item.toLowerCase()).sort();
        const normA = normalize(a);
        const normB = normalize(b);
        return normA.every((value, index) => value === normB[index]);
      };

      editForm?.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!currentEditMovieId) {
          closeEditDialog();
          return;
        }

        const detail = currentEditDetail || {};
        let hasChanges = false;
        const payload = {};

        const titleValue = editTitleInput ? editTitleInput.value.trim() : '';
        if (titleValue === '' && titleValue !== (detail.title || '')) {
          setEditStatus('Title cannot be empty.', true);
          editTitleInput?.focus();
          return;
        }
        if (titleValue && titleValue !== (detail.title || '')) {
          payload.title = titleValue;
          hasChanges = true;
        }

        if (editYearInput && editYearInput.value !== '') {
          const yearValue = Number.parseInt(editYearInput.value, 10);
          if (!Number.isNaN(yearValue) && yearValue !== (detail.year ?? null)) {
            payload.year = yearValue;
            hasChanges = true;
          }
        }

        if (editRuntimeInput && editRuntimeInput.value !== '') {
          const runtimeValue = Number.parseInt(editRuntimeInput.value, 10);
          if (!Number.isNaN(runtimeValue) && runtimeValue !== (detail.runtime ?? null)) {
            payload.runtime = runtimeValue;
            hasChanges = true;
          }
        }

        const plotValue = editPlotInput ? editPlotInput.value.trim() : '';
        if (plotValue !== (detail.plot || '')) {
          payload.plot = plotValue;
          hasChanges = true;
        }

        const posterValue = editPosterInput ? editPosterInput.value.trim() : '';
        if (posterValue !== (detail.poster_url || '')) {
          payload.poster_url = posterValue;
          hasChanges = true;
        }

        const providersList = parseProvidersInput(editProvidersInput ? editProvidersInput.value : '');
        const originalProviders = Array.isArray(detail.where_to_watch) ? detail.where_to_watch : [];
        if (!arraysEqualCI(providersList, originalProviders)) {
          payload.where_to_watch = providersList;
          hasChanges = true;
        }

        const genresList = parseGenresInput(editGenresInput ? editGenresInput.value : '');
        const originalGenres = Array.isArray(detail.genres) ? detail.genres : [];
        if (!arraysEqualCI(genresList, originalGenres)) {
          payload.genres = genresList;
          hasChanges = true;
        }

        if (editResolveInput && editResolveInput.checked) {
          payload.resolve_flag = true;
          hasChanges = true;
        }

        if (!hasChanges) {
          showToastMessage('No changes to save.');
          closeEditDialog({ restoreFocus: true });
          return;
        }

        try {
          if (editSubmitButton) {
            editSubmitButton.disabled = true;
            editSubmitButton.setAttribute('aria-busy', 'true');
          }
          setEditStatus('Saving changes…');
          const response = await fetch(`/movies/${currentEditMovieId}`, {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
          });
          if (!response.ok) {
            throw new Error(`Update failed (${response.status})`);
          }
          const updated = await response.json();
          updateMovieDisplays(updated);
          updateFlagUI(String(updated.id), updated.flagged);
          showToastMessage('Movie updated.');
          closeEditDialog({ restoreFocus: true });
        } catch (error) {
          console.error('Failed to update movie', error);
          setEditStatus('Could not save changes—try again?', true);
        } finally {
          if (editSubmitButton) {
            editSubmitButton.disabled = false;
            editSubmitButton.removeAttribute('aria-busy');
          }
        }
      });

      const loadMemory = () => {
        const list = document.getElementById('memory-list');
        if (!list) return;
        fetch('/fliclists/history')
          .then((resp) => (resp.ok ? resp.json() : Promise.reject()))
          .then((items) => {
            if (!items.length) {
              list.innerHTML = '<li class="memory-placeholder">No recent picks yet.</li>';
              return;
            }
            list.innerHTML = '';
            items.forEach((entry) => {
              const li = document.createElement('li');
              const link = document.createElement('a');
              link.href = `/ui/movies/${entry.movie_id}`;
              link.textContent = `#${entry.movie_id} · picked ${new Date(entry.created_at).toLocaleString()}`;
              li.appendChild(link);
              list.appendChild(li);
            });
          })
          .catch(() => {
            list.innerHTML = '<li class="memory-placeholder">I couldn\'t load memory.</li>';
          });
      };

      loadMemory();

      const goToPage = (target) => {
        if (!form || !pageInput) return;
        if (!totalPages || totalPages <= 1) return;
        const desired = Number(target);
        if (Number.isNaN(desired)) return;
        const clamped = Math.max(1, Math.min(totalPages, desired));
        if (clamped === currentPage) return;
        pageInput.value = String(clamped);
        currentPage = clamped;
        syncHiddenInputs();
        form.requestSubmit();
      };

      document.querySelectorAll('[data-goto-page]').forEach((control) => {
        control.addEventListener('click', (event) => {
          if (control.getAttribute('data-disabled') === 'true') {
            event.preventDefault();
            return;
          }
          const targetPage = Number(control.getAttribute('data-goto-page'));
          if (!Number.isNaN(targetPage)) {
            event.preventDefault();
            goToPage(targetPage);
          }
        });
      });

      const doPick = async () => {
        const snapshot = getFiltersSnapshot();
        const params = new URLSearchParams();
        if (snapshot.genres?.length) params.set('genre', snapshot.genres[0]);
        if (snapshot.moods?.length) params.set('mood', snapshot.moods[0]);
        if (typeof snapshot.year_min === 'number') params.set('year_min', snapshot.year_min);
        if (typeof snapshot.year_max === 'number') params.set('year_max', snapshot.year_max);
        if (typeof snapshot.runtime_max === 'number') params.set('runtime_max', snapshot.runtime_max);
        try {
          const response = await fetch(`/movies/picks?${params.toString()}`);
          if (response.status === 404) {
            window.showToast('Nothing matched—want me to widen the net?');
            return;
          }
          if (!response.ok) {
            window.showToast('I hit a snag—try again?');
            return;
          }
          const data = await response.json();
          const successMessage = `I queued "${data.title}" for you.`;
          if (typeof window.persistToastMessage === 'function') {
            window.persistToastMessage(successMessage);
          }
          window.showToast(successMessage);
          loadMemory();
          setTimeout(() => {
            window.location.href = `/ui/movies/${data.id}`;
          }, 600);
        } catch (error) {
          console.error(error);
          window.showToast('Network hiccup—try again soon?');
        }
      };

      document.getElementById('pick-button')?.addEventListener('click', doPick);
      window.addEventListener('flic:trigger-pick', (event) => {
        if (event && typeof event.preventDefault === 'function') {
          event.preventDefault();
        }
        doPick();
      });

      document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') return;
        if (editDialog && editDialog.classList.contains('is-open')) {
          closeEditDialog({ restoreFocus: true });
          return;
        }
        if (filtersDialog && filtersDialog.classList.contains('is-open') && !isDesktop()) {
          closeFilters({ restoreFocus: true });
        }
      });
    });
  })();

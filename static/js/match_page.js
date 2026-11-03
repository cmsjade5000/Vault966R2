(function () {
  let pending = false;
  const prefersReducedMotion = () =>
    Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches);

  const countLabel = (count) => {
    const value = Number.parseInt(count, 10);
    if (!Number.isFinite(value) || value < 0) return "0 left";
    return `${value.toLocaleString()} left`;
  };

  const setPending = (link) => {
    pending = true;
    const page = document.querySelector("[data-match-page]");
    page?.classList.add("is-loading");
    if (!prefersReducedMotion()) {
      link?.classList.add("is-pressed");
    }
    link?.setAttribute("aria-busy", "true");
    if (typeof window.setVaultBusy === "function") {
      window.setVaultBusy("Narrowing the Vault…", { delay: 0 });
    }
  };

  const clearPending = () => {
    pending = false;
    const page = document.querySelector("[data-match-page]");
    page?.classList.remove("is-loading");
    page?.querySelectorAll("[aria-busy], .is-pressed").forEach((link) => {
      link.removeAttribute("aria-busy");
      link.classList.remove("is-pressed");
    });
  };

  window.addEventListener?.("pageshow", clearPending);

  const answerCount = (query) => {
    if (!query) return 0;
    return query.split(",").filter(Boolean).length;
  };

  const nextAnswers = (currentAnswers, answerId) =>
    [...currentAnswers.filter(Boolean), answerId].join(",");

  const showPicksQuery = (currentAnswers) => {
    const answers = currentAnswers.filter(Boolean).join(",");
    return answers ? `answers=${encodeURIComponent(answers)}&show=1` : "show=1";
  };

  window.VaultMatchSupport = {
    answerCount,
    countLabel,
    nextAnswers,
    showPicksQuery,
    prefersReducedMotion,
  };

  document.addEventListener("click", (event) => {
    if (
      event.defaultPrevented ||
      (event.button != null && event.button !== 0) ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    )
      return;
    const link = event.target.closest(
      "[data-match-answer], [data-match-back], [data-match-reset], [data-match-reroll], " +
        "[data-match-show], [data-match-edit]",
    );
    if (!link) return;
    if (pending) {
      event.preventDefault();
      return;
    }
    setPending(link);
  });
})();

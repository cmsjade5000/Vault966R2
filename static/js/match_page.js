(function () {
  const setPending = (link) => {
    const page = document.querySelector("[data-match-page]");
    page?.classList.add("is-loading");
    link?.setAttribute("aria-busy", "true");
    if (typeof window.setVaultBusy === "function") {
      window.setVaultBusy("Narrowing the Vault…", { delay: 0 });
    }
  };

  const answerCount = (query) => {
    if (!query) return 0;
    return query.split(",").filter(Boolean).length;
  };

  const nextAnswers = (currentAnswers, answerId) =>
    [...currentAnswers.filter(Boolean), answerId].join(",");

  window.VaultMatchSupport = {
    answerCount,
    nextAnswers,
  };

  document.addEventListener("click", (event) => {
    const link = event.target.closest(
      "[data-match-answer], [data-match-back], [data-match-reset], [data-match-reroll]",
    );
    if (!link) return;
    setPending(link);
  });
})();

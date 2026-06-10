(function () {
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-confirm]");
    if (!button) return;
    if (!window.confirm(button.dataset.confirm)) {
      event.preventDefault();
    }
  });
})();

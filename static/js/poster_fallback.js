(function () {
  const IMAGE_SELECTOR = "[data-poster-image]";
  const FRAME_SELECTOR = "[data-poster-frame]";
  const FALLBACK_SELECTOR = "[data-poster-fallback]";

  const findPosterParts = (image) => {
    const frame = image?.closest?.(FRAME_SELECTOR);
    const fallback = frame?.querySelector?.(FALLBACK_SELECTOR);
    return { fallback, frame };
  };

  const revealPosterFallback = (image) => {
    const { fallback, frame } = findPosterParts(image);
    if (!frame || !fallback) return false;

    image.hidden = true;
    fallback.hidden = false;
    frame.dataset.posterState = "fallback";
    return true;
  };

  const markPosterLoaded = (image) => {
    const { fallback, frame } = findPosterParts(image);
    if (!frame || !fallback) return false;

    image.hidden = false;
    fallback.hidden = true;
    frame.dataset.posterState = "loaded";
    return true;
  };

  const isPosterImage = (target) => target?.matches?.(IMAGE_SELECTOR) === true;

  const setupPosterFallbacks = (root) => {
    root.addEventListener(
      "load",
      (event) => {
        if (isPosterImage(event.target)) markPosterLoaded(event.target);
      },
      true,
    );
    root.addEventListener(
      "error",
      (event) => {
        if (isPosterImage(event.target)) revealPosterFallback(event.target);
      },
      true,
    );

    const images = Array.from(root.querySelectorAll(IMAGE_SELECTOR));
    images.forEach((image) => {
      if (!image.complete) return;
      if (image.naturalWidth > 0) {
        markPosterLoaded(image);
      } else {
        revealPosterFallback(image);
      }
    });
    return images.length;
  };

  window.VaultPosterFallbackSupport = {
    markPosterLoaded,
    revealPosterFallback,
    setupPosterFallbacks,
  };

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      () => setupPosterFallbacks(document),
      { once: true },
    );
  } else {
    setupPosterFallbacks(document);
  }
})();

(function () {
  const STORAGE_KEY = "linktree-theme";
  const root = document.documentElement;
  const toggle = document.querySelector(".theme-toggle");

  function applyTheme(theme) {
    root.dataset.theme = theme;

    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (error) {
      /* ignore private mode */
    }

    if (!toggle) {
      return;
    }

    const isLight = theme === "light";
    toggle.setAttribute("aria-pressed", String(isLight));
    toggle.setAttribute(
      "aria-label",
      isLight ? "Ativar modo escuro" : "Ativar modo claro"
    );
  }

  applyTheme(root.dataset.theme || "dark");

  toggle?.addEventListener("click", () => {
    applyTheme(root.dataset.theme === "light" ? "dark" : "light");
  });

  window
    .matchMedia("(prefers-color-scheme: light)")
    .addEventListener("change", (event) => {
      try {
        if (localStorage.getItem(STORAGE_KEY)) {
          return;
        }
      } catch (error) {
        return;
      }

      applyTheme(event.matches ? "light" : "dark");
    });
})();

document.querySelectorAll(".link-card").forEach((button) => {
  button.addEventListener("click", () => {
    button.style.transform = "scale(0.985)";
    window.setTimeout(() => {
      button.style.transform = "";
    }, 120);
  });
});

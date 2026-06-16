document.querySelectorAll(".link-card").forEach((button) => {
  button.addEventListener("click", () => {
    button.style.transform = "scale(0.985)";
    window.setTimeout(() => {
      button.style.transform = "";
    }, 120);
  });
});

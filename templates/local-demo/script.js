document.getElementById("year").textContent = String(new Date().getFullYear());

const nav = document.querySelector(".site-nav");
if (nav) {
  const onScroll = () => nav.classList.toggle("is-scrolled", window.scrollY > 12);
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });
}

const revealItems = document.querySelectorAll(".reveal");
if (revealItems.length && "IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
  );
  revealItems.forEach((item) => observer.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add("is-visible"));
}

const whatsappLinks = document.querySelectorAll('a[href*="wa.me"]');
whatsappLinks.forEach((link) => {
  if (!link.getAttribute("href") || link.getAttribute("href") === "#contato") {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      document.getElementById("contato")?.scrollIntoView({ behavior: "smooth" });
    });
  }
});

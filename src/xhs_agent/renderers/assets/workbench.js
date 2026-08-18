document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action='print']");
  if (button) window.print();
});

const filter = document.querySelector("[data-claim-filter]");
if (filter) {
  filter.addEventListener("input", () => {
    const query = filter.value.trim().toLocaleLowerCase("zh-CN");
    document.querySelectorAll("[data-claim]").forEach((claim) => {
      const haystack = (claim.dataset.search || "").toLocaleLowerCase("zh-CN");
      claim.classList.toggle("hidden-by-filter", Boolean(query) && !haystack.includes(query));
    });
    document.querySelectorAll("[data-claim-group]").forEach((group) => {
      const visible = group.querySelectorAll("[data-claim]:not(.hidden-by-filter)").length;
      group.classList.toggle("hidden-by-filter", visible === 0);
    });
  });
}

const tocLinks = [...document.querySelectorAll(".toc a[href^='#']")];
const sections = tocLinks
  .map((link) => document.querySelector(link.getAttribute("href")))
  .filter(Boolean);

if (sections.length && "IntersectionObserver" in window) {
  const linksById = new Map(
    tocLinks.map((link) => [link.getAttribute("href").slice(1), link])
  );
  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (!visible) return;
      tocLinks.forEach((link) => link.classList.remove("is-active"));
      const active = linksById.get(visible.target.id);
      if (active) active.classList.add("is-active");
    },
    { rootMargin: "-18% 0px -68% 0px" }
  );
  sections.forEach((section) => observer.observe(section));
}

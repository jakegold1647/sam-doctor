(() => {
  const count = document.getElementById("github-contributor-count");
  const label = document.getElementById("github-contributor-label");
  if (!count || !label) return;

  const fallback = count.dataset.fallback || count.textContent;
  const endpoint =
    "https://api.github.com/repos/jakegold1647/sam-doctor/contributors?anon=1&per_page=100";

  fetch(endpoint, {
    headers: { Accept: "application/vnd.github+json" },
  })
    .then((response) => {
      if (!response.ok) throw new Error("GitHub contributor request failed");
      return response.json();
    })
    .then((contributors) => {
      if (!Array.isArray(contributors) || contributors.length === 0) {
        throw new Error("GitHub returned no contributor data");
      }
      count.textContent = String(contributors.length);
      count.dataset.source = "github";
      label.textContent = "GitHub contributors (live)";
    })
    .catch(() => {
      count.textContent = fallback;
      count.dataset.source = "snapshot";
      label.textContent = "named community contributors (offline snapshot)";
    });
})();

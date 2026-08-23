(function () {
  "use strict";

  const form = document.getElementById("error-guide-search-form");
  const input = document.getElementById("error-guide-search");
  const clearButton = document.getElementById("error-guide-search-clear");
  const status = document.getElementById("error-guide-search-status");
  const emptyState = document.getElementById("error-guide-search-empty");

  if (!form || !input || !clearButton || !status || !emptyState) {
    return;
  }

  const searchableSections = Array.from(document.querySelectorAll("section.steps"))
    .map((section) => {
      const rows = Array.from(section.querySelectorAll('a[href^="./"]'))
        .map((link) => link.closest("li") || link.closest("p"))
        .filter(Boolean);

      return {
        section,
        rows: Array.from(new Set(rows)).map((row) => ({
          row,
          haystack: normalize(`${row.textContent} ${row.querySelector('a[href^="./"]')?.getAttribute("href") || ""}`),
        })),
      };
    })
    .filter(({ rows }) => rows.length > 0);

  const total = searchableSections.reduce((count, { rows }) => count + rows.length, 0);

  function normalize(value) {
    return value.normalize("NFKD").toLocaleLowerCase().replace(/\s+/g, " ").trim();
  }

  function updateUrl(query) {
    const url = new URL(window.location.href);
    if (query) {
      url.searchParams.set("q", query);
    } else {
      url.searchParams.delete("q");
    }
    history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }

  function filterGuides() {
    const rawQuery = input.value.trim();
    const query = normalize(rawQuery);
    let visible = 0;

    searchableSections.forEach(({ section, rows }) => {
      let visibleInSection = 0;
      rows.forEach(({ row, haystack }) => {
        const matches = !query || haystack.includes(query);
        row.hidden = !matches;
        visibleInSection += Number(matches);
      });
      section.hidden = visibleInSection === 0;
      visible += visibleInSection;
    });

    clearButton.disabled = !rawQuery;
    emptyState.hidden = visible !== 0;
    status.textContent = rawQuery
      ? `Showing ${visible} of ${total} guides for “${rawQuery}”.`
      : `Showing all ${total} guides.`;
    updateUrl(rawQuery);
  }

  function clearSearch() {
    input.value = "";
    filterGuides();
    input.focus();
  }

  function focusFirstVisibleGuide() {
    const firstVisibleRow = searchableSections
      .flatMap(({ rows }) => rows)
      .find(({ row }) => !row.hidden);
    firstVisibleRow?.row.querySelector('a[href^="./"]')?.focus();
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    focusFirstVisibleGuide();
  });
  input.addEventListener("input", filterGuides);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && input.value) {
      event.preventDefault();
      clearSearch();
    } else if (event.key === "Enter") {
      event.preventDefault();
      focusFirstVisibleGuide();
    }
  });
  clearButton.addEventListener("click", clearSearch);

  input.value = new URLSearchParams(window.location.search).get("q") || "";
  filterGuides();
})();

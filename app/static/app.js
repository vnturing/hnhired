/**
 * app.js — Alpine.js component for HN Explorer.
 *
 * State lives entirely in the Alpine component.  Filtering is client-side
 * after the initial fetch so interactions feel instant.
 *
 * The component function is assigned to window so Alpine can find it via
 * x-data="jobExplorer()" in the HTML.
 */
function jobExplorer() {
  return {
    // ── State ──────────────────────────────────────────────────────────────
    allJobs: [],
    filtered: [],
    loading: true,
    error: null,

    // Filter controls — bound to form inputs via x-model
    remoteFilter: "",
    techFilter: "",
    searchFilter: "",

    // ── Lifecycle ──────────────────────────────────────────────────────────
    async init() {
      try {
        const resp = await fetch("/api/jobs");
        if (!resp.ok) throw new Error(`API error: ${resp.status}`);
        this.allJobs = await resp.json();
        this.applyFilters();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },

    // ── Filtering ──────────────────────────────────────────────────────────
    applyFilters() {
      let jobs = this.allJobs;

      if (this.remoteFilter) {
        jobs = jobs.filter(j => j.remote_type === this.remoteFilter);
      }

      if (this.techFilter.trim()) {
        const q = this.techFilter.trim().toLowerCase();
        jobs = jobs.filter(j =>
          j.tech_tags.some(t => t.toLowerCase().includes(q))
        );
      }

      if (this.searchFilter.trim()) {
        const q = this.searchFilter.trim().toLowerCase();
        jobs = jobs.filter(j =>
          j.company.toLowerCase().includes(q) ||
          j.role.toLowerCase().includes(q) ||
          j.raw_text.toLowerCase().includes(q)
        );
      }

      this.filtered = jobs;
    },

    // ── Helpers ────────────────────────────────────────────────────────────
    remoteLabel(type) {
      const labels = {
        "global":     "🌍 Global Remote",
        "us-only":    "🇺🇸 US Only",
        "eu-only":    "🇪🇺 EU Only",
        "tz-limited": "🕐 TZ Limited",
        "onsite":     "🏢 Onsite",
      };
      return labels[type] ?? type;
    },

    hnLink(hnItemId) {
      return `https://news.ycombinator.com/item?id=${hnItemId}`;
    },
  };
}

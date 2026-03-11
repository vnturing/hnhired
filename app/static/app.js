/**
 * app.js — Alpine.js component for HN Explorer.
 *
 * State lives entirely in the Alpine component.  Filtering is client-side
 * after the initial fetch so interactions feel instant.
 *
 * localStorage keys
 *   hn_viewed    — JSON array of hn_item_id numbers that have been opened
 *   hn_dismissed — JSON array of hn_item_id numbers that have been dismissed
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

    // Viewed / dismissed — Sets for O(1) lookup; serialised to localStorage
    viewedIds: new Set(),
    dismissedIds: new Set(),

    // When true, dismissed jobs are shown in a muted style instead of hidden
    showDismissed: false,

    // ── Lifecycle ──────────────────────────────────────────────────────────
    async init() {
      // Rehydrate from localStorage
      try {
        const v = localStorage.getItem("hn_viewed");
        if (v) this.viewedIds = new Set(JSON.parse(v));
      } catch (_) {}
      try {
        const d = localStorage.getItem("hn_dismissed");
        if (d) this.dismissedIds = new Set(JSON.parse(d));
      } catch (_) {}

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

      // Hide dismissed jobs unless the user has toggled "show dismissed"
      if (!this.showDismissed) {
        jobs = jobs.filter(j => !this.dismissedIds.has(j.hn_item_id));
      }

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

    // ── Viewed / Dismissed actions ─────────────────────────────────────────
    markViewed(id) {
      this.viewedIds.add(id);
      this._saveViewed();
      // Trigger Alpine reactivity (Sets are not reactive by default)
      this.viewedIds = new Set(this.viewedIds);
    },

    dismiss(id) {
      this.dismissedIds.add(id);
      this._saveDismissed();
      this.dismissedIds = new Set(this.dismissedIds);
      this.applyFilters();
    },

    undismiss(id) {
      this.dismissedIds.delete(id);
      this._saveDismissed();
      this.dismissedIds = new Set(this.dismissedIds);
      this.applyFilters();
    },

    toggleShowDismissed() {
      this.showDismissed = !this.showDismissed;
      this.applyFilters();
    },

    // ── Computed helpers (used in template) ───────────────────────────────
    isViewed(id)    { return this.viewedIds.has(id); },
    isDismissed(id) { return this.dismissedIds.has(id); },

    get dismissedCount() { return this.dismissedIds.size; },

    // ── Persistence ────────────────────────────────────────────────────────
    _saveViewed() {
      try {
        localStorage.setItem("hn_viewed", JSON.stringify([...this.viewedIds]));
      } catch (_) {}
    },

    _saveDismissed() {
      try {
        localStorage.setItem("hn_dismissed", JSON.stringify([...this.dismissedIds]));
      } catch (_) {}
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

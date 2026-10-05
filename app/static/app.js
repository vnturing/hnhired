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
    monthFilter: "",
    availableMonths: [],
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
      // Rehydrate viewed / dismissed from localStorage
      try {
        const v = localStorage.getItem("hn_viewed");
        if (v) this.viewedIds = new Set(JSON.parse(v));
      } catch (_) {}
      try {
        const d = localStorage.getItem("hn_dismissed");
        if (d) this.dismissedIds = new Set(JSON.parse(d));
      } catch (_) {}

      // Rehydrate filter preferences from localStorage and URL parameters
      let savedFilters = {};
      try {
        const f = localStorage.getItem("hn_filters");
        if (f) savedFilters = JSON.parse(f);
      } catch (_) {}

      try {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has("month")) savedFilters.month = urlParams.get("month");
        if (urlParams.has("remote")) savedFilters.remote = urlParams.get("remote");
        if (urlParams.has("tech")) savedFilters.tech = urlParams.get("tech");
        if (urlParams.has("q")) savedFilters.search = urlParams.get("q");
        if (urlParams.has("dismissed")) savedFilters.showDismissed = urlParams.get("dismissed") === "true";
      } catch (_) {}

      if (savedFilters.remote !== undefined) this.remoteFilter = savedFilters.remote;
      if (savedFilters.tech !== undefined) this.techFilter = savedFilters.tech;
      if (savedFilters.search !== undefined) this.searchFilter = savedFilters.search;
      if (savedFilters.showDismissed !== undefined) this.showDismissed = !!savedFilters.showDismissed;

      try {
        const resp = await fetch("/api/jobs");
        if (!resp.ok) throw new Error(`API error: ${resp.status}`);
        this.allJobs = await resp.json();

        // Extract distinct months and sort descending (newest first)
        const monthsSet = new Set();
        for (const j of this.allJobs) {
          if (j.month && j.month.trim()) {
            monthsSet.add(j.month.trim());
          }
        }
        this.availableMonths = this.sortMonths([...monthsSet]);

        // If user had a saved monthFilter preference, use it if valid; otherwise default to newest month
        if (
          savedFilters.month !== undefined &&
          (savedFilters.month === "" || this.availableMonths.includes(savedFilters.month))
        ) {
          this.monthFilter = savedFilters.month;
        } else if (this.availableMonths.length > 0) {
          this.monthFilter = this.availableMonths[0];
        }

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

      // Filter by month
      if (this.monthFilter) {
        jobs = jobs.filter(j => j.month === this.monthFilter);
      }

      // Hide dismissed jobs unless the user has toggled "show dismissed"
      if (!this.showDismissed) {
        jobs = jobs.filter(j => !this.dismissedIds.has(j.hn_item_id));
      }

      if (this.remoteFilter) {
        jobs = jobs.filter(j => j.remote_type === this.remoteFilter);
      }

      if (this.techFilter.trim()) {
        const raw = this.techFilter.trim();
        const ast = parseSearchQuery(raw);
        if (ast) {
          jobs = jobs.filter(j => evaluateAst(ast, j, "tech"));
        } else {
          const q = raw.toLowerCase();
          jobs = jobs.filter(j =>
            j.tech_tags.some(t => t.toLowerCase().includes(q))
          );
        }
      }

      if (this.searchFilter.trim()) {
        const raw = this.searchFilter.trim();
        const ast = parseSearchQuery(raw);
        if (ast) {
          jobs = jobs.filter(j => evaluateAst(ast, j, "all"));
        } else {
          const q = raw.toLowerCase();
          jobs = jobs.filter(j =>
            j.company.toLowerCase().includes(q) ||
            j.role.toLowerCase().includes(q) ||
            j.raw_text.toLowerCase().includes(q)
          );
        }
      }

      this.filtered = jobs;
      this._saveFilters();
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

    get monthJobCount() {
      let jobs = this.allJobs;
      if (this.monthFilter) {
        jobs = jobs.filter(j => j.month === this.monthFilter);
      }
      if (!this.showDismissed) {
        jobs = jobs.filter(j => !this.dismissedIds.has(j.hn_item_id));
      }
      return jobs.length;
    },

    get headerSubtitle() {
      if (this.monthFilter) {
        return `${this.monthFilter} • ${this.filtered.length} jobs`;
      }
      return `${this.allJobs.length} jobs indexed`;
    },

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

    _saveFilters() {
      try {
        const filters = {
          month: this.monthFilter,
          remote: this.remoteFilter,
          tech: this.techFilter,
          search: this.searchFilter,
          showDismissed: this.showDismissed,
        };
        localStorage.setItem("hn_filters", JSON.stringify(filters));

        // Update URL query parameters cleanly without full page refresh
        const params = new URLSearchParams();
        if (this.monthFilter) params.set("month", this.monthFilter);
        if (this.remoteFilter) params.set("remote", this.remoteFilter);
        if (this.techFilter.trim()) params.set("tech", this.techFilter.trim());
        if (this.searchFilter.trim()) params.set("q", this.searchFilter.trim());
        if (this.showDismissed) params.set("dismissed", "true");

        const query = params.toString() ? `?${params.toString()}` : "";
        window.history.replaceState(null, "", window.location.pathname + query);
      } catch (_) {}
    },

    // ── Helpers ────────────────────────────────────────────────────────────
    sortMonths(months) {
      const monthNames = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
      ];
      return months.sort((a, b) => {
        const parse = (str) => {
          const parts = str.trim().split(/\s+/);
          if (parts.length === 2) {
            const mIdx = monthNames.indexOf(parts[0].toLowerCase());
            const yr = parseInt(parts[1], 10);
            if (mIdx !== -1 && !isNaN(yr)) {
              return yr * 100 + mIdx;
            }
          }
          const t = Date.parse(str);
          return isNaN(t) ? 0 : t;
        };
        return parse(b) - parse(a);
      });
    },

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


// ── Boolean Search Parser & Evaluator ────────────────────────────────────────

/**
 * Parse a search query containing C-style boolean operators into an AST:
 *   &&, +, AND -> logical AND
 *   ||, |, OR  -> logical OR
 *   !, ~, NOT  -> logical NOT
 *   ( )        -> grouping
 *   "quoted"   -> exact phrase
 */
function parseSearchQuery(query) {
  if (!query || !query.trim()) return null;

  const tokens = [];
  const regex =
    /\s*(?:(\|\||\||\bOR\b)|(&&|&|\+|\bAND\b)|([!~]|\bNOT\b)|(\()|(\))|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^\s()|&!~+]+))\s*/gi;
  let match;

  while ((match = regex.exec(query)) !== null) {
    if (match[1]) {
      tokens.push({ type: "OR" });
    } else if (match[2]) {
      tokens.push({ type: "AND" });
    } else if (match[3]) {
      tokens.push({ type: "NOT" });
    } else if (match[4]) {
      tokens.push({ type: "LPAREN" });
    } else if (match[5]) {
      tokens.push({ type: "RPAREN" });
    } else if (match[6]) {
      let val = match[6];
      if (
        (val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))
      ) {
        val = val.slice(1, -1);
      }
      tokens.push({ type: "TERM", value: val });
    }
  }

  if (tokens.length === 0) return null;

  let pos = 0;
  function peek() {
    return tokens[pos] || null;
  }
  function consume() {
    return tokens[pos++];
  }

  function parseOr() {
    let left = parseAnd();
    if (!left) return null;
    while (peek() && peek().type === "OR") {
      consume();
      const right = parseAnd();
      if (!right) break;
      left = { type: "OR", left, right };
    }
    return left;
  }

  function parseAnd() {
    let left = parseNot();
    if (!left) return null;
    while (
      peek() &&
      (peek().type === "AND" ||
        peek().type === "NOT" ||
        peek().type === "LPAREN" ||
        peek().type === "TERM")
    ) {
      if (peek().type === "AND") consume();
      const right = parseNot();
      if (!right) break;
      left = { type: "AND", left, right };
    }
    return left;
  }

  function parseNot() {
    if (peek() && peek().type === "NOT") {
      consume();
      const operand = parseNot();
      if (!operand) return null;
      return { type: "NOT", expr: operand };
    }
    return parsePrimary();
  }

  function parsePrimary() {
    const token = peek();
    if (!token) return null;
    if (token.type === "LPAREN") {
      consume();
      const expr = parseOr();
      if (peek() && peek().type === "RPAREN") consume();
      return expr;
    }
    if (token.type === "TERM") {
      consume();
      return { type: "TERM", value: token.value };
    }
    return null;
  }

  try {
    return parseOr();
  } catch (_) {
    return null;
  }
}

function matchTerm(job, term, mode = "all") {
  if (!term) return true;
  const q = term.trim().toLowerCase();
  if (!q) return true;

  // 1. Check in tech_tags
  if (job.tech_tags && job.tech_tags.length > 0) {
    for (const tag of job.tech_tags) {
      const tLower = tag.toLowerCase();
      if (tLower === q) return true;
      if (q.length > 2 && tLower.includes(q)) return true;
    }
  }

  if (mode === "tech") {
    // In tech mode, check raw_text with word boundary so e.g. standalone "C" or "C++" matches
    if (job.raw_text) {
      if (q.length <= 2) {
        const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        if (new RegExp(`\\b${escaped}\\b`, "i").test(job.raw_text)) return true;
      } else {
        if (job.raw_text.toLowerCase().includes(q)) return true;
      }
    }
    return false;
  }

  // 2. Check company and role
  if (job.company && job.company.toLowerCase().includes(q)) return true;
  if (job.role && job.role.toLowerCase().includes(q)) return true;

  // 3. Check raw_text
  if (job.raw_text) {
    if (q.length <= 2) {
      const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      if (new RegExp(`\\b${escaped}\\b`, "i").test(job.raw_text)) return true;
    } else {
      if (job.raw_text.toLowerCase().includes(q)) return true;
    }
  }

  return false;
}

function evaluateAst(ast, job, mode = "all") {
  if (!ast) return true;
  switch (ast.type) {
    case "AND":
      return evaluateAst(ast.left, job, mode) && evaluateAst(ast.right, job, mode);
    case "OR":
      return evaluateAst(ast.left, job, mode) || evaluateAst(ast.right, job, mode);
    case "NOT":
      return !evaluateAst(ast.expr, job, mode);
    case "TERM":
      return matchTerm(job, ast.value, mode);
    default:
      return true;
  }
}

const api = {
  async request(path, params = {}) {
    const url = new URL(path, window.location.origin);

    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });

    const response = await fetch(url.toString(), {
      headers: {
        Accept: "application/json",
      },
    });

    const payload = await response.json();

    if (!response.ok || !payload.success) {
      throw new Error(payload?.error?.message || "Request failed");
    }

    return payload.data;
  },
};

const qs = (selector, scope = document) => scope.querySelector(selector);
const qsa = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));

const page = document.body.dataset.page;

const galleryState = {
  limit: 6,
  offset: 0,
  total: 0,
  appending: false,
  filters: {
    query: "",
    category: "",
    location: "",
  },
};

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDate(value) {
  if (!value) return "Recently published";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Recently published";

  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(parsed);
}

function buildComparisonPanel(url, label, side, alt) {
  if (!url) {
    return `
      <div class="comparison__panel comparison__panel--placeholder">
        <span class="comparison__label comparison__label--${side}">${label}</span>
        <span>No ${label.toLowerCase()} image</span>
      </div>
    `;
  }

  return `
    <div class="comparison__panel">
      <span class="comparison__label comparison__label--${side}">${label}</span>
      <img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" loading="lazy" />
    </div>
  `;
}

function buildSessionCard(session, options = {}) {
  const wideClass = options.wide ? " case-card--wide" : "";
  const practice = session.practice || {};
  const provider = session.provider || {};
  const caseHref = `/case-study/?id=${encodeURIComponent(session.id)}`;
  const providerHref = `/provider/?slug=${encodeURIComponent(practice.widget_slug || "")}`;

  return `
    <article class="case-card${wideClass}">
      <a class="comparison" href="${caseHref}">
        ${buildComparisonPanel(
          session.before_image_url,
          "Before",
          "before",
          `${session.treatment} before result`
        )}
        ${buildComparisonPanel(
          session.after_image_url,
          "After",
          "after",
          `${session.treatment} after result`
        )}
      </a>
      <div class="case-card__body">
        <div class="meta-row">
          <span class="meta-pill">${escapeHtml(session.category || "Transformation")}</span>
          <span class="meta-pill">${escapeHtml(formatDate(session.published_at))}</span>
        </div>
        <h3 class="case-card__title">${escapeHtml(session.treatment)}</h3>
        <p class="case-card__subtitle">
          ${escapeHtml(provider.name || practice.name || "Veriba Provider")}
          ${practice.location ? ` in ${escapeHtml(practice.location)}` : ""}
        </p>
        <div class="case-card__footer">
          <a class="subtle-link" href="${providerHref}">View provider</a>
          <a class="button-primary" href="${caseHref}">View case study</a>
        </div>
      </div>
    </article>
  `;
}

function buildPracticeCard(practice) {
  const href = `/provider/?slug=${encodeURIComponent(practice.widget_slug)}`;
  const image = practice.featured_image_url
    ? `<img src="${escapeHtml(practice.featured_image_url)}" alt="${escapeHtml(practice.name)} featured result" loading="lazy" />`
    : `<div class="provider-card__image--fallback">${escapeHtml(
        (practice.provider_initials || practice.name || "V").slice(0, 2)
      )}</div>`;

  return `
    <article class="provider-card">
      <a class="provider-card__image" href="${href}">
        ${image}
      </a>
      <div class="provider-card__body">
        <div class="meta-row">
          <span class="meta-pill">${escapeHtml(practice.location || "Veriba Partner")}</span>
          <span class="meta-pill">${escapeHtml(
            `${practice.published_session_count || 0} published cases`
          )}</span>
        </div>
        <h3 class="provider-card__title">${escapeHtml(practice.provider_name || practice.name)}</h3>
        <p class="provider-card__subtitle">
          ${escapeHtml(practice.name)}
          ${practice.featured_treatment ? ` • ${escapeHtml(practice.featured_treatment)}` : ""}
        </p>
        <div class="provider-card__footer">
          <a class="subtle-link" href="${practice.website || href}" ${
            practice.website ? 'target="_blank" rel="noreferrer"' : ""
          }>
            ${practice.website ? "Visit website" : "Open profile"}
          </a>
          <a class="button-secondary" href="${href}">Explore profile</a>
        </div>
      </div>
    </article>
  `;
}

function buildTimelineItem(item) {
  return `
    <article class="timeline__item">
      <span class="timeline__bullet"></span>
      <div>
        <h4>${escapeHtml(item.label)}</h4>
        <p>${escapeHtml(item.detail || "Verified checkpoint")}</p>
        <time>${escapeHtml(formatDate(item.timestamp))}</time>
      </div>
    </article>
  `;
}

function setLoading(target, message = "Loading...") {
  if (target) {
    target.innerHTML = `<p class="loading">${escapeHtml(message)}</p>`;
  }
}

function setEmpty(target, title, copy) {
  if (target) {
    target.innerHTML = `
      <div class="empty-state">
        <h3 class="headline-md">${escapeHtml(title)}</h3>
        <p class="muted">${escapeHtml(copy)}</p>
      </div>
    `;
  }
}

function readQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name) || "";
}

function buildQueryString(filters) {
  const search = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value) search.set(key, value);
  });

  const output = search.toString();
  return output ? `?${output}` : "";
}

function syncGalleryUrl() {
  const query = buildQueryString({
    q: galleryState.filters.query,
    category: galleryState.filters.category,
    location: galleryState.filters.location,
  });

  window.history.replaceState({}, "", `${window.location.pathname}${query}`);
}

async function initHomePage() {
  const featuredSessionsRoot = qs("#featured-sessions");
  const featuredPracticesRoot = qs("#featured-practices");
  const heroImage = qs("#home-hero-image");
  const heroSummary = qs("#home-hero-summary");

  setLoading(featuredSessionsRoot, "Curating transformations...");
  setLoading(featuredPracticesRoot, "Loading provider spotlights...");

  try {
    const data = await api.request("/api/gallery/home");
    const featuredSessions = data.featured_sessions || [];
    const featuredPractices = data.featured_practices || [];
    const heroSession = featuredSessions[0];

    if (heroSession && heroSession.after_image_url) {
      heroImage.innerHTML = `<img src="${escapeHtml(heroSession.after_image_url)}" alt="${escapeHtml(
        heroSession.treatment
      )} transformation" />`;
      heroSummary.innerHTML = `
        <span class="eyebrow">Freshly Published</span>
        <h2 class="headline-md">${escapeHtml(heroSession.treatment)}</h2>
        <p class="hero-visual__caption">
          A recently verified transformation from ${escapeHtml(
            heroSession.practice?.name || "a Veriba medspa"
          )}, presented with chain-of-custody context and editorial detail.
        </p>
      `;
    }

    if (featuredSessions.length) {
      featuredSessionsRoot.innerHTML = featuredSessions
        .map((session, index) => buildSessionCard(session, { wide: index === 0 }))
        .join("");
    } else {
      setEmpty(
        featuredSessionsRoot,
        "No published transformations yet",
        "Once medspas publish cases, they will appear here automatically."
      );
    }

    if (featuredPractices.length) {
      featuredPracticesRoot.innerHTML = featuredPractices.map(buildPracticeCard).join("");
    } else {
      setEmpty(
        featuredPracticesRoot,
        "No provider spotlights yet",
        "Featured medspas will appear here as soon as public cases exist."
      );
    }
  } catch (error) {
    setEmpty(
      featuredSessionsRoot,
      "The gallery is waking up",
      error.message || "We could not load featured transformations."
    );
    setEmpty(
      featuredPracticesRoot,
      "Provider spotlights unavailable",
      "Try refreshing in a moment."
    );
  }

  qsa("[data-gallery-search]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const q = data.get("q") || "";
      window.location.href = `/gallery/${buildQueryString({ q })}`;
    });
  });
}

async function fetchGalleryResults({ append = false } = {}) {
  const resultsRoot = qs("#gallery-results");
  const summary = qs("#results-summary");
  const loadMore = qs("#gallery-load-more");
  const filters = galleryState.filters;

  if (!append) {
    setLoading(resultsRoot, "Loading transformations...");
    galleryState.offset = 0;
  }

  try {
    const data = await api.request("/api/gallery/sessions", {
      query: filters.query,
      category: filters.category,
      location: filters.location,
      offset: galleryState.offset,
      limit: galleryState.limit,
    });
    const results = data.sessions || [];

    if (!append) {
      const categorySelect = qs("#gallery-category");
      const current = filters.category;
      const options = [
        `<option value="">All treatments</option>`,
        ...(data.available_categories || []).map(
          (value) =>
            `<option value="${escapeHtml(value)}" ${
              value === current ? "selected" : ""
            }>${escapeHtml(value)}</option>`
        ),
      ];
      if (categorySelect) {
        categorySelect.innerHTML = options.join("");
      }
    }

    galleryState.total = data.total || 0;

    if (!results.length && !append) {
      setEmpty(
        resultsRoot,
        "No transformations match those filters",
        "Try a broader treatment or location search."
      );
    } else {
      const markup = results
        .map((session, index) => buildSessionCard(session, { wide: !append && index === 2 }))
        .join("");

      if (append) {
        resultsRoot.insertAdjacentHTML("beforeend", markup);
      } else {
        resultsRoot.innerHTML = markup;
      }
    }

    if (summary) {
      const prefix = galleryState.total === 1 ? "case study" : "case studies";
      summary.textContent = `${galleryState.total} public ${prefix} available`;
    }

    if (loadMore) {
      const shown = galleryState.offset + results.length;
      const hasMore = shown < galleryState.total;
      loadMore.hidden = !hasMore;
      galleryState.offset = shown;
    }
  } catch (error) {
    if (!append) {
      setEmpty(
        resultsRoot,
        "Gallery results unavailable",
        error.message || "We could not load public transformations."
      );
    }
    if (loadMore) {
      loadMore.hidden = true;
    }
  }
}

async function initGalleryPage() {
  galleryState.filters.query = readQueryParam("q");
  galleryState.filters.category = readQueryParam("category");
  galleryState.filters.location = readQueryParam("location");

  const form = qs("#gallery-search-form");
  const queryInput = qs("#gallery-query");
  const locationInput = qs("#gallery-location");
  const loadMore = qs("#gallery-load-more");

  if (queryInput) queryInput.value = galleryState.filters.query;
  if (locationInput) locationInput.value = galleryState.filters.location;

  if (form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      galleryState.filters.query = String(data.get("q") || "");
      galleryState.filters.category = String(data.get("category") || "");
      galleryState.filters.location = String(data.get("location") || "");
      syncGalleryUrl();
      await fetchGalleryResults();
    });
  }

  if (loadMore) {
    loadMore.addEventListener("click", async () => {
      await fetchGalleryResults({ append: true });
    });
  }

  await fetchGalleryResults();
}

async function initProviderPage() {
  const slug = readQueryParam("slug");
  const root = qs("#provider-root");

  if (!slug) {
    setEmpty(root, "Provider not selected", "Open a provider card from the gallery to continue.");
    return;
  }

  setLoading(root, "Loading provider profile...");

  try {
    const data = await api.request(`/api/gallery/practices/${encodeURIComponent(slug)}`);
    const practice = data.practice;
    const sessions = data.sessions || [];

    document.title = `${practice.provider_name || practice.name} | Veriba Gallery`;

    root.innerHTML = `
      <section class="provider-hero">
        <div class="provider-hero__copy">
          <span class="eyebrow">Provider profile</span>
          <h1 class="headline-lg">${escapeHtml(practice.provider_name || practice.name)}</h1>
          <p class="lede">
            ${escapeHtml(practice.name)} in ${escapeHtml(
              practice.location || "Veriba"
            )}. A curated collection of verified before-and-after work presented through the Veriba public gallery.
          </p>
          <div class="provider-hero__meta">
            <span class="meta-pill">${escapeHtml(practice.location || "Veriba")}</span>
            <span class="meta-pill">${escapeHtml(
              `${practice.published_session_count || 0} public cases`
            )}</span>
            ${
              practice.website
                ? `<a class="button-secondary" href="${escapeHtml(
                    practice.website
                  )}" target="_blank" rel="noreferrer">Visit website</a>`
                : ""
            }
          </div>
          <div class="stats-grid">
            <div class="stat-card">
              <strong>${escapeHtml(String(practice.published_session_count || 0))}</strong>
              <span>Published transformations</span>
            </div>
            <div class="stat-card">
              <strong>${escapeHtml(practice.location || "Veriba")}</strong>
              <span>Primary location</span>
            </div>
            <div class="stat-card">
              <strong>${escapeHtml(practice.featured_treatment || "Editorial")}</strong>
              <span>Featured treatment</span>
            </div>
          </div>
        </div>
        <div class="provider-hero__media">
          <div class="comparison">
            ${buildComparisonPanel(
              sessions[0]?.before_image_url,
              "Before",
              "before",
              `${sessions[0]?.treatment || practice.name} before result`
            )}
            ${buildComparisonPanel(
              sessions[0]?.after_image_url,
              "After",
              "after",
              `${sessions[0]?.treatment || practice.name} after result`
            )}
          </div>
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <div class="section-head__copy">
            <span class="eyebrow">Published work</span>
            <h2 class="headline-md">A catalog of refined transformations</h2>
            <p>Each case is accessible as an editorial detail page with verification context and publication metadata.</p>
          </div>
        </div>
        <div class="cases-grid" id="provider-sessions">
          ${sessions.map((session, index) => buildSessionCard(session, { wide: index === 0 })).join("")}
        </div>
      </section>
    `;
  } catch (error) {
    setEmpty(root, "Provider unavailable", error.message || "We could not load this provider profile.");
  }
}

async function initCaseStudyPage() {
  const id = readQueryParam("id");
  const root = qs("#case-root");

  if (!id) {
    setEmpty(root, "Case study not selected", "Open a transformation card from the gallery to continue.");
    return;
  }

  setLoading(root, "Loading case study...");

  try {
    const data = await api.request(`/api/gallery/sessions/${encodeURIComponent(id)}`);
    const session = data.session;
    const practice = data.practice;
    const related = data.related_sessions || [];
    const providerHref = `/provider/?slug=${encodeURIComponent(practice.widget_slug)}`;
    const timeline = session.chain_of_custody?.checkpoints || [];

    document.title = `${session.treatment} | Veriba Gallery`;

    root.innerHTML = `
      <section class="case-hero">
        <div class="case-hero__copy">
          <span class="eyebrow">Case study</span>
          <h1 class="headline-lg">${escapeHtml(session.treatment)}</h1>
          <p class="lede">
            ${escapeHtml(practice.provider_name || practice.name)} at ${escapeHtml(
              practice.name
            )}, ${escapeHtml(practice.location || "Veriba")}.
          </p>
          <div class="case-hero__meta">
            <span class="meta-pill">${escapeHtml(session.category || "Transformation")}</span>
            <span class="meta-pill">${escapeHtml(formatDate(session.published_at))}</span>
            <span class="meta-pill">${escapeHtml(
              `${session.chain_of_custody?.checkpoints?.length || 0} verification checkpoints`
            )}</span>
          </div>
          <div class="hero__actions">
            <a class="button-primary" href="${providerHref}">View provider profile</a>
            <a class="button-secondary" href="/gallery/">Back to gallery</a>
          </div>
        </div>
        <div class="case-hero__media">
          <div class="comparison">
            ${buildComparisonPanel(
              session.before_image_url,
              "Before",
              "before",
              `${session.treatment} before image`
            )}
            ${buildComparisonPanel(
              session.after_image_url,
              "After",
              "after",
              `${session.treatment} after image`
            )}
          </div>
        </div>
      </section>

      <section class="case-layout">
        <div class="case-section">
          <h3>Editorial summary</h3>
          <p>${
            session.treatment_details
              ? escapeHtml(session.treatment_details)
              : "This published transformation is now part of the Veriba public gallery. The case detail experience is designed to keep the visual story elegant while still surfacing verification and provider context."
          }</p>
          <div class="meta-row">
            <span class="meta-pill">${escapeHtml(practice.name)}</span>
            <span class="meta-pill">${escapeHtml(practice.location || "Veriba")}</span>
            <span class="meta-pill">${escapeHtml(session.obscure_mode || "none")} obscuring</span>
          </div>
        </div>
        <div class="case-section">
          <h3>Chain of custody</h3>
          <div class="timeline">
            ${
              timeline.length
                ? timeline.map(buildTimelineItem).join("")
                : '<p class="inline-note">No verification checkpoints were recorded for this case.</p>'
            }
          </div>
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <div class="section-head__copy">
            <span class="eyebrow">More from this provider</span>
            <h2 class="headline-md">Related published transformations</h2>
          </div>
        </div>
        <div class="cases-grid--three cases-grid">
          ${
            related.length
              ? related.map((item) => buildSessionCard(item)).join("")
              : '<div class="empty-state"><h3 class="headline-md">No related cases yet</h3><p class="muted">This provider has not published additional transformations.</p></div>'
          }
        </div>
      </section>
    `;
  } catch (error) {
    setEmpty(root, "Case study unavailable", error.message || "We could not load this case study.");
  }
}

function markActiveNav() {
  const current = page;
  const navMap = {
    home: "/",
    gallery: "/gallery/",
    provider: "/gallery/",
    "case-study": "/gallery/",
  };
  qsa("[data-nav-link]").forEach((link) => {
    if (link.getAttribute("href") === navMap[current]) {
      link.setAttribute("aria-current", "page");
    }
  });
}

async function init() {
  markActiveNav();

  if (page === "home") {
    await initHomePage();
  }

  if (page === "gallery") {
    await initGalleryPage();
  }

  if (page === "provider") {
    await initProviderPage();
  }

  if (page === "case-study") {
    await initCaseStudyPage();
  }
}

init();

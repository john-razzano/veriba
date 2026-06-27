const ACCESS_TOKEN_KEY = "veriba.medspa.access_token";
const REFRESH_TOKEN_KEY = "veriba.medspa.refresh_token";
const AUTH_MODE_KEY = "veriba.medspa.auth_mode";

const state = {
  authMode: localStorage.getItem(AUTH_MODE_KEY) || "login",
  user: null,
  practice: null,
  practiceStats: null,
  creditsStats: null,
  credits: [],
  sessions: [],
  filters: {
    query: "",
    status: "",
  },
  refreshPromise: null,
};

const elements = {
  authShell: document.querySelector("#medspa-auth-shell"),
  dashboard: document.querySelector("#medspa-dashboard"),
  authCopy: document.querySelector("#auth-copy"),
  authStatus: document.querySelector("#auth-status"),
  dashboardStatus: document.querySelector("#dashboard-status"),
  loginForm: document.querySelector("#login-form"),
  signupForm: document.querySelector("#signup-form"),
  createSessionForm: document.querySelector("#create-session-form"),
  practiceForm: document.querySelector("#practice-settings-form"),
  accountForm: document.querySelector("#account-form"),
  passwordForm: document.querySelector("#password-form"),
  refreshButton: document.querySelector("#dashboard-refresh"),
  logoutButton: document.querySelector("#dashboard-logout"),
  practiceName: document.querySelector("#dashboard-practice-name"),
  practiceCopy: document.querySelector("#dashboard-practice-copy"),
  practiceMeta: document.querySelector("#dashboard-practice-meta"),
  publicLink: document.querySelector("#dashboard-public-link"),
  dashboardHighlight: document.querySelector("#dashboard-highlight"),
  stats: document.querySelector("#dashboard-stats"),
  creditSummary: document.querySelector("#credit-summary-grid"),
  recentCredits: document.querySelector("#recent-credits"),
  sessionList: document.querySelector("#session-list"),
  sessionSummary: document.querySelector("#session-list-summary"),
  filterForm: document.querySelector("#session-filter-form"),
  filterQuery: document.querySelector("#session-filter-query"),
  filterStatus: document.querySelector("#session-filter-status"),
};

const sessionCategoryOptions = ["Botox", "Fillers", "Skin", "Hair", "Body", "Other"];
const obscureModeOptions = ["none", "eyes", "upper", "full"];
const consentTierOptions = [
  { value: "full", label: "Full consent" },
  { value: "partial", label: "Partial consent" },
  { value: "full_blur", label: "Full blur consent" },
  { value: "decline", label: "Decline" },
];

function qs(selector, scope = document) {
  return scope.querySelector(selector);
}

function qsa(selector, scope = document) {
  return Array.from(scope.querySelectorAll(selector));
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDate(value) {
  if (!value) return "Not recorded yet";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Not recorded yet";

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(parsed);
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

function titleCase(value = "") {
  return String(value)
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function maybeString(value) {
  const trimmed = String(value ?? "").trim();
  return trimmed || undefined;
}

function maybeNumber(value) {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || "";
}

function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY) || "";
}

function storeTokens(payload) {
  if (payload?.access_token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  }
  if (payload?.refresh_token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
  }
}

function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

function setNotice(element, message, type = "info") {
  if (!element) return;
  if (!message) {
    element.hidden = true;
    element.className = "status-banner";
    element.textContent = "";
    return;
  }

  element.hidden = false;
  element.className = `status-banner status-banner--${type}`;
  element.textContent = message;
}

function setAuthMode(mode) {
  state.authMode = mode;
  localStorage.setItem(AUTH_MODE_KEY, mode);

  qsa("[data-auth-mode]").forEach((button) => {
    const active = button.dataset.authMode === mode;
    button.setAttribute("aria-selected", active ? "true" : "false");
  });

  if (elements.loginForm) {
    elements.loginForm.hidden = mode !== "login";
  }
  if (elements.signupForm) {
    elements.signupForm.hidden = mode !== "signup";
  }

  setNotice(elements.authStatus, "");
  if (elements.authCopy) {
    elements.authCopy.textContent =
      mode === "login"
        ? "Log in with your existing medspa credentials to manage cases and publish results."
        : "Create a practice owner account and start populating your Veriba presence immediately.";
  }
}

function showAuth() {
  if (elements.authShell) {
    elements.authShell.hidden = false;
  }
  if (elements.dashboard) {
    elements.dashboard.hidden = true;
  }
}

function showDashboard() {
  if (elements.authShell) {
    elements.authShell.hidden = true;
  }
  if (elements.dashboard) {
    elements.dashboard.hidden = false;
  }
}

function setButtonBusy(button, busy, busyLabel = "Saving...") {
  if (!button) return;
  if (busy) {
    button.dataset.originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = busyLabel;
    return;
  }

  button.disabled = false;
  if (button.dataset.originalLabel) {
    button.textContent = button.dataset.originalLabel;
  }
}

async function refreshAccessToken() {
  if (!getRefreshToken()) {
    throw new Error("Your session has ended. Please log in again.");
  }

  if (!state.refreshPromise) {
    state.refreshPromise = (async () => {
      try {
        const payload = await apiRequest("/api/auth/refresh", {
          method: "POST",
          auth: false,
          body: {
            refresh_token: getRefreshToken(),
          },
        });
        storeTokens(payload);
        return payload.access_token;
      } catch (error) {
        clearTokens();
        throw error;
      } finally {
        state.refreshPromise = null;
      }
    })();
  }

  return state.refreshPromise;
}

async function apiRequest(
  path,
  { method = "GET", body, formData, auth = true, retry = true, headers = {} } = {}
) {
  const finalHeaders = {
    Accept: "application/json",
    ...headers,
  };

  if (auth && getAccessToken()) {
    finalHeaders.Authorization = `Bearer ${getAccessToken()}`;
  }

  let requestBody = undefined;
  if (formData) {
    requestBody = formData;
  } else if (body !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }

  const response = await fetch(path, {
    method,
    headers: finalHeaders,
    body: requestBody,
  });

  if (response.status === 401 && auth && retry && getRefreshToken()) {
    await refreshAccessToken();
    return apiRequest(path, { method, body, formData, auth, retry: false, headers });
  }

  let payload = null;
  const isJson = response.headers.get("content-type")?.includes("application/json");
  if (isJson) {
    payload = await response.json();
  }

  if (!response.ok || !payload?.success) {
    const message = payload?.error?.message || `Request failed (${response.status})`;
    throw new Error(message);
  }

  return payload.data;
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

function progressChip(label, tone) {
  return `<span class="progress-chip progress-chip--${tone}">${escapeHtml(label)}</span>`;
}

function buildStatCard(value, label) {
  return `
    <article class="stat-card">
      <strong>${escapeHtml(value)}</strong>
      <span>${escapeHtml(label)}</span>
    </article>
  `;
}

function buildCreditTile(value, label) {
  return `
    <div class="credit-tile">
      <strong>${escapeHtml(value)}</strong>
      <span>${escapeHtml(label)}</span>
    </div>
  `;
}

function buildCreditRow(credit) {
  return `
    <div class="credit-list__item">
      <div>
        <strong>${escapeHtml(credit.patient_initials || "Patient")} • ${escapeHtml(
          formatCurrency(credit.amount)
        )}</strong>
        <span>${escapeHtml(titleCase(credit.status || "active"))} • Expires ${escapeHtml(
          formatDate(credit.expires_at)
        )}</span>
      </div>
      <span>${escapeHtml(credit.code || "")}</span>
    </div>
  `;
}

function buildSessionCard(session) {
  const published = session.status === "published";
  const publicHref =
    published && state.practice?.widget_slug
      ? `/case-study/?id=${encodeURIComponent(session.id)}`
      : "";

  const progress = [
    progressChip(
      session.before_image_url ? "Before uploaded" : "Before pending",
      session.before_image_url ? "good" : "pending"
    ),
    progressChip(
      session.after_image_url ? "After uploaded" : "After pending",
      session.after_image_url ? "good" : "pending"
    ),
    progressChip(
      session.consent_tier ? `Consent: ${titleCase(session.consent_tier)}` : "Consent pending",
      session.consent_tier ? "good" : "pending"
    ),
    progressChip(
      published ? "Published live" : titleCase(session.status || "draft"),
      published ? "good" : "muted"
    ),
  ].join("");

  return `
    <details class="admin-case" ${published ? "open" : ""}>
      <summary class="admin-case__summary">
        <div class="comparison admin-case__comparison">
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
        <div class="admin-case__summary-copy">
          <div class="meta-row">
            <span class="meta-pill">${escapeHtml(session.category || "Other")}</span>
            <span class="meta-pill">${escapeHtml(titleCase(session.status || "draft"))}</span>
            <span class="meta-pill">Updated ${escapeHtml(formatDate(session.updated_at))}</span>
          </div>
          <h3>${escapeHtml(session.treatment)}</h3>
          <p>
            Patient ${escapeHtml(session.patient_initials)}${
              session.published_at ? ` • Published ${escapeHtml(formatDate(session.published_at))}` : ""
            }
          </p>
          <div class="admin-case__progress">${progress}</div>
        </div>
      </summary>

      <div class="admin-case__body">
        <form class="admin-form session-edit-form" data-session-id="${escapeHtml(session.id)}">
          <div class="admin-form__head">
            <div>
              <h4>Case details</h4>
              <p>Keep treatment, patient initials, and obscuring preferences up to date.</p>
            </div>
          </div>
          <div class="form-grid">
            <label class="field field--stacked">
              <span class="field__label">Patient initials</span>
              <input type="text" name="patient_initials" maxlength="10" value="${escapeHtml(
                session.patient_initials
              )}" required />
            </label>
            <label class="field field--stacked">
              <span class="field__label">Treatment</span>
              <input type="text" name="treatment" value="${escapeHtml(session.treatment)}" required />
            </label>
          </div>
          <div class="form-grid">
            <label class="field field--stacked">
              <span class="field__label">Category</span>
              <select name="category">
                ${sessionCategoryOptions
                  .map(
                    (value) =>
                      `<option value="${escapeHtml(value)}" ${
                        value === session.category ? "selected" : ""
                      }>${escapeHtml(value)}</option>`
                  )
                  .join("")}
              </select>
            </label>
            <label class="field field--stacked">
              <span class="field__label">Obscure mode</span>
              <select name="obscure_mode">
                ${obscureModeOptions
                  .map(
                    (value) =>
                      `<option value="${escapeHtml(value)}" ${
                        value === (session.obscure_mode || "none") ? "selected" : ""
                      }>${escapeHtml(titleCase(value))}</option>`
                  )
                  .join("")}
              </select>
            </label>
          </div>
          <button class="button-secondary" type="submit">Save case details</button>
        </form>

        <div class="session-upload-grid">
          <form
            class="admin-form session-upload-form"
            data-session-id="${escapeHtml(session.id)}"
            data-image-kind="before"
          >
            <div class="admin-form__head">
              <div>
                <h4>Before image</h4>
                <p>Upload the capture that starts the transformation timeline.</p>
              </div>
            </div>
            <label class="field field--stacked">
              <span class="field__label">Image file</span>
              <input type="file" name="file" accept="image/*" required />
            </label>
            <button class="button-primary" type="submit">Upload before image</button>
          </form>

          <form
            class="admin-form session-upload-form"
            data-session-id="${escapeHtml(session.id)}"
            data-image-kind="after"
          >
            <div class="admin-form__head">
              <div>
                <h4>After image</h4>
                <p>Upload the post-treatment result when the patient is ready.</p>
              </div>
            </div>
            <label class="field field--stacked">
              <span class="field__label">Image file</span>
              <input type="file" name="file" accept="image/*" required />
            </label>
            <button class="button-primary" type="submit">Upload after image</button>
          </form>
        </div>

        <form class="admin-form session-consent-form" data-session-id="${escapeHtml(session.id)}">
          <div class="admin-form__head">
            <div>
              <h4>Consent and reward</h4>
              <p>Choose a consent tier and optional obscuring mode before publishing.</p>
            </div>
          </div>
          <div class="form-grid">
            <label class="field field--stacked">
              <span class="field__label">Consent tier</span>
              <select name="consent_tier">
                ${consentTierOptions
                  .map(
                    (option) =>
                      `<option value="${escapeHtml(option.value)}" ${
                        option.value === (session.consent_tier || "full") ? "selected" : ""
                      }>${escapeHtml(option.label)}</option>`
                  )
                  .join("")}
              </select>
            </label>
            <label class="field field--stacked">
              <span class="field__label">Obscure mode</span>
              <select name="obscure_mode">
                ${obscureModeOptions
                  .map(
                    (value) =>
                      `<option value="${escapeHtml(value)}" ${
                        value === (session.obscure_mode || "none") ? "selected" : ""
                      }>${escapeHtml(titleCase(value))}</option>`
                  )
                  .join("")}
              </select>
            </label>
          </div>
          <div class="form-grid">
            <label class="field field--stacked">
              <span class="field__label">Discount applied</span>
              <input type="number" name="discount_applied" min="0" placeholder="Use practice default" />
            </label>
            <label class="field field--stacked">
              <span class="field__label">Signature SVG</span>
              <input type="text" name="signature_svg" placeholder="Optional signature path data" />
            </label>
          </div>
          <button class="button-secondary" type="submit">Record consent</button>
        </form>

        <form class="admin-form session-publish-form" data-session-id="${escapeHtml(session.id)}">
          <div class="admin-form__head">
            <div>
              <h4>Publish to Veriba</h4>
              <p>Once a case is ready, send it to the public gallery and widget destinations.</p>
            </div>
          </div>
          <label class="field field--stacked">
            <span class="field__label">Treatment details</span>
            <textarea
              name="treatment_details"
              placeholder="Optional narrative for the public case study and SEO layer"
            ></textarea>
          </label>
          <div class="button-row">
            <button class="button-primary" type="submit">Publish case</button>
            ${
              publicHref
                ? `<a class="button-secondary" href="${publicHref}" target="_blank" rel="noreferrer">View public case</a>`
                : ""
            }
            ${
              published
                ? `<button class="button-secondary" type="button" data-action="unpublish" data-session-id="${escapeHtml(
                    session.id
                  )}">Unpublish</button>`
                : ""
            }
            <button
              class="button-ghost"
              type="button"
              data-action="archive"
              data-session-id="${escapeHtml(session.id)}"
            >
              Archive case
            </button>
          </div>
        </form>
      </div>
    </details>
  `;
}

function filteredSessions() {
  const query = state.filters.query.trim().toLowerCase();
  const status = state.filters.status.trim().toLowerCase();

  return state.sessions.filter((session) => {
    const matchesQuery =
      !query ||
      [session.patient_initials, session.treatment, session.category, session.status]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query));
    const matchesStatus = !status || String(session.status || "").toLowerCase() === status;
    return matchesQuery && matchesStatus;
  });
}

function renderOverview() {
  const practice = state.practice;
  const user = state.user;
  if (!practice || !user) return;

  if (elements.practiceName) {
    elements.practiceName.textContent = practice.name;
  }
  if (elements.practiceCopy) {
    elements.practiceCopy.textContent = `${practice.location} • Managed by ${user.name}. This studio writes directly to the live Veriba API and powers the public gallery when cases are published.`;
  }
  if (elements.practiceMeta) {
    elements.practiceMeta.innerHTML = `
      <span class="meta-pill">${escapeHtml(practice.location || "Location pending")}</span>
      <span class="meta-pill">${escapeHtml(user.email)}</span>
      <span class="meta-pill">${escapeHtml(practice.auto_publish ? "Auto-publish enabled" : "Manual publishing")}</span>
      <span class="meta-pill">${escapeHtml(`Slug: ${practice.widget_slug}`)}</span>
    `;
  }
  if (elements.publicLink) {
    elements.publicLink.href = `/provider/?slug=${encodeURIComponent(practice.widget_slug)}`;
  }

  if (elements.dashboardHighlight) {
    elements.dashboardHighlight.innerHTML = `
      <div class="dashboard-highlight__panel">
        <span class="eyebrow">Connection status</span>
        <h3>Website and database are connected</h3>
        <p>
          The public gallery is already wired to the backend. If you are not seeing imagery yet,
          that usually means this practice has not published any completed cases yet.
        </p>
      </div>
      <div class="dashboard-highlight__panel">
        <span class="eyebrow">Next best action</span>
        <h3>Populate your first live case</h3>
        <div class="metric-stack">
          <div class="metric-stack__line">
            <strong>1. Create a case</strong>
            <span>Patient initials, treatment, and category</span>
          </div>
          <div class="metric-stack__line">
            <strong>2. Upload before and after</strong>
            <span>Images are stored through the live Veriba media pipeline</span>
          </div>
          <div class="metric-stack__line">
            <strong>3. Record consent and publish</strong>
            <span>The case can then surface on the public gallery and widget endpoints</span>
          </div>
        </div>
      </div>
    `;
  }
}

function renderStats() {
  const stats = state.practiceStats;
  const creditStats = state.creditsStats;

  if (!elements.stats) {
    return;
  }

  if (!stats || !creditStats) {
    elements.stats.innerHTML = buildStatCard("...", "Loading stats");
    return;
  }

  elements.stats.innerHTML = [
    buildStatCard(String(stats.total_published || 0), "Published transformations"),
    buildStatCard(String(stats.total_pending || 0), "Cases waiting on next step"),
    buildStatCard(String(stats.profile_views_total || 0), "Total profile views"),
    buildStatCard(formatCurrency(creditStats.active_value || 0), "Active credit value"),
    buildStatCard(
      `${Math.round((creditStats.redemption_rate || 0) * 100)}%`,
      "Credit redemption rate"
    ),
    buildStatCard(String(creditStats.credits_expiring_30d || 0), "Credits expiring in 30 days"),
  ].join("");
}

function renderPracticeForms() {
  const practice = state.practice;
  const user = state.user;
  if (!practice || !user) return;

  if (elements.practiceForm) {
    elements.practiceForm.elements.name.value = practice.name || "";
    elements.practiceForm.elements.location.value = practice.location || "";
    elements.practiceForm.elements.website.value = practice.website || "";
    elements.practiceForm.elements.discount_full.value = practice.default_discounts?.full ?? "";
    elements.practiceForm.elements.discount_partial.value =
      practice.default_discounts?.partial ?? "";
    elements.practiceForm.elements.discount_full_blur.value =
      practice.default_discounts?.full_blur ?? "";
    elements.practiceForm.elements.credit_expiration_days.value =
      practice.credit_expiration_days ?? "";
    elements.practiceForm.elements.auto_publish.checked = Boolean(practice.auto_publish);
  }

  if (elements.accountForm) {
    elements.accountForm.elements.name.value = user.name || "";
    elements.accountForm.elements.email.value = user.email || "";
  }
}

function renderCredits() {
  const creditStats = state.creditsStats;

  if (!elements.creditSummary || !elements.recentCredits) {
    return;
  }

  if (!creditStats) {
    elements.creditSummary.innerHTML = buildCreditTile("...", "Loading credits");
    elements.recentCredits.innerHTML = "";
    return;
  }

  elements.creditSummary.innerHTML = [
    buildCreditTile(String(creditStats.total_issued || 0), "Credits issued"),
    buildCreditTile(formatCurrency(creditStats.active_value || 0), "Active value"),
    buildCreditTile(formatCurrency(creditStats.redeemed_value || 0), "Redeemed value"),
    buildCreditTile(String(creditStats.total_active || 0), "Active credits"),
  ].join("");

  if (!state.credits.length) {
    elements.recentCredits.innerHTML = `
      <div class="credit-list__item">
        <div>
          <strong>No credits yet</strong>
          <span>Credits will show up here once patients begin completing the consent and follow-up flow.</span>
        </div>
      </div>
    `;
    return;
  }

  elements.recentCredits.innerHTML = state.credits.map(buildCreditRow).join("");
}

function renderSessions() {
  if (!elements.sessionSummary || !elements.sessionList) {
    return;
  }

  const sessions = filteredSessions();
  const total = state.sessions.length;

  elements.sessionSummary.textContent = `${sessions.length} of ${total} cases shown. Published cases become visible on the public site once they are live.`;

  if (!total) {
    elements.sessionList.innerHTML = `
      <div class="empty-state">
        <h3 class="headline-md">No cases yet for this medspa</h3>
        <p class="muted">
          The site is connected to the live backend. Create your first case above, then upload
          imagery, record consent, and publish it to start populating the public gallery.
        </p>
      </div>
    `;
    return;
  }

  if (!sessions.length) {
    elements.sessionList.innerHTML = `
      <div class="empty-state">
        <h3 class="headline-md">No cases match these filters</h3>
        <p class="muted">Try a broader treatment search or clear the status filter.</p>
      </div>
    `;
    return;
  }

  elements.sessionList.innerHTML = sessions.map(buildSessionCard).join("");
}

function renderDashboard() {
  renderOverview();
  renderStats();
  renderPracticeForms();
  renderCredits();
  renderSessions();
}

async function loadDashboard({ notice, noticeType = "success" } = {}) {
  showDashboard();
  setNotice(elements.dashboardStatus, "");
  if (elements.practiceName) {
    elements.practiceName.textContent = "Loading your studio...";
  }
  if (elements.practiceCopy) {
    elements.practiceCopy.textContent = "Refreshing your practice, sessions, and credit metrics.";
  }

  try {
    const [user, practice, practiceStats, sessionsPayload, creditsStats, creditsPayload] =
      await Promise.all([
        apiRequest("/api/users/me"),
        apiRequest("/api/practices/me"),
        apiRequest("/api/practices/me/stats"),
        apiRequest("/api/sessions?limit=100"),
        apiRequest("/api/credits/stats"),
        apiRequest("/api/credits?limit=6"),
      ]);

    state.user = user;
    state.practice = practice;
    state.practiceStats = practiceStats;
    state.creditsStats = creditsStats;
    state.sessions = sessionsPayload.sessions || [];
    state.credits = creditsPayload.credits || [];

    renderDashboard();

    if (notice) {
      setNotice(elements.dashboardStatus, notice, noticeType);
    }
  } catch (error) {
    const authMissing = !getAccessToken() && !getRefreshToken();
    if (authMissing) {
      state.user = null;
      state.practice = null;
      state.practiceStats = null;
      state.creditsStats = null;
      state.credits = [];
      state.sessions = [];
      showAuth();
      setAuthMode("login");
      setNotice(elements.authStatus, error.message, "error");
      return;
    }

    setNotice(elements.dashboardStatus, error.message, "error");
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const submitter = event.submitter;
  setButtonBusy(submitter, true, "Logging in...");
  setNotice(elements.authStatus, "");

  try {
    const data = new FormData(event.currentTarget);
    const payload = await apiRequest("/api/auth/login", {
      method: "POST",
      auth: false,
      body: {
        email: String(data.get("email") || "").trim(),
        password: String(data.get("password") || ""),
      },
    });
    storeTokens(payload);
    await loadDashboard({
      notice: `Welcome back, ${payload.user?.name || "team"}.`,
    });
    event.currentTarget.reset();
  } catch (error) {
    setNotice(elements.authStatus, error.message, "error");
  } finally {
    setButtonBusy(submitter, false);
  }
}

async function handleSignup(event) {
  event.preventDefault();
  const submitter = event.submitter;
  setButtonBusy(submitter, true, "Creating account...");
  setNotice(elements.authStatus, "");

  try {
    const data = new FormData(event.currentTarget);
    const payload = await apiRequest("/api/auth/register", {
      method: "POST",
      auth: false,
      body: {
        name: String(data.get("name") || "").trim(),
        email: String(data.get("email") || "").trim(),
        password: String(data.get("password") || ""),
        practice_name: String(data.get("practice_name") || "").trim(),
        practice_location: String(data.get("practice_location") || "").trim(),
        practice_website: maybeString(data.get("practice_website")),
      },
    });
    storeTokens(payload);
    await loadDashboard({
      notice: "Your medspa account is live. Create a case to start populating the gallery.",
    });
    event.currentTarget.reset();
  } catch (error) {
    setNotice(elements.authStatus, error.message, "error");
  } finally {
    setButtonBusy(submitter, false);
  }
}

async function handleLogout() {
  setNotice(elements.dashboardStatus, "");
  try {
    await apiRequest("/api/auth/logout", { method: "POST" });
  } catch (_) {
    // Ignore logout failures and clear local auth regardless.
  } finally {
    clearTokens();
    state.user = null;
    state.practice = null;
    state.practiceStats = null;
    state.creditsStats = null;
    state.credits = [];
    state.sessions = [];
    showAuth();
    setAuthMode("login");
    setNotice(elements.authStatus, "You have been logged out.", "info");
  }
}

async function handleCreateSession(event) {
  event.preventDefault();
  const submitter = event.submitter;
  setButtonBusy(submitter, true, "Creating...");
  setNotice(elements.dashboardStatus, "");

  try {
    const data = new FormData(event.currentTarget);
    await apiRequest("/api/sessions", {
      method: "POST",
      body: {
        patient_initials: String(data.get("patient_initials") || "").trim(),
        treatment: String(data.get("treatment") || "").trim(),
        category: String(data.get("category") || "Other"),
        status: String(data.get("status") || "draft"),
      },
    });
    event.currentTarget.reset();
    event.currentTarget.elements.category.value = "Other";
    event.currentTarget.elements.status.value = "draft";
    await loadDashboard({
      notice: "Case created. Upload imagery and record consent when ready.",
    });
  } catch (error) {
    setNotice(elements.dashboardStatus, error.message, "error");
  } finally {
    setButtonBusy(submitter, false);
  }
}

async function handlePracticeUpdate(event) {
  event.preventDefault();
  const submitter = event.submitter;
  setButtonBusy(submitter, true);
  setNotice(elements.dashboardStatus, "");

  try {
    const data = new FormData(event.currentTarget);
    const defaultDiscounts = {
      full: maybeNumber(data.get("discount_full")),
      partial: maybeNumber(data.get("discount_partial")),
      full_blur: maybeNumber(data.get("discount_full_blur")),
    };

    const payload = {
      name: maybeString(data.get("name")),
      location: maybeString(data.get("location")),
      website: maybeString(data.get("website")),
      credit_expiration_days: maybeNumber(data.get("credit_expiration_days")),
      auto_publish: Boolean(event.currentTarget.elements.auto_publish.checked),
      default_discounts:
        Object.values(defaultDiscounts).some((value) => value !== undefined) ? defaultDiscounts : undefined,
    };

    await apiRequest("/api/practices/me", {
      method: "PATCH",
      body: payload,
    });
    await loadDashboard({
      notice: "Practice settings updated.",
    });
  } catch (error) {
    setNotice(elements.dashboardStatus, error.message, "error");
  } finally {
    setButtonBusy(submitter, false);
  }
}

async function handleAccountUpdate(event) {
  event.preventDefault();
  const submitter = event.submitter;
  setButtonBusy(submitter, true);
  setNotice(elements.dashboardStatus, "");

  try {
    const data = new FormData(event.currentTarget);
    await apiRequest("/api/users/me", {
      method: "PATCH",
      body: {
        name: maybeString(data.get("name")),
        email: maybeString(data.get("email")),
      },
    });
    await loadDashboard({
      notice: "Profile updated.",
    });
  } catch (error) {
    setNotice(elements.dashboardStatus, error.message, "error");
  } finally {
    setButtonBusy(submitter, false);
  }
}

async function handlePasswordUpdate(event) {
  event.preventDefault();
  const submitter = event.submitter;
  setButtonBusy(submitter, true, "Updating...");
  setNotice(elements.dashboardStatus, "");

  try {
    const data = new FormData(event.currentTarget);
    await apiRequest("/api/users/me/password", {
      method: "PATCH",
      body: {
        current_password: String(data.get("current_password") || ""),
        new_password: String(data.get("new_password") || ""),
      },
    });
    event.currentTarget.reset();
    setNotice(elements.dashboardStatus, "Password updated.", "success");
  } catch (error) {
    setNotice(elements.dashboardStatus, error.message, "error");
  } finally {
    setButtonBusy(submitter, false);
  }
}

async function handleSessionSubmit(event) {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;

  const submitter = event.submitter;
  const sessionId = form.dataset.sessionId;
  if (!sessionId) return;

  if (!form.matches(".session-edit-form, .session-upload-form, .session-consent-form, .session-publish-form")) {
    return;
  }

  event.preventDefault();
  setButtonBusy(submitter, true);
  setNotice(elements.dashboardStatus, "");

  try {
    if (form.matches(".session-edit-form")) {
      const data = new FormData(form);
      await apiRequest(`/api/sessions/${encodeURIComponent(sessionId)}`, {
        method: "PATCH",
        body: {
          patient_initials: String(data.get("patient_initials") || "").trim(),
          treatment: String(data.get("treatment") || "").trim(),
          category: String(data.get("category") || "Other"),
          obscure_mode: String(data.get("obscure_mode") || "none"),
        },
      });
      await loadDashboard({ notice: "Case details updated." });
      return;
    }

    if (form.matches(".session-upload-form")) {
      const imageKind = form.dataset.imageKind;
      const data = new FormData(form);
      const file = data.get("file");
      if (!(file instanceof File) || !file.size) {
        throw new Error("Choose an image file before uploading.");
      }
      const payload = new FormData();
      payload.append("file", file);

      await apiRequest(`/api/sessions/${encodeURIComponent(sessionId)}/images/${imageKind}`, {
        method: "POST",
        formData: payload,
      });
      await loadDashboard({
        notice: `${titleCase(imageKind)} image uploaded.`,
      });
      return;
    }

    if (form.matches(".session-consent-form")) {
      const data = new FormData(form);
      await apiRequest(`/api/sessions/${encodeURIComponent(sessionId)}/consent`, {
        method: "POST",
        body: {
          consent_tier: String(data.get("consent_tier") || "full"),
          obscure_mode: String(data.get("obscure_mode") || "none"),
          discount_applied: maybeNumber(data.get("discount_applied")),
          signature_svg: maybeString(data.get("signature_svg")),
        },
      });
      await loadDashboard({
        notice: "Consent recorded.",
      });
      return;
    }

    if (form.matches(".session-publish-form")) {
      const data = new FormData(form);
      await apiRequest(`/api/sessions/${encodeURIComponent(sessionId)}/publish`, {
        method: "POST",
        body: {
          destinations: ["widget", "gallery"],
          treatment_details: maybeString(data.get("treatment_details")),
        },
      });
      await loadDashboard({
        notice: "Case published to Veriba.",
      });
    }
  } catch (error) {
    setNotice(elements.dashboardStatus, error.message, "error");
  } finally {
    setButtonBusy(submitter, false);
  }
}

async function handleSessionAction(event) {
  const button = event.target.closest("[data-action]");
  if (!(button instanceof HTMLButtonElement)) return;

  const action = button.dataset.action;
  const sessionId = button.dataset.sessionId;
  if (!action || !sessionId) return;

  event.preventDefault();
  setButtonBusy(button, true, action === "archive" ? "Archiving..." : "Working...");
  setNotice(elements.dashboardStatus, "");

  try {
    if (action === "unpublish") {
      await apiRequest(`/api/sessions/${encodeURIComponent(sessionId)}/unpublish`, {
        method: "POST",
      });
      await loadDashboard({
        notice: "Case unpublished.",
      });
    }

    if (action === "archive") {
      const confirmed = window.confirm(
        "Archive this case? It will be removed from the active medspa workflow."
      );
      if (!confirmed) return;

      await apiRequest(`/api/sessions/${encodeURIComponent(sessionId)}`, {
        method: "DELETE",
      });
      await loadDashboard({
        notice: "Case archived.",
      });
    }
  } catch (error) {
    setNotice(elements.dashboardStatus, error.message, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

function handleFilterChange(event) {
  if (event) {
    event.preventDefault();
  }

  state.filters.query = elements.filterQuery?.value || "";
  state.filters.status = elements.filterStatus?.value || "";
  renderSessions();
}

function bindEvents() {
  qsa("[data-auth-mode]").forEach((button) => {
    button.addEventListener("click", () => setAuthMode(button.dataset.authMode));
  });

  if (elements.loginForm) {
    elements.loginForm.addEventListener("submit", handleLogin);
  }
  if (elements.signupForm) {
    elements.signupForm.addEventListener("submit", handleSignup);
  }
  if (elements.createSessionForm) {
    elements.createSessionForm.addEventListener("submit", handleCreateSession);
  }
  if (elements.practiceForm) {
    elements.practiceForm.addEventListener("submit", handlePracticeUpdate);
  }
  if (elements.accountForm) {
    elements.accountForm.addEventListener("submit", handleAccountUpdate);
  }
  if (elements.passwordForm) {
    elements.passwordForm.addEventListener("submit", handlePasswordUpdate);
  }
  if (elements.refreshButton) {
    elements.refreshButton.addEventListener("click", () =>
      loadDashboard({ notice: "Studio refreshed.", noticeType: "info" })
    );
  }
  if (elements.logoutButton) {
    elements.logoutButton.addEventListener("click", handleLogout);
  }
  if (elements.filterForm) {
    elements.filterForm.addEventListener("submit", handleFilterChange);
  }
  if (elements.filterQuery) {
    elements.filterQuery.addEventListener("input", handleFilterChange);
  }
  if (elements.filterStatus) {
    elements.filterStatus.addEventListener("change", handleFilterChange);
  }
  if (elements.sessionList) {
    elements.sessionList.addEventListener("submit", handleSessionSubmit);
    elements.sessionList.addEventListener("click", handleSessionAction);
  }
}

async function init() {
  bindEvents();
  setAuthMode(state.authMode);

  if (getAccessToken() || getRefreshToken()) {
    await loadDashboard();
  } else {
    showAuth();
  }
}

init();

const ACCESS_TOKEN_KEY = "veriba.internal.access_token";
const REFRESH_TOKEN_KEY = "veriba.internal.refresh_token";

const state = {
  user: null,
  overview: null,
  practices: [],
  practiceDetails: new Map(),
  query: "",
  refreshPromise: null,
};

const elements = {
  authShell: document.querySelector("#internal-auth-shell"),
  authStatus: document.querySelector("#internal-auth-status"),
  loginForm: document.querySelector("#internal-login-form"),
  dashboard: document.querySelector("#internal-dashboard"),
  dashboardStatus: document.querySelector("#internal-dashboard-status"),
  title: document.querySelector("#internal-dashboard-title"),
  copy: document.querySelector("#internal-dashboard-copy"),
  meta: document.querySelector("#internal-dashboard-meta"),
  highlight: document.querySelector("#internal-highlight"),
  stats: document.querySelector("#internal-stats"),
  refreshButton: document.querySelector("#internal-refresh"),
  logoutButton: document.querySelector("#internal-logout"),
  createPracticeForm: document.querySelector("#internal-create-practice-form"),
  searchForm: document.querySelector("#internal-search-form"),
  searchQuery: document.querySelector("#internal-search-query"),
  practiceSummary: document.querySelector("#internal-practice-summary"),
  practiceList: document.querySelector("#internal-practice-list"),
};

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

function showAuth() {
  elements.authShell.hidden = false;
  elements.dashboard.hidden = true;
}

function showDashboard() {
  elements.authShell.hidden = true;
  elements.dashboard.hidden = false;
}

function setButtonBusy(button, busy, busyLabel = "Working...") {
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
          body: { refresh_token: getRefreshToken() },
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
  { method = "GET", body, auth = true, retry = true, headers = {} } = {}
) {
  const finalHeaders = {
    Accept: "application/json",
    ...headers,
  };

  if (auth && getAccessToken()) {
    finalHeaders.Authorization = `Bearer ${getAccessToken()}`;
  }

  let requestBody;
  if (body !== undefined) {
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
    return apiRequest(path, { method, body, auth, retry: false, headers });
  }

  const payload = await response.json();
  if (!response.ok || !payload?.success) {
    throw new Error(payload?.error?.message || `Request failed (${response.status})`);
  }
  return payload.data;
}

function buildStatCard(value, label) {
  return `
    <article class="stat-card">
      <strong>${escapeHtml(value)}</strong>
      <span>${escapeHtml(label)}</span>
    </article>
  `;
}

function buildPracticeSummary(practice) {
  return `
    <details class="internal-practice" data-practice-id="${escapeHtml(practice.id)}">
      <summary class="internal-practice__summary">
        <div>
          <div class="meta-row">
            <span class="meta-pill">${escapeHtml(practice.location || "Location pending")}</span>
            <span class="meta-pill">${escapeHtml(`Slug: ${practice.widget_slug}`)}</span>
            <span class="meta-pill">${escapeHtml(practice.auto_publish ? "Auto-publish" : "Manual publish")}</span>
          </div>
          <h3>${escapeHtml(practice.name)}</h3>
          <p>
            ${escapeHtml(practice.owner?.name || "No owner assigned")}
            ${practice.owner?.email ? ` • ${escapeHtml(practice.owner.email)}` : ""}
          </p>
          <div class="internal-link-row">
            <a class="button-secondary" href="/provider/?slug=${encodeURIComponent(
              practice.widget_slug
            )}" target="_blank" rel="noreferrer">Public profile</a>
          </div>
        </div>
        <div class="internal-glance-grid">
          <div class="internal-glance-card">
            <strong>${escapeHtml(String(practice.stats?.published_sessions || 0))}</strong>
            <span>Published sessions</span>
          </div>
          <div class="internal-glance-card">
            <strong>${escapeHtml(String(practice.stats?.pending_sessions || 0))}</strong>
            <span>Pending sessions</span>
          </div>
          <div class="internal-glance-card">
            <strong>${escapeHtml(String(practice.stats?.team_count || 0))}</strong>
            <span>Practice users</span>
          </div>
          <div class="internal-glance-card">
            <strong>${escapeHtml(formatCurrency(practice.stats?.active_credit_value || 0))}</strong>
            <span>Active credit value</span>
          </div>
        </div>
      </summary>
      <div class="internal-practice__body" id="internal-practice-body-${escapeHtml(practice.id)}">
        <p class="loading">Open to load medspa detail...</p>
      </div>
    </details>
  `;
}

function buildSessionRow(session, practice) {
  return `
    <div class="internal-list__item">
      <div>
        <strong>${escapeHtml(session.treatment)}</strong>
        <span>${escapeHtml(titleCase(session.status || "draft"))} • ${escapeHtml(
          formatDate(session.updated_at)
        )}</span>
      </div>
      ${
        practice.widget_slug
          ? `<a class="button-secondary" href="/provider/?slug=${encodeURIComponent(
              practice.widget_slug
            )}" target="_blank" rel="noreferrer">Profile</a>`
          : ""
      }
    </div>
  `;
}

function buildCreditRow(credit) {
  return `
    <div class="internal-list__item">
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

function renderPracticeDetail(practiceId) {
  const detail = state.practiceDetails.get(practiceId);
  const container = document.querySelector(`#internal-practice-body-${CSS.escape(practiceId)}`);
  if (!container || !detail) return;

  const practice = detail.practice;
  const owner = detail.owner || {};
  const sessions = detail.recent_sessions || [];
  const credits = detail.recent_credits || [];

  container.innerHTML = `
    <div class="internal-grid">
      <form class="admin-form internal-practice-form" data-practice-id="${escapeHtml(practice.id)}">
        <div class="admin-form__head">
          <div>
            <h4>Practice settings</h4>
            <p>Update medspa profile data and reward defaults on behalf of the partner.</p>
          </div>
        </div>
        <div class="form-grid">
          <label class="field field--stacked">
            <span class="field__label">Practice name</span>
            <input type="text" name="name" value="${escapeHtml(practice.name)}" required />
          </label>
          <label class="field field--stacked">
            <span class="field__label">Location</span>
            <input type="text" name="location" value="${escapeHtml(practice.location)}" required />
          </label>
        </div>
        <label class="field field--stacked">
          <span class="field__label">Website</span>
          <input type="text" name="website" value="${escapeHtml(practice.website || "")}" />
        </label>
        <div class="form-grid">
          <label class="field field--stacked">
            <span class="field__label">Full consent credit</span>
            <input type="number" name="discount_full" min="0" value="${escapeHtml(
              String(practice.default_discounts?.full ?? "")
            )}" />
          </label>
          <label class="field field--stacked">
            <span class="field__label">Partial consent credit</span>
            <input type="number" name="discount_partial" min="0" value="${escapeHtml(
              String(practice.default_discounts?.partial ?? "")
            )}" />
          </label>
        </div>
        <div class="form-grid">
          <label class="field field--stacked">
            <span class="field__label">Full blur credit</span>
            <input type="number" name="discount_full_blur" min="0" value="${escapeHtml(
              String(practice.default_discounts?.full_blur ?? "")
            )}" />
          </label>
          <label class="field field--stacked">
            <span class="field__label">Credit expiration days</span>
            <input type="number" name="credit_expiration_days" min="30" max="365" value="${escapeHtml(
              String(practice.credit_expiration_days ?? "")
            )}" />
          </label>
        </div>
        <label class="checkbox-row">
          <input type="checkbox" name="auto_publish" ${practice.auto_publish ? "checked" : ""} />
          <span>Auto-publish approved cases</span>
        </label>
        <button class="button-primary" type="submit">Save practice settings</button>
      </form>

      <form class="admin-form internal-owner-form" data-practice-id="${escapeHtml(practice.id)}">
        <div class="admin-form__head">
          <div>
            <h4>Owner contact</h4>
            <p>Update the primary medspa owner without logging into the partner account.</p>
          </div>
        </div>
        <div class="form-grid">
          <label class="field field--stacked">
            <span class="field__label">Owner name</span>
            <input type="text" name="name" value="${escapeHtml(owner.name || "")}" />
          </label>
          <label class="field field--stacked">
            <span class="field__label">Owner email</span>
            <input type="email" name="email" value="${escapeHtml(owner.email || "")}" />
          </label>
        </div>
        <div class="metric-stack">
          <div class="metric-stack__line">
            <strong>Created</strong>
            <span>${escapeHtml(formatDate(owner.created_at))}</span>
          </div>
          <div class="metric-stack__line">
            <strong>Practice users</strong>
            <span>${escapeHtml(String(detail.users?.length || 0))}</span>
          </div>
          <div class="metric-stack__line">
            <strong>Published sessions</strong>
            <span>${escapeHtml(String(detail.stats?.published_sessions || 0))}</span>
          </div>
        </div>
        <button class="button-secondary" type="submit">Save owner contact</button>
      </form>
    </div>

    <div class="internal-grid">
      <div class="internal-list-card">
        <div class="admin-form__head">
          <div>
            <h4>Recent sessions</h4>
            <p>Latest case activity across the medspa workflow.</p>
          </div>
        </div>
        <div class="internal-list">
          ${
            sessions.length
              ? sessions.map((session) => buildSessionRow(session, practice)).join("")
              : '<p class="inline-note">No sessions have been created for this medspa yet.</p>'
          }
        </div>
      </div>

      <div class="internal-list-card">
        <div class="admin-form__head">
          <div>
            <h4>Recent credits</h4>
            <p>Reward activity for this medspa.</p>
          </div>
        </div>
        <div class="internal-list">
          ${
            credits.length
              ? credits.map(buildCreditRow).join("")
              : '<p class="inline-note">No credits have been issued for this medspa yet.</p>'
          }
        </div>
      </div>
    </div>
  `;
}

function renderOverview() {
  const overview = state.overview;
  const user = state.user;
  if (!overview || !user) return;

  elements.title.textContent = "Veriba partner portfolio";
  elements.copy.textContent = `Signed in as ${user.name}. This internal portal can onboard medspas and inspect partner activity across the full Veriba network.`;
  elements.meta.innerHTML = `
    <span class="meta-pill">${escapeHtml(user.email)}</span>
    <span class="meta-pill">${escapeHtml(titleCase(user.role))}</span>
    <span class="meta-pill">${escapeHtml(`${overview.practice_count} medspas onboarded`)}</span>
  `;
  elements.highlight.innerHTML = `
    <div class="dashboard-highlight__panel">
      <span class="eyebrow">Portal scope</span>
      <h3>Cross-practice administration</h3>
      <p>
        Internal admins can create new medspa accounts, update practice settings, and review
        portfolio-wide activity without using the public or medspa portals.
      </p>
    </div>
    <div class="dashboard-highlight__panel">
      <span class="eyebrow">Hidden route</span>
      <h3>No public navigation exposure</h3>
      <p>
        This page is intentionally reachable only by direct URL and internal credentials.
      </p>
    </div>
  `;
  elements.stats.innerHTML = [
    buildStatCard(String(overview.practice_count || 0), "Medspas onboarded"),
    buildStatCard(String(overview.medspa_user_count || 0), "Partner users"),
    buildStatCard(String(overview.published_session_count || 0), "Published sessions"),
    buildStatCard(String(overview.pending_session_count || 0), "Pending sessions"),
    buildStatCard(formatCurrency(overview.active_credit_value || 0), "Active credit value"),
    buildStatCard(formatCurrency(overview.redeemed_credit_value || 0), "Redeemed credit value"),
  ].join("");
}

function renderPracticeDirectory() {
  const practices = state.practices || [];
  elements.practiceSummary.textContent = `${practices.length} medspas visible in the internal directory.`;
  if (!practices.length) {
    elements.practiceList.innerHTML = `
      <div class="empty-state">
        <h3 class="headline-md">No medspas match that search</h3>
        <p class="muted">Try a broader practice, slug, or city query.</p>
      </div>
    `;
    return;
  }
  elements.practiceList.innerHTML = practices.map(buildPracticeSummary).join("");
}

async function loadPracticeDetail(practiceId, { force = false } = {}) {
  if (!force && state.practiceDetails.has(practiceId)) {
    renderPracticeDetail(practiceId);
    return;
  }
  const detail = await apiRequest(`/api/internal/practices/${encodeURIComponent(practiceId)}`);
  state.practiceDetails.set(practiceId, detail);
  renderPracticeDetail(practiceId);
}

async function loadDashboard({ notice, noticeType = "success" } = {}) {
  showDashboard();
  setNotice(elements.dashboardStatus, "");

  try {
    const [user, overview, practicesPayload] = await Promise.all([
      apiRequest("/api/users/me"),
      apiRequest("/api/internal/overview"),
      apiRequest(`/api/internal/practices?limit=50${state.query ? `&query=${encodeURIComponent(state.query)}` : ""}`),
    ]);

    if (user.role !== "internal_admin") {
      clearTokens();
      state.user = null;
      showAuth();
      setNotice(elements.authStatus, "This account is not authorized for the internal portal.", "error");
      return;
    }

    state.user = user;
    state.overview = overview;
    state.practices = practicesPayload.practices || [];
    state.practiceDetails.clear();

    renderOverview();
    renderPracticeDirectory();
    if (notice) {
      setNotice(elements.dashboardStatus, notice, noticeType);
    }
  } catch (error) {
    const authMissing = !getAccessToken() && !getRefreshToken();
    if (authMissing) {
      showAuth();
      setNotice(elements.authStatus, error.message, "error");
      return;
    }
    setNotice(elements.dashboardStatus, error.message, "error");
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const submitter = event.submitter;
  setButtonBusy(submitter, true, "Signing in...");
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

    if (payload.user?.role !== "internal_admin") {
      throw new Error("This account is not authorized for the internal portal.");
    }

    storeTokens(payload);
    await loadDashboard({ notice: `Welcome back, ${payload.user.name}.` });
    event.currentTarget.reset();
  } catch (error) {
    clearTokens();
    setNotice(elements.authStatus, error.message, "error");
  } finally {
    setButtonBusy(submitter, false);
  }
}

async function handleLogout() {
  try {
    await apiRequest("/api/auth/logout", { method: "POST" });
  } catch (_) {
    // Best effort only.
  } finally {
    clearTokens();
    showAuth();
    setNotice(elements.authStatus, "You have been logged out.", "info");
  }
}

async function handleCreatePractice(event) {
  event.preventDefault();
  const submitter = event.submitter;
  setButtonBusy(submitter, true, "Creating...");
  setNotice(elements.dashboardStatus, "");

  try {
    const data = new FormData(event.currentTarget);
    const defaultDiscounts = {
      full: maybeNumber(data.get("discount_full")),
      partial: maybeNumber(data.get("discount_partial")),
      full_blur: maybeNumber(data.get("discount_full_blur")),
    };
    await apiRequest("/api/internal/practices", {
      method: "POST",
      body: {
        practice_name: String(data.get("practice_name") || "").trim(),
        practice_location: String(data.get("practice_location") || "").trim(),
        practice_website: maybeString(data.get("practice_website")),
        owner_name: String(data.get("owner_name") || "").trim(),
        owner_email: String(data.get("owner_email") || "").trim(),
        owner_password: String(data.get("owner_password") || ""),
        auto_publish: Boolean(event.currentTarget.elements.auto_publish.checked),
        credit_expiration_days: maybeNumber(data.get("credit_expiration_days")),
        default_discounts:
          Object.values(defaultDiscounts).some((value) => value !== undefined) ? defaultDiscounts : undefined,
      },
    });
    event.currentTarget.reset();
    await loadDashboard({ notice: "New medspa created and added to the internal directory." });
  } catch (error) {
    setNotice(elements.dashboardStatus, error.message, "error");
  } finally {
    setButtonBusy(submitter, false);
  }
}

async function handleSearch(event) {
  event.preventDefault();
  state.query = elements.searchQuery.value || "";
  await loadDashboard({ notice: "Directory updated.", noticeType: "info" });
}

async function handlePracticeFormSubmit(event) {
  const form = event.target.closest(".internal-practice-form, .internal-owner-form");
  if (!(form instanceof HTMLFormElement)) return;

  event.preventDefault();
  const submitter = event.submitter;
  const practiceId = form.dataset.practiceId;
  if (!practiceId) return;

  setButtonBusy(submitter, true);
  setNotice(elements.dashboardStatus, "");

  try {
    if (form.matches(".internal-practice-form")) {
      const data = new FormData(form);
      const defaultDiscounts = {
        full: maybeNumber(data.get("discount_full")),
        partial: maybeNumber(data.get("discount_partial")),
        full_blur: maybeNumber(data.get("discount_full_blur")),
      };
      await apiRequest(`/api/internal/practices/${encodeURIComponent(practiceId)}`, {
        method: "PATCH",
        body: {
          name: maybeString(data.get("name")),
          location: maybeString(data.get("location")),
          website: maybeString(data.get("website")),
          credit_expiration_days: maybeNumber(data.get("credit_expiration_days")),
          auto_publish: Boolean(form.elements.auto_publish.checked),
          default_discounts:
            Object.values(defaultDiscounts).some((value) => value !== undefined) ? defaultDiscounts : undefined,
        },
      });
      await loadDashboard({ notice: "Practice settings updated." });
    }

    if (form.matches(".internal-owner-form")) {
      const data = new FormData(form);
      await apiRequest(`/api/internal/practices/${encodeURIComponent(practiceId)}/owner`, {
        method: "PATCH",
        body: {
          name: maybeString(data.get("name")),
          email: maybeString(data.get("email")),
        },
      });
      await loadDashboard({ notice: "Owner contact updated." });
    }
  } catch (error) {
    setNotice(elements.dashboardStatus, error.message, "error");
  } finally {
    setButtonBusy(submitter, false);
  }
}

function bindEvents() {
  elements.loginForm.addEventListener("submit", handleLogin);
  elements.logoutButton.addEventListener("click", handleLogout);
  elements.refreshButton.addEventListener("click", () =>
    loadDashboard({ notice: "Portal refreshed.", noticeType: "info" })
  );
  elements.createPracticeForm.addEventListener("submit", handleCreatePractice);
  elements.searchForm.addEventListener("submit", handleSearch);
  elements.practiceList.addEventListener("submit", handlePracticeFormSubmit);
  elements.practiceList.addEventListener("toggle", async (event) => {
    const details = event.target;
    if (!(details instanceof HTMLDetailsElement) || !details.open) return;
    const practiceId = details.dataset.practiceId;
    if (!practiceId) return;
    await loadPracticeDetail(practiceId);
  }, true);
}

async function init() {
  bindEvents();
  if (getAccessToken() || getRefreshToken()) {
    await loadDashboard();
  } else {
    showAuth();
  }
}

init();

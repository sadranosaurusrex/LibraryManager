import { api } from "./api.js";
import { buildCoverMarkup, renderHorizontalBars, renderStatusDonut } from "./charts.js";
import {
  applyLanguage,
  escapeHtml,
  formatBookDate,
  formatNum,
  i18nState,
  setTranslations,
  t,
} from "./i18n.js";

const STATUS_VALUES = ["Unread", "Reading", "Finished", "Dropped"];

const state = {
  activeTab: "library",
  viewMode: "table",
  filters: {
    q: "",
    storage: "",
    floor: "",
    row: "",
    genre: "",
    status: "",
    rating: "",
    sort_by: "id",
    sort_dir: "desc",
    page: 1,
    per_page: 50,
    all: false,
  },
  books: [],
  totalFiltered: 0,
  totalBooks: 0,
  totalPages: 1,
  facets: { storages: [], floors: [], rows: [], genres: [], statuses: STATUS_VALUES },
  selectedBookId: null,
  selectedShelfSlot: null,
  analytics: null,
  hygiene: null,
  pendingCoverUpload: null,
  clearCoverFlag: false,
  deleteTargetBook: null,
};

let searchTimer = null;

function showToast(message, isError = false) {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast${isError ? " toast-error" : ""}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => {
    el.remove();
  }, 3800);
}

function renderStars(rating) {
  if (rating === null || rating === undefined || rating <= 0) {
    return `<span class="rating-empty">${escapeHtml(t("label_unrated"))}</span>`;
  }
  const rounded = Math.round(rating);
  const full = "★".repeat(Math.min(5, Math.max(0, rounded)));
  const empty = "☆".repeat(Math.max(0, 5 - rounded));
  return `<span class="rating-stars" title="${formatNum(rating)}">${full}${empty}</span>`;
}

function renderLocationChip(book) {
  const parts = [book.storage || t("label_unknown")];
  if (book.floor !== null && book.floor !== undefined) {
    parts.push(`${t("label_floor_prefix")} ${formatNum(book.floor)}`);
  }
  if (book.row !== null && book.row !== undefined) {
    parts.push(`${t("label_row_prefix")} ${formatNum(book.row)}`);
  }
  return `<span class="loc-chip bidi-auto">${escapeHtml(parts.join(" · "))}</span>`;
}

function highlightMatch(text, query) {
  const raw = String(text || "");
  const q = (query || "").trim();
  if (!q || q.length < 2) {
    return escapeHtml(raw);
  }
  const idx = raw.toLowerCase().indexOf(q.toLowerCase());
  if (idx === -1) {
    return escapeHtml(raw);
  }
  const before = escapeHtml(raw.slice(0, idx));
  const hit = escapeHtml(raw.slice(idx, idx + q.length));
  const after = escapeHtml(raw.slice(idx + q.length));
  return `${before}<mark class="search-hit">${hit}</mark>${after}`;
}

function buildFilterParams() {
  const p = {
    q: state.filters.q,
    storage: state.filters.storage,
    floor: state.filters.floor,
    row: state.filters.row,
    genre: state.filters.genre,
    status: state.filters.status,
    rating: state.filters.rating,
    sort_by: state.filters.sort_by,
    sort_dir: state.filters.sort_dir,
    page: state.filters.page,
    per_page: state.filters.per_page,
  };
  if (state.filters.all) {
    p.all = "1";
  }
  return p;
}

async function refreshBooks() {
  const data = await api.listBooks(buildFilterParams());
  state.books = data.items || [];
  state.totalFiltered = data.total_filtered || 0;
  state.totalBooks = data.total_books || 0;
  state.totalPages = data.total_pages || 1;
  state.filters.page = data.page || 1;
  state.facets = data.facets || state.facets;

  renderHeaderBadges();
  populateFilterDropdowns();
  renderLibraryView();
}

function renderHygieneNavBadge() {
  const badge = document.getElementById("hygiene-nav-badge");
  const count = (state.hygiene && state.hygiene.auto_fixable_count) || 0;
  if (count > 0) {
    badge.textContent = formatNum(count);
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
}

async function refreshHygieneBadge() {
  try {
    const report = await api.getHygiene();
    state.hygiene = report;
    renderHygieneNavBadge();
    if (state.activeTab === "hygiene") {
      renderHygieneTab();
    }
  } catch {
    // Non-fatal
  }
}

function renderHeaderBadges() {
  const totalBadge = document.getElementById("header-total-badge");
  totalBadge.textContent = `${formatNum(state.totalBooks)} ${t("label_books_unit")}`;
}

function populateSelect(selectEl, options, currentVal) {
  selectEl.innerHTML = options
    .map((opt) => `<option value="${escapeHtml(opt.value)}">${escapeHtml(opt.label)}</option>`)
    .join("");
  selectEl.value = currentVal || "";
}

function populateFilterDropdowns() {
  const storageOpts = [{ value: "", label: t("filter_all") }].concat(
    (state.facets.storages || []).map((s) => ({
      value: s.name,
      label: `${s.name} (${formatNum(s.count)})`,
    }))
  );
  populateSelect(document.getElementById("filter-storage"), storageOpts, state.filters.storage);

  const floorOpts = [{ value: "", label: t("filter_all") }].concat(
    (state.facets.floors || []).map((f) => ({ value: String(f), label: formatNum(f) }))
  );
  populateSelect(document.getElementById("filter-floor"), floorOpts, state.filters.floor);

  const rowOpts = [{ value: "", label: t("filter_all") }].concat(
    (state.facets.rows || []).map((r) => ({ value: String(r), label: formatNum(r) }))
  );
  populateSelect(document.getElementById("filter-row"), rowOpts, state.filters.row);

  const genreOpts = [{ value: "", label: t("filter_all") }].concat(
    (state.facets.genres || []).map((g) => ({
      value: g.name,
      label: `${g.name} (${formatNum(g.count)})`,
    }))
  );
  populateSelect(document.getElementById("filter-genre"), genreOpts, state.filters.genre);

  const statusOpts = [{ value: "", label: t("filter_all") }].concat(
    STATUS_VALUES.map((st) => ({ value: st, label: t(`status_${st}`) }))
  );
  populateSelect(document.getElementById("filter-status"), statusOpts, state.filters.status);

  const ratingOpts = [
    { value: "", label: t("filter_all") },
    { value: "rated", label: t("filter_rating_rated") },
    { value: "4plus", label: t("filter_rating_4plus") },
    { value: "5", label: t("filter_rating_5") },
    { value: "unrated", label: t("filter_rating_unrated") },
  ];
  populateSelect(document.getElementById("filter-rating"), ratingOpts, state.filters.rating);

  // Also update modal datalists
  const storageList = document.getElementById("storage-datalist");
  storageList.innerHTML = (state.facets.storages || [])
    .map((s) => `<option value="${escapeHtml(s.name)}"></option>`)
    .join("");
  const genreList = document.getElementById("genre-datalist");
  genreList.innerHTML = (state.facets.genres || [])
    .slice(0, 60)
    .map((g) => `<option value="${escapeHtml(g.name)}"></option>`)
    .join("");
}

function renderSortHeaders() {
  document.querySelectorAll(".books-table thead th.sortable").forEach((th) => {
    const col = th.getAttribute("data-sort");
    const arrowEl = th.querySelector(".sort-arrow");
    if (!arrowEl) return;
    if (col === state.filters.sort_by) {
      arrowEl.textContent = state.filters.sort_dir === "asc" ? "▲" : "▼";
    } else {
      arrowEl.textContent = "";
    }
  });
}

function renderLibraryView() {
  const summaryEl = document.getElementById("results-summary");
  summaryEl.textContent = `${formatNum(state.totalFiltered)} ${t("results_count")} (${t("of_total")} ${formatNum(state.totalBooks)})`;

  const pageInd = document.getElementById("page-indicator");
  pageInd.textContent = `${formatNum(state.filters.page)} / ${formatNum(state.totalPages)}`;
  document.getElementById("btn-prev-page").disabled = state.filters.page <= 1;
  document.getElementById("btn-next-page").disabled = state.filters.page >= state.totalPages;

  const emptyEl = document.getElementById("library-empty-state");
  const tableWrap = document.getElementById("table-view-container");
  const cardsWrap = document.getElementById("cards-view-container");

  if (!state.books.length) {
    emptyEl.classList.remove("hidden");
    tableWrap.classList.add("hidden");
    cardsWrap.classList.add("hidden");
    return;
  }

  emptyEl.classList.add("hidden");
  renderSortHeaders();

  if (state.viewMode === "table") {
    tableWrap.classList.remove("hidden");
    cardsWrap.classList.add("hidden");
    renderTableRows();
  } else {
    tableWrap.classList.add("hidden");
    cardsWrap.classList.remove("hidden");
    renderBookCards();
  }
}

function renderTableRows() {
  const tbody = document.getElementById("books-tbody");
  tbody.innerHTML = state.books
    .map((book) => {
      const genresMarkup = (book.genre_tags || [])
        .slice(0, 3)
        .map((tag) => `<span class="genre-tag bidi-auto">${escapeHtml(tag)}</span>`)
        .join("");

      return `
        <tr data-book-id="${book.id}">
          <td class="cell-id">${formatNum(book.id)}</td>
          <td>
            <div class="cell-title-main bidi-auto">${highlightMatch(book.book_name, state.filters.q)}</div>
          </td>
          <td class="bidi-auto">${book.author ? highlightMatch(book.author, state.filters.q) : '<span class="rating-empty">—</span>'}</td>
          <td><div class="genre-tags">${genresMarkup || '<span class="rating-empty">—</span>'}</div></td>
          <td>${renderLocationChip(book)}</td>
          <td><span class="status-badge status-${escapeHtml(book.status)}">${escapeHtml(t(`status_${book.status}`))}</span></td>
          <td>${renderStars(book.rating)}</td>
          <td>${escapeHtml(formatBookDate(book, "date_added", false))}</td>
          <td>
            <div class="row-actions">
              <button class="btn btn-ghost btn-sm btn-row-edit" type="button" data-edit-id="${book.id}">${escapeHtml(t("btn_edit"))}</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderBookCards() {
  const cardsWrap = document.getElementById("cards-view-container");
  cardsWrap.innerHTML = state.books
    .map((book) => {
      return `
        <article class="book-card" data-book-id="${book.id}">
          <div class="book-card-cover">${buildCoverMarkup(book)}</div>
          <div class="book-card-body">
            <div>
              <h3 class="book-card-title bidi-auto">${highlightMatch(book.book_name, state.filters.q)}</h3>
              <div class="book-card-author bidi-auto">${escapeHtml(book.author || t("label_unknown"))}</div>
            </div>
            <div>${renderLocationChip(book)}</div>
            <div class="book-card-footer">
              <span class="status-badge status-${escapeHtml(book.status)}">${escapeHtml(t(`status_${book.status}`))}</span>
              ${renderStars(book.rating)}
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

async function openBookDrawer(bookId) {
  const book = await api.getBook(bookId);
  state.selectedBookId = book.id;

  document.getElementById("drawer-book-id").textContent = `#${formatNum(book.id)}`;
  const body = document.getElementById("drawer-body");

  const genreChips = (book.genre_tags || [])
    .map((g) => `<span class="genre-tag">${escapeHtml(g)}</span>`)
    .join("");

  const statusButtons = STATUS_VALUES.map((st) => {
    const active = book.status === st;
    return `<button type="button" class="btn btn-sm ${active ? "btn-primary" : "btn-ghost"} drawer-status-btn" data-status="${st}">${escapeHtml(t(`status_${st}`))}</button>`;
  }).join("");

  const currentStars = Math.round(book.rating || 0);
  const starButtons = [1, 2, 3, 4, 5]
    .map(
      (n) =>
        `<button type="button" class="star-btn ${n <= currentStars ? "active" : ""}" data-star="${n}" aria-label="${n}">★</button>`
    )
    .join("");

  body.innerHTML = `
    <div class="drawer-hero">
      <div class="drawer-cover">${buildCoverMarkup(book)}</div>
      <div>
        <h3 class="drawer-title bidi-auto">${escapeHtml(book.book_name)}</h3>
        <p class="drawer-author bidi-auto">${escapeHtml(book.author || t("label_unknown"))}</p>
        <div class="genre-tags">${genreChips}</div>
      </div>
    </div>

    <div class="drawer-section">
      <h4>${escapeHtml(t("col_location"))}</h4>
      <div>${renderLocationChip(book)}</div>
    </div>

    <div class="drawer-section">
      <h4>${escapeHtml(t("col_status"))}</h4>
      <div class="quick-status-row">${statusButtons}</div>
    </div>

    <div class="drawer-section">
      <h4>${escapeHtml(t("col_rating"))}</h4>
      <div class="star-picker">
        ${starButtons}
        <button type="button" class="btn btn-ghost btn-sm" id="btn-drawer-clear-rating">${escapeHtml(t("label_unrated"))}</button>
      </div>
    </div>

    <div class="drawer-section">
      <h4>${escapeHtml(t("col_date_added"))} / ${escapeHtml(t("col_date_finished"))}</h4>
      <div>${escapeHtml(t("col_date_added"))}: <strong>${escapeHtml(formatBookDate(book, "date_added", true))}</strong> <span class="section-subtitle">(${escapeHtml(book.date_added || "—")})</span></div>
      <div>${escapeHtml(t("col_date_finished"))}: <strong>${escapeHtml(formatBookDate(book, "date_finished", true))}</strong></div>
    </div>

    ${
      book.description
        ? `<div class="drawer-section"><h4>${escapeHtml(t("field_description"))}</h4><p class="bidi-auto">${escapeHtml(book.description)}</p></div>`
        : ""
    }

    ${
      book.notes
        ? `<div class="drawer-section"><h4>${escapeHtml(t("field_notes"))}</h4><p class="bidi-auto">${escapeHtml(book.notes)}</p></div>`
        : ""
    }

    <div class="modal-footer">
      <button type="button" class="btn btn-danger btn-sm" id="btn-drawer-delete">${escapeHtml(t("btn_delete"))}</button>
      <button type="button" class="btn btn-primary" id="btn-drawer-edit">${escapeHtml(t("btn_edit"))}</button>
    </div>
  `;

  body.querySelectorAll(".drawer-status-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const nextStatus = btn.getAttribute("data-status");
      await api.patchBook(book.id, { status: nextStatus });
      showToast(t("toast_saved"));
      await refreshBooks();
      await openBookDrawer(book.id);
    });
  });

  body.querySelectorAll(".star-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const stars = Number(btn.getAttribute("data-star"));
      await api.patchBook(book.id, { rating: stars });
      showToast(t("toast_saved"));
      await refreshBooks();
      await openBookDrawer(book.id);
    });
  });

  body.querySelector("#btn-drawer-clear-rating").addEventListener("click", async () => {
    await api.patchBook(book.id, { rating: null });
    showToast(t("toast_saved"));
    await refreshBooks();
    await openBookDrawer(book.id);
  });

  body.querySelector("#btn-drawer-edit").addEventListener("click", () => {
    closeBookDrawer();
    openBookModal(book);
  });

  body.querySelector("#btn-drawer-delete").addEventListener("click", () => {
    openDeleteConfirm(book);
  });

  document.getElementById("drawer-backdrop").classList.remove("hidden");
  document.getElementById("book-drawer").classList.remove("hidden");
  document.getElementById("book-drawer").setAttribute("aria-hidden", "false");
}

function closeBookDrawer() {
  document.getElementById("drawer-backdrop").classList.add("hidden");
  document.getElementById("book-drawer").classList.add("hidden");
  document.getElementById("book-drawer").setAttribute("aria-hidden", "true");
}

function openBookModal(book = null, presetSlot = null) {
  state.pendingCoverUpload = null;
  state.clearCoverFlag = false;

  const isEdit = Boolean(book && book.id);
  document.getElementById("book-modal-title").textContent = isEdit
    ? t("modal_edit_title")
    : t("modal_add_title");
  document.getElementById("btn-submit-book-modal").textContent = isEdit
    ? t("btn_save_changes")
    : t("btn_save");

  document.getElementById("form-error-banner").classList.add("hidden");
  document.getElementById("form-book-id").value = isEdit ? String(book.id) : "";
  document.getElementById("form-book-name").value = book ? book.book_name || "" : "";
  document.getElementById("form-author").value = book ? book.author || "" : "";
  document.getElementById("form-genre").value = book ? book.genre || "" : "";
  document.getElementById("form-storage").value = book
    ? book.storage || ""
    : (presetSlot && presetSlot.storage) || "";
  document.getElementById("form-floor").value =
    book && book.floor !== null && book.floor !== undefined
      ? String(book.floor)
      : presetSlot && presetSlot.floor
      ? String(presetSlot.floor)
      : "1";
  document.getElementById("form-row").value =
    book && book.row !== null && book.row !== undefined
      ? String(book.row)
      : presetSlot && presetSlot.row
      ? String(presetSlot.row)
      : "1";

  const statusSel = document.getElementById("form-status");
  statusSel.innerHTML = STATUS_VALUES.map(
    (st) => `<option value="${st}">${escapeHtml(t(`status_${st}`))}</option>`
  ).join("");
  statusSel.value = book ? book.status : "Unread";

  document.getElementById("form-rating").value =
    book && book.rating !== null && book.rating !== undefined ? String(book.rating) : "";
  document.getElementById("form-date-added").value = book
    ? (i18nState.lang === "fa" ? book.date_added_jalali || book.date_added : book.date_added) || ""
    : "";
  document.getElementById("form-date-finished").value = book
    ? (i18nState.lang === "fa" ? book.date_finished_jalali || book.date_finished : book.date_finished) || ""
    : "";
  document.getElementById("form-description").value = book ? book.description || "" : "";
  document.getElementById("form-notes").value = book ? book.notes || "" : "";

  const previewEl = document.getElementById("form-cover-preview");
  const coverNameEl = document.getElementById("form-cover-name");
  if (book && book.cover_path) {
    const encoded = encodeURIComponent(book.cover_path).replaceAll("%2F", "/");
    previewEl.innerHTML = `<img src="/api/covers/${encoded}" alt="cover" />`;
    coverNameEl.textContent = book.cover_path;
  } else {
    previewEl.innerHTML = "<span>📕</span>";
    coverNameEl.textContent = "";
  }

  document.getElementById("book-modal-backdrop").classList.remove("hidden");
  document.getElementById("form-book-name").focus();
}

function closeBookModal() {
  document.getElementById("book-modal-backdrop").classList.add("hidden");
}

async function handleBookFormSubmit(event) {
  event.preventDefault();
  const errBanner = document.getElementById("form-error-banner");
  errBanner.classList.add("hidden");

  const idVal = document.getElementById("form-book-id").value;
  const payload = {
    book_name: document.getElementById("form-book-name").value,
    author: document.getElementById("form-author").value,
    genre: document.getElementById("form-genre").value,
    storage: document.getElementById("form-storage").value,
    floor: document.getElementById("form-floor").value || null,
    row: document.getElementById("form-row").value || null,
    status: document.getElementById("form-status").value,
    rating: document.getElementById("form-rating").value || null,
    date_added: document.getElementById("form-date-added").value,
    date_finished: document.getElementById("form-date-finished").value,
    description: document.getElementById("form-description").value,
    notes: document.getElementById("form-notes").value,
  };
  if (state.clearCoverFlag) {
    payload.cover_path = "";
  }

  try {
    let savedBook;
    if (idVal) {
      savedBook = await api.updateBook(Number(idVal), payload);
    } else {
      savedBook = await api.createBook(payload);
    }
    if (state.pendingCoverUpload && savedBook && savedBook.id) {
      await api.uploadCover(
        savedBook.id,
        state.pendingCoverUpload.filename,
        state.pendingCoverUpload.dataBase64
      );
    }
    closeBookModal();
    showToast(t("toast_saved"));
    await refreshBooks();
    await refreshHygieneBadge();
    if (state.activeTab === "shelf-map") {
      await loadAndRenderShelfMap();
    } else if (state.activeTab === "analytics") {
      await loadAndRenderAnalytics();
    }
  } catch (err) {
    errBanner.textContent = t(err.code || "err_unknown");
    errBanner.classList.remove("hidden");
  }
}

function openDeleteConfirm(book) {
  state.deleteTargetBook = book;
  document.getElementById("confirm-delete-book-label").textContent = book.book_name;
  document.getElementById("confirm-modal-backdrop").classList.remove("hidden");
}

function closeDeleteConfirm() {
  state.deleteTargetBook = null;
  document.getElementById("confirm-modal-backdrop").classList.add("hidden");
}

async function confirmDeleteBook() {
  if (!state.deleteTargetBook) return;
  try {
    await api.deleteBook(state.deleteTargetBook.id);
    closeDeleteConfirm();
    closeBookDrawer();
    showToast(t("toast_deleted"));
    await refreshBooks();
    await refreshHygieneBadge();
  } catch (err) {
    showToast(t(err.code || "err_unknown"), true);
  }
}

/* SHELF MAP */
async function loadAndRenderShelfMap() {
  const analytics = await api.getAnalytics();
  state.analytics = analytics;
  const grid = document.getElementById("shelf-map-grid");
  const shelfMap = analytics.shelf_map || [];

  grid.innerHTML = shelfMap
    .map((cab) => {
      const floorsHtml = (cab.floors || [])
        .map((fl) => {
          const rowsHtml = (fl.rows || [])
            .map((rw) => {
              const isSelected =
                state.selectedShelfSlot &&
                state.selectedShelfSlot.storage === cab.storage &&
                state.selectedShelfSlot.floor === fl.floor &&
                state.selectedShelfSlot.row === rw.row;
              return `
                <button
                  type="button"
                  class="row-slot-btn ${isSelected ? "active" : ""}"
                  data-storage="${escapeHtml(cab.storage)}"
                  data-floor="${fl.floor}"
                  data-row="${rw.row}"
                >
                  <span>${escapeHtml(t("label_row_prefix"))} ${formatNum(rw.row)}</span>
                  <span class="pill pill-accent">${formatNum(rw.count)}</span>
                </button>
              `;
            })
            .join("");

          return `
            <div class="floor-band">
              <div class="floor-label">${escapeHtml(t("label_floor_prefix"))} ${formatNum(fl.floor)} (${formatNum(fl.count)} ${escapeHtml(t("label_books_unit"))})</div>
              <div class="row-slots">${rowsHtml}</div>
            </div>
          `;
        })
        .join("");

      const unplacedBtn =
        cab.unplaced_books && cab.unplaced_books.length
          ? `<button type="button" class="row-slot-btn" data-storage="${escapeHtml(cab.storage)}" data-unplaced="1">${escapeHtml(t("shelf_unplaced"))} <span class="pill pill-accent">${formatNum(cab.unplaced_books.length)}</span></button>`
          : "";

      return `
        <article class="cabinet-card">
          <div class="cabinet-header">
            <h3 class="bidi-auto">🗄️ ${escapeHtml(cab.storage)}</h3>
            <span class="pill pill-accent">${formatNum(cab.total_books)} ${escapeHtml(t("label_books_unit"))}</span>
          </div>
          <div class="floor-row-group">
            ${floorsHtml}
            ${unplacedBtn}
          </div>
        </article>
      `;
    })
    .join("");

  grid.querySelectorAll(".row-slot-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const storage = btn.getAttribute("data-storage");
      const unplaced = btn.getAttribute("data-unplaced") === "1";
      const floor = unplaced ? null : Number(btn.getAttribute("data-floor"));
      const row = unplaced ? null : Number(btn.getAttribute("data-row"));
      selectShelfSlot(storage, floor, row, unplaced);
    });
  });

  if (state.selectedShelfSlot) {
    renderSelectedShelfInspector();
  }
}

function selectShelfSlot(storage, floor, row, unplaced = false) {
  state.selectedShelfSlot = { storage, floor, row, unplaced };
  renderSelectedShelfInspector();
  document.querySelectorAll(".row-slot-btn").forEach((btn) => {
    const match =
      btn.getAttribute("data-storage") === storage &&
      (unplaced
        ? btn.getAttribute("data-unplaced") === "1"
        : Number(btn.getAttribute("data-floor")) === floor &&
          Number(btn.getAttribute("data-row")) === row);
    btn.classList.toggle("active", match);
  });
}

function renderSelectedShelfInspector() {
  const slot = state.selectedShelfSlot;
  if (!slot || !state.analytics) return;

  const cab = (state.analytics.shelf_map || []).find((c) => c.storage === slot.storage);
  if (!cab) return;

  let books = [];
  let titleText = slot.storage;
  if (slot.unplaced) {
    books = cab.unplaced_books || [];
    titleText = `${slot.storage} · ${t("shelf_unplaced")}`;
  } else {
    const fl = (cab.floors || []).find((f) => f.floor === slot.floor);
    const rw = fl ? (fl.rows || []).find((r) => r.row === slot.row) : null;
    books = rw ? rw.books : [];
    titleText = `${slot.storage} · ${t("label_floor_prefix")} ${formatNum(slot.floor)} · ${t("label_row_prefix")} ${formatNum(slot.row)}`;
  }

  document.querySelector(".shelf-workspace").classList.add("has-selection");
  const inspector = document.getElementById("shelf-slot-inspector");
  inspector.classList.remove("hidden");
  document.getElementById("shelf-slot-title").textContent = titleText;
  document.getElementById("shelf-slot-count").textContent = `${formatNum(books.length)} ${t("label_books_unit")}`;

  const listEl = document.getElementById("shelf-slot-books");
  listEl.innerHTML = books
    .map(
      (b) => `
      <div class="slot-book-item" data-book-id="${b.id}">
        <div>
          <div class="cell-title-main bidi-auto">${escapeHtml(b.book_name)}</div>
          <div class="book-card-author bidi-auto">${escapeHtml(b.author || t("label_unknown"))}</div>
        </div>
        <span class="status-badge status-${escapeHtml(b.status)}">${escapeHtml(t(`status_${b.status}`))}</span>
      </div>
    `
    )
    .join("");

  listEl.querySelectorAll(".slot-book-item").forEach((el) => {
    el.addEventListener("click", () => {
      openBookDrawer(Number(el.getAttribute("data-book-id")));
    });
  });
}

/* ANALYTICS */
async function loadAndRenderAnalytics() {
  const data = await api.getAnalytics();
  state.analytics = data;
  const k = data.kpis;

  const pctMark = i18nState.lang === "fa" ? "٪" : "%";
  document.getElementById("kpi-grid").innerHTML = `
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(t("kpi_total"))}</div>
      <div class="kpi-value">${formatNum(k.total_books)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(t("kpi_finished"))}</div>
      <div class="kpi-value">${formatNum(k.finished_books)}</div>
      <div class="kpi-sub">${formatNum(k.completion_rate)}${pctMark}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(t("kpi_reading"))}</div>
      <div class="kpi-value">${formatNum(k.reading_books)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(t("kpi_avg_rating"))}</div>
      <div class="kpi-value">${k.average_rating !== null ? formatNum(k.average_rating) : "—"} ★</div>
      <div class="kpi-sub">${formatNum(k.rated_books)} ${escapeHtml(t("label_books_unit"))}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(t("kpi_authors"))}</div>
      <div class="kpi-value">${formatNum(k.unique_authors)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(t("kpi_genres"))}</div>
      <div class="kpi-value">${formatNum(k.unique_genres)}</div>
    </div>
  `;

  renderStatusDonut(document.getElementById("chart-status-container"), data.by_status || []);
  renderHorizontalBars(
    document.getElementById("chart-storage-container"),
    data.by_storage || [],
    "storage",
    "count",
    "var(--primary)"
  );
  renderHorizontalBars(
    document.getElementById("chart-genres-container"),
    data.top_genres || [],
    "genre",
    "count",
    "var(--teal)"
  );
  const ratingBars = (data.rating_distribution || []).map((r) => ({
    label: `${"★".repeat(r.stars)} (${formatNum(r.stars)})`,
    count: r.count,
  }));
  renderHorizontalBars(
    document.getElementById("chart-ratings-container"),
    ratingBars,
    "label",
    "count",
    "var(--amber)"
  );
}

/* HYGIENE */
async function loadAndRenderHygiene() {
  state.hygiene = await api.getHygiene();
  renderHygieneTab();
}

function renderHygieneTab() {
  const report = state.hygiene;
  if (!report) return;
  const counts = report.issue_counts || {};

  document.getElementById("btn-hygiene-fix").disabled = (report.auto_fixable_count || 0) === 0;

  document.getElementById("hygiene-summary-grid").innerHTML = `
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(t("hygiene_persian_norm"))}</div>
      <div class="kpi-value">${formatNum(counts.persian_normalization || 0)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(t("hygiene_status_casing"))}</div>
      <div class="kpi-value">${formatNum(counts.status_casing || 0)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(t("hygiene_missing_loc"))}</div>
      <div class="kpi-value">${formatNum(counts.missing_location || 0)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(t("hygiene_missing_author"))}</div>
      <div class="kpi-value">${formatNum(counts.missing_author || 0)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(t("hygiene_missing_genre"))}</div>
      <div class="kpi-value">${formatNum(counts.missing_genre || 0)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(t("hygiene_duplicates"))}</div>
      <div class="kpi-value">${formatNum((report.duplicate_groups || []).length)}</div>
    </div>
  `;

  const container = document.getElementById("hygiene-content");
  const parts = [];

  if ((report.issues || []).length === 0 && (report.duplicate_groups || []).length === 0) {
    parts.push(`<div class="empty-state"><div class="empty-icon">✅</div><h3>${escapeHtml(t("hygiene_no_issues"))}</h3></div>`);
  } else {
    if ((report.issues || []).length > 0) {
      const sampleRows = report.issues.slice(0, 50).map(
        (iss) => `
          <tr data-book-id="${iss.book_id}" class="hygiene-issue-row">
            <td>${formatNum(iss.book_id)}</td>
            <td class="bidi-auto">${escapeHtml(iss.book_name)}</td>
            <td>${escapeHtml(iss.field)}</td>
            <td class="bidi-auto">${escapeHtml(iss.current_value)}</td>
            <td class="bidi-auto">${escapeHtml(iss.suggested_value || "—")}</td>
          </tr>
        `
      ).join("");

      parts.push(`
        <div class="hygiene-panel">
          <div class="table-scroll">
            <table class="books-table">
              <thead>
                <tr>
                  <th>${escapeHtml(t("col_id"))}</th>
                  <th>${escapeHtml(t("hygiene_col_field"))}</th>
                  <th>${escapeHtml(t("hygiene_col_current"))}</th>
                  <th>${escapeHtml(t("hygiene_col_suggested"))}th>
                  <th>Suggested</th>
                </tr>
              </thead>
              <tbody>${sampleRows}</tbody>
            </table>
          </div>
        </div>
      `);
    }

    if ((report.duplicate_groups || []).length > 0) {
      const dupHtml = report.duplicate_groups
        .map(
          (grp) => `
            <div class="dup-group">
              ${grp
                .map(
                  (item) => `
                  <div class="slot-book-item" data-book-id="${item.id}">
                    <span class="bidi-auto"><strong>#${formatNum(item.id)}</strong> — ${escapeHtml(item.book_name)} (${escapeHtml(item.author || "—")})</span>
                    <span>${escapeHtml(item.storage || "")}</span>
                  </div>
                `
                )
                .join("")}
            </div>
          `
        )
        .join("");

      parts.push(`
        <div class="hygiene-panel">
          <h3>${escapeHtml(t("hygiene_duplicates"))}</h3>
          ${dupHtml}
        </div>
      `);
    }
  }

  container.innerHTML = parts.join("");
  container.querySelectorAll("[data-book-id]").forEach((el) => {
    el.addEventListener("click", () => {
      openBookDrawer(Number(el.getAttribute("data-book-id")));
    });
  });
}

/* BACKUPS MODAL */
async function openBackupsModal() {
  document.getElementById("backups-modal-backdrop").classList.remove("hidden");
  await renderBackupsList();
}

async function renderBackupsList() {
  const data = await api.listBackups();
  const listEl = document.getElementById("backups-list");
  const backups = data.backups || [];
  if (!backups.length) {
    listEl.innerHTML = `<p class="section-subtitle">—</p>`;
    return;
  }
  listEl.innerHTML = backups
    .map(
      (b) => `
      <div class="backup-item">
        <div>
          <div><strong>${escapeHtml(b.name)}</strong></div>
          <div class="section-subtitle">${escapeHtml(b.modified_at)} · ${formatNum(Math.round(b.size_bytes / 1024))} KB</div>
        </div>
        <button type="button" class="btn btn-secondary btn-sm btn-restore-backup" data-name="${escapeHtml(b.name)}">${escapeHtml(t("btn_restore"))}</button>
      </div>
    `
    )
    .join("");

  listEl.querySelectorAll(".btn-restore-backup").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api.restoreBackup(btn.getAttribute("data-name"));
      showToast(t("toast_restored"));
      await refreshBooks();
      await refreshHygieneBadge();
      await renderBackupsList();
    });
  });
}

/* TAB SWITCHING */
async function switchTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tabName}`);
  });

  if (tabName === "shelf-map") {
    await loadAndRenderShelfMap();
  } else if (tabName === "analytics") {
    await loadAndRenderAnalytics();
  } else if (tabName === "hygiene") {
    await loadAndRenderHygiene();
  }
}

/* THEME */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("library_v2_theme", theme);
  const icon = document.getElementById("theme-icon");
  const label = document.getElementById("theme-label");
  if (theme === "dark") {
    icon.textContent = "☀️";
    label.setAttribute("data-i18n", "btn_theme_light");
    label.textContent = t("btn_theme_light");
  } else {
    icon.textContent = "🌙";
    label.setAttribute("data-i18n", "btn_theme_dark");
    label.textContent = t("btn_theme_dark");
  }
}

function wireEvents() {
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.getAttribute("data-tab")));
  });

  document.getElementById("btn-lang-toggle").addEventListener("click", async () => {
    const nextLang = i18nState.lang === "fa" ? "en" : "fa";
    applyLanguage(nextLang);
    applyTheme(document.documentElement.getAttribute("data-theme") || "light");
    populateFilterDropdowns();
    renderHeaderBadges();
    renderHygieneNavBadge();
    renderLibraryView();
    if (state.activeTab === "shelf-map") await loadAndRenderShelfMap();
    if (state.activeTab === "analytics") await loadAndRenderAnalytics();
    if (state.activeTab === "hygiene") renderHygieneTab();
    const health = await api.getHealth();
    updateDateBadge(health);
  });

  document.getElementById("btn-theme-toggle").addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    applyTheme(current === "light" ? "dark" : "light");
  });

  const searchInput = document.getElementById("search-input");
  const clearBtn = document.getElementById("btn-clear-search");
  searchInput.addEventListener("input", () => {
    clearBtn.classList.toggle("hidden", !searchInput.value);
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.filters.q = searchInput.value;
      state.filters.page = 1;
      refreshBooks();
    }, 150);
  });

  clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    clearBtn.classList.add("hidden");
    state.filters.q = "";
    state.filters.page = 1;
    refreshBooks();
  });

  const filterBindings = [
    ["filter-storage", "storage"],
    ["filter-floor", "floor"],
    ["filter-row", "row"],
    ["filter-genre", "genre"],
    ["filter-status", "status"],
    ["filter-rating", "rating"],
  ];
  filterBindings.forEach(([id, key]) => {
    document.getElementById(id).addEventListener("change", (e) => {
      state.filters[key] = e.target.value;
      state.filters.page = 1;
      refreshBooks();
    });
  });

  const resetAllFilters = () => {
    searchInput.value = "";
    clearBtn.classList.add("hidden");
    state.filters.q = "";
    state.filters.storage = "";
    state.filters.floor = "";
    state.filters.row = "";
    state.filters.genre = "";
    state.filters.status = "";
    state.filters.rating = "";
    state.filters.page = 1;
    refreshBooks();
  };
  document.getElementById("btn-reset-filters").addEventListener("click", resetAllFilters);
  document.getElementById("btn-empty-reset").addEventListener("click", resetAllFilters);

  document.querySelectorAll(".view-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.viewMode = btn.getAttribute("data-view");
      document.querySelectorAll(".view-btn").forEach((b) => b.classList.toggle("active", b === btn));
      renderLibraryView();
    });
  });

  document.querySelectorAll(".books-table thead th.sortable").forEach((th) => {
    th.addEventListener("click", () => {
      const col = th.getAttribute("data-sort");
      if (state.filters.sort_by === col) {
        state.filters.sort_dir = state.filters.sort_dir === "asc" ? "desc" : "asc";
      } else {
        state.filters.sort_by = col;
        state.filters.sort_dir = col === "id" ? "desc" : "asc";
      }
      state.filters.page = 1;
      refreshBooks();
    });
  });

  document.getElementById("per-page-select").addEventListener("change", (e) => {
    const val = e.target.value;
    if (val === "all") {
      state.filters.all = true;
    } else {
      state.filters.all = false;
      state.filters.per_page = Number(val);
    }
    state.filters.page = 1;
    refreshBooks();
  });

  document.getElementById("btn-prev-page").addEventListener("click", () => {
    if (state.filters.page > 1) {
      state.filters.page -= 1;
      refreshBooks();
    }
  });

  document.getElementById("btn-next-page").addEventListener("click", () => {
    if (state.filters.page < state.totalPages) {
      state.filters.page += 1;
      refreshBooks();
    }
  });

  // Table & Card click delegation
  document.getElementById("books-tbody").addEventListener("click", (e) => {
    const editBtn = e.target.closest(".btn-row-edit");
    if (editBtn) {
      e.stopPropagation();
      const id = Number(editBtn.getAttribute("data-edit-id"));
      api.getBook(id).then((book) => openBookModal(book));
      return;
    }
    const row = e.target.closest("tr[data-book-id]");
    if (row) {
      openBookDrawer(Number(row.getAttribute("data-book-id")));
    }
  });

  document.getElementById("cards-view-container").addEventListener("click", (e) => {
    const card = e.target.closest(".book-card[data-book-id]");
    if (card) {
      openBookDrawer(Number(card.getAttribute("data-book-id")));
    }
  });

  // Modals & Drawer
  document.getElementById("btn-add-book").addEventListener("click", () => openBookModal());
  document.getElementById("btn-shelf-add-here").addEventListener("click", () => {
    openBookModal(null, state.selectedShelfSlot);
  });
  document.getElementById("btn-close-drawer").addEventListener("click", closeBookDrawer);
  document.getElementById("drawer-backdrop").addEventListener("click", closeBookDrawer);

  document.getElementById("btn-close-book-modal").addEventListener("click", closeBookModal);
  document.getElementById("btn-cancel-book-modal").addEventListener("click", closeBookModal);
  document.getElementById("book-form").addEventListener("submit", handleBookFormSubmit);

  document.getElementById("btn-choose-cover").addEventListener("click", () => {
    document.getElementById("form-cover-file").click();
  });
  document.getElementById("form-cover-file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      state.pendingCoverUpload = { filename: file.name, dataBase64: reader.result };
      state.clearCoverFlag = false;
      document.getElementById("form-cover-preview").innerHTML = `<img src="${reader.result}" alt="preview" />`;
      document.getElementById("form-cover-name").textContent = file.name;
    };
    reader.readAsDataURL(file);
  });
  document.getElementById("btn-clear-cover").addEventListener("click", () => {
    state.pendingCoverUpload = null;
    state.clearCoverFlag = true;
    document.getElementById("form-cover-preview").innerHTML = "<span>📕</span>";
    document.getElementById("form-cover-name").textContent = "";
  });

  // Delete confirm
  document.getElementById("btn-close-confirm-modal").addEventListener("click", closeDeleteConfirm);
  document.getElementById("btn-cancel-delete").addEventListener("click", closeDeleteConfirm);
  document.getElementById("btn-confirm-delete").addEventListener("click", confirmDeleteBook);

  // Backups
  document.getElementById("btn-backups").addEventListener("click", openBackupsModal);
  document.getElementById("btn-close-backups-modal").addEventListener("click", () => {
    document.getElementById("backups-modal-backdrop").classList.add("hidden");
  });
  document.getElementById("btn-create-backup-now").addEventListener("click", async () => {
    await api.createBackup();
    showToast(t("toast_backup_done"));
    await renderBackupsList();
  });

  // Hygiene auto fix
  document.getElementById("btn-hygiene-fix").addEventListener("click", async () => {
    const res = await api.runHygieneFix();
    state.hygiene = res.report;
    showToast(t("toast_hygiene_done"));
    renderHygieneTab();
    await refreshBooks();
    await refreshHygieneBadge();
  });

  // Export CSV / XLSX with current filters
  const buildExportQuery = () => {
    const p = buildFilterParams();
    delete p.page;
    delete p.per_page;
    delete p.all;
    return new URLSearchParams(
      Object.entries(p).filter(([, v]) => v !== "" && v !== null && v !== undefined)
    ).toString();
  };
  document.getElementById("btn-export-csv").addEventListener("click", () => {
    window.location.href = `/api/export/csv?${buildExportQuery()}`;
  });
  document.getElementById("btn-export-xlsx").addEventListener("click", () => {
    window.location.href = `/api/export/xlsx?${buildExportQuery()}`;
  });

  // Keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      switchTab("library");
      searchInput.focus();
      searchInput.select();
    } else if (e.key === "Escape") {
      closeBookModal();
      closeDeleteConfirm();
      closeBookDrawer();
      document.getElementById("backups-modal-backdrop").classList.add("hidden");
    }
  });
}

function updateDateBadge(health) {
  const el = document.getElementById("header-date-badge");
  if (!el || !health) return;
  el.textContent = i18nState.lang === "fa" ? health.today_jalali_long : health.today_iso;
}

async function init() {
  const [i18nPayload, health] = await Promise.all([api.getI18n(), api.getHealth()]);
  setTranslations(i18nPayload);
  const savedTheme = localStorage.getItem("library_v2_theme") || "light";
  applyTheme(savedTheme);
  updateDateBadge(health);
  wireEvents();
  await refreshBooks();
  await refreshHygieneBadge();
}

init().catch((err) => {
  console.error(err);
  showToast(err.message || "Error loading app", true);
});

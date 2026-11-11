const PERSIAN_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];

export const i18nState = {
  lang: "fa",
  bundles: { fa: {}, en: {} },
};

export function setTranslations(payload) {
  i18nState.bundles = payload.translations || { fa: {}, en: {} };
  const saved = localStorage.getItem("library_v2_lang");
  const initial = saved && i18nState.bundles[saved] ? saved : payload.default_lang || "fa";
  applyLanguage(initial);
}

export function applyLanguage(lang) {
  i18nState.lang = lang === "en" ? "en" : "fa";
  localStorage.setItem("library_v2_lang", i18nState.lang);
  document.documentElement.lang = i18nState.lang;
  document.documentElement.dir = i18nState.lang === "fa" ? "rtl" : "ltr";
  document.title = t("app_title");
  translateStaticDom();
}

export function t(key) {
  const bundle = i18nState.bundles[i18nState.lang] || {};
  return bundle[key] || (i18nState.bundles.fa && i18nState.bundles.fa[key]) || key;
}

export function translateStaticDom() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (key) {
      el.textContent = t(key);
    }
  });
  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    searchInput.placeholder = t("search_placeholder");
  }
  const appTitleEl = document.getElementById("app-title");
  if (appTitleEl) {
    appTitleEl.textContent = i18nState.lang === "fa" ? "کتاب‌خانهٔ من" : "My Library Studio";
  }
  const subEl = document.getElementById("app-subtitle");
  if (subEl) {
    subEl.textContent = t("app_subtitle");
  }
  const langLabel = document.getElementById("lang-switch-label");
  if (langLabel) {
    langLabel.textContent = t("lang_switch_label");
  }
}

export function formatNum(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  const str = String(value);
  if (i18nState.lang !== "fa") {
    return str;
  }
  return str.replace(/\d/g, (d) => PERSIAN_DIGITS[Number(d)]);
}

export function formatBookDate(book, fieldPrefix = "date_added", longFormat = false) {
  if (i18nState.lang === "fa") {
    const jKey = longFormat ? `${fieldPrefix}_jalali_long` : `${fieldPrefix}_jalali`;
    return book[jKey] || formatNum(book[fieldPrefix]) || "—";
  }
  return book[fieldPrefix] || "—";
}

export function escapeHtml(raw) {
  return String(raw ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

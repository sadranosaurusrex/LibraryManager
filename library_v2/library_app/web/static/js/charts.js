import { escapeHtml, formatNum, i18nState, t } from "./i18n.js";

const COVER_PALETTES = [
  ["#1e3a5f", "#d97706"],
  ["#0f766e", "#f59e0b"],
  ["#7c2d12", "#fbbf24"],
  ["#312e81", "#38bdf8"],
  ["#4c1d95", "#f472b6"],
  ["#14532d", "#a3e635"],
  ["#881337", "#fda4af"],
];

function hashString(str) {
  let h = 0;
  for (let i = 0; i < str.length; i += 1) {
    h = (h * 31 + str.charCodeAt(i)) >>> 0;
  }
  return h;
}

function wrapTitleLines(title, maxChars = 16) {
  const words = title.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return ["", ""];
  let line1 = "";
  let idx = 0;
  while (idx < words.length) {
    const candidate = line1 ? `${line1} ${words[idx]}` : words[idx];
    if (candidate.length <= maxChars || !line1) {
      line1 = candidate;
      idx += 1;
    } else {
      break;
    }
  }
  const rest = words.slice(idx).join(" ");
  const line2 = rest.length > maxChars + 2 ? `${rest.slice(0, maxChars)}…` : rest;
  return [line1.slice(0, maxChars + 2), line2];
}

export function buildCoverMarkup(book) {
  if (book.cover_path) {
    const encoded = encodeURIComponent(book.cover_path).replaceAll("%2F", "/");
    return `<img src="/api/covers/${encoded}" alt="${escapeHtml(book.book_name)}" loading="lazy" />`;
  }
  const palette = COVER_PALETTES[hashString(book.genre || book.book_name || "book") % COVER_PALETTES.length];
  const rawTitle = String(book.book_name || "");
  const [rawLine1, rawLine2] = wrapTitleLines(rawTitle, 16);
  const line1 = escapeHtml(rawLine1);
  const line2 = escapeHtml(rawLine2);
  const shortAuthor = escapeHtml(String(book.author || "").slice(0, 24));
  const spineId = escapeHtml(formatNum(book.id));

  return `
    <svg viewBox="0 0 120 170" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeHtml(rawTitle)}">
      <defs>
        <linearGradient id="g-${book.id}" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="${palette[0]}"/>
          <stop offset="100%" stop-color="#0f172a"/>
        </linearGradient>
      </defs>
      <rect width="120" height="170" rx="6" fill="url(#g-${book.id})"/>
      <rect x="0" y="0" width="10" height="170" fill="${palette[1]}" opacity="0.85"/>
      <rect x="18" y="14" width="90" height="142" rx="4" fill="none" stroke="${palette[1]}" stroke-opacity="0.45" stroke-width="1.2"/>
      <text x="63" y="64" text-anchor="middle" fill="#ffffff" font-size="11.5" font-weight="700" font-family="Vazirmatn, Tahoma, sans-serif">${line1}</text>
      <text x="63" y="82" text-anchor="middle" fill="#ffffff" font-size="10.5" font-weight="700" font-family="Vazirmatn, Tahoma, sans-serif">${line2}</text>
      <text x="63" y="122" text-anchor="middle" fill="#e2e8f0" font-size="9" font-family="Vazirmatn, Tahoma, sans-serif">${shortAuthor}</text>
      <text x="63" y="146" text-anchor="middle" fill="${palette[1]}" font-size="8.5" font-weight="700">#${spineId}</text>
    </svg>
  `;
}

export function renderStatusDonut(container, byStatus) {
  const colors = {
    Finished: "var(--teal)",
    Reading: "var(--indigo)",
    Unread: "#94a3b8",
    Dropped: "var(--rose)",
  };
  const total = byStatus.reduce((acc, item) => acc + item.count, 0);
  if (!total) {
    container.innerHTML = `<p class="section-subtitle">—</p>`;
    return;
  }

  const radius = 56;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  const segments = byStatus
    .filter((s) => s.count > 0)
    .map((s) => {
      const pct = s.count / total;
      const dash = pct * circumference;
      const seg = `<circle cx="75" cy="75" r="${radius}" fill="transparent" stroke="${colors[s.status] || "#888"}" stroke-width="20" stroke-dasharray="${dash} ${circumference - dash}" stroke-dashoffset="${-offset}" />`;
      offset += dash;
      return seg;
    })
    .join("");

  const pctMark = i18nState.lang === "fa" ? "٪" : "%";
  const legend = byStatus
    .map((s) => {
      const pct = total ? Math.round((s.count / total) * 100) : 0;
      return `
        <div class="legend-item">
          <span class="legend-dot" style="background:${colors[s.status] || "#888"}"></span>
          <span>${escapeHtml(t(`status_${s.status}`))}</span>
          <strong>${formatNum(s.count)}</strong>
          <span class="section-subtitle">(${formatNum(pct)}${pctMark})</span>
        </div>
      `;
    })
    .join("");

  container.innerHTML = `
    <div class="donut-wrap">
      <svg width="150" height="150" viewBox="0 0 150 150">
        <g transform="rotate(-90 75 75)">${segments}</g>
        <text x="75" y="72" text-anchor="middle" fill="var(--text)" font-size="18" font-weight="800">${formatNum(total)}</text>
        <text x="75" y="92" text-anchor="middle" fill="var(--text-muted)" font-size="10">${escapeHtml(t("label_books_unit"))}</text>
      </svg>
      <div class="donut-legend">${legend}</div>
    </div>
  `;
}

export function renderHorizontalBars(container, items, labelKey, countKey, fillColor = "var(--primary)") {
  if (!items.length) {
    container.innerHTML = `<p class="section-subtitle">—</p>`;
    return;
  }
  const maxCount = Math.max(...items.map((i) => i[countKey]), 1);
  container.innerHTML = `
    <div class="bar-list">
      ${items
        .map((item) => {
          const count = item[countKey];
          const width = Math.max(3, Math.round((count / maxCount) * 100));
          return `
            <div class="bar-row">
              <span class="bar-label bidi-auto" title="${escapeHtml(item[labelKey])}">${escapeHtml(item[labelKey])}</span>
              <div class="bar-track"><div class="bar-fill" style="width:${width}%;background:${fillColor}"></div></div>
              <strong>${formatNum(count)}</strong>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

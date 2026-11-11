async function requestJson(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.detail || data.error || `HTTP ${res.status}`);
    err.code = data.error || "err_unknown";
    err.field = data.field || "";
    throw err;
  }
  return data;
}

export const api = {
  getHealth: () => requestJson("/api/health"),
  getI18n: () => requestJson("/api/i18n"),
  listBooks: (params) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) {
        qs.set(k, String(v));
      }
    });
    return requestJson(`/api/books?${qs.toString()}`);
  },
  getBook: (id) => requestJson(`/api/books/${id}`),
  createBook: (payload) =>
    requestJson("/api/books", { method: "POST", body: JSON.stringify(payload) }),
  updateBook: (id, payload) =>
    requestJson(`/api/books/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  patchBook: (id, payload) =>
    requestJson(`/api/books/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteBook: (id) => requestJson(`/api/books/${id}`, { method: "DELETE" }),
  uploadCover: (id, filename, dataBase64) =>
    requestJson(`/api/books/${id}/cover`, {
      method: "POST",
      body: JSON.stringify({ filename, data_base64: dataBase64 }),
    }),
  getAnalytics: () => requestJson("/api/analytics"),
  getHygiene: () => requestJson("/api/hygiene"),
  runHygieneFix: () => requestJson("/api/hygiene/fix", { method: "POST", body: "{}" }),
  listBackups: () => requestJson("/api/backups"),
  createBackup: () => requestJson("/api/backups", { method: "POST", body: "{}" }),
  restoreBackup: (name) =>
    requestJson("/api/backups/restore", { method: "POST", body: JSON.stringify({ name }) }),
};

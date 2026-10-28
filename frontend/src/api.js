const API_ROOT = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      credentials: "same-origin",
      ...options,
      headers: {
        ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(options.headers || {}),
      },
    });
  } catch {
    throw new Error("The Python API is not reachable. Check the integration guide or open the labeled demo workspace.");
  }

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      message = body.error || body.message || body.detail || message;
    } catch {
      // The API contract normally sends JSON errors; keep a safe generic fallback.
    }
    throw new Error(message);
  }
  return response;
}

async function json(path, options) {
  return (await request(path, options)).json();
}

export const api = {
  session: () => json("/session", { method: "GET", headers: {} }),
  analyzeFile: (file, options) => {
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("options", JSON.stringify(options));
    return json("/analyze", { method: "POST", body: form, headers: {} });
  },
  analyzeUrl: (url, options) => json("/analyze-url", { method: "POST", body: JSON.stringify({ url, options }) }),
  job: (jobId) => json(`/jobs/${encodeURIComponent(jobId)}`, { method: "GET", headers: {} }),
  forecast: (settings) => json("/forecast", { method: "POST", body: JSON.stringify(settings) }),
  report: () => request("/report", { method: "POST", body: "{}" }),
  save: (name) => json("/save", { method: "POST", body: JSON.stringify({ name }) }),
  saved: () => json("/saved", { method: "GET", headers: {} }),
  savedPreview: (id) => json(`/saved/${encodeURIComponent(id)}?limit=100`, { method: "GET", headers: {} }),
  removeSaved: (id) => json(`/saved/${encodeURIComponent(id)}`, { method: "DELETE", headers: {} }),
  downloadClean: () => request("/download/clean.csv", { method: "GET", headers: {} }),
  downloadMlReady: () => request("/download/ml-ready.csv", { method: "GET", headers: {} }),
  savedCsv: (id) => request(`/saved/${encodeURIComponent(id)}/csv`, { method: "GET", headers: {} }),
};

export { API_ROOT };

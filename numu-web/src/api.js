// src/api.js

export const API_BASE = 'http://127.0.0.1:8000';

// Build query string from an object, e.g. { lesson: 5, page: 2 } -> ?lesson=5&page=2
function buildQuery(params = {}) {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== ''
  );
  if (entries.length === 0) return '';
  const searchParams = new URLSearchParams();
  for (const [key, value] of entries) {
    searchParams.append(key, value);
  }
  return `?${searchParams.toString()}`;
}

// Generic GET wrapper
async function apiGet(path, params = {}) {
  const query = buildQuery(params);
  const url = `${API_BASE}${path}${query}`;

  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`GET ${url} failed: HTTP ${res.status} – ${text}`);
  }
  return res.json();
}

// Specific helpers

export async function fetchEntries(params = {}) {
  // params can include pagination/filter later, e.g. { page: 2, lesson: 5 }
  return apiGet('/api/entries/', params);
}

export async function fetchLessons(params = {}) {
  return apiGet('/api/lessons/', params);
}

export async function fetchDiscs(params = {}) {
  return apiGet('/api/discs/', params);
}

export async function fetchLexemes(params = {}) {
  // supports ?q=, ?page=, etc.
  return apiGet('/api/lexemes/', params);
}

export async function fetchLexemeDetail(id) {
  return apiGet(`/api/lexemes/${id}/`);
}

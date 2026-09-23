const API_BASE = 'http://localhost:8000'

export async function uploadMatch(title, file) {
  const form = new FormData()
  form.append('title', title)
  form.append('file', file)
  const res = await fetch(`${API_BASE}/matches/`, { method: 'POST', body: form })
  if (!res.ok) throw new Error('Failed to upload match')
  return res.json()
}

export async function listMatches() {
  const res = await fetch(`${API_BASE}/matches/`)
  return res.json()
}

export async function listRallies(matchId) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/rallies/`)
  return res.json()
}

export async function createRally(matchId, rally) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/rallies/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rally),
  })
  if (!res.ok) throw new Error('Failed to save rally')
  return res.json()
}

export async function exportClip(matchId, rallyId) {
  const res = await fetch(
    `${API_BASE}/matches/${matchId}/rallies/${rallyId}/export-clip`,
    { method: 'POST' },
  )
  if (!res.ok) throw new Error('Failed to export clip')
  return res.json()
}

export async function buildHighlightReel(matchId, outcomes) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/highlight-reel/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ outcomes }),
  })
  if (!res.ok) throw new Error('Failed to build highlight reel')
  return res.json()
}

export function videoUrl(relativePath) {
  return `${API_BASE}/${relativePath}`
}

// --- Automatic highlight detection ---------------------------------------

async function jsonOrThrow(res, fallback) {
  if (res.ok) return res.json()
  let detail = fallback
  try {
    detail = (await res.json()).detail ?? fallback
  } catch {
    // keep the fallback message
  }
  throw new Error(typeof detail === 'string' ? detail : fallback)
}

export async function startAnalysis(matchId, settings = {}) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/analysis/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ settings }),
  })
  return jsonOrThrow(res, 'Failed to start analysis')
}

// Resolves to null if the match has never been analysed.
export async function getAnalysis(matchId) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/analysis/`)
  if (res.status === 404) return null
  return jsonOrThrow(res, 'Failed to load analysis')
}

export async function deleteHighlight(matchId, highlightId) {
  const res = await fetch(
    `${API_BASE}/matches/${matchId}/analysis/highlights/${highlightId}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error('Failed to remove highlight')
}

export async function renderAutoReel(matchId) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/analysis/reel/render`, {
    method: 'POST',
  })
  return jsonOrThrow(res, 'Failed to render reel')
}

export function formatTime(seconds) {
  const s = Math.max(0, Math.round(seconds * 10) / 10)
  const m = Math.floor(s / 60)
  return `${m}:${(s - m * 60).toFixed(1).padStart(4, '0')}`
}

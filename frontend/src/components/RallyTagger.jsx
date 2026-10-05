import { useEffect, useRef, useState } from 'react'
import { createRally, deleteRally, formatTime, listRallies, mediaUrl, reclip } from '../api.js'
import AutoHighlights from './AutoHighlights.jsx'

// Must match the backend's Outcome and Skill enums (backend/app/models.py).
const OUTCOMES = ['kill', 'ace', 'block', 'dig', 'error', 'other']
const SKILLS = ['serve', 'attack', 'set', 'pass', 'block', 'dig']
const POLL_MS = 1500

export default function RallyTagger({ match }) {
  const videoRef = useRef(null)
  const [rallies, setRallies] = useState([])
  const [markStart, setMarkStart] = useState(null)
  const [skills, setSkills] = useState([])
  const [error, setError] = useState(null)

  const refresh = async () => {
    try {
      setRallies(await listRallies(match.id))
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    refresh()
    setMarkStart(null)
    setSkills([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [match.id])

  // Clips are cut in the background: poll until none are pending.
  const cutting = rallies.some((r) => r.clip && ['pending', 'processing'].includes(r.clip.status))
  useEffect(() => {
    if (!cutting) return
    const timer = setInterval(refresh, POLL_MS)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cutting, match.id])

  const toggleSkill = (s) =>
    setSkills((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]))

  const handleMarkEnd = async (outcome) => {
    if (markStart === null) return
    setError(null)
    try {
      await createRally(match.id, {
        start: markStart,
        end: videoRef.current.currentTime,
        outcome,
        skills,
      })
      setMarkStart(null)
      setSkills([])
      refresh()
    } catch (e) {
      setError(e.message)
    }
  }

  const seek = (t) => {
    videoRef.current.currentTime = t
    videoRef.current.play()
  }

  return (
    <div>
      <h2>{match.title}</h2>
      <video
        ref={videoRef}
        src={mediaUrl(match.video_url)}
        controls
        style={{ width: '100%', maxWidth: 640 }}
      />

      <div style={{ margin: '1rem 0', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <button onClick={() => setMarkStart(videoRef.current.currentTime)}>Mark rally start</button>
        {markStart !== null && (
          <>
            <span>start = {markStart.toFixed(1)}s — skills:</span>
            {SKILLS.map((s) => (
              <label key={s} style={{ whiteSpace: 'nowrap' }}>
                <input type="checkbox" checked={skills.includes(s)} onChange={() => toggleSkill(s)} /> {s}
              </label>
            ))}
            <span>— tag the end:</span>
            {OUTCOMES.map((o) => (
              <button key={o} onClick={() => handleMarkEnd(o)}>
                {o}
              </button>
            ))}
          </>
        )}
        {error && <span>{error}</span>}
      </div>

      <AutoHighlights match={match} videoRef={videoRef} />

      <h3>Tagged rallies</h3>
      <ul style={{ paddingLeft: '1.2rem' }}>
        {rallies.map((r) => (
          <li key={r.id} style={{ marginBottom: '0.4rem' }}>
            <button onClick={() => seek(r.start)} title="Jump to this rally">
              {formatTime(r.start)}–{formatTime(r.end)}
            </button>{' '}
            {r.outcome}
            {r.skills.length > 0 && ` (${r.skills.join(', ')})`}{' '}
            {r.clip?.status === 'ready' && (
              <a href={mediaUrl(r.clip.url)} target="_blank" rel="noreferrer">clip</a>
            )}
            {['pending', 'processing'].includes(r.clip?.status) && <span>cutting clip…</span>}
            {r.clip?.status === 'failed' && (
              <>
                <span title={r.clip.error}>clip failed</span>{' '}
                <button onClick={async () => { await reclip(r.id); refresh() }}>Retry</button>
              </>
            )}{' '}
            <button onClick={async () => { await deleteRally(r.id); refresh() }} title="Delete this rally">
              ✕
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

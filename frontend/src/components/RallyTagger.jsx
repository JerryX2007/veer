import { useEffect, useRef, useState } from 'react'
import { createRally, exportClip, listRallies, videoUrl } from '../api.js'
import AutoHighlights from './AutoHighlights.jsx'

const OUTCOMES = ['kill', 'ace', 'error', 'block', 'dig', 'serve', 'attack']

export default function RallyTagger({ match }) {
  const videoRef = useRef(null)
  const [rallies, setRallies] = useState([])
  const [markStart, setMarkStart] = useState(null)

  const refresh = async () => {
    setRallies(await listRallies(match.id))
  }

  useEffect(() => {
    refresh()
    setMarkStart(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [match.id])

  const handleMarkStart = () => {
    setMarkStart(videoRef.current.currentTime)
  }

  const handleMarkEnd = async (outcome) => {
    if (markStart === null) return
    await createRally(match.id, {
      start_time: markStart,
      end_time: videoRef.current.currentTime,
      outcome,
    })
    setMarkStart(null)
    refresh()
  }

  const handleExport = async (rallyId) => {
    await exportClip(match.id, rallyId)
    refresh()
  }

  return (
    <div>
      <h2>{match.title}</h2>
      <video
        ref={videoRef}
        src={videoUrl(match.video_path)}
        controls
        style={{ width: '100%', maxWidth: 640 }}
      />

      <div style={{ margin: '1rem 0', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <button onClick={handleMarkStart}>Mark rally start</button>
        {markStart !== null && (
          <>
            <span>start = {markStart.toFixed(1)}s — tag the end:</span>
            {OUTCOMES.map((o) => (
              <button key={o} onClick={() => handleMarkEnd(o)}>
                {o}
              </button>
            ))}
          </>
        )}
      </div>

      <AutoHighlights match={match} videoRef={videoRef} />

      <h3>Tagged rallies</h3>
      <ul style={{ paddingLeft: '1.2rem' }}>
        {rallies.map((r) => (
          <li key={r.id} style={{ marginBottom: '0.4rem' }}>
            {r.start_time.toFixed(1)}s–{r.end_time.toFixed(1)}s: {r.outcome}{' '}
            {r.clip_path ? (
              <span>(clip exported)</span>
            ) : (
              <button onClick={() => handleExport(r.id)}>Export clip</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

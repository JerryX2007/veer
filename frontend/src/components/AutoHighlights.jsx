import { useEffect, useRef, useState } from 'react'
import {
  deleteHighlight,
  formatTime,
  getAnalysis,
  renderAutoReel,
  startAnalysis,
  videoUrl,
} from '../api.js'

const POLL_MS = 2000
// Playback crosses a clip's end by well under this between timeupdate events;
// anything further away is the viewer seeking.
const SEEK_TOLERANCE_S = 1

// Detect highlights automatically, list them as timestamps, and play the
// reel (every highlighted rally, serve to end) by seeking the source video.
export default function AutoHighlights({ match, videoRef }) {
  const [analysis, setAnalysis] = useState(null)
  const [error, setError] = useState(null)
  const [playingSegment, setPlayingSegment] = useState(null)
  const [rendered, setRendered] = useState(null)
  const [rendering, setRendering] = useState(false)
  const reelRef = useRef(null) // { segments, index } while the reel plays

  const running = analysis && ['pending', 'running'].includes(analysis.status)

  const refresh = async () => {
    try {
      setAnalysis(await getAnalysis(match.id))
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    setAnalysis(null)
    setError(null)
    setRendered(null)
    stopReel()
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [match.id])

  useEffect(() => {
    if (!running) return
    const timer = setInterval(refresh, POLL_MS)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, match.id])

  // While the reel plays, jump to the next segment when one ends.
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const onTimeUpdate = () => {
      const reel = reelRef.current
      if (!reel) return
      const segment = reel.segments[reel.index]
      const t = video.currentTime
      if (t < segment.start - SEEK_TOLERANCE_S || t > segment.end + SEEK_TOLERANCE_S) {
        stopReel() // the viewer scrubbed elsewhere: leave reel mode
        return
      }
      if (t < segment.end) return
      if (reel.index + 1 < reel.segments.length) {
        reel.index += 1
        setPlayingSegment(reel.index)
        video.currentTime = reel.segments[reel.index].start
      } else {
        video.pause()
        stopReel()
      }
    }
    video.addEventListener('timeupdate', onTimeUpdate)
    return () => video.removeEventListener('timeupdate', onTimeUpdate)
  }, [videoRef])

  function stopReel() {
    reelRef.current = null
    setPlayingSegment(null)
  }

  const seek = (time, play = false) => {
    stopReel()
    const video = videoRef.current
    video.currentTime = time
    if (play) video.play()
  }

  const handleStart = async () => {
    setError(null)
    setRendered(null)
    try {
      await startAnalysis(match.id)
      await refresh()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleReject = async (highlightId) => {
    await deleteHighlight(match.id, highlightId)
    setRendered(null)
    refresh()
  }

  const handlePlayReel = () => {
    const segments = analysis.reel.segments
    reelRef.current = { segments, index: 0 }
    setPlayingSegment(0)
    videoRef.current.currentTime = segments[0].start
    videoRef.current.play()
  }

  const handleRender = async () => {
    setRendering(true)
    setError(null)
    try {
      setRendered(await renderAutoReel(match.id))
    } catch (e) {
      setError(e.message)
    } finally {
      setRendering(false)
    }
  }

  const reel = analysis?.reel
  const highlighted = analysis?.rallies?.filter((r) => r.highlights.length > 0) ?? []

  return (
    <section style={{ margin: '1.5rem 0' }}>
      <h3>Automatic highlights</h3>

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <button onClick={handleStart} disabled={running}>
          {analysis ? 'Re-run detection' : 'Detect highlights'}
        </button>
        {running && <span>Analysing… {Math.round(analysis.progress * 100)}%</span>}
        {analysis?.status === 'failed' && <span>Analysis failed: {analysis.error}</span>}
        {error && <span>{error}</span>}
      </div>

      {analysis?.status === 'done' && (
        <>
          <p style={{ opacity: 0.8 }}>
            Found {analysis.rallies.length} rallies, {highlighted.length} with highlights.
            {analysis.diagnostics && !analysis.diagnostics.scale_calibrated &&
              ' (Ball tracking was patchy, so speeds and heights are rough.)'}
          </p>

          {highlighted.length === 0 && <p>No highlights found in this match.</p>}
          <ul style={{ paddingLeft: '1.2rem' }}>
            {highlighted.map((rally) => (
              <li key={rally.id} style={{ marginBottom: '0.6rem' }}>
                <button onClick={() => seek(rally.start_time, true)}>
                  ▶ Rally {rally.index + 1}
                </button>{' '}
                {formatTime(rally.start_time)}–{formatTime(rally.end_time)}
                <ul style={{ paddingLeft: '1.2rem' }}>
                  {rally.highlights.map((h) => (
                    <li key={h.id}>
                      <button onClick={() => seek(h.time)} title="Jump to this moment">
                        {formatTime(h.time)}
                      </button>{' '}
                      <strong>{h.label}</strong> ({h.score.toFixed(2)}): {h.description}{' '}
                      <button onClick={() => handleReject(h.id)} title="Not a highlight: remove it">
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>

          {reel && reel.segments.length > 0 && (
            <>
              <h4>
                Highlight reel: {reel.segments.length} clip(s), {formatTime(reel.duration)}
              </h4>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                {playingSegment === null ? (
                  <button onClick={handlePlayReel}>▶ Play reel</button>
                ) : (
                  <>
                    <button onClick={() => { videoRef.current.pause(); stopReel() }}>
                      ■ Stop reel
                    </button>
                    <span>
                      Clip {playingSegment + 1} of {reel.segments.length}
                    </span>
                  </>
                )}
                <button onClick={handleRender} disabled={rendering}>
                  {rendering ? 'Rendering…' : 'Render reel to MP4'}
                </button>
                {rendered && (
                  <a href={videoUrl(rendered.reel_path)} target="_blank" rel="noreferrer">
                    Open rendered reel
                  </a>
                )}
              </div>
              <details style={{ marginTop: '0.5rem' }}>
                <summary>Timestamps (text)</summary>
                <pre style={{ whiteSpace: 'pre-wrap' }}>{reel.text}</pre>
              </details>
            </>
          )}
        </>
      )}
    </section>
  )
}

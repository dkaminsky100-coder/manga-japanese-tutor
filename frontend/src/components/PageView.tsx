import { useEffect, useState } from 'react'
import { getAnalysis, pageImageUrl, type PageAnalysis, type PageInfo, type TextBlock } from '../api/client'
import { bboxToPercent } from '../lib/coords'
import Bubble from './Bubble'

const POLL_MS = 1000

interface Props {
  page: PageInfo
  showBoxes: boolean
}

export default function PageView({ page, showBoxes }: Props) {
  const [analysis, setAnalysis] = useState<PageAnalysis | null>(null)
  const [fetchError, setFetchError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    // No state reset needed: Reader mounts PageView with key={page.id}, so each page starts fresh.
    const poll = async () => {
      try {
        const a = await getAnalysis(page.id)
        if (cancelled) return
        setAnalysis(a)
        if (a.status === 'done' || a.status === 'error') return
      } catch (e) {
        if (cancelled) return
        setFetchError(e instanceof Error ? e.message : 'Request failed')
      }
      timer = setTimeout(poll, POLL_MS)
    }
    poll()

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [page.id])

  /** Swap in a block the user just corrected (or reset) without refetching the page. */
  const replaceBlock = (updated: TextBlock) =>
    setAnalysis((a) => a && { ...a, blocks: a.blocks.map((b) => (b.id === updated.id ? updated : b)) })

  const status =
    fetchError ??
    (analysis?.status === 'error'
      ? `Analysis failed: ${analysis.error}`
      : analysis?.status === 'done'
        ? `${analysis.blocks.length} text blocks${analysis.upscaled ? ' · upscaled' : ''}`
        : 'Reading page…')

  return (
    <div className="page-view">
      <div className="page-status">{status}</div>
      {/* Overlays are positioned in % of the natural page size inside this wrapper, so they
          stay glued to the image however it is scaled. */}
      <div className="page-frame">
        <img src={pageImageUrl(page.id)} width={page.width} height={page.height} alt="" draggable={false} />
        {analysis?.blocks.map((b, i) => {
          const r = bboxToPercent(b.bbox, page.width, page.height)
          return <Bubble key={b.id} block={b} rect={r} label={showBoxes ? i + 1 : null} onChange={replaceBlock} />
        })}
      </div>
      {showBoxes && analysis?.status === 'done' && (
        <ol className="block-list">
          {analysis.blocks.map((b) => (
            <li key={b.id}>{b.text}</li>
          ))}
        </ol>
      )}
    </div>
  )
}

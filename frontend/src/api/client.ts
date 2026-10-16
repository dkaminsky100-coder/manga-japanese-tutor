export interface ChapterSummary {
  id: number
  title: string
  created_at: string
  page_count: number
}

export interface PageInfo {
  id: number
  idx: number
  width: number
  height: number
}

export interface Chapter {
  id: number
  title: string
  pages: PageInfo[]
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const listChapters = () => fetch('/api/chapters').then(json<ChapterSummary[]>)

export const getChapter = (id: number) => fetch(`/api/chapters/${id}`).then(json<Chapter>)

export const pageImageUrl = (pageId: number) => `/api/pages/${pageId}/image`

export interface TextBlock {
  id: number
  /** [x1, y1, x2, y2] in the page image's natural pixels */
  bbox: [number, number, number, number]
  vertical: boolean
  conf: number
  text: string
}

export interface PageAnalysis {
  status: 'none' | 'pending' | 'running' | 'done' | 'error'
  error: string | null
  upscaled: boolean
  detect_ms: number | null
  ocr_ms: number | null
  blocks: TextBlock[]
}

/** Starts analysis on first call (and prefetches the next pages); poll until status is done/error. */
export const getAnalysis = (pageId: number) => fetch(`/api/pages/${pageId}/analysis`).then(json<PageAnalysis>)

export function uploadChapter(title: string, files: File[]) {
  const form = new FormData()
  form.append('title', title)
  files.forEach((f) => form.append('files', f))
  return fetch('/api/chapters', { method: 'POST', body: form }).then(
    json<{ id: number; title: string; page_count: number }>,
  )
}

export async function deleteChapter(id: number) {
  const res = await fetch(`/api/chapters/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(res.statusText)
}

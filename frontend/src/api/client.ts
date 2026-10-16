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

/** A piece of a word; `ruby` is the furigana to show above it (null for kana that needs none). */
export interface RubySegment {
  text: string
  ruby: string | null
}

export interface DictSense {
  pos: string[]
  glosses: string[]
  misc: string[]
}

export interface DictEntry {
  id: number
  common: boolean
  kanji: string[]
  kana: string[]
  senses: DictSense[]
  more_senses: number
}

export interface WordToken {
  surface: string
  /** hiragana */
  reading: string
  dictionary_form: string
  /** Sudachi top-level POS, e.g. 動詞 */
  pos: string
  /** English label, e.g. "verb" */
  pos_label: string
  pos_detail: string
  conj_type: string
  conj_form: string
  ruby: RubySegment[]
  entries: DictEntry[]
  /** Finer split of a compound word, when there is one */
  parts: Omit<WordToken, 'entries' | 'parts'>[]
}

/** A multi-token dictionary phrase, e.g. 気 + を + つけろ -> 気をつける. start/end index into `tokens` (end exclusive). */
export interface Compound {
  start: number
  end: number
  text: string
  entries: DictEntry[]
}

export interface TextBlock {
  id: number
  /** [x1, y1, x2, y2] in the page image's natural pixels */
  bbox: [number, number, number, number]
  vertical: boolean
  conf: number
  text: string
  tokens: WordToken[]
  compounds: Compound[]
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

export interface Translation {
  translation: string
  model: string
  cached: boolean
}

/** Rough local machine translation of one block (cached server-side; the first call loads the model). */
export const translateBlock = (blockId: number) =>
  fetch(`/api/blocks/${blockId}/translate`, { method: 'POST' }).then(json<Translation>)

/** UI state of a block's translation request. */
export type TranslationState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'done'; text: string }
  | { status: 'error'; message: string }

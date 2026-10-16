import type { TextBlock } from '../api/client'

/** Tooltip body. For now just the recognized text; furigana, definitions and grammar come next. */
export default function BubbleTooltip({ block, pinned }: { block: TextBlock; pinned: boolean }) {
  return (
    <div className="tooltip" role="tooltip">
      <p className="tooltip-text" lang="ja">
        {block.text}
      </p>
      <p className="tooltip-hint">{pinned ? 'Pinned · click the bubble or press Esc to close' : 'Click to pin'}</p>
    </div>
  )
}

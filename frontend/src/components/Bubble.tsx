import { useState } from 'react'
import {
  FloatingPortal,
  autoUpdate,
  flip,
  offset,
  safePolygon,
  shift,
  useDismiss,
  useFloating,
  useHover,
  useInteractions,
  type OpenChangeReason,
} from '@floating-ui/react'
import { translateBlock, type TextBlock, type TranslationState } from '../api/client'
import type { PercentRect } from '../lib/coords'
import BubbleTooltip from './BubbleTooltip'

interface Props {
  block: TextBlock
  rect: PercentRect
  /** 1-based position, shown only in the debug view */
  label: number | null
}

/**
 * One detected text block: an invisible hit-box over the page that shows a tooltip on
 * hover and keeps it open ("pins" it) when clicked.
 */
export default function Bubble({ block, rect, label }: Props) {
  const [hoverOpen, setHoverOpen] = useState(false)
  const [pinned, setPinned] = useState(false)
  const open = hoverOpen || pinned
  // Kept here, not in the tooltip, so a translation survives the tooltip closing and reopening.
  const [translation, setTranslation] = useState<TranslationState>({ status: 'idle' })

  function translate() {
    if (translation.status === 'loading') return
    setTranslation({ status: 'loading' })
    translateBlock(block.id)
      .then((r) => setTranslation({ status: 'done', text: r.translation }))
      .catch((e) => setTranslation({ status: 'error', message: e instanceof Error ? e.message : 'Translation failed' }))
  }

  const { refs, floatingStyles, context } = useFloating({
    open,
    onOpenChange: (next: boolean, _event?: Event, reason?: OpenChangeReason) => {
      setHoverOpen(next)
      // Moving the mouse away (reasons 'hover' / 'safe-polygon') only closes a hover;
      // Escape or clicking elsewhere also unpins.
      if (!next && (reason === 'escape-key' || reason === 'outside-press')) setPinned(false)
    },
    placement: 'bottom',
    middleware: [offset(8), flip({ padding: 8 }), shift({ padding: 8 })],
    whileElementsMounted: autoUpdate,
  })

  const hover = useHover(context, { handleClose: safePolygon(), delay: { open: 60, close: 120 } })
  const dismiss = useDismiss(context)
  const { getReferenceProps, getFloatingProps } = useInteractions([hover, dismiss])

  return (
    <>
      <div
        ref={refs.setReference}
        className={`block-box${label !== null ? ' debug' : ''}${open ? ' active' : ''}${pinned ? ' pinned' : ''}`}
        style={{ left: `${rect.left}%`, top: `${rect.top}%`, width: `${rect.width}%`, height: `${rect.height}%` }}
        {...getReferenceProps({ onClick: () => setPinned((p) => !p) })}
      >
        {label !== null && <span className="block-label">{label}</span>}
      </div>
      {open && (
        <FloatingPortal>
          <div ref={refs.setFloating} style={floatingStyles} className="tooltip-wrap" {...getFloatingProps()}>
            <BubbleTooltip block={block} pinned={pinned} translation={translation} onTranslate={translate} />
          </div>
        </FloatingPortal>
      )}
    </>
  )
}

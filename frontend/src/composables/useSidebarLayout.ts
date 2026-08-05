import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const LEFT_KEY = 'ds.layout.sideLeft'
const RIGHT_KEY = 'ds.layout.sideRight'

const LEFT_DEFAULT = 248
const RIGHT_DEFAULT = 288
const LEFT_MIN = 188
const LEFT_MAX = 420
const RIGHT_MIN = 220
const RIGHT_MAX = 520

function loadWidth(key: string, fallback: number, min: number, max: number): number {
  try {
    const n = Number(localStorage.getItem(key))
    if (Number.isFinite(n) && n >= min && n <= max) return Math.round(n)
  } catch {
    /* ignore */
  }
  return fallback
}

/** Chat layout: resizable left/right sidebars with persisted widths. */
export function useSidebarLayout() {
  const sideLeft = ref(loadWidth(LEFT_KEY, LEFT_DEFAULT, LEFT_MIN, LEFT_MAX))
  const sideRight = ref(loadWidth(RIGHT_KEY, RIGHT_DEFAULT, RIGHT_MIN, RIGHT_MAX))
  const resizing = ref<'left' | 'right' | null>(null)
  /** Below this breakpoint overview stacks; skip custom columns + resizers. */
  const layoutNarrow = ref(false)

  const layoutStyle = computed(() => {
    if (layoutNarrow.value) return undefined
    return {
      gridTemplateColumns: `${sideLeft.value}px 6px minmax(0, 1fr) 6px ${sideRight.value}px`,
    }
  })

  let startX = 0
  let startW = 0

  function onMove(e: MouseEvent) {
    if (!resizing.value) return
    const dx = e.clientX - startX
    if (resizing.value === 'left') {
      sideLeft.value = Math.min(LEFT_MAX, Math.max(LEFT_MIN, Math.round(startW + dx)))
    } else {
      sideRight.value = Math.min(RIGHT_MAX, Math.max(RIGHT_MIN, Math.round(startW - dx)))
    }
  }

  function onUp() {
    if (!resizing.value) return
    try {
      localStorage.setItem(LEFT_KEY, String(sideLeft.value))
      localStorage.setItem(RIGHT_KEY, String(sideRight.value))
    } catch {
      /* ignore */
    }
    resizing.value = null
    document.body.classList.remove('is-col-resizing')
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }

  function startResize(which: 'left' | 'right', e: MouseEvent) {
    if (layoutNarrow.value) return
    e.preventDefault()
    resizing.value = which
    startX = e.clientX
    startW = which === 'left' ? sideLeft.value : sideRight.value
    document.body.classList.add('is-col-resizing')
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  let mq: MediaQueryList | null = null
  function syncNarrow() {
    layoutNarrow.value = mq?.matches ?? false
  }

  onMounted(() => {
    mq = window.matchMedia('(max-width: 1280px)')
    syncNarrow()
    mq.addEventListener('change', syncNarrow)
  })

  onBeforeUnmount(() => {
    mq?.removeEventListener('change', syncNarrow)
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
    document.body.classList.remove('is-col-resizing')
  })

  return {
    sideLeft,
    sideRight,
    resizing,
    layoutNarrow,
    layoutStyle,
    startResize,
  }
}

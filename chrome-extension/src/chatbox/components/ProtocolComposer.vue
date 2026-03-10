<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { getProtocolByMode, protocolRegistry, protocolTokenNodes, detectProtocolByTextBeforeCursor } from '@/chatbox/protocols/registry.js'
import { normalizeString } from '@/chatbox/protocols/common.js'

const DEFAULT_PROTOCOL_MODE = 'skill'

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  placeholder: {
    type: String,
    default: '输入消息',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  canSubmit: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['update:modelValue', 'submit'])

// 通用面板状态机：协议类型、query、触发替换范围、键盘高亮索引。
const panelVisible = ref(false)
const panelMode = ref(DEFAULT_PROTOCOL_MODE)
const panelQuery = ref('')
const panelRange = ref(null)
const activeIndex = ref(-1)
const panelHintVisible = ref(false)
const panelHintText = ref('')
let panelHintTimer = null

// 当用户通过按钮手动关闭某个协议面板时，短暂抑制“光标停在触发符上导致的自动重开”。
// 抑制条件只绑定当前编辑器文本快照；文本一旦变化，抑制立即失效。
const autoOpenSuppression = reactive({
  mode: '',
  text: '',
})

function clearAutoOpenSuppression() {
  autoOpenSuppression.mode = ''
  autoOpenSuppression.text = ''
}

function setAutoOpenSuppression(mode) {
  autoOpenSuppression.mode = normalizeString(mode)
  autoOpenSuppression.text = serializeEditorText()
}

function isAutoOpenSuppressed(mode) {
  const suppressedMode = normalizeString(autoOpenSuppression.mode)
  if (!suppressedMode || suppressedMode !== normalizeString(mode)) return false

  const currentText = serializeEditorText()
  if (currentText !== autoOpenSuppression.text) {
    clearAutoOpenSuppression()
    return false
  }
  return true
}

const catalogStateByMode = reactive(
  protocolRegistry.reduce((state, protocol) => {
    state[protocol.mode] = {
      items: [],
      loaded: false,
      loading: false,
      error: '',
    }
    return state
  }, {}),
)

const activeProtocol = computed(() => getProtocolByMode(panelMode.value))
const activeCatalogState = computed(() => catalogStateByMode[activeProtocol.value.mode])

const visibleOptions = computed(() => {
  const protocol = activeProtocol.value
  const catalogState = activeCatalogState.value
  const sourceItems = Array.isArray(catalogState?.items) ? catalogState.items : []
  const query = normalizeString(panelQuery.value)

  return sourceItems
    .map((item) => protocol.toOption(item))
    .filter((option) => option)
    .filter((option) => protocol.filterOption(option, query))
})

function isOptionSelectable(option) {
  return activeProtocol.value.isSelectable(option)
}

const hasSelectableOption = computed(() => visibleOptions.value.some((option) => isOptionSelectable(option)))

function normalizeActiveIndex() {
  const options = visibleOptions.value
  if (!options.length || !hasSelectableOption.value) {
    activeIndex.value = -1
    return
  }

  const currentOption = options[activeIndex.value]
  if (activeIndex.value >= 0 && currentOption && isOptionSelectable(currentOption)) return
  activeIndex.value = options.findIndex((option) => isOptionSelectable(option))
}

function getNextSelectableIndex(step) {
  const options = visibleOptions.value
  if (!options.length || !hasSelectableOption.value) return -1

  let next = activeIndex.value
  for (let i = 0; i < options.length; i += 1) {
    next = (next + step + options.length) % options.length
    if (isOptionSelectable(options[next])) {
      return next
    }
  }
  return -1
}

const editor = useEditor({
  extensions: [
    StarterKit.configure({
      heading: false,
      bulletList: false,
      orderedList: false,
      listItem: false,
      blockquote: false,
      codeBlock: false,
      horizontalRule: false,
      hardBreak: true,
      history: true,
    }),
    Placeholder.configure({
      placeholder: props.placeholder,
      emptyEditorClass: 'is-empty',
      showOnlyWhenEditable: false,
    }),
    ...protocolTokenNodes,
  ],
  autofocus: false,
  editable: !props.disabled,
  content: '',
  onUpdate: () => {
    emitSerializedPrompt()
    updatePanelStateByCursor()
  },
  editorProps: {
    attributes: {
      class: 'protocol-composer-editor skill-composer-editor',
    },
    handleKeyDown: (_view, event) => {
      if (props.disabled) return false

      if (panelVisible.value && visibleOptions.value.length > 0) {
        if (event.key === 'ArrowDown') {
          event.preventDefault()
          const nextIndex = getNextSelectableIndex(1)
          if (nextIndex >= 0) activeIndex.value = nextIndex
          return true
        }
        if (event.key === 'ArrowUp') {
          event.preventDefault()
          const nextIndex = getNextSelectableIndex(-1)
          if (nextIndex >= 0) activeIndex.value = nextIndex
          return true
        }
        if (event.key === 'Enter' || event.key === 'Tab') {
          event.preventDefault()
          const target = visibleOptions.value[activeIndex.value]
          insertSelectedOption(target)
          return true
        }
        if (event.key === 'Escape') {
          event.preventDefault()
          closePanel()
          return true
        }
      }

      if (event.key === 'Enter' && !event.shiftKey) {
        if (!props.canSubmit) return false
        event.preventDefault()
        emit('submit')
        return true
      }
      return false
    },
  },
})

watch(
  () => props.disabled,
  (disabled) => {
    if (!editor.value) return
    editor.value.setEditable(!disabled)
  },
)

watch(
  () => props.modelValue,
  (nextValue) => {
    if (!editor.value) return
    const current = serializeEditorText()
    const incoming = String(nextValue || '')
    if (incoming === current) return
    if (!incoming.trim()) {
      editor.value.commands.clearContent(true)
      closePanel()
    }
  },
)

watch([visibleOptions, panelVisible, panelMode], () => {
  if (!panelVisible.value) return
  normalizeActiveIndex()
})

async function ensureProtocolCatalogLoaded(protocol, options = {}) {
  const { forceReload = false } = options
  const catalogState = catalogStateByMode[protocol.mode]
  if (!catalogState) return

  if (catalogState.loading) return
  if (!forceReload && catalogState.loaded) return

  catalogState.loading = true
  catalogState.error = ''

  try {
    const items = await protocol.loadItems()
    catalogState.items = Array.isArray(items) ? items : []
    catalogState.loaded = true
  } catch (error) {
    catalogState.items = []
    catalogState.loaded = false
    catalogState.error = String(error?.message || '加载失败')
  } finally {
    catalogState.loading = false
  }
}

const composerRootRef = ref(null)

function handleGlobalPointerDown(event) {
  if (!panelVisible.value) return
  const root = composerRootRef.value
  if (!root) return

  const path = typeof event.composedPath === 'function' ? event.composedPath() : null
  const clickedTriggerButton = Array.isArray(path)
    ? path.some((el) => el && el.dataset && el.dataset.protocolTriggerBtn === '1')
    : false
  if (clickedTriggerButton) return

  const targetElement = event.target instanceof Element ? event.target : null
  if (targetElement?.closest?.('[data-protocol-trigger-btn="1"]')) return

  const isInside = Array.isArray(path) ? path.includes(root) : root.contains(event.target)
  if (isInside) return

  closePanel()
}

function showPanelHint(hintText) {
  panelHintText.value = hintText
  panelHintVisible.value = true

  if (panelHintTimer) {
    clearTimeout(panelHintTimer)
    panelHintTimer = null
  }

  panelHintTimer = setTimeout(() => {
    panelHintVisible.value = false
    panelHintTimer = null
  }, 5000)
}

function serializeEditorText() {
  const instance = editor.value
  if (!instance) return ''
  return instance.getText({ blockSeparator: '\n' }).replace(/\u00a0/g, ' ')
}

function appendDisplaySegment(segments, segment) {
  if (!segment) return
  if (segment.type !== 'text') {
    segments.push(segment)
    return
  }
  const text = String(segment.text || '')
  if (!text) return
  const lastSegment = segments[segments.length - 1]
  if (lastSegment && lastSegment.type === 'text') {
    lastSegment.text = `${lastSegment.text}${text}`
    return
  }
  segments.push({ type: 'text', text })
}

function buildDisplaySegments() {
  const instance = editor.value
  if (!instance) return []

  const segments = []
  instance.state.doc.descendants((node) => {
    if (node.type.name === 'text') {
      appendDisplaySegment(segments, { type: 'text', text: node.text || '' })
      return
    }
    if (node.type.name === 'hardBreak') {
      appendDisplaySegment(segments, { type: 'text', text: '\n' })
      return
    }
    if (node.type.name === 'protocolSkillToken') {
      appendDisplaySegment(segments, {
        type: 'skill',
        name: normalizeString(node.attrs?.name),
      })
      return
    }
    if (node.type.name === 'protocolNodeToken') {
      const nodeId = normalizeString(node.attrs?.nodeId)
      const label = normalizeString(node.attrs?.label || nodeId)
      appendDisplaySegment(segments, {
        type: 'node',
        node_id: nodeId,
        label,
      })
    }
  })

  if (!segments.length) {
    return [{ type: 'text', text: '' }]
  }
  return segments
}

function buildSnapshot() {
  return {
    prompt: serializeEditorText(),
    displaySegments: buildDisplaySegments(),
  }
}

function emitSerializedPrompt() {
  emit('update:modelValue', serializeEditorText())
}

function closePanel() {
  panelVisible.value = false
  panelMode.value = DEFAULT_PROTOCOL_MODE
  panelQuery.value = ''
  panelRange.value = null
  activeIndex.value = -1
  panelHintVisible.value = false
  panelHintText.value = ''
}

// 基于“光标前文本”自动识别当前触发的是哪种协议（/ 或 #）。
function updatePanelStateByCursor() {
  const instance = editor.value
  if (!instance || props.disabled) {
    closePanel()
    return
  }

  const suppressMode = normalizeString(autoOpenSuppression.mode)
  if (suppressMode && autoOpenSuppression.text !== serializeEditorText()) {
    clearAutoOpenSuppression()
  }

  const selection = instance.state.selection
  if (!selection.empty) {
    closePanel()
    return
  }

  const { $from, from } = selection
  if (!$from.parent.isTextblock) {
    closePanel()
    return
  }

  const textBeforeCursor = $from.parent.textBetween(0, $from.parentOffset, '\n', '\0')
  const matched = detectProtocolByTextBeforeCursor(textBeforeCursor)

  if (!matched) {
    closePanel()
    return
  }

  if (!panelVisible.value && isAutoOpenSuppressed(matched.protocol.mode)) {
    closePanel()
    return
  }

  const wasSamePanel = panelVisible.value && panelMode.value === matched.protocol.mode
  panelMode.value = matched.protocol.mode
  panelQuery.value = matched.query
  panelRange.value = {
    from: from - matched.tokenLength,
    to: from,
  }
  panelVisible.value = true
  activeIndex.value = -1

  if (!wasSamePanel) {
    ensureProtocolCatalogLoaded(matched.protocol, { forceReload: matched.protocol.reloadOnOpen === true })
  }

  normalizeActiveIndex()
}

function insertSelectedOption(option) {
  if (!option || !panelRange.value) return

  const protocol = activeProtocol.value
  if (!protocol.isSelectable(option)) return

  const attrs = protocol.toInsertAttrs(option)
  if (!attrs) return

  editor.value
    .chain()
    .focus()
    .deleteRange(panelRange.value)
    .insertContent([
      { type: protocol.tokenNodeName, attrs },
      { type: 'text', text: ' ' },
    ])
    .run()

  closePanel()
  emitSerializedPrompt()
}

function onOptionClick(option) {
  insertSelectedOption(option)
}

function onEditorClick() {
  ensureProtocolCatalogLoaded(getProtocolByMode(DEFAULT_PROTOCOL_MODE))
  updatePanelStateByCursor()
}

async function triggerProtocolFromButton(mode) {
  if (props.disabled) return

  const protocol = getProtocolByMode(mode)
  const instance = editor.value
  if (!instance) return

  // 同一协议按钮二次点击：直接关闭，形成开/关切换体验。
  if (panelVisible.value && panelMode.value === protocol.mode) {
    setAutoOpenSuppression(protocol.mode)
    closePanel()
    return
  }

  // 显式按钮触发优先级高于自动抑制，允许用户直接再次打开面板。
  clearAutoOpenSuppression()

  instance.commands.focus('end')
  await nextTick()
  updatePanelStateByCursor()

  // 未命中面板时，模拟输入 triggerChar，复用同一触发链路。
  if (!(panelVisible.value && panelMode.value === protocol.mode)) {
    const currentText = serializeEditorText()
    const needLeadingSpace = !!currentText && !/\s$/.test(currentText)
    instance
      .chain()
      .focus('end')
      .insertContent(needLeadingSpace ? ` ${protocol.triggerChar}` : protocol.triggerChar)
      .run()
    updatePanelStateByCursor()
  }

  if (panelVisible.value && panelMode.value === protocol.mode) {
    await ensureProtocolCatalogLoaded(protocol, { forceReload: protocol.reloadOnOpen === true })
    showPanelHint(protocol.panel.hintText)
  }
}

async function triggerSlashFromButton() {
  await triggerProtocolFromButton('skill')
}

async function triggerHashFromButton() {
  await triggerProtocolFromButton('node')
}

function focusEditor() {
  if (!editor.value) return
  editor.value.commands.focus('end')
  ensureProtocolCatalogLoaded(getProtocolByMode(DEFAULT_PROTOCOL_MODE))
}

function clear() {
  if (!editor.value) return
  editor.value.commands.clearContent(true)
  closePanel()
  emitSerializedPrompt()
}

defineExpose({
  buildSnapshot,
  clear,
  focusEditor,
  triggerProtocolFromButton,
  triggerSlashFromButton,
  triggerHashFromButton,
})

onMounted(() => {
  window.addEventListener('pointerdown', handleGlobalPointerDown, true)
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', handleGlobalPointerDown, true)
  if (panelHintTimer) {
    clearTimeout(panelHintTimer)
    panelHintTimer = null
  }
  if (editor.value) {
    editor.value.destroy()
  }
})
</script>

<template>
  <div ref="composerRootRef" class="protocol-composer skill-composer" @click="onEditorClick">
    <EditorContent :editor="editor" />

    <div
      v-if="panelVisible"
      class="protocol-panel skill-slash-panel"
      :class="[`protocol-panel--${activeProtocol.mode}`, activeProtocol.panel.sectionClass]"
    >
      <div v-if="panelHintVisible" class="protocol-panel-hint skill-slash-hint">
        {{ panelHintText }}
      </div>

      <div class="protocol-section skill-slash-section" :class="activeProtocol.panel.sectionClass">
        <div class="protocol-header skill-slash-header">
          <span class="protocol-header-title skill-slash-header-title">{{ activeProtocol.panel.title }}</span>
          <span class="protocol-header-badge skill-slash-header-badge">{{ activeProtocol.panel.badge }}</span>
        </div>

        <div v-if="activeCatalogState.loading" class="protocol-empty skill-slash-empty">
          {{ activeProtocol.panel.loadingText }}
        </div>
        <div v-else-if="activeCatalogState.error" class="protocol-empty skill-slash-empty">
          {{ activeCatalogState.error }}
        </div>
        <div v-else-if="visibleOptions.length === 0" class="protocol-empty skill-slash-empty">
          {{ activeProtocol.panel.emptyText }}
        </div>

        <button
          v-for="(option, index) in visibleOptions"
          :key="option.key"
          type="button"
          class="protocol-item skill-slash-item"
          :class="{ active: index === activeIndex, 'is-disabled': !isOptionSelectable(option) }"
          :disabled="!isOptionSelectable(option)"
          @mousedown.prevent="onOptionClick(option)"
        >
          <div class="protocol-item-line skill-slash-item-line">
            <span class="protocol-item-name skill-slash-item-name">{{ option.leftLabel }}</span>
            <span class="protocol-item-desc skill-slash-item-desc" :class="[option.rightClass, { only: !option.rightLabel }]" :title="option.rightTitle || ''">
              {{ option.rightLabel || '-' }}
            </span>
          </div>
        </button>
      </div>

      <template v-if="activeProtocol.secondarySection && !activeCatalogState.loading && !activeCatalogState.error">
        <div class="protocol-divider skill-slash-divider"></div>

        <div class="protocol-section skill-slash-section" :class="activeProtocol.secondarySection.sectionClass">
          <div class="protocol-header skill-slash-header">
            <span class="protocol-header-title skill-slash-header-title">{{ activeProtocol.secondarySection.title }}</span>
            <span class="protocol-header-badge skill-slash-header-badge">{{ activeProtocol.secondarySection.badge }}</span>
          </div>

          <div class="protocol-item skill-slash-item is-disabled is-placeholder">
            <div class="protocol-item-line skill-slash-item-line">
              <span class="protocol-item-desc skill-slash-item-desc only">{{ activeProtocol.secondarySection.placeholderText }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

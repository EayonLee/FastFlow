function appendTextSegment(segments, text) {
  const normalizedText = String(text || '')
  if (!normalizedText) return

  const lastSegment = segments[segments.length - 1]
  if (lastSegment?.type === 'text') {
    lastSegment.text = `${lastSegment.text}${normalizedText}`
    return
  }
  segments.push({ type: 'text', text: normalizedText })
}

function normalizeSegment(segment) {
  if (!segment || typeof segment !== 'object') return null

  if (segment.type === 'text') {
    return { type: 'text', text: String(segment.text || '') }
  }
  if (segment.type === 'node') {
    const nodeId = String(segment.node_id || '').trim()
    if (!nodeId) return null
    return {
      type: 'node',
      node_id: nodeId,
      label: String(segment.label || '').trim(),
    }
  }
  if (segment.type === 'skill') {
    const skillName = String(segment.name || '').trim()
    if (!skillName) return null
    return { type: 'skill', name: skillName }
  }
  return null
}

function dedupePreserveOrder(values) {
  const deduped = []
  const seen = new Set()

  for (const value of values) {
    const normalized = String(value || '').trim()
    if (!normalized || seen.has(normalized)) continue
    seen.add(normalized)
    deduped.push(normalized)
  }

  return deduped
}

export function normalizeDisplaySegments(rawSegments, fallbackText = '') {
  const segments = []
  const sourceSegments = Array.isArray(rawSegments) ? rawSegments : [{ type: 'text', text: fallbackText }]

  for (const segment of sourceSegments) {
    const normalized = normalizeSegment(segment)
    if (!normalized) continue
    if (normalized.type === 'text') {
      appendTextSegment(segments, normalized.text)
      continue
    }
    segments.push(normalized)
  }

  if (segments.length > 0) return segments
  return [{ type: 'text', text: String(fallbackText || '') }]
}

export function buildRequestPayloadFromSegments(rawSegments, fallbackText = '') {
  const displaySegments = normalizeDisplaySegments(rawSegments, fallbackText)
  const selectedNodes = []
  const selectedSkills = []
  const promptChunks = []

  for (const segment of displaySegments) {
    if (segment.type === 'text') {
      promptChunks.push(String(segment.text || ''))
      continue
    }
    if (segment.type === 'node') {
      selectedNodes.push(segment.node_id)
      continue
    }
    if (segment.type === 'skill') {
      selectedSkills.push(segment.name)
    }
  }

  const prompt = promptChunks.join('')
  const executionHints = {
    selected_nodes: dedupePreserveOrder(selectedNodes),
    selected_skills: dedupePreserveOrder(selectedSkills),
  }

  return {
    prompt,
    displaySegments,
    executionHints,
    hasContent: Boolean(
      String(prompt || '').trim()
      || executionHints.selected_nodes.length > 0
      || executionHints.selected_skills.length > 0
    ),
  }
}

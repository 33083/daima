/**
 * SSE 流式对话解析
 * 用 fetch + ReadableStream 实现，支持 POST 带 body
 */
export async function chatStream({ repoId, question, convId, conversationId, useAgent = true, maxToolCalls = 8 }, { onEvent }) {
  const cid = convId || conversationId
  const response = await fetch('/api/v1/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      repo_id: repoId,
      question,
      conv_id: cid || null,
      use_agent: useAgent,
      max_tool_calls: maxToolCalls,
    }),
  })

  if (!response.ok) {
    throw new Error(`请求失败: ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // 按 \n\n 切分 SSE 帧
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      const event = parseSSEEvent(part)
      if (event && onEvent) {
        onEvent(event.type, event.data)
      }
    }
  }
}

function parseSSEEvent(part) {
  if (!part.trim()) return null

  const lines = part.split('\n')
  let eventType = 'message'
  let dataStr = ''

  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataStr += line.slice(5).trim()
    }
  }

  let data = dataStr
  try {
    data = JSON.parse(dataStr)
  } catch (e) {
    // 不是 JSON 就返回原始字符串
  }

  return { type: eventType, data }
}

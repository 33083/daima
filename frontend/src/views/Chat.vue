<template>
  <div class="chat-page">
    <!-- 左侧：会话列表 + 仓库选择 -->
    <div class="chat-sidebar">
      <div class="sidebar-header">
        <h2>💬 对话</h2>
        <el-button size="small" type="primary" :icon="Plus" @click="createNewConv">新建</el-button>
      </div>

      <!-- 仓库选择 -->
      <div class="sidebar-section">
        <el-select v-model="selectedRepoId" placeholder="选择仓库" @change="onRepoChange" style="width: 100%">
          <el-option
            v-for="repo in repos"
            :key="repo.id"
            :label="repo.name"
            :value="repo.id"
            :disabled="repo.status !== 'ready'"
          />
        </el-select>
      </div>

      <!-- 会话列表 -->
      <div class="conv-list" v-loading="convListLoading">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === currentConvId }"
          @click="switchConversation(conv.id)"
        >
          <div class="conv-title" :title="conv.title">
            <el-icon><ChatDotRound /></el-icon>
            <span>{{ conv.title || '新对话' }}</span>
          </div>
          <div class="conv-meta">
            <span class="conv-count">{{ conv.message_count }} 条</span>
            <el-button
              size="small"
              text
              type="danger"
              :icon="Delete"
              @click.stop="deleteConv(conv.id)"
            />
          </div>
        </div>
        <el-empty v-if="conversations.length === 0 && !convListLoading" description="暂无会话，开始提问吧" :image-size="60" />
      </div>

      <!-- Agent 设置 -->
      <div class="sidebar-section">
        <h3>Agent 模式</h3>
        <div class="agent-toggle">
          <el-switch v-model="useAgent" active-text="启用" inactive-text="关闭" />
        </div>
        <p class="agent-desc">
          启用后 AI 可主动调用工具（搜索代码、查看文件、git diff 等）
        </p>
      </div>

      <div class="sidebar-section" v-if="messages.length > 0">
        <el-button size="small" @click="exportChat" :icon="Download" style="width: 100%">
          导出对话记录
        </el-button>
      </div>
    </div>

    <!-- 中间：聊天区域 -->
    <div class="chat-main">
      <div class="chat-messages" ref="messagesRef">
        <el-empty
          v-if="messages.length === 0"
          description="选择仓库后开始提问，我会帮你分析代码"
          :image-size="100"
        />

        <div v-for="msg in messages" :key="msg.id" class="message" :class="msg.role">
          <div class="msg-avatar">
            <el-icon v-if="msg.role === 'user'"><User /></el-icon>
            <el-icon v-else><Cpu /></el-icon>
          </div>
          <div class="msg-content">
            <div class="msg-bubble" v-html="msg.contentHtml"></div>
            <div v-if="msg.role === 'assistant' && msg.agentActions && msg.agentActions.length > 0" class="msg-meta">
              <el-tag size="small" type="success">Agent 调用了 {{ msg.agentActions.length }} 次工具</el-tag>
            </div>
          </div>
        </div>

        <!-- Agent 思考中展示 -->
        <div v-if="loading && currentTool" class="message assistant">
          <div class="msg-avatar"><el-icon><Cpu /></el-icon></div>
          <div class="msg-content">
            <div class="msg-bubble tool-calling">
              <div class="tool-calling-header">
                <el-icon class="spinning"><Loading /></el-icon>
                <span>正在调用工具: {{ currentTool }}</span>
              </div>
              <div class="tool-calling-args" v-if="currentToolArgs">
                <span v-for="(val, key) in currentToolArgs" :key="key" class="arg-chip">
                  {{ key }}: {{ typeof val === 'string' ? (val.length > 40 ? val.slice(0,40)+'...' : val) : val }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="loading && !currentTool" class="message assistant">
          <div class="msg-avatar"><el-icon><Cpu /></el-icon></div>
          <div class="msg-content">
            <div class="msg-bubble thinking">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <el-input
          v-model="question"
          type="textarea"
          :rows="2"
          placeholder="输入你的问题，比如：这个项目的登录逻辑在哪？"
          @keydown.enter.ctrl="sendMessage"
          :disabled="!selectedRepoId || loading"
        />
        <div class="input-actions">
          <span class="tip">Ctrl + Enter 发送 · {{ useAgent ? 'Agent 模式' : '快速模式' }}</span>
          <el-button
            type="primary"
            :icon="Promotion"
            @click="sendMessage"
            :disabled="!selectedRepoId || !question.trim() || loading"
            :loading="loading"
          >
            发送
          </el-button>
        </div>
      </div>
    </div>

    <!-- 右侧：代码查看器 -->
    <div class="code-viewer" v-if="viewingFile">
      <div class="viewer-header">
        <span>{{ viewingFile.file_path }}</span>
        <el-button size="small" text @click="viewingFile = null">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
      <div class="viewer-body">
        <pre><code v-html="highlightedCode"></code></pre>
      </div>
    </div>

    <!-- 文件内容对话框 -->
    <el-dialog v-model="showFileDialog" title="文件内容" width="800px" top="5vh">
      <template #footer>
        <el-button @click="showFileDialog = false">关闭</el-button>
        <el-button type="primary" @click="copyFileContent">复制代码</el-button>
      </template>
      <div class="file-dialog-content">
        <div class="file-path">{{ currentFile?.path }}</div>
        <pre class="file-content" v-html="highlightedFileCode"></pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  User, Cpu, Promotion, Close, Download, Plus, Delete, ChatDotRound, Loading
} from '@element-plus/icons-vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import { getRepoList, getFileContent } from '../api/repo'
import { chatStream } from '../api/chat'
import {
  getConversationList, createConversation,
  deleteConversation, getConversationMessages,
} from '../api/conversation'

const route = useRoute()

const repos = ref([])
const selectedRepoId = ref(null)
const question = ref('')
const messages = ref([])
const loading = ref(false)
const references = ref([])
const agentActions = ref([])
const currentTool = ref(null)
const currentToolArgs = ref(null)
const conversationId = ref(null)
const useAgent = ref(true)
const messagesRef = ref(null)

// 持久化会话
const conversations = ref([])
const currentConvId = ref(null)
const convListLoading = ref(false)

const viewingFile = ref(null)
const showFileDialog = ref(false)
const currentFile = ref(null)
const fileContent = ref('')

// 配置 marked
marked.setOptions({
  highlight: function(code, lang) {
    try {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value
      }
      return hljs.highlightAuto(code).value
    } catch (e) {
      return code
    }
  },
  breaks: true,
})

const highlightedCode = computed(() => {
  if (!viewingFile.value) return ''
  try {
    return hljs.highlight(viewingFile.value.content || '', {
      language: viewingFile.value.language || 'plaintext'
    }).value
  } catch {
    return viewingFile.value.content || ''
  }
})

const highlightedFileCode = computed(() => {
  try {
    return hljs.highlightAuto(fileContent.value).value
  } catch {
    return fileContent.value
  }
})

function getScore(ref) {
  if (ref.rerank_score !== undefined) return (ref.rerank_score * 100).toFixed(0) + '%'
  if (ref.rrf_score !== undefined) return (ref.rrf_score * 100).toFixed(0) + '%'
  if (ref.score !== undefined) return (ref.score * 100).toFixed(0) + '%'
  return '-'
}

function loadRepos() {
  getRepoList().then(res => {
    repos.value = res.data
    if (route.query.repoId) {
      selectedRepoId.value = parseInt(route.query.repoId)
    } else if (res.data.length > 0) {
      const ready = res.data.find(r => r.status === 'ready')
      if (ready) selectedRepoId.value = ready.id
    }
    if (selectedRepoId.value) {
      loadConversations()
    }
  })
}

function onRepoChange() {
  messages.value = []
  references.value = []
  agentActions.value = []
  conversationId.value = null
  currentConvId.value = null
  loadConversations()
}

// ===== 会话管理 =====

function loadConversations() {
  if (!selectedRepoId.value) {
    conversations.value = []
    return
  }
  convListLoading.value = true
  getConversationList(selectedRepoId.value, 1, 50).then(res => {
    conversations.value = res.data.items || []
  }).finally(() => {
    convListLoading.value = false
  })
}

function createNewConv() {
  if (!selectedRepoId.value) {
    ElMessage.warning('请先选择仓库')
    return
  }
  messages.value = []
  currentConvId.value = null
  conversationId.value = null
  agentActions.value = []
  references.value = []
}

function switchConversation(convId) {
  if (convId === currentConvId.value) return
  currentConvId.value = convId
  messages.value = []
  agentActions.value = []
  references.value = []

  getConversationMessages(convId, 1, 100).then(res => {
    const msgs = res.data.items || []
    for (const msg of msgs) {
      const extra = {}
      if (msg.meta && msg.meta.agent_actions) {
        extra.agentActions = msg.meta.agent_actions
      }
      messages.value.push({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        contentHtml: marked.parse(msg.content),
        ...extra,
      })
    }
    scrollToBottom()
  })
}

function deleteConv(convId) {
  ElMessageBox.confirm('确定要删除这个会话吗？', '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).then(() => {
    deleteConversation(convId).then(() => {
      ElMessage.success('已删除')
      if (currentConvId.value === convId) {
        currentConvId.value = null
        messages.value = []
      }
      loadConversations()
    })
  }).catch(() => {})
}

function addMessage(role, content, extra = {}) {
  const id = Date.now() + Math.random()
  const msg = {
    id,
    role,
    content,
    contentHtml: marked.parse(content),
    ...extra,
  }
  messages.value.push(msg)
  scrollToBottom()
  return msg
}

function updateMessage(id, content) {
  const msg = messages.value.find(m => m.id === id)
  if (msg) {
    msg.content = content
    msg.contentHtml = marked.parse(content)
    scrollToBottom()
  }
}

async function sendMessage() {
  if (!selectedRepoId.value || !question.value.trim() || loading.value) return

  const q = question.value.trim()
  question.value = ''
  loading.value = true
  agentActions.value = []
  currentTool.value = null
  currentToolArgs.value = null

  addMessage('user', q)

  let assistantMsg = null
  const actions = []

  try {
    await chatStream({
      repoId: selectedRepoId.value,
      question: q,
      convId: currentConvId.value,
      useAgent: useAgent.value,
    }, {
      onEvent: (type, data) => {
        if (type === 'start') {
          if (data.conv_id) {
            currentConvId.value = data.conv_id
          }
          assistantMsg = addMessage('assistant', '')
        } else if (type === 'tool_call') {
          currentTool.value = data.tool
          currentToolArgs.value = data.args
          actions.push(data)
        } else if (type === 'tool_result') {
          currentTool.value = null
          currentToolArgs.value = null
        } else if (type === 'delta') {
          if (assistantMsg) {
            const currentContent = assistantMsg.content + (data.content || '')
            updateMessage(assistantMsg.id, currentContent)
          }
        } else if (type === 'end') {
          agentActions.value = actions
          references.value = data.references || []
          if (assistantMsg) {
            assistantMsg.agentActions = actions
          }
          loading.value = false
          currentTool.value = null
          loadConversations()  // 刷新会话列表
        } else if (type === 'error') {
          ElMessage.error(data.message || '生成失败')
          loading.value = false
          currentTool.value = null
        }
      }
    })
  } catch (e) {
    ElMessage.error(e.message || '请求失败')
    loading.value = false
  }
}

function showRefFile(ref) {
  getFileContent(selectedRepoId.value, ref.file_path).then(res => {
    currentFile.value = { path: ref.file_path }
    fileContent.value = res.data.content
    showFileDialog.value = true
  }).catch(() => {
    viewingFile.value = ref
  })
}

function copyFileContent() {
  navigator.clipboard.writeText(fileContent.value).then(() => {
    ElMessage.success('已复制到剪贴板')
  })
}

function exportChat() {
  if (messages.value.length === 0) return

  let md = '# CodeRAG 对话记录\n\n'
  md += `> 仓库: ${repos.value.find(r => r.id === selectedRepoId.value)?.name || '未知'}\n`
  md += `> 时间: ${new Date().toLocaleString()}\n`
  md += `> 模式: ${useAgent.value ? 'Agent 模式' : '快速模式'}\n\n`
  md += '---\n\n'

  for (const msg of messages.value) {
    if (msg.role === 'user') {
      md += `## 👤 用户\n\n${msg.content}\n\n`
    } else {
      md += `## 🤖 AI\n\n${msg.content}\n\n`
      if (msg.agentActions && msg.agentActions.length > 0) {
        md += `> Agent 调用了 ${msg.agentActions.length} 次工具\n\n`
      }
    }
  }

  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `coderag_chat_${Date.now()}.md`
  a.click()
  URL.revokeObjectURL(url)

  ElMessage.success('对话记录已导出')
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

onMounted(() => {
  loadRepos()
})
</script>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
  gap: 12px;
}

/* 左侧栏 */
.chat-sidebar {
  width: 260px;
  background: white;
  border-radius: 8px;
  padding: 12px;
  overflow-y: auto;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}
.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 4px 12px;
}
.sidebar-header h2 {
  font-size: 16px;
  margin: 0;
  color: #303133;
}
.conv-list {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 12px;
  min-height: 200px;
}
.conv-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: all 0.2s;
}
.conv-item:hover {
  background: #f5f7fa;
}
.conv-item.active {
  background: #ecf5ff;
  border-left: 3px solid #409eff;
  padding-left: 9px;
}
.conv-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.conv-count {
  font-size: 11px;
  color: #909399;
}
.sidebar-section {
  margin-bottom: 16px;
}
.sidebar-section h3 {
  font-size: 14px;
  color: #303133;
  margin-bottom: 10px;
}
.agent-toggle {
  margin-bottom: 8px;
}
.agent-desc {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin: 0;
}

.action-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.action-item {
  padding: 8px 10px;
  background: #f0f9ff;
  border-radius: 6px;
  border-left: 3px solid #409eff;
}
.action-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  color: #409eff;
  font-weight: 500;
}
.action-tool {
  flex: 1;
}
.action-step {
  color: #909399;
  font-weight: normal;
}
.action-args {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.ref-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ref-item {
  padding: 8px 10px;
  background: #f5f7fa;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.ref-item:hover {
  background: #ecf5ff;
}
.ref-file {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
  word-break: break-all;
}
.ref-meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: #909399;
}
.ref-score {
  color: #67c23a;
  font-weight: 600;
}

/* 中间聊天区 */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 8px;
  overflow: hidden;
}
.chat-messages {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}
.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}
.message.user {
  flex-direction: row-reverse;
}
.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #409eff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.message.assistant .msg-avatar {
  background: #67c23a;
}
.msg-content {
  max-width: 75%;
}
.msg-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  background: #f5f7fa;
  line-height: 1.6;
  font-size: 14px;
  color: #303133;
}
.message.user .msg-bubble {
  background: #409eff;
  color: white;
}
.message.user .msg-bubble :deep(code) {
  background: rgba(255,255,255,0.2);
  color: white;
}
.msg-bubble :deep(p) {
  margin: 0 0 8px 0;
}
.msg-bubble :deep(p:last-child) {
  margin-bottom: 0;
}
.msg-bubble :deep(ul), .msg-bubble :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}
.msg-bubble.thinking {
  display: flex;
  gap: 4px;
  padding: 16px 20px;
}
.msg-bubble.thinking .dot {
  width: 8px;
  height: 8px;
  background: #c0c4cc;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}
.msg-bubble.thinking .dot:nth-child(1) { animation-delay: -0.32s; }
.msg-bubble.thinking .dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.msg-bubble.tool-calling {
  background: #f0f9ff;
  border: 1px solid #b3d8ff;
}
.tool-calling-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #409eff;
  font-weight: 500;
  margin-bottom: 8px;
}
.spinning {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.tool-calling-args {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.arg-chip {
  background: white;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #606266;
  border: 1px solid #dcdfe6;
}

.msg-meta {
  margin-top: 6px;
}

/* 输入区 */
.chat-input-area {
  border-top: 1px solid #ebeef5;
  padding: 12px 16px;
}
.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
.tip {
  font-size: 12px;
  color: #909399;
}

/* 代码查看器 */
.code-viewer {
  width: 400px;
  background: white;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.viewer-header {
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 500;
}
.viewer-body {
  flex: 1;
  overflow: auto;
}
.viewer-body pre {
  margin: 0;
  border-radius: 0;
  padding: 12px;
}

.file-dialog-content {
  max-height: 70vh;
  overflow: auto;
}
.file-path {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 12px;
  font-family: monospace;
  font-size: 12px;
}
.file-content {
  margin: 0;
}

/* 暗色模式适配 */
:deep(html.dark) .chat-sidebar,
:deep(html.dark) .chat-main,
:deep(html.dark) .code-viewer {
  background: #161b22;
}
:deep(html.dark) .sidebar-header h2 {
  color: #e6edf3;
}
:deep(html.dark) .conv-item {
  color: #e6edf3;
}
:deep(html.dark) .conv-item:hover {
  background: #21262d;
}
:deep(html.dark) .conv-item.active {
  background: #132240;
  border-left-color: #58a6ff;
}
:deep(html.dark) .conv-title {
  color: #e6edf3;
}
:deep(html.dark) .sidebar-section h3 {
  color: #e6edf3;
}
:deep(html.dark) .ref-item {
  background: #21262d;
}
:deep(html.dark) .ref-item:hover {
  background: #30363d;
}
:deep(html.dark) .ref-file {
  color: #e6edf3;
}
:deep(html.dark) .msg-bubble {
  background: #21262d;
  color: #e6edf3;
}
:deep(html.dark) .message.user .msg-bubble {
  background: #1f6feb;
}
:deep(html.dark) .msg-bubble.tool-calling {
  background: #132240;
  border-color: #1f6feb;
}
:deep(html.dark) .chat-input-area {
  border-top-color: #30363d;
}
:deep(html.dark) .viewer-header {
  border-bottom-color: #30363d;
  color: #e6edf3;
}
:deep(html.dark) .action-item {
  background: #132240;
  border-left-color: #58a6ff;
}
:deep(html.dark) .action-header {
  color: #58a6ff;
}
:deep(html.dark) .file-path {
  background: #21262d;
  color: #8b949e;
}
</style>

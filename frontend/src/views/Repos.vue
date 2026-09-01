<template>
  <div class="repos-page">
    <div class="page-header">
      <h2>仓库管理</h2>
      <el-button type="primary" :icon="Plus" @click="showImportDialog = true">
        导入仓库
      </el-button>
    </div>

    <!-- 仓库列表 -->
    <el-row :gutter="20">
      <el-col :span="8" v-for="repo in repos" :key="repo.id">
        <el-card class="repo-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="repo-name">{{ repo.name }}</span>
              <el-tag :type="statusType(repo.status)" size="small">
                {{ statusText(repo.status) }}
              </el-tag>
            </div>
          </template>

          <!-- 索引进度条 -->
          <div v-if="repo.status === 'indexing'" class="index-progress">
            <el-progress
              :percentage="getProgress(repo.id)"
              :status="progressStatus(repo.id)"
              :stroke-width="6"
            />
            <div class="progress-text">{{ progressMessage(repo.id) }}</div>
          </div>

          <!-- 项目简介 -->
          <div v-if="repo.description" class="repo-desc">
            {{ repo.description }}
          </div>
          <div v-else-if="repo.status === 'ready'" class="repo-desc placeholder">
            暂无简介
          </div>

          <div class="repo-info">
            <div class="info-item">
              <span class="label">语言:</span>
              <span>{{ repo.language || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="label">文件数:</span>
              <span>{{ repo.file_count }}</span>
            </div>
            <div class="info-item">
              <span class="label">切片数:</span>
              <span>{{ repo.chunk_count }}</span>
            </div>
            <div class="info-item">
              <span class="label">来源:</span>
              <span>{{ repo.source_type === 'git' ? 'Git' : '本地' }}</span>
            </div>
          </div>

          <div v-if="repo.status === 'error' && repo.error_msg" class="error-msg">
            <el-alert :title="repo.error_msg" type="error" :closable="false" show-icon size="small" />
          </div>

          <div class="repo-actions">
            <el-button
              size="small"
              type="primary"
              :icon="ChatDotRound"
              @click="goChat(repo.id)"
              :disabled="repo.status !== 'ready'"
            >
              开始问答
            </el-button>
            <el-button
              size="small"
              :icon="Refresh"
              @click="handleReindex(repo.id)"
              :disabled="repo.status === 'indexing'"
            >
              重新索引
            </el-button>
            <el-button size="small" type="danger" :icon="Delete" @click="handleDelete(repo)">
              删除
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="repos.length === 0" description="暂无仓库，点击右上角导入" />

    <!-- 导入对话框 -->
    <el-dialog v-model="showImportDialog" title="导入代码仓库" width="560px">
      <el-tabs v-model="importType">
        <!-- GitHub 搜索 -->
        <el-tab-pane label="GitHub 搜索" name="github">
          <div class="github-search">
            <el-input
              v-model="githubKeyword"
              placeholder="搜索 GitHub 仓库，如 fastapi"
              clearable
              @keyup.enter="searchGithub"
            >
              <template #append>
                <el-button :icon="Search" @click="searchGithub" :loading="githubSearching">搜索</el-button>
              </template>
            </el-input>
          </div>
          <div class="github-results" v-if="githubResults.length > 0">
            <div
              class="github-item"
              v-for="item in githubResults"
              :key="item.id"
              @click="selectGithubRepo(item)"
            >
              <div class="github-repo-name">
                <el-icon><Promotion /></el-icon>
                {{ item.full_name }}
              </div>
              <div class="github-repo-desc">{{ item.description || '暂无描述' }}</div>
              <div class="github-repo-meta">
                <el-tag size="small" v-if="item.language">{{ item.language }}</el-tag>
                <span>⭐ {{ item.stargazers_count }}</span>
                <span>🍴 {{ item.forks_count }}</span>
              </div>
            </div>
          </div>
          <el-empty v-else-if="githubSearched && githubResults.length === 0" description="未找到相关仓库" :image-size="60" />
          <div v-else class="github-tip">
            <el-icon><InfoFilled /></el-icon>
            输入关键词搜索 GitHub 上的开源仓库
          </div>
        </el-tab-pane>

        <!-- Git 地址 -->
        <el-tab-pane label="Git 地址" name="git">
          <el-form :model="gitForm" label-width="80px">
            <el-form-item label="仓库名称">
              <el-input v-model="gitForm.name" placeholder="给仓库起个名字" />
            </el-form-item>
            <el-form-item label="Git 地址">
              <el-input v-model="gitForm.url" placeholder="https://github.com/xxx/xxx.git" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleImportGit" :loading="importing">
                开始导入
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 本地目录 -->
        <el-tab-pane label="本地目录" name="local">
          <el-form :model="localForm" label-width="80px">
            <el-form-item label="仓库名称">
              <el-input v-model="localForm.name" placeholder="给仓库起个名字" />
            </el-form-item>
            <el-form-item label="本地路径">
              <el-input v-model="localForm.local_path" placeholder="点击右侧按钮选择目录" readonly>
                <template #append>
                  <el-button :icon="Folder" @click="openFolderBrowser">选择目录</el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleImportLocal" :loading="importing">
                开始索引
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- 文件夹浏览器 -->
    <el-dialog v-model="folderBrowserVisible" title="选择文件夹" width="700px" append-to-body class="folder-dialog">
      <div class="folder-toolbar">
        <el-button-group>
          <el-button :icon="Back" size="small" :disabled="!folderParent" @click="browseDirs(folderParent)" />
          <el-button :icon="Refresh" size="small" @click="browseDirs(folderCurrent)" />
        </el-button-group>
        <div class="folder-breadcrumb">
          <span class="crumb-item" @click="browseDirs('')">此电脑</span>
          <template v-for="(seg, i) in folderPathSegments" :key="i">
            <span class="crumb-sep">›</span>
            <span class="crumb-item" @click="browseDirs(seg.path)">{{ seg.name }}</span>
          </template>
        </div>
      </div>
      <div class="quick-bar">
        <span class="quick-label">快捷访问:</span>
        <el-button
          v-for="q in folderQuick"
          :key="q.path"
          size="small"
          text
          @click="browseDirs(q.path)"
        >
          {{ q.name }}
        </el-button>
      </div>
      <div class="explorer-table">
        <div class="explorer-header">
          <div class="col-name">名称</div>
          <div class="col-date">修改日期</div>
          <div class="col-type">类型</div>
        </div>
        <div class="explorer-body">
          <div
            v-for="dir in folderDirs"
            :key="dir.path"
            class="explorer-row"
            :class="{ selected: folderSelectedPath === dir.path }"
            @click="selectFolder(dir.path)"
            @dblclick="browseDirs(dir.path)"
          >
            <div class="col-name">
              <el-icon class="row-icon"><FolderOpened /></el-icon>
              <span>{{ dir.name }}</span>
            </div>
            <div class="col-date">{{ dir.modified }}</div>
            <div class="col-type">{{ dir.type }}</div>
          </div>
          <div v-if="folderDirs.length === 0" class="explorer-empty">
            <el-icon :size="32"><FolderRemove /></el-icon>
            <span>此文件夹没有子目录</span>
          </div>
        </div>
      </div>
      <div class="folder-statusbar">
        <span v-if="folderSelectedPath">已选择: {{ folderSelectedPath }}</span>
        <span v-else>{{ folderDirs.length }} 个项目</span>
      </div>
      <template #footer>
        <el-button @click="folderBrowserVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmFolder" :disabled="!folderSelectedPath">
          选择文件夹
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, ChatDotRound, Refresh, Delete, Search, Promotion, InfoFilled,
  Folder, FolderOpened, FolderRemove, Back, Check
} from '@element-plus/icons-vue'
import { computed } from 'vue'
import { getRepoList, importGitRepo, importLocalRepo, deleteRepo, reindexRepo } from '../api/repo'

const router = useRouter()
const repos = ref([])
const showImportDialog = ref(false)
const importType = ref('github')
const importing = ref(false)

const gitForm = ref({ name: '', url: '' })
const localForm = ref({ name: '', local_path: '' })

// 文件夹浏览器
const folderBrowserVisible = ref(false)
const folderCurrent = ref('')
const folderParent = ref(null)
const folderDirs = ref([])
const folderQuick = ref([])
const folderSelectedPath = ref('')

async function openFolderBrowser() {
  folderSelectedPath.value = ''
  folderBrowserVisible.value = true
  await browseDirs('')
}

async function browseDirs(path) {
  try {
    const res = await fetch(`/api/v1/repos/browse/dirs?path=${encodeURIComponent(path)}`)
    const data = await res.json()
    folderCurrent.value = data.current || ''
    folderParent.value = data.parent
    folderDirs.value = data.dirs || []
    folderQuick.value = data.quick || []
    folderSelectedPath.value = ''
  } catch (e) {
    ElMessage.error('浏览目录失败')
  }
}

function selectFolder(path) {
  folderSelectedPath.value = path
}

function confirmFolder() {
  if (folderSelectedPath.value) {
    localForm.value.local_path = folderSelectedPath.value
    folderBrowserVisible.value = false
  }
}

const folderPathSegments = computed(() => {
  if (!folderCurrent.value) return []
  const parts = folderCurrent.value.replace(/\\/g, '/').split('/').filter(Boolean)
  const segs = []
  let acc = ''
  for (const p of parts) {
    acc = acc ? acc + '/' + p : p
    segs.push({ name: p, path: acc.includes(':') && !acc.endsWith(':') ? acc + '/' : acc })
    if (acc.match(/^[A-Z]:$/)) acc = acc + '/'
  }
  return segs
})

// GitHub 搜索
const githubKeyword = ref('')
const githubSearching = ref(false)
const githubResults = ref([])
const githubSearched = ref(false)

// 进度数据 { repoId: { progress, message, status } }
const progressMap = ref({})
let pollTimer = null

function loadRepos() {
  getRepoList().then(res => {
    repos.value = res.data
  })
}

function statusType(status) {
  const map = {
    pending: 'info',
    indexing: 'warning',
    ready: 'success',
    error: 'danger',
  }
  return map[status] || 'info'
}

function statusText(status) {
  const map = {
    pending: '等待中',
    indexing: '索引中',
    ready: '就绪',
    error: '失败',
  }
  return map[status] || status
}

function getProgress(repoId) {
  return progressMap.value[repoId]?.progress || 0
}

function progressMessage(repoId) {
  const p = progressMap.value[repoId]
  if (!p) return '准备中...'
  if (p.current_file) {
    return `${p.message} (${p.processed_files || 0}/${p.total_files || 0})`
  }
  return p.message || '处理中...'
}

function progressStatus(repoId) {
  const p = progressMap.value[repoId]
  if (p?.status === 'error') return 'exception'
  if (p?.status === 'done') return 'success'
  return ''
}

// GitHub 搜索
async function searchGithub() {
  if (!githubKeyword.value.trim()) return
  githubSearching.value = true
  try {
    const res = await fetch(
      `https://api.github.com/search/repositories?q=${encodeURIComponent(githubKeyword.value)}&sort=stars&per_page=10`
    )
    const data = await res.json()
    githubResults.value = data.items || []
    githubSearched.value = true
  } catch (e) {
    ElMessage.error('GitHub 搜索失败，请检查网络')
  } finally {
    githubSearching.value = false
  }
}

function selectGithubRepo(item) {
  gitForm.value.name = item.name
  gitForm.value.url = item.clone_url
  importType.value = 'git'
}

async function handleImportGit() {
  if (!gitForm.value.name || !gitForm.value.url) {
    ElMessage.warning('请填写名称和 Git 地址')
    return
  }
  importing.value = true
  try {
    await importGitRepo(gitForm.value)
    ElMessage.success('导入任务已开始，正在后台处理...')
    showImportDialog.value = false
    loadRepos()
    startProgressPolling()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

async function handleImportLocal() {
  if (!localForm.value.name || !localForm.value.local_path) {
    ElMessage.warning('请填写名称和本地路径')
    return
  }
  importing.value = true
  try {
    await importLocalRepo(localForm.value)
    ElMessage.success('索引任务已开始，正在后台处理...')
    showImportDialog.value = false
    loadRepos()
    startProgressPolling()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '索引失败')
  } finally {
    importing.value = false
  }
}

async function handleDelete(repo) {
  try {
    await ElMessageBox.confirm(`确定删除仓库 "${repo.name}" 吗？`, '确认', {
      type: 'warning',
    })
    await deleteRepo(repo.id)
    ElMessage.success('已删除')
    loadRepos()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

async function handleReindex(id) {
  try {
    await reindexRepo(id)
    ElMessage.success('重新索引任务已开始')
    loadRepos()
    startProgressPolling()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

function goChat(id) {
  router.push({ path: '/chat', query: { repoId: id } })
}

// 进度轮询
function startProgressPolling() {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    const indexingRepos = repos.value.filter(r => r.status === 'indexing')
    if (indexingRepos.length === 0) {
      // 没有正在索引的，停止轮询
      clearInterval(pollTimer)
      pollTimer = null
      loadRepos()
      return
    }
    indexingRepos.forEach(repo => {
      const taskId = `repo_${repo.id}_import`
      fetch(`/api/v1/repos/${repo.id}/tasks/${taskId}`)
        .then(r => {
          if (r.status === 404) {
            // 任务不存在（后端可能重启了），检查仓库实际状态
            return getRepoList().then(() => {
              const updated = repos.value.find(x => x.id === repo.id)
              if (updated && updated.status !== 'indexing') {
                loadRepos()
              }
            })
          }
          return r.json()
        })
        .then(data => {
          if (!data) return
          progressMap.value[repo.id] = data
          if (data.status === 'completed' || data.status === 'done' || data.status === 'error' || data.status === 'failed') {
            loadRepos()
          }
        })
        .catch(() => {})
    })
  }, 2000)
}

onMounted(() => {
  loadRepos()
  // 如果有正在索引的，启动轮询
  setTimeout(() => {
    const indexing = repos.value.filter(r => r.status === 'indexing')
    if (indexing.length > 0) {
      startProgressPolling()
    }
  }, 500)
})

onBeforeUnmount(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<style scoped>
.repos-page {
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0;
  color: #303133;
}
.repo-card {
  margin-bottom: 20px;
  height: 100%;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.repo-name {
  font-weight: 600;
  font-size: 16px;
}
.index-progress {
  margin-bottom: 12px;
}
.progress-text {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.repo-info {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  color: #606266;
}
.repo-desc {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  max-height: 100px;
  overflow-y: auto;
}
.repo-desc.placeholder {
  color: #c0c4cc;
  font-style: italic;
}
:deep(html.dark) .repo-desc {
  background: #21262d;
  color: #8b949e;
}
.info-item .label {
  color: #909399;
  margin-right: 4px;
}
.error-msg {
  margin-bottom: 12px;
}
.repo-actions {
  display: flex;
  gap: 8px;
}

/* GitHub 搜索 */
.github-search {
  margin-bottom: 16px;
}
.github-results {
  max-height: 400px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.github-item {
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.github-item:hover {
  border-color: #409eff;
  background: #f5faff;
}
.github-repo-name {
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.github-repo-desc {
  font-size: 12px;
  color: #606266;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.github-repo-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #909399;
}
.github-tip {
  text-align: center;
  padding: 40px 0;
  color: #909399;
  font-size: 13px;
}
.github-tip .el-icon {
  margin-right: 4px;
  vertical-align: middle;
}

/* Windows 资源管理器风格 */
.folder-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-bottom: none;
  border-radius: 4px 4px 0 0;
}
.folder-breadcrumb {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 13px;
  overflow: hidden;
  flex: 1;
}
.crumb-item {
  cursor: pointer;
  color: #409eff;
  white-space: nowrap;
  padding: 2px 6px;
  border-radius: 3px;
}
.crumb-item:hover {
  background: #ecf5ff;
}
.crumb-sep {
  color: #c0c4cc;
  margin: 0 2px;
}
.quick-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: #fafafa;
  border: 1px solid #e4e7ed;
  border-top: none;
  border-bottom: 1px solid #e4e7ed;
}
.quick-label {
  font-size: 12px;
  color: #909399;
  margin-right: 4px;
  white-space: nowrap;
}
.quick-bar .el-button {
  margin: 0;
  padding: 4px 10px;
  font-size: 12px;
}
.explorer-table {
  border: 1px solid #e4e7ed;
  border-radius: 0 0 4px 4px;
  overflow: hidden;
}
.explorer-header {
  display: flex;
  background: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
  font-size: 12px;
  color: #909399;
  font-weight: 600;
  user-select: none;
}
.explorer-header > div {
  padding: 8px 12px;
}
.explorer-body {
  max-height: 360px;
  overflow-y: auto;
  background: #fff;
}
.explorer-row {
  display: flex;
  cursor: pointer;
  font-size: 13px;
  color: #303133;
  transition: background 0.08s;
  border-bottom: 1px solid #f0f0f0;
}
.explorer-row:hover {
  background: #e8f2ff;
}
.explorer-row.selected {
  background: #cce4ff;
}
.explorer-row > div {
  padding: 8px 12px;
  display: flex;
  align-items: center;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.col-name {
  flex: 1;
  min-width: 0;
}
.col-date {
  width: 150px;
  flex-shrink: 0;
  color: #606266;
  font-size: 12px;
}
.col-type {
  width: 100px;
  flex-shrink: 0;
  color: #909399;
  font-size: 12px;
}
.row-icon {
  font-size: 18px;
  color: #f5b041;
  margin-right: 8px;
  flex-shrink: 0;
}
.explorer-row.selected .row-icon {
  color: #409eff;
}
.explorer-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 50px 0;
  color: #c0c4cc;
  font-size: 13px;
}
.folder-statusbar {
  padding: 8px 0 0;
  font-size: 12px;
  color: #909399;
}
</style>

<template>
  <div class="architecture-page">
    <div class="page-header">
      <h2>🏗️ 项目架构概览</h2>
      <el-select v-model="selectedRepoId" placeholder="选择仓库" @change="loadOverview" style="width: 260px">
        <el-option
          v-for="repo in repos"
          :key="repo.id"
          :label="repo.name"
          :value="repo.id"
          :disabled="repo.status !== 'ready'"
        />
      </el-select>
    </div>

    <div v-loading="loading" v-if="overview" class="overview-content">
      <!-- 技术栈 -->
      <div class="card">
        <h3>🔧 技术栈</h3>
        <div class="tech-grid">
          <div class="tech-item" v-if="overview.tech_stack.languages.length">
            <div class="tech-label">编程语言</div>
            <div class="tech-tags">
              <el-tag v-for="lang in overview.tech_stack.languages" :key="lang" type="primary">{{ lang }}</el-tag>
            </div>
          </div>
          <div class="tech-item" v-if="overview.tech_stack.frameworks.length">
            <div class="tech-label">框架</div>
            <div class="tech-tags">
              <el-tag v-for="fw in overview.tech_stack.frameworks" :key="fw" type="success">{{ fw }}</el-tag>
            </div>
          </div>
          <div class="tech-item" v-if="overview.tech_stack.databases.length">
            <div class="tech-label">数据库</div>
            <div class="tech-tags">
              <el-tag v-for="db in overview.tech_stack.databases" :key="db" type="warning">{{ db }}</el-tag>
            </div>
          </div>
          <div class="tech-item" v-if="overview.tech_stack.build_tools.length">
            <div class="tech-label">构建工具</div>
            <div class="tech-tags">
              <el-tag v-for="tool in overview.tech_stack.build_tools" :key="tool">{{ tool }}</el-tag>
            </div>
          </div>
          <div class="tech-item" v-if="overview.tech_stack.other.length">
            <div class="tech-label">其他</div>
            <div class="tech-tags">
              <el-tag v-for="o in overview.tech_stack.other" :key="o" type="info">{{ o }}</el-tag>
            </div>
          </div>
        </div>
      </div>

      <div class="row">
        <!-- 模块说明 -->
        <div class="card flex-1">
          <h3>📦 模块说明</h3>
          <div class="module-list">
            <div class="module-item" v-for="mod in overview.modules" :key="mod.name">
              <div class="module-name">
                <el-icon><Folder /></el-icon>
                <span>{{ mod.name }}</span>
              </div>
              <div class="module-desc">
                {{ mod.description }}
                <el-tag v-if="mod.confidence === 'high'" size="small" type="success" style="margin-left: 6px">高置信</el-tag>
              </div>
            </div>
          </div>
        </div>

        <!-- 入口文件 -->
        <div class="card flex-1">
          <h3>🚪 入口文件</h3>
          <div class="entry-list">
            <div class="entry-item" v-for="ep in overview.entry_points" :key="ep.path">
              <div class="entry-path">
                <el-icon><Document /></el-icon>
                <span>{{ ep.path }}</span>
              </div>
              <div class="entry-desc">{{ ep.description }}</div>
            </div>
            <el-empty v-if="overview.entry_points.length === 0" description="未识别到入口文件" :image-size="60" />
          </div>
        </div>
      </div>

      <div class="row">
        <!-- 代码统计 -->
        <div class="card flex-1">
          <h3>📊 代码统计</h3>
          <div class="stats-overview">
            <div class="stat-card">
              <div class="stat-value">{{ overview.stats.total_files }}</div>
              <div class="stat-label">文件数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ overview.stats.total_lines.toLocaleString() }}</div>
              <div class="stat-label">代码行数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ overview.stats.total_functions }}</div>
              <div class="stat-label">函数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ overview.stats.total_classes }}</div>
              <div class="stat-label">类</div>
            </div>
          </div>
          <div class="lang-stats">
            <h4>按语言分布</h4>
            <div
              v-for="lang in overview.stats.by_language"
              :key="lang.language"
              class="lang-bar-row"
            >
              <span class="lang-name">{{ lang.language }}</span>
              <div class="lang-bar-wrap">
                <div
                  class="lang-bar"
                  :style="{ width: getLangPercent(lang) + '%' }"
                ></div>
              </div>
              <span class="lang-count">{{ lang.lines.toLocaleString() }} 行 ({{ lang.files }} 文件)</span>
            </div>
          </div>
        </div>

        <!-- 目录树 -->
        <div class="card flex-1">
          <h3>🌲 目录结构</h3>
          <div class="tree-view">
            <tree-node :node="overview.tree" />
          </div>
        </div>
      </div>
    </div>

    <el-empty v-else-if="!loading" description="选择仓库查看架构概览" :image-size="120" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Folder, Document } from '@element-plus/icons-vue'
import { getRepoList } from '../api/repo'
import { getArchitectureOverview } from '../api/architecture'

const repos = ref([])
const selectedRepoId = ref(null)
const overview = ref(null)
const loading = ref(false)

function loadRepos() {
  getRepoList().then(res => {
    repos.value = res.data
    const ready = res.data.find(r => r.status === 'ready')
    if (ready) {
      selectedRepoId.value = ready.id
      loadOverview()
    }
  })
}

function loadOverview() {
  if (!selectedRepoId.value) return
  loading.value = true
  getArchitectureOverview(selectedRepoId.value).then(res => {
    overview.value = res.data
  }).catch(err => {
    ElMessage.error('加载架构概览失败')
  }).finally(() => {
    loading.value = false
  })
}

const maxLines = computed(() => {
  if (!overview.value?.stats?.by_language?.length) return 1
  return Math.max(...overview.value.stats.by_language.map(l => l.lines))
})

function getLangPercent(lang) {
  return (lang.lines / maxLines.value) * 100
}

onMounted(() => {
  loadRepos()
})
</script>

<!-- 递归树节点组件 -->
<script>
import { defineComponent, h } from 'vue'

const TreeNode = defineComponent({
  name: 'TreeNode',
  props: {
    node: { type: Object, required: true },
    depth: { type: Number, default: 0 },
  },
  setup(props) {
    return () => {
      const node = props.node
      const icon = node.type === 'dir' ? '📁' : node.type === 'more' ? '...' : '📄'
      const children = node.children || []

      return h('div', { class: 'tree-node', style: { paddingLeft: props.depth * 16 + 'px' } }, [
        h('div', { class: 'tree-label' }, [
          h('span', { class: 'tree-icon' }, icon),
          h('span', { class: 'tree-name' }, node.name),
        ]),
        children.length > 0 ? children.map(child =>
          h(TreeNode, { node: child, depth: props.depth + 1 })
        ) : null,
      ])
    }
  },
})
</script>

<style scoped>
.architecture-page {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
}
.card h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  color: #303133;
}
.row {
  display: flex;
  gap: 16px;
}
.flex-1 {
  flex: 1;
}

/* 技术栈 */
.tech-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}
.tech-item {
  min-width: 180px;
}
.tech-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}
.tech-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* 模块列表 */
.module-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.module-item {
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 6px;
}
.module-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
  color: #303133;
}
.module-desc {
  font-size: 13px;
  color: #606266;
  padding-left: 22px;
}

/* 入口文件 */
.entry-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.entry-item {
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 6px;
}
.entry-path {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: monospace;
  font-size: 13px;
  color: #409eff;
  margin-bottom: 4px;
}
.entry-desc {
  font-size: 12px;
  color: #606266;
  padding-left: 22px;
}

/* 统计 */
.stats-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.stat-card {
  text-align: center;
  padding: 16px 8px;
  background: #f5f7fa;
  border-radius: 8px;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #409eff;
  margin-bottom: 4px;
}
.stat-label {
  font-size: 12px;
  color: #909399;
}

.lang-stats h4 {
  font-size: 14px;
  margin: 0 0 12px 0;
  color: #606266;
}
.lang-bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 12px;
}
.lang-name {
  width: 80px;
  color: #303133;
  font-weight: 500;
}
.lang-bar-wrap {
  flex: 1;
  height: 16px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}
.lang-bar {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #67c23a);
  border-radius: 4px;
  transition: width 0.5s;
}
.lang-count {
  width: 140px;
  text-align: right;
  color: #909399;
}

/* 目录树 */
.tree-view {
  max-height: 400px;
  overflow-y: auto;
  font-size: 13px;
  font-family: monospace;
}
.tree-node {
  line-height: 1.8;
}
.tree-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 4px;
  border-radius: 4px;
}
.tree-label:hover {
  background: #f5f7fa;
}
.tree-icon {
  font-size: 14px;
}
.tree-name {
  color: #303133;
}

/* 暗色模式 */
:deep(html.dark) .card {
  background: #161b22;
}
:deep(html.dark) .card h3 {
  color: #e6edf3;
}
:deep(html.dark) .module-item,
:deep(html.dark) .entry-item,
:deep(html.dark) .stat-card {
  background: #21262d;
}
:deep(html.dark) .module-name,
:deep(html.dark) .tree-name,
:deep(html.dark) .lang-name,
:deep(html.dark) .stat-value {
  color: #e6edf3;
}
:deep(html.dark) .module-desc,
:deep(html.dark) .entry-desc,
:deep(html.dark) .stat-label,
:deep(html.dark) .lang-count,
:deep(html.dark) .tech-label {
  color: #8b949e;
}
:deep(html.dark) .lang-bar-wrap {
  background: #21262d;
}
:deep(html.dark) .tree-label:hover {
  background: #21262d;
}
</style>

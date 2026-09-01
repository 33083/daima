<template>
  <el-container class="app-layout">
    <el-header class="app-header">
      <div class="logo">
        <el-icon :size="24" color="#409eff"><FolderOpened /></el-icon>
        <span>CodeRAG 代码智能助手</span>
      </div>
      <div class="header-right">
        <span class="subtitle">基于 RAG 的代码仓库智能问答系统</span>
        <el-button text @click="appStore.toggleDarkMode()" class="dark-toggle">
          <el-icon :size="18">
            <Moon v-if="!appStore.darkMode" />
            <Sunny v-else />
          </el-icon>
        </el-button>
      </div>
    </el-header>
    <el-container>
      <el-aside width="240px" class="app-aside">
        <el-menu
          :default-active="activeMenu"
          router
          class="side-menu"
        >
          <el-menu-item index="/repos">
            <el-icon><Folder /></el-icon>
            <span>仓库管理</span>
          </el-menu-item>
          <el-menu-item index="/chat">
            <el-icon><ChatDotRound /></el-icon>
            <span>代码问答</span>
          </el-menu-item>
          <el-menu-item index="/architecture">
            <el-icon><DataAnalysis /></el-icon>
            <span>架构概览</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  FolderOpened, Folder, ChatDotRound, Moon, Sunny, DataAnalysis
} from '@element-plus/icons-vue'
import { useAppStore } from './stores/app'

const route = useRoute()
const appStore = useAppStore()
const activeMenu = computed(() => route.path)

onMounted(() => {
  appStore.initDarkMode()
})
</script>

<style scoped>
.app-layout {
  height: 100vh;
}
.app-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: none;
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 600;
}
.subtitle {
  font-size: 14px;
  opacity: 0.85;
}
.app-aside {
  background: #fff;
  border-right: 1px solid #e4e7ed;
}
.side-menu {
  border-right: none;
  height: 100%;
}
.app-main {
  background: #f5f7fa;
  padding: 20px;
  overflow-y: auto;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

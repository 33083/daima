import request from '../utils/request'

// 获取项目架构概览
export function getArchitectureOverview(repoId) {
  return request.get(`/architecture/overview/${repoId}`)
}

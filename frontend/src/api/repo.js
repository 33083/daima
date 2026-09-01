import request from './request'

// 仓库列表
export function getRepoList() {
  return request.get('/repos')
}

// 仓库详情
export function getRepo(id) {
  return request.get(`/repos/${id}`)
}

// 导入 Git 仓库
export function importGitRepo(data) {
  return request.post('/repos', { ...data, source_type: 'git' })
}

// 导入本地仓库
export function importLocalRepo(data) {
  return request.post('/repos', { ...data, source_type: 'local' })
}

// 删除仓库
export function deleteRepo(id) {
  return request.delete(`/repos/${id}`)
}

// 重新索引
export function reindexRepo(id) {
  return request.post(`/repos/${id}/reindex`)
}

// 文件列表
export function getRepoFiles(id, params) {
  return request.get(`/repos/${id}/files`, { params })
}

// 文件内容
export function getFileContent(id, path) {
  return request.get(`/repos/${id}/files/content`, { params: { path } })
}

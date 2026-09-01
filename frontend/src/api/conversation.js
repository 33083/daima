import request from '../utils/request'

// 获取仓库的会话列表
export function getConversationList(repoId, page = 1, pageSize = 20) {
  return request.get('/conversations', { params: { repo_id: repoId, page, page_size: pageSize } })
}

// 创建新会话
export function createConversation(repoId, title, mode = 'agent') {
  return request.post('/conversations', { repo_id: repoId, title, mode })
}

// 获取会话详情
export function getConversation(convId) {
  return request.get(`/conversations/${convId}`)
}

// 删除会话
export function deleteConversation(convId) {
  return request.delete(`/conversations/${convId}`)
}

// 获取会话消息列表
export function getConversationMessages(convId, page = 1, pageSize = 50) {
  return request.get(`/conversations/${convId}/messages`, { params: { page, page_size: pageSize } })
}

// 更新会话标题
export function updateConversationTitle(convId, title) {
  return request.patch(`/conversations/${convId}/title`, { title })
}

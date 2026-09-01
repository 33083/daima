import sqlite3, json, urllib.request, time, os

DB_PATH = 'C:/Users/33083/Desktop/code-rag-assistant/backend/dev.db'
BASE_URL = 'http://localhost:8000'

# 1. 清理数据库
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('DELETE FROM code_repos')
c.execute('DELETE FROM code_files')
conn.commit()
conn.close()
print('Cleared DB')

# 2. 本地导入（用新名字避免冲突）
data = json.dumps({
    'name': 'coderag-test',
    'local_path': 'C:/Users/33083/Desktop/code-rag-assistant',
    'source_type': 'local'
}).encode('utf-8')
req = urllib.request.Request(
    BASE_URL + '/api/v1/repos',
    data=data,
    headers={'Content-Type': 'application/json'}
)
resp = urllib.request.urlopen(req, timeout=30)
result = json.loads(resp.read().decode())
repo_id = result['id']
print('Import started: repo_id={}, status={}'.format(repo_id, result['status']))

# 3. 轮询进度
task_id = 'repo_{}_import'.format(repo_id)
for i in range(120):
    time.sleep(3)
    try:
        r = urllib.request.urlopen(
            BASE_URL + '/api/v1/repos/{}/tasks/{}'.format(repo_id, task_id),
            timeout=5
        )
        t = json.loads(r.read().decode())
        print('[{}s] {} {}% {}'.format(i*3, t['status'], t['progress'], t['message']))
        if t['status'] == 'completed':
            print('=== SUCCESS ===')
            r2 = urllib.request.urlopen(BASE_URL + '/api/v1/repos/{}'.format(repo_id), timeout=5)
            repo = json.loads(r2.read().decode())
            print('Files: {}, Chunks: {}'.format(repo['file_count'], repo['chunk_count']))
            if repo.get('description'):
                print('Desc:', repo['description'][:200])
            break
        elif t['status'] in ('failed', 'error'):
            print('=== FAILED ===')
            print('Error:', t.get('error_msg', 'unknown'))
            break
    except Exception as e:
        print('[{}s] poll error: {}'.format(i*3, str(e)[:100]))
else:
    print('TIMEOUT')

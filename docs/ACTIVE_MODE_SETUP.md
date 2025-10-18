# Active Mode Setup Guide

## 概述

Video Processor 支援兩種運作模式：

1. **被動模式 (Passive Mode)** - 預設模式
   - 等待來自 Node.js worker 的請求
   - 適用於線上/生產環境部署

2. **主動模式 (Active Mode)** - 備援模式
   - 主動輪詢後端 API 獲取失敗任務
   - 自動處理並回傳結果
   - 適用於本地備援實例，當線上服務故障時自動接手

---

## 架構說明

### 線上環境（被動模式）
```
Node.js Worker (主動) → Video Processor (被動) → 線上資料庫
     ↓                         ↓
  輪詢任務                  處理並返回
```

### 本地備援（主動模式）
```
Video Processor (主動) → 後端 API → 線上資料庫
     ↓                      ↓
  輪詢失敗任務           處理並回傳
     ↓
  自動接手處理
```

---

## 快速啟動

### 1. 線上環境配置（被動模式）

**.env**
```bash
# 使用預設被動模式
PROCESSOR_MODE=passive
PORT=8000

# 其他必要配置
GEMINI_API_KEY=your_api_key_here
```

**啟動**
```bash
python -m src.main
# 或
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### 2. 本地備援配置（主動模式）

**.env**
```bash
# 啟用主動模式
PROCESSOR_MODE=active

# ⚠️ 重要：主動模式必須使用單一 worker
UVICORN_WORKERS=1

# 後端 API URL（線上環境的 backend URL）
BACKEND_API_URL=https://your-production-backend.com

# 輪詢間隔（毫秒）
POLL_INTERVAL_MS=60000

# 本地服務端口（避免與線上衝突）
PORT=8001

# 其他必要配置
GEMINI_API_KEY=your_api_key_here
```

**啟動**
```bash
python -m src.main
# 或
uvicorn src.main:app --host 0.0.0.0 --port 8001
```

---

## 主動模式工作流程

### 1. 輪詢失敗任務
每 60 秒（可配置）向後端 API 發送請求：
```
GET https://your-backend.com/v1/analysis/failed?limit=3
```

### 2. 處理任務
- 從後端獲取失敗任務列表
- 逐一處理每個任務（下載影片 → 提取幀 → Gemini 分析）
- 並行處理多個任務（預設 3 個）

### 3. 回傳結果
將處理結果提交回後端：
```
PUT https://your-backend.com/v1/analysis/:jobId/result
Body: {
  recipe: { name, ingredients, steps, ... },
  metadata: { gemini_tokens, video_info }
}
```

### 4. 後端處理
後端 API 接收結果後：
- ✅ 儲存食譜到資料庫
- ✅ 扣除使用者點數
- ✅ 更新分析日誌狀態
- ✅ 發送 LINE 通知給使用者

---

## 環境變數說明

| 變數名稱 | 必填 | 預設值 | 說明 |
|---------|------|--------|------|
| `PROCESSOR_MODE` | 否 | `passive` | 運作模式：`passive` 或 `active` |
| `UVICORN_WORKERS` | 否 | `0` (自動) | Worker 數量。**Active Mode 必須設為 1** |
| `BACKEND_API_URL` | 主動模式必填 | `http://localhost:3000` | 後端 API 基礎 URL |
| `POLL_INTERVAL_MS` | 否 | `60000` | 輪詢間隔（毫秒） |
| `PORT` | 否 | `8000` | 服務端口 |
| `GEMINI_API_KEY` | 是 | - | Google Gemini API 金鑰 |

### Workers 設定重要說明

**被動模式（Passive Mode）**：
- ✅ 可以使用多個 workers（建議：2x CPU 核心數）
- 提高併發處理能力
- 無狀態設計，多個 workers 不會衝突

**主動模式（Active Mode）**：
- ⚠️ **必須設定 `UVICORN_WORKERS=1`**
- 原因：每個 worker 都會啟動獨立的輪詢循環
- 多個 workers 會導致：
  - 重複處理同一任務
  - 資源浪費
  - 可能的競態條件

**範例配置**：
```bash
# 線上環境（被動模式）- 可用多個 workers
PROCESSOR_MODE=passive
UVICORN_WORKERS=8

# 本地備援（主動模式）- 只能用 1 個 worker
PROCESSOR_MODE=active
UVICORN_WORKERS=1
```

---

## 日誌監控

### 被動模式日誌
```
[Passive Mode] Starting in PASSIVE mode (default)
[Passive Mode] Waiting for requests on /analyze and /analyze-from-url endpoints
```

### 主動模式日誌
```
[Active Mode] Starting in ACTIVE mode
[Active Mode] Will poll https://api.production.com every 60000ms
[Active Mode] Starting active worker (poll interval: 60.0s)
[Active Mode] Backend API: https://api.production.com
[Active Mode] Polling for failed jobs...
[Active Mode] Found 2 failed jobs
[Active Mode] Processing job abc-123-def
[Active Mode] Analyzing from URL: https://youtube.com/...
[Active Mode] Submitting result for job abc-123-def
[Active Mode] ✅ Job abc-123-def completed successfully
```

---

## 故障轉移場景

### 場景 1：線上服務正常運作
- 本地主動模式：**閒置**（輪詢發現無失敗任務）
- 線上被動模式：正常處理所有任務

### 場景 2：線上服務故障
1. 線上 video-processor 掛掉
2. Node.js worker 處理任務時失敗
3. 任務標記為 `status = 'failed'`
4. 本地主動模式輪詢到失敗任務
5. 本地處理並回傳結果
6. 使用者收到 LINE 通知（自動恢復）

### 場景 3：本地服務也故障
- 失敗任務保留在資料庫
- 等待任一服務恢復後處理
- 可透過後端 API 手動重試

---

## 安全考量

### API 端點保護（TODO）
目前主動模式使用的後端 API 端點尚未加入認證機制：
- `GET /v1/analysis/failed`
- `PUT /v1/analysis/:jobId/result`

**建議改進**：
1. 加入 API Key 認證
2. 使用 IP 白名單
3. 實作 rate limiting

**範例實作**（backend）：
```typescript
// middleware/api_key_auth.ts
export function verifyApiKey(req, res, next) {
  const apiKey = req.headers['x-api-key'];
  if (apiKey !== process.env.INTERNAL_API_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
}

// routes/api.ts
router.get('/analysis/failed', verifyApiKey, getFailedJobs);
router.put('/analysis/:jobId/result', verifyApiKey, submitAnalysisResult);
```

**範例實作**（video-processor）：
```python
# main.py - active_mode_worker()
headers = {
    'X-API-Key': os.getenv('INTERNAL_API_KEY')
}
resp = await client.get(f"{BACKEND_API_URL}/v1/analysis/failed", headers=headers)
```

---

## 測試指南

### 1. 測試被動模式
```bash
# 啟動服務（預設被動模式）
python -m src.main

# 發送測試請求
curl -X POST http://localhost:8000/analyze-from-url \
  -F "video_url=https://youtube.com/watch?v=..."
```

### 2. 測試主動模式
```bash
# 1. 確保後端 API 正在運行
cd backend && npm run dev

# 2. 建立測試失敗任務（透過資料庫或 API）
# 在資料庫中插入一筆 status='failed' 的 analysis_log

# 3. 啟動主動模式 video-processor
cd video-processor
export PROCESSOR_MODE=active
export BACKEND_API_URL=http://localhost:3000
python -m src.main

# 4. 觀察日誌
# 應該看到輪詢、處理、提交的完整流程
```

### 3. 測試故障轉移
```bash
# 1. 啟動線上環境（被動模式）
cd video-processor
python -m src.main

# 2. 啟動本地備援（主動模式）
cd video-processor-backup
export PROCESSOR_MODE=active
export BACKEND_API_URL=http://localhost:3000
export PORT=8001
python -m src.main

# 3. 停止線上環境模擬故障
# Ctrl+C 停止 video-processor

# 4. 建立測試任務
# 任務會失敗並被本地備援接手處理
```

---

## 常見問題

### Q1: 主動模式會不會處理到正在處理中的任務？
**A:** 不會。主動模式只查詢 `status = 'failed'` 的任務，不會碰到 `processing` 狀態的任務。

### Q2: 為什麼主動模式不能用多個 workers？
**A:** 因為每個 worker 都會獨立啟動輪詢循環，導致：
- 同一任務被多次處理
- 資源浪費（重複下載影片、重複分析）
- 可能的競態條件

**解決方案**：主動模式必須設定 `UVICORN_WORKERS=1`。如需更高處理能力，應該：
1. 運行多個獨立的主動模式實例（不同機器）
2. 在後端實作分散式鎖機制

### Q3: 多個主動模式實例會不會重複處理同一任務？
**A:** 理論上會。目前實作未加鎖機制。建議只運行一個主動模式實例，或在後端實作分散式鎖。

### Q4: 主動模式的處理速度如何？
**A:** 與被動模式相同（都使用相同的處理邏輯），但會有輪詢延遲（預設 60 秒）。

### Q5: 可以同時運行多個被動模式實例嗎？
**A:** 可以。被動模式是無狀態的，可以使用負載均衡器分散流量，並且可以用多個 workers。

### Q6: 如何監控主動模式是否正常運作？
**A:** 檢查日誌中的輪詢記錄：
```
[Active Mode] Polling for failed jobs...
```
如果停止輸出，表示服務可能掛掉。

---

## 生產環境建議

### 1. 監控告警
- 監控失敗任務數量
- 設定告警閾值（例如：失敗任務 > 10）
- 監控主動模式服務健康狀態

### 2. 日誌管理
- 使用集中式日誌系統（如 ELK、Grafana Loki）
- 保留至少 7 天的日誌
- 建立日誌搜尋和分析儀表板

### 3. 資源配置
- 主動模式建議：2 vCPU + 4GB RAM
- 輪詢間隔不宜過短（建議 60-120 秒）
- 並行處理任務數量根據資源調整

### 4. 備份策略
- 建議至少有一個本地主動模式實例
- 定期測試故障轉移流程
- 保留歷史失敗任務記錄

---

## 相關文件

- [Backend API 文件](../backend/README.md)
- [Video Processor 開發指南](./README.md)
- [部署指南](./DEPLOY.md)

---

## 更新記錄

- **2025-10-13**: 初版發布，加入主動模式支援

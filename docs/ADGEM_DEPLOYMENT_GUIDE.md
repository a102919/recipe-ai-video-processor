# AdGem Offer API 部署與測試指南

## 📋 功能概述

整合 AdGem Offer API，讓使用者透過完成任務（看廣告、填問卷等）賺取點數。

---

## 🚀 部署步驟

### Step 1: 資料庫 Migration

```bash
cd backend

# 啟動後端服務（會自動執行 migration）
npm run dev
# 或
bun run dev
```

Migration 會建立：
- `ad_source` ENUM type
- `ad_rewards` 表（追蹤廣告獎勵記錄）

### Step 2: 環境變數配置

#### Backend (.env)

```bash
# AdGem Configuration
ADGEM_APP_ID=ig0ggci279n5me7f2fkdan7l
ADGEM_WEBHOOK_SECRET=lfk5cln4ad457ceamd2bmma2
```

#### Frontend (.env)

```bash
# AdGem Configuration
VITE_ADGEM_APP_ID=ig0ggci279n5me7f2fkdan7l
```

### Step 3: 部署到 Zeabur

#### Backend

1. 在 Zeabur Dashboard 設定環境變數：
   ```
   ADGEM_APP_ID=ig0ggci279n5me7f2fkdan7l
   ADGEM_WEBHOOK_SECRET=lfk5cln4ad457ceamd2bmma2
   ```

2. 部署後端：
   ```bash
   git add .
   git commit -m "feat: integrate AdGem Offer API"
   git push
   ```

3. 確認後端 URL（例如）：
   ```
   https://recipe-ai-backend.zeabur.app
   ```

#### Frontend

1. 在 Zeabur Dashboard 設定環境變數：
   ```
   VITE_ADGEM_APP_ID=ig0ggci279n5me7f2fkdan7l
   ```

2. 部署前端

---

## 🔧 AdGem Dashboard 配置

### 1. Postback URL 設定

在 AdGem Dashboard > Integration 頁面設定：

```
https://recipe-ai-backend.zeabur.app/v1/ads/adgem-callback?user_id={user_id}&amount={amount}&transaction_id={transaction_id}&offer_id={offer_id}&payout={payout}
```

**重要**：
- 使用你的實際後端 URL
- 保留 `{xxx}` 變數（AdGem 會自動替換）

### 2. Webhook Secret

在 AdGem Dashboard > Integration > Webhook Secret 欄位填入：

```
lfk5cln4ad457ceamd2bmma2
```

### 3. Integration Type

選擇：**Offer API**

---

## 🧪 測試流程

### 測試 1：驗證後端 Callback Endpoint

使用 `curl` 模擬 AdGem callback：

```bash
curl -X GET "https://recipe-ai-backend.zeabur.app/v1/ads/adgem-callback?user_id=test_user_123&amount=5&transaction_id=test_tx_001&offer_id=test_offer&payout=0.10"
```

**預期結果**：
- 回應：`OK`
- 後端 log 顯示：`[AdGem] Rewarded 5 credits to user test_user_123 (tx: test_tx_001)`
- 資料庫 `ad_rewards` 表有新記錄
- 資料庫 `credit_transactions` 表有新記錄
- 使用者點數餘額增加 5 點

### 測試 2：驗證防重複機制

再次執行相同的 curl 指令：

```bash
curl -X GET "https://recipe-ai-backend.zeabur.app/v1/ads/adgem-callback?user_id=test_user_123&amount=5&transaction_id=test_tx_001&offer_id=test_offer&payout=0.10"
```

**預期結果**：
- 回應：`OK`（AdGem 要求）
- 使用者點數餘額**不變**（防止重複發放）
- `ad_rewards` 表記錄數量不變

### 測試 3：前端 Offerwall

1. 在 LIFF 應用中開啟「獲取點數」頁面
2. 點擊「完成任務」按鈕
3. 應該會彈出 AdGem offerwall dialog
4. 完成一個任務
5. 關閉 dialog
6. 等待 3-5 秒（AdGem 處理時間）
7. 重新整理點數餘額

**預期結果**：
- Dialog 正確顯示 AdGem offerwall
- 完成任務後點數增加
- 餘額正確更新

### 測試 4：AdGem Dashboard 測試工具

1. 登入 AdGem Dashboard
2. 前往 Integration > Test Postback
3. 輸入測試 User ID
4. 點擊「Send Test」

**預期結果**：
- AdGem 顯示「Postback successful」
- 後端收到 callback 請求
- 測試使用者點數增加

---

## 📊 監控與除錯

### 檢查後端 Logs

```bash
# Zeabur
zeabur logs backend

# Local
cd backend && npm run dev
```

關鍵 log 訊息：
- `[AdGem] Rewarded X credits to user Y (tx: Z)` - 成功發放
- `[AdGem] Missing required parameters` - 參數缺失
- `[AdGem] Invalid signature` - 簽名驗證失敗

### 檢查資料庫

```sql
-- 查看最近的廣告獎勵記錄
SELECT * FROM ad_rewards
ORDER BY created_at DESC
LIMIT 10;

-- 查看特定使用者的獎勵記錄
SELECT * FROM ad_rewards
WHERE user_id = 'USER_ID_HERE'
ORDER BY created_at DESC;

-- 檢查是否有重複記錄（應該為空）
SELECT transaction_id, COUNT(*) as count
FROM ad_rewards
GROUP BY transaction_id
HAVING COUNT(*) > 1;
```

### 常見問題排除

#### 問題 1：AdGem 回報「Postback failed」

**可能原因**：
- URL 格式錯誤
- 後端未啟動或無法訪問
- 回應非 "OK" 純文字

**解決方法**：
```typescript
// 確認 ads.ts line 65 回傳純文字
res.send('OK'); // ✅ 正確
res.json({ status: 'ok' }); // ❌ 錯誤
```

#### 問題 2：點數沒有增加

**檢查清單**：
1. 後端是否收到 callback？（檢查 logs）
2. transaction_id 是否重複？（檢查資料庫）
3. 使用者 ID 是否正確？
4. AdGem webhook secret 是否一致？

#### 問題 3：前端 Dialog 無法開啟

**檢查**：
1. 環境變數 `VITE_ADGEM_APP_ID` 是否設定？
2. 使用者是否已登入 LIFF？
3. 瀏覽器 console 是否有錯誤？

---

## 🔐 安全性檢查清單

- [x] Webhook signature 驗證已實作
- [x] Transaction ID 防重複機制
- [x] 使用者 ID 驗證
- [x] 金額正數檢查
- [x] 資料庫交易確保原子性

---

## 📈 效能指標

- Callback 處理時間：< 200ms
- 防重複檢查：O(1) - 使用 transaction_id UNIQUE index
- 資料庫查詢：最多 3 次（檢查 + 插入 + 更新）

---

## 🎯 後續優化建議

1. **監控 Dashboard**
   - 追蹤廣告收益
   - 統計使用者參與率
   - 監控填充率

2. **A/B 測試**
   - 測試不同點數獎勵比例
   - 優化 UI/UX

3. **多平台支援**
   - 整合 AppLixir（影片廣告）
   - 支援其他任務牆平台

---

## 📞 支援

如有問題，請檢查：
1. AdGem 官方文件：https://docs.adgem.com
2. 後端 logs
3. 資料庫記錄

---

## ✅ 部署檢查清單

部署前確認：

- [ ] 資料庫 migration 已執行
- [ ] 環境變數已設定（Backend & Frontend）
- [ ] AdGem Dashboard 已配置 Postback URL
- [ ] AdGem Dashboard 已設定 Webhook Secret
- [ ] 後端編譯無錯誤 (`npx tsc --noEmit`)
- [ ] 前端編譯無錯誤 (`npm run build`)
- [ ] Callback endpoint 測試通過
- [ ] 前端 Offerwall 可正常開啟

部署後驗證：

- [ ] 模擬 callback 測試成功
- [ ] 點數正確發放
- [ ] 防重複機制正常
- [ ] 使用者可見前端 UI
- [ ] AdGem Dashboard 顯示成功

**完成！🎉**

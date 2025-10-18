# GCP Always Free Tier Migration Guide

## 問題診斷

您的 GCP VM **不符合免費標準**，原因如下：

### 收費項目

| 項目 | 當前配置 | 免費標準 | 月費 |
|------|---------|---------|------|
| 靜態 IP | ❌ video-processor-ip | ✅ Ephemeral IP | **$7.20** |
| 磁碟類型 | ❌ pd-balanced | ✅ pd-standard | **$1.00** |
| 網路層級 | ❌ PREMIUM | ✅ STANDARD | **$0.50-$2** |
| **總計** | | | **~$8.70-$10.20/月** |

### 符合標準的部分 ✅

- ✅ 機器類型: e2-micro
- ✅ 區域: us-central1-c
- ✅ 磁碟容量: 10GB < 30GB
- ✅ 運行時間: < 730 小時/月

---

## 解決方案

### 選項 A：快速修復（推薦）

**立即省錢，3 步完成**

```bash
cd /Users/alan/code/RecipeAI/video-processor

# 1. 釋放靜態 IP（省 $7.20/月）
gcloud compute addresses delete video-processor-ip \
    --region=us-central1 \
    --project=gen-lang-client-0768313457 \
    --quiet

# 2. 取得當前 VM 的臨時 IP
NEW_IP=$(gcloud compute instances describe foodai \
    --zone=us-central1-c \
    --project=gen-lang-client-0768313457 \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "New service URL: http://${NEW_IP}:8000"

# 3. 更新 backend/.env
# VIDEO_PROCESSOR_URL=http://${NEW_IP}:8000
```

**立即節省**: $7.20/月
**剩餘成本**: $1-2/月（磁碟 + 網路）

---

### 選項 B：完全免費部署（最佳方案）

**遷移到 100% 免費配置**

```bash
cd /Users/alan/code/RecipeAI/video-processor

# 執行自動遷移腳本
./migrate_to_free_tier.sh
```

**腳本會自動做這些事：**
1. ✅ 建立當前磁碟快照（安全備份）
2. ✅ 創建新的免費磁碟（30GB pd-standard）
3. ✅ 創建新的免費 VM（e2-micro + STANDARD 網路）
4. ✅ 釋放靜態 IP
5. ✅ 停止舊 VM（保留資料）

**完成後成本**: **$0/月** 🎉

---

## GCP Always Free Tier 規格

要完全免費，必須符合以下所有條件：

### 計算實例
```yaml
機器類型: e2-micro
vCPUs: 0.25-2 (共享)
記憶體: 1 GB
數量: 1 個實例
區域: us-west1, us-central1, us-east1
```

### 磁碟儲存
```yaml
類型: pd-standard (HDD)
容量: 30 GB
快照: 5 GB
```

### 網路
```yaml
層級: STANDARD
IP: Ephemeral (臨時)
流量: 1 GB egress/月 (北美)
```

### 限制
- ✅ 每月 730 小時（= 1 個實例不停機）
- ❌ 靜態 IP 永遠收費（$7.20/月）
- ❌ pd-balanced/pd-ssd 收費（$0.10/GB/月）
- ❌ PREMIUM 網路流量較貴

---

## 執行步驟

### 方案 A：快速省錢（5 分鐘）

```bash
# 1. 釋放靜態 IP
gcloud compute addresses delete video-processor-ip \
    --region=us-central1 \
    --project=gen-lang-client-0768313457 \
    --quiet

# 2. 驗證 VM 仍在運行
gcloud compute instances describe foodai \
    --zone=us-central1-c \
    --project=gen-lang-client-0768313457 \
    --format="get(networkInterfaces[0].accessConfigs[0].natIP)"

# 3. 測試服務
NEW_IP=$(gcloud compute instances describe foodai \
    --zone=us-central1-c \
    --project=gen-lang-client-0768313457 \
    --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

curl http://${NEW_IP}:8000/health
```

✅ **立即節省 $7.20/月**

---

### 方案 B：完全免費（30 分鐘）

```bash
cd /Users/alan/code/RecipeAI/video-processor

# 1. 執行遷移腳本
./migrate_to_free_tier.sh

# 2. 等待遷移完成（約 10 分鐘）

# 3. 部署程式碼到新 VM
./deploy_gcp_free.sh

# 4. 驗證服務
NEW_IP=$(gcloud compute instances describe foodai-free \
    --zone=us-central1-c \
    --project=gen-lang-client-0768313457 \
    --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

curl http://${NEW_IP}:8000/health

# 5. 更新 backend/.env
echo "VIDEO_PROCESSOR_URL=http://${NEW_IP}:8000" >> ../backend/.env

# 6. 測試通過後，刪除舊 VM
gcloud compute instances delete foodai \
    --zone=us-central1-c \
    --project=gen-lang-client-0768313457 \
    --quiet
```

✅ **完全免費 $0/月**

---

## 臨時 IP 的注意事項

### ⚠️ 重要：IP 會改變

**臨時 IP 在以下情況會變化：**
- VM 停止後重新啟動
- VM 被刪除後重新創建
- GCP 強制重新分配（罕見）

### 解決方案

#### 選項 1：動態更新（簡單）

每次 VM 重啟後，更新 backend/.env：

```bash
# 取得最新 IP
NEW_IP=$(gcloud compute instances describe foodai-free \
    --zone=us-central1-c \
    --project=gen-lang-client-0768313457 \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# 更新 backend
echo "VIDEO_PROCESSOR_URL=http://${NEW_IP}:8000" > ../backend/.env

# 重啟 backend
cd ../backend
npm run dev
```

#### 選項 2：使用內部 DNS（進階）

在 GCP 內部使用實例名稱：

```bash
# backend/.env
VIDEO_PROCESSOR_URL=http://foodai-free.us-central1-c.c.gen-lang-client-0768313457.internal:8000
```

僅在 backend 也部署在 GCP 同專案時有效。

#### 選項 3：使用 Cloud DNS（專業）

設置自訂域名（需要註冊域名）：

```bash
# 1. 註冊域名（例如 example.com）
# 2. 設置 Cloud DNS
# 3. 創建 A 記錄指向 VM IP
# 4. 使用 cron 自動更新 DNS 記錄

VIDEO_PROCESSOR_URL=http://video.example.com:8000
```

---

## 驗證免費狀態

### 檢查當前配置

```bash
# 檢查 VM 類型
gcloud compute instances describe foodai-free \
    --zone=us-central1-c \
    --project=gen-lang-client-0768313457 \
    --format="value(machineType)" | xargs basename

# 應該顯示: e2-micro ✅

# 檢查磁碟類型
gcloud compute disks list \
    --project=gen-lang-client-0768313457 \
    --filter="name:foodai-free" \
    --format="table(name,sizeGb,type)"

# 應該顯示: pd-standard ✅

# 檢查靜態 IP
gcloud compute addresses list \
    --project=gen-lang-client-0768313457

# 應該是空的（無靜態 IP）✅
```

### 查看帳單

1. 前往 [GCP Billing Console](https://console.cloud.google.com/billing/)
2. 選擇專案 `gen-lang-client-0768313457`
3. 查看「當月費用預測」
4. 應該顯示 **$0.00** ✅

---

## 常見問題

### Q1: 為什麼靜態 IP 要收費？

靜態 IP 是稀缺資源，GCP 鼓勵釋放未使用的 IP。即使 VM 關機，靜態 IP 仍然收費（$7.20/月）。

### Q2: 臨時 IP 會不會用完？

不會。每次 VM 啟動時，GCP 會自動分配一個可用的臨時 IP。

### Q3: 我需要靜態 IP 嗎？

**大多數情況不需要**：
- ✅ 臨時 IP 在 VM 運行期間不會改變
- ✅ 可以用 Cloud DNS 綁定域名
- ✅ 內部服務可用實例名稱溝通

**需要靜態 IP 的情況**：
- 外部服務需要白名單 IP
- 使用 SSL 證書綁定 IP
- 高可用性要求（VM 替換後 IP 不變）

### Q4: pd-standard 會不會太慢？

對於 video-processor，**完全足夠**：
- 影片處理主要消耗 CPU 和記憶體
- 讀寫速度差異不大（HDD vs SSD）
- 30GB 儲存對暫存影片綽綽有餘

---

## 總結

### 當前狀態
```
機器: e2-micro ✅
區域: us-central1-c ✅
磁碟: 10GB pd-balanced ❌ ($1/月)
IP: 靜態 ❌ ($7.20/月)
網路: PREMIUM ❌ ($0.50-$2/月)
────────────────────────────
總成本: $8.70-$10.20/月
```

### 目標狀態（方案 B）
```
機器: e2-micro ✅
區域: us-central1-c ✅
磁碟: 30GB pd-standard ✅
IP: 臨時 ✅
網路: STANDARD ✅
────────────────────────────
總成本: $0/月 🎉
```

---

## 立即行動

### 🚀 推薦方案

```bash
cd /Users/alan/code/RecipeAI/video-processor

# 完全免費遷移（30 分鐘）
./migrate_to_free_tier.sh
```

### 💰 快速省錢

```bash
# 只釋放靜態 IP（5 分鐘，省 $7.20/月）
gcloud compute addresses delete video-processor-ip \
    --region=us-central1 \
    --project=gen-lang-client-0768313457 \
    --quiet
```

---

**問題？** 在遷移過程中遇到問題，隨時問我！

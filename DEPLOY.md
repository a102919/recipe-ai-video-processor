# Video Processor 部署指南

**簡單三步驟：改程式碼 → 部署 → 驗證**

---

## 快速部署（更新程式碼）

### 1. 確認本地改動

```bash
cd /Users/alan/code/RecipeAI/video-processor

# 查看改了什麼
git status
git diff

# 提交改動（可選，建議做）
git add .
git commit -m "描述你改了什麼"
git push
```

### 2. 執行部署腳本

```bash
./deploy_gcp.sh
```

**就這樣。** 腳本會自動：
- 打包程式碼（排除 .git, node_modules 等）
- 上傳到 GCP VM
- 用 `--no-cache` 重新建 Docker image（保證拿到新程式碼）
- 重啟容器
- 顯示部署結果和日誌

**預計時間**：3-4 分鐘（大部分時間在 Docker build）

### 3. 驗證部署

腳本執行完會顯示：
```
✅ Deployment Complete!

Service URL: http://136.114.216.235:8000
Health Check: http://136.114.216.235:8000/health
```

**驗證健康狀態：**
```bash
curl http://136.114.216.235:8000/health
# 預期： {"status":"healthy","service":"video-processor"}
```

**測試 YouTube 下載：**
```bash
curl -X POST "http://136.114.216.235:8000/analyze-from-url" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "video_url=https://youtube.com/shorts/cJmBiqy0IDU"
```

---

## 常見問題

### Q: 部署後程式碼沒更新？

**A: 這不可能發生。** 因為：
1. 腳本用 `docker-compose build --no-cache` 強制重建
2. 每次都重新上傳程式碼

如果真的懷疑，SSH 進 VM 檢查：
```bash
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457"
cd /home/alan/video-processor
cat src/downloader.py | head -20  # 檢查程式碼
docker-compose logs --tail=20      # 檢查日誌
```

### Q: 只改了 .env 怎麼辦？

**A: 一樣執行 `./deploy_gcp.sh`**

腳本會單獨上傳 `.env` 並重啟容器。

### Q: 部署失敗怎麼辦？

**A: 看錯誤訊息。** 通常是：

1. **SSH 連不上**
   ```bash
   gcloud compute config-ssh --project "gen-lang-client-0768313457"
   ```

2. **Docker 掛了**
   ```bash
   gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
     --command "sudo systemctl restart docker"
   ```

3. **權限問題**
   ```bash
   # 確認你的 gcloud 帳號是對的
   gcloud config list account
   ```

### Q: 如何查看即時日誌？

```bash
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "cd /home/alan/video-processor && docker-compose logs -f"

# 按 Ctrl+C 離開
```

### Q: 如何重啟服務（不重新部署）？

```bash
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "cd /home/alan/video-processor && docker-compose restart"
```

### Q: 如何停止服務？

```bash
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "cd /home/alan/video-processor && docker-compose down"
```

---

## 環境變數更新

如果只改 `.env`：

1. **本地編輯** `.env`
2. **執行部署** `./deploy_gcp.sh`
3. **自動生效**（腳本會上傳 .env 並重啟容器）

**不需要** 手動 SSH 進 VM 改。

---

## 緊急回滾

如果新版本有問題，快速回到上一版：

```bash
# 1. Git 回到上一版
git log --oneline -5  # 找到上一個 commit ID
git checkout <commit-id>

# 2. 重新部署
./deploy_gcp.sh

# 3. 修復完後回到最新版
git checkout main
```

---

## 部署檢查清單

每次部署前：
- [ ] 本地測試過嗎？
- [ ] Git commit 了嗎？（可選但建議）
- [ ] `.env` 有敏感資料嗎？（有的話確認不在 git 中）

部署後：
- [ ] 健康檢查通過？ `curl .../health`
- [ ] 日誌正常嗎？ `docker-compose logs`
- [ ] 功能測試通過？（發個測試請求）

---

## 技術細節

### 部署腳本做了什麼

```bash
./deploy_gcp.sh
```

1. **打包程式碼** → `/tmp/video-processor-<timestamp>.tar.gz`
   - 排除：.git, node_modules, __pycache__, downloads
   - 包含：src/, requirements.txt, Dockerfile, docker-compose.yml

2. **上傳到 VM** → `/home/alan/video-processor/`
   - 上傳 tar.gz
   - 解壓縮
   - 單獨上傳 `.env`（安全）

3. **重建 Docker Image**
   ```bash
   docker-compose down          # 停止舊容器
   docker-compose build --no-cache  # 強制重建（無快取）
   docker-compose up -d         # 啟動新容器
   ```

4. **顯示狀態**
   - 容器狀態
   - 最近 20 行日誌
   - 服務 URL

### 為什麼用 `--no-cache`？

**保證拿到最新程式碼。** Docker layer cache 可能導致舊程式碼殘留，`--no-cache` 強制從零開始建。

**代價**：建置時間 2-3 分鐘（可接受）

---

## 效能優化建議

### 如果需要更快部署

可以改用 `docker-compose build`（有快取），但：
- 改 Python 檔案 → 會更新 ✅
- 改 requirements.txt → 會更新 ✅
- 改 Dockerfile → **可能不更新** ❌

**建議**：保持 `--no-cache`，穩定優於速度。

---

## 後端連接設定

後端需要指向 GCP 的 video-processor：

### 開發環境（本地）
```bash
# /Users/alan/code/RecipeAI/backend/.env
VIDEO_PROCESSOR_URL=http://localhost:8000
```

### 生產環境
```bash
# /Users/alan/code/RecipeAI/backend/.env
VIDEO_PROCESSOR_URL=http://136.114.216.235:8000
```

**改完記得重啟後端：**
```bash
cd /Users/alan/code/RecipeAI/backend
npm run dev  # 或 pm2 restart
```

---

## 監控與警報（可選）

### 設定健康檢查 Cron

SSH 進 VM：
```bash
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457"
```

建立健康檢查腳本：
```bash
cat > /home/alan/healthcheck.sh << 'EOF'
#!/bin/bash
if ! curl -f http://localhost:8000/health &>/dev/null; then
  cd /home/alan/video-processor && docker-compose restart
fi
EOF

chmod +x /home/alan/healthcheck.sh
```

設定 cron（每 5 分鐘檢查一次）：
```bash
(crontab -l 2>/dev/null; echo '*/5 * * * * /home/alan/healthcheck.sh') | crontab -
```

---

## 成本管理

**當前配置**：GCP n1-standard-1 (1 vCPU, 3.75 GB RAM)
- **費用**：約 $24/月
- **包含**：VM 運算 + 外部 IP + 30GB 硬碟

### 省錢小技巧

1. **不用時關機**
   ```bash
   gcloud compute instances stop foodai --zone "us-central1-c"
   # 開機
   gcloud compute instances start foodai --zone "us-central1-c"
   ```

2. **改用 Preemptible VM**（省 70% 但可能被中斷）
   ```bash
   # 需要重建 VM，不建議生產環境用
   ```

---

## 總結

**部署流程**：
```bash
# 1. 改程式碼
vim src/downloader.py

# 2. 部署
./deploy_gcp.sh

# 3. 驗證
curl http://136.114.216.235:8000/health
```

**就這三步。簡單、可靠、無廢話。**

---

## 進階：首次設定（已完成，僅供參考）

如果要在新 VM 上部署：

```bash
# 1. 建立 VM（GCP Console 或 gcloud）
gcloud compute instances create foodai \
  --zone=us-central1-c \
  --machine-type=n1-standard-1 \
  --image-family=ubuntu-2004-lts \
  --image-project=ubuntu-os-cloud

# 2. 首次設定（安裝 Docker）
./deploy_gcp.sh --init

# 3. 設定防火牆
gcloud compute firewall-rules create allow-video-processor \
  --allow tcp:8000 \
  --source-ranges 0.0.0.0/0 \
  --project "gen-lang-client-0768313457"

# 4. 正常部署
./deploy_gcp.sh
```

**當前 VM 已完成設定，直接用 `./deploy_gcp.sh` 即可。**

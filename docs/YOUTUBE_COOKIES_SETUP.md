# YouTube Cookies 設置指南

## 為何需要 Cookies？

當你下載 YouTube 受保護的視頻時，可能會遇到以下問題：

```
ERROR: [YouTube] age-restricted video
ERROR: [YouTube] Video unavailable. This video requires payment
ERROR: [YouTube] Video unavailable. This video is private
```

**解決方案**：提供已登入的 YouTube cookies，讓 yt-dlp 使用你的帳號權限下載。

---

## 🆕 新架構：Cookies 自動從 R2 讀取

**好消息！** 現在 cookies 會自動從 R2 讀取，無需配置環境變數！

**Cookies 位置**：
```
https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.youtube.com_cookies.txt
```

**優點**：
- ✅ 更新 cookies 不需要重啟服務
- ✅ 無需配置 Zeabur 環境變數
- ✅ 無環境變數大小限制
- ✅ 更容易管理和更新
- ✅ 自動根據視頻平台選擇對應 cookies（支援 YouTube + Instagram）

---

## 步驟 1：獲取 Cookies（本地操作）

**推薦方法：使用 yt-dlp 直接提取** ⭐

```bash
# 1. 確保已在 Chrome 登入 YouTube（使用你自己的帳號即可）

# 2. 在 video-processor 目錄執行
cd /Users/alan/code/RecipeAI/video-processor

# 3. 從 Chrome 提取 cookies
yt-dlp --cookies-from-browser chrome --cookies youtube_cookies_only.txt "https://www.youtube.com/"

# 4. 檢查提取的 cookies（應該有 50+ 行）
cat youtube_cookies_only.txt | wc -l

# 5. 驗證關鍵 cookies 存在
grep -E "(VISITOR_INFO1_LIVE|CONSENT|PREF)" youtube_cookies_only.txt
```

**預期輸出**：
```
Extracted 3000+ cookies from chrome
✅ 應該看到 VISITOR_INFO1_LIVE, CONSENT, PREF 等關鍵 cookies
```

---

## 步驟 2：上傳到 R2

上傳 cookies 文件到 R2（自動被服務使用）：

```bash
# 確保在 video-processor 目錄
cd /Users/alan/code/RecipeAI/video-processor

# 創建上傳腳本（如果沒有）
cat > upload_youtube_cookies.py << 'EOF'
import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

r2_client = boto3.client(
    's3',
    endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
    aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
    region_name='auto'
)

with open('youtube_cookies_only.txt', 'rb') as f:
    r2_client.put_object(
        Bucket=os.getenv('R2_BUCKET_NAME'),
        Key='thumbnails/www.youtube.com_cookies.txt',
        Body=f,
        ContentType='text/plain'
    )

print("✅ Uploaded to R2: https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.youtube.com_cookies.txt")
EOF

# 執行上傳
python3 upload_youtube_cookies.py
```

**預期輸出**：
```
✅ Uploaded to R2: https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.youtube.com_cookies.txt
```

---

## 步驟 3：驗證（無需重啟服務！）

Cookies 會在**下次請求時自動載入**，無需重啟 Zeabur 服務！

**測試方法**：

```bash
# 發送測試請求（替換為你的 Zeabur URL 和一個受保護的 YouTube 視頻）
curl -X POST https://your-zeabur-url.zeabur.app/analyze-from-url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=EXAMPLE"}'
```

**檢查日誌**：
```
INFO:src.downloader:Downloading Youtube cookies from R2...
INFO:src.downloader:Using Youtube cookies from R2
INFO:src.downloader:Cookies validation: Netscape header=True, Cookie count=50+, Cookie names=[...]
INFO:src.downloader:All critical cookies present ✓
```

**預期結果**：
- ✅ 不再出現 age-restricted 錯誤
- ✅ 可以下載私密或會員專屬視頻
- ✅ 無需重啟服務

---

## 維護：更新 Cookies

### 何時需要更新？

當你看到錯誤：

```
ERROR: [YouTube] age-restricted video
ERROR: [YouTube] Video unavailable
WARNING: The cookies from R2 may have expired
```

或者距離上次設置已超過 **3-6 個月**。

### 如何更新？（超簡單！）

```bash
# 1. 提取新的 cookies
yt-dlp --cookies-from-browser chrome --cookies youtube_cookies_only.txt "https://www.youtube.com/"

# 2. 上傳到 R2
python3 upload_youtube_cookies.py

# 3. 完成！無需重啟服務
```

**建議**：設置日曆提醒，每 3-6 個月更新一次。

---

## 安全注意事項 ⚠️

### DO ✅
- ✅ YouTube cookies 可以使用你的個人帳號（不像 Instagram 需要測試帳號）
- ✅ 僅用於下載視頻，不會進行任何其他操作
- ✅ 定期更新 cookies（每 3-6 個月）
- ✅ 添加到 `.gitignore`（已配置）：
  ```
  *cookies*.txt
  secrets/
  ```

### DON'T ❌
- ❌ **永遠不要**提交 cookies 到 Git
- ❌ **永遠不要**在公開 URL 暴露 cookies
- ❌ **永遠不要**分享 cookies 給不信任的人
- ❌ **不要**在 cookies 文件所在期間進行敏感操作（購買、修改帳號設定等）

---

## 故障排除

### 問題 1：仍然出現 age-restricted 錯誤

**症狀**：
```
ERROR: [YouTube] age-restricted video
```

**解決方案**：
```bash
# 1. 檢查 R2 cookies 是否可訪問
curl https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.youtube.com_cookies.txt

# 2. 驗證 cookies 包含關鍵字段
curl -s https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.youtube.com_cookies.txt | grep VISITOR_INFO1_LIVE

# 3. 如果 cookies 過期，重新提取並上傳（見「維護：更新 Cookies」）
```

### 問題 2：日誌顯示 "Failed to download cookies from R2"

**可能原因**：
- R2 URL 無法訪問
- 網路問題

**解決方案**：
```bash
# 檢查 R2 連線
curl -I https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.youtube.com_cookies.txt

# 應該返回 HTTP/2 200
```

### 問題 3：日誌顯示 "Missing some critical cookies"

**症狀**：
```
WARNING:src.downloader:Missing some critical cookies: {'VISITOR_INFO1_LIVE'}
```

**解決方案**：
重新提取 cookies，確保：
1. Chrome 已登入 YouTube
2. 在 YouTube 頁面停留並刷新一次
3. 重新執行 yt-dlp 命令提取 cookies

**注意**：YouTube cookies 可能因帳號狀態而略有不同，缺少部分 cookies 通常不會影響功能。

---

## 總結

**🚀 新流程（R2 自動載入）：**
```
1. 在 Chrome 登入 YouTube
   ↓
2. 本地提取 cookies（yt-dlp --cookies-from-browser）
   ↓
3. 上傳到 R2（python3 upload_youtube_cookies.py）
   ↓
4. 完成！服務自動使用新 cookies（無需重啟）
   ↓
5. 每 3-6 個月重複步驟 2-3 更新
```

**✨ 優點：**
- ✅ 可以下載年齡限制、私密、會員專屬視頻
- ✅ 自動根據平台選擇對應 cookies（YouTube/Instagram）
- ✅ 更新 cookies 無需重啟服務
- ✅ 無需配置 Zeabur 環境變數
- ✅ 更容易管理和維護

**📊 成本：**
- R2 存儲：免費（5KB 文件）
- R2 流量：極低（每次請求下載一次 cookies）
- 維護時間：每 3-6 個月 2 分鐘

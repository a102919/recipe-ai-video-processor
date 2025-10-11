# Instagram Cookies 設置指南

## 為何需要 Cookies？

當你連續下載多個 Instagram 視頻時，Instagram 的反爬蟲機制會觸發 rate limiting：

```
ERROR: [Instagram] rate-limit reached or login required
```

**解決方案**：提供已登入的 Instagram cookies，讓 yt-dlp 假裝成瀏覽器。

---

## 🆕 新架構：Cookies 自動從 R2 讀取

**好消息！** 現在 cookies 會自動從 R2 讀取，無需配置環境變數！

**Cookies 位置**：
```
https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.instagram.com_cookies.txt
```

**優點**：
- ✅ 更新 cookies 不需要重啟服務
- ✅ 無需配置 Zeabur 環境變數
- ✅ 無環境變數大小限制
- ✅ 更容易管理和更新

---

## 步驟 1：獲取 Cookies（本地操作）

**推薦方法：使用 yt-dlp 直接提取** ⭐

```bash
# 1. 確保已在 Chrome 登入 Instagram（使用測試帳號）

# 2. 在 video-processor 目錄執行
cd /Users/alan/code/RecipeAI/video-processor

# 3. 從 Chrome 提取 cookies
yt-dlp --cookies-from-browser chrome --cookies instagram_cookies_only.txt "https://www.instagram.com/"

# 4. 檢查提取的 cookies（應該有 10+ 行）
cat instagram_cookies_only.txt | wc -l

# 5. 驗證關鍵 cookies 存在
grep -E "(sessionid|csrftoken|ds_user_id)" instagram_cookies_only.txt
```

**預期輸出**：
```
Extracted 3260 cookies from chrome
✅ 應該看到 sessionid, csrftoken, ds_user_id 三個關鍵 cookies
```

---

## 步驟 2：上傳到 R2

上傳 cookies 文件到 R2（自動被服務使用）：

```bash
# 確保在 video-processor 目錄
cd /Users/alan/code/RecipeAI/video-processor

# 創建上傳腳本（如果沒有）
cat > upload_cookies.py << 'EOF'
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

with open('instagram_cookies_only.txt', 'rb') as f:
    r2_client.put_object(
        Bucket=os.getenv('R2_BUCKET_NAME'),
        Key='thumbnails/www.instagram.com_cookies.txt',
        Body=f,
        ContentType='text/plain'
    )

print("✅ Uploaded to R2: https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.instagram.com_cookies.txt")
EOF

# 執行上傳
python3 upload_cookies.py
```

**預期輸出**：
```
✅ Uploaded to R2: https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.instagram.com_cookies.txt
```

---

## 步驟 3：驗證（無需重啟服務！）

Cookies 會在**下次請求時自動載入**，無需重啟 Zeabur 服務！

**測試方法**：

```bash
# 發送測試請求（替換為你的 Zeabur URL）
curl -X POST https://your-zeabur-url.zeabur.app/analyze-from-url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.instagram.com/reel/DPYq1HMiWzp/"}'
```

**檢查日誌**：
```
INFO:src.downloader:Downloading Instagram cookies from R2...
INFO:src.downloader:Using Instagram cookies from R2
INFO:src.downloader:Cookies validation: Netscape header=True, Cookie count=14, Cookie names=[...]
INFO:src.downloader:All critical cookies present ✓
```

**預期結果**：
- ✅ 不再出現 rate-limit 錯誤
- ✅ 連續下載多個視頻都成功
- ✅ 無需重啟服務

---

## 維護：更新 Cookies

### 何時需要更新？

當你看到錯誤：

```
ERROR: [Instagram] rate-limit reached or login required
WARNING: The cookies from R2 may have expired
```

或者距離上次設置已超過 **1-3 個月**。

### 如何更新？（超簡單！）

```bash
# 1. 提取新的 cookies
yt-dlp --cookies-from-browser chrome --cookies instagram_cookies_only.txt "https://www.instagram.com/"

# 2. 上傳到 R2
python3 upload_cookies.py

# 3. 完成！無需重啟服務
```

**建議**：設置日曆提醒，每 1-2 個月更新一次。

---

## 安全注意事項 ⚠️

### DO ✅
- ✅ 使用測試 Instagram 帳號（不是個人帳號）
- ✅ 只在 Zeabur 環境變量中配置（加密存儲）
- ✅ 定期更新 cookies
- ✅ 添加到 `.gitignore`：
  ```
  *cookies*.txt
  secrets/
  ```

### DON'T ❌
- ❌ **永遠不要**提交 cookies 到 Git
- ❌ **永遠不要**在公開 URL 暴露 cookies
- ❌ **永遠不要**使用個人 Instagram 帳號
- ❌ **永遠不要**分享 cookies 給他人

---

## 故障排除

### 問題 1：仍然出現 rate-limit 錯誤

**症狀**：
```
ERROR: [Instagram] rate-limit reached or login required
```

**解決方案**：
```bash
# 1. 檢查 R2 cookies 是否可訪問
curl https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.instagram.com_cookies.txt

# 2. 驗證 cookies 包含關鍵字段
curl -s https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.instagram.com_cookies.txt | grep sessionid

# 3. 如果 cookies 過期，重新提取並上傳（見「維護：更新 Cookies」）
```

### 問題 2：日志顯示 "Failed to download cookies from R2"

**可能原因**：
- R2 URL 無法訪問
- 網路問題

**解決方案**：
```bash
# 檢查 R2 連線
curl -I https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.instagram.com_cookies.txt

# 應該返回 HTTP/2 200
```

### 問題 3：日志顯示 "Missing critical cookies"

**症狀**：
```
WARNING:src.downloader:Missing critical cookies: {'sessionid'}
```

**解決方案**：
重新提取 cookies，確保：
1. Chrome 已登入 Instagram
2. 在 Instagram 頁面停留並刷新一次
3. 重新執行 yt-dlp 命令提取 cookies

---

## 總結

**🚀 新流程（R2 自動載入）：**
```
1. 創建測試 Instagram 帳號並登入 Chrome
   ↓
2. 本地提取 cookies（yt-dlp --cookies-from-browser）
   ↓
3. 上傳到 R2（python3 upload_cookies.py）
   ↓
4. 完成！服務自動使用新 cookies（無需重啟）
   ↓
5. 每 1-2 個月重複步驟 2-3 更新
```

**✨ 優點：**
- ✅ 可以連續下載多個 Instagram 視頻
- ✅ 不再頻繁遇到 rate-limit 錯誤
- ✅ 更新 cookies 無需重啟服務
- ✅ 無需配置 Zeabur 環境變數
- ✅ 更容易管理和維護

**📊 成本：**
- R2 存儲：免費（2KB 文件）
- R2 流量：極低（每次請求下載一次 cookies）
- 維護時間：每月 2 分鐘

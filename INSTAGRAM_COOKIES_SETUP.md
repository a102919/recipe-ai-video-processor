# Instagram Cookies 設置指南

## 為何需要 Cookies？

當你連續下載多個 Instagram 視頻時，Instagram 的反爬蟲機制會觸發 rate limiting：

```
ERROR: [Instagram] rate-limit reached or login required
```

**解決方案**：提供已登入的 Instagram cookies，讓 yt-dlp 假裝成瀏覽器。

---

## 步驟 1：獲取 Cookies（本地操作）

### 方法 A：使用 Chrome 擴展（最簡單）✅

1. **安裝擴展**
   - Chrome: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - Edge: 搜索同名擴展

2. **登入 Instagram**
   - 在瀏覽器打開 [instagram.com](https://instagram.com)
   - 登入你的帳號（建議使用測試帳號）

3. **導出 Cookies**
   - 停留在任意 Instagram 頁面
   - 點擊擴展圖標
   - 選擇 "Export" → 選擇 "instagram.com"
   - 保存為 `instagram_cookies.txt`

### 方法 B：使用 Firefox 擴展

1. **安裝擴展**
   - [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

2. **導出 Cookies**
   - 登入 Instagram
   - 點擊擴展圖標
   - "Export cookies for instagram.com"
   - 保存文件

### 方法 C：使用 yt-dlp 命令（進階）

```bash
# 自動從 Chrome 提取 Instagram cookies
yt-dlp --cookies-from-browser chrome --cookies instagram_cookies.txt "https://www.instagram.com/"
```

---

## 步驟 2：配置到 Zeabur（線上環境）

### 2.1 準備 Cookies 內容

在本地終端執行：

```bash
cat instagram_cookies.txt
```

**複製整個文件內容**，應該類似：

```
# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	1735689600	sessionid	12345678%3Aabcdefg
.instagram.com	TRUE	/	FALSE	1735689600	csrftoken	xyzABC123
.instagram.com	TRUE	/	FALSE	1735689600	ds_user_id	987654321
```

### 2.2 在 Zeabur 設置環境變量

1. 打開 Zeabur Dashboard
2. 選擇你的 `video-processor` 服務
3. 進入 "Variables" (環境變量) 設置
4. 添加新變量：
   - **變量名**：`INSTAGRAM_COOKIES`
   - **變量值**：貼上步驟 2.1 複製的內容
5. 保存並重啟服務

### 2.3 驗證配置

檢查日志中是否出現：

```
INFO:src.downloader:Using Instagram cookies from environment variable
```

如果出現，說明配置成功！

---

## 步驟 3：測試

發送測試請求：

```bash
curl -X POST https://your-zeabur-url.zeabur.app/analyze-from-url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.instagram.com/reel/DOd79NzEr9f/"}'
```

**預期結果**：
- ✅ 不再出現 rate-limit 錯誤
- ✅ 連續下載多個視頻都成功

---

## 維護：更新 Cookies

### 何時需要更新？

當你看到錯誤：

```
ERROR: [Instagram] Unable to extract ... (cookies expired)
```

或者距離上次設置已超過 **1-3 個月**。

### 如何更新？

1. 重複「步驟 1：獲取 Cookies」
2. 在 Zeabur 更新 `INSTAGRAM_COOKIES` 環境變量
3. 重啟服務

**建議**：設置日曆提醒，每月檢查一次。

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

**可能原因**：
- Cookies 格式不正確
- Cookies 已過期
- Instagram 帳號被封鎖

**解決方案**：
1. 重新導出 cookies（確保完整複製）
2. 檢查 Instagram 帳號是否正常登入
3. 嘗試用不同 Instagram 帳號

### 問題 2：日志沒有顯示 "Using Instagram cookies"

**可能原因**：
- 環境變量名稱錯誤（必須是 `INSTAGRAM_COOKIES`）
- 環境變量未保存
- 服務未重啟

**解決方案**：
1. 確認變量名拼寫正確
2. 在 Zeabur Dashboard 檢查變量是否存在
3. 重啟服務

### 問題 3：Cookies 文件格式錯誤

**症狀**：
```
WARNING:src.downloader:Failed to create cookies file: ...
```

**解決方案**：
- 確保使用 Netscape 格式（瀏覽器擴展自動生成）
- 檢查文件開頭是否有 `# Netscape HTTP Cookie File`
- 重新導出 cookies

---

## 替代方案

如果 cookies 方案不適合你，可以考慮：

### 方案 B：增加請求間隔
已經實作了 `sleep_interval: 3` 秒，可以增加到 10 秒：

```python
'sleep_interval': 10,
'max_sleep_interval': 30,
```

### 方案 C：使用 Proxy
需要付費 proxy 服務（不推薦）。

---

## 總結

**最佳實踐流程：**
```
1. 創建測試 Instagram 帳號
   ↓
2. 用擴展導出 cookies.txt
   ↓
3. 設置 Zeabur 環境變量 INSTAGRAM_COOKIES
   ↓
4. 重啟服務
   ↓
5. 每 1-2 個月更新一次
```

**預期效果：**
- ✅ 可以連續下載多個 Instagram 視頻
- ✅ 不再頻繁遇到 rate-limit 錯誤
- ✅ 更穩定的下載成功率

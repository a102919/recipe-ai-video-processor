# Video Processor 快速啟動指南

## 🚀 快速啟動方式

### 方法 1：使用啟動腳本（推薦）
```bash
./start.sh
```

### 方法 2：使用 VSCode
1. 打開 VSCode
2. 按 `F5` 或點擊「Run and Debug」
3. 選擇「🚀 Start Video Processor」

### 方法 3：手動啟動
```bash
source venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port 8001
```

## 📍 服務地址

- **API**: http://localhost:8001
- **文檔**: http://localhost:8001/docs
- **健康檢查**: http://localhost:8001/health

## ⚙️ 環境變量

確保 `.env` 文件已配置：
- `GEMINI_API_KEY`: Gemini Vision API 金鑰
- `R2_*`: Cloudflare R2 儲存配置
- `PORT`: 服務端口（預設 8001）

## 🛠️ 開發工具

- **熱重載**: 修改程式碼自動重新載入
- **API 文檔**: Swagger UI 在 `/docs`
- **調試**: VSCode 已配置斷點調試

## 🔧 故障排除

### Port 已被占用
修改 `.env` 中的 `PORT` 或使用：
```bash
PORT=8002 ./start.sh
```

### Import 錯誤
確保在虛擬環境中且依賴已安裝：
```bash
source venv/bin/activate
pip install -r requirements.txt
```

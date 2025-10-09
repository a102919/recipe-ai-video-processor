# Video Processor - Quick Start

## 🚀 快速开始（推荐方式）

### 方式 1: Docker Compose（最简单）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API keys

# 2. 启动服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 测试
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

访问 API 文档: http://localhost:8000/docs

停止服务: `docker-compose down`

---

### 方式 2: 自动测试脚本

```bash
# 一键构建、测试、启动
./test-docker.sh
```

这会自动：
- ✅ 构建 Docker 镜像
- ✅ 测试 FFmpeg 安装
- ✅ 启动服务
- ✅ 验证健康检查

---

### 方式 3: 本地开发（不使用 Docker）

```bash
# 1. 安装系统依赖（macOS）
brew install ffmpeg

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装 Python 依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env

# 5. 启动服务
./start.sh
# 或
uvicorn src.main:app --reload --port 8001
```

---

## 🧪 验证部署

### 1. Health Check（健康检查）
```bash
curl http://localhost:8000/health
```
预期输出:
```json
{"status":"healthy","service":"video-processor"}
```

### 2. Ready Check（依赖检查）
```bash
curl http://localhost:8000/ready
```
预期输出:
```json
{
  "status": "ready",
  "checks": {
    "ffmpeg": "ok",
    "gemini_api_key": "ok"
  }
}
```

如果 `ffmpeg` 显示 error，说明 FFmpeg 未正确安装。

### 3. 测试视频分析

访问 Swagger UI: http://localhost:8000/docs

使用 `/analyze-from-url` 端点测试：
```bash
curl -X POST "http://localhost:8000/analyze-from-url" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "video_url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

---

## 🔧 环境变量配置

必需变量（见 `.env.example`）：

```env
# Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Cloudflare R2
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=recipeai-thumbnails
R2_PUBLIC_URL=https://your-r2-url.com

# 服务配置
PORT=8000
UVICORN_WORKERS=4  # Docker 默认 4，本地可用 2
```

---

## 📦 Zeabur 部署

### 前置检查
```bash
# 确保这些文件存在
ls -la Dockerfile
ls -la .dockerignore
ls -la zbpack.json
ls -la docker-compose.yml
```

### 部署步骤

1. **提交代码**
```bash
git add .
git commit -m "feat: Add Docker support with FFmpeg"
git push
```

2. **Zeabur 配置**
- 连接 Git 仓库
- Zeabur 会自动检测 `Dockerfile`
- 配置环境变量（同上）

3. **验证部署**
```bash
# 替换为你的 Zeabur URL
curl https://your-app.zeabur.app/ready
```

应该看到 `"status":"ready"` 和所有 checks 为 `"ok"`

---

## 🐛 故障排查

### FFmpeg 未找到
**症状**: `/ready` 返回 `"ffmpeg": "error: ..."`

**Docker 用户**:
```bash
# 进入容器检查
docker exec -it recipeai-video-processor bash
ffmpeg -version  # 应该输出版本信息
```

**本地用户**:
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# 验证
ffmpeg -version
ffprobe -version
```

### Gemini API Key 问题
**症状**: `/ready` 返回 `"gemini_api_key": "missing"`

**解决**:
1. 检查 `.env` 文件是否存在
2. 确认 `GEMINI_API_KEY` 已设置
3. Docker 用户: 确保传入环境变量
   ```bash
   docker run --env-file .env ...
   ```

### 端口已被占用
**症状**: `Address already in use`

**解决**:
```bash
# 修改 .env 中的 PORT
PORT=8001

# 或临时覆盖
PORT=8001 docker-compose up
PORT=8001 ./start.sh
```

### 内存不足
**症状**: 容器 OOM killed

**解决**:
1. 减少 worker 数量:
   ```env
   UVICORN_WORKERS=2
   ```
2. 限制 Docker 内存:
   ```bash
   docker run -m 1g ...
   ```

---

## 📚 更多文档

- 完整部署指南: [DEPLOYMENT.md](./DEPLOYMENT.md)
- 启动说明: [README_STARTUP.md](./README_STARTUP.md)
- API 文档: http://localhost:8000/docs (服务运行后)

---

## ✅ 检查清单

部署前确认：

- [ ] `.env` 已配置所有必需变量
- [ ] FFmpeg 已安装（Docker 自动 / 本地手动）
- [ ] Gemini API key 有效
- [ ] R2 credentials 正确
- [ ] 端口未被占用
- [ ] Docker 已安装（如果使用 Docker）
- [ ] 已测试 `/health` 和 `/ready` 端点

部署成功标志：
- [ ] `/ready` 返回 `"status":"ready"`
- [ ] 所有 checks 为 `"ok"`
- [ ] 可以访问 `/docs`
- [ ] 视频分析功能正常

---

Happy cooking! 🍳

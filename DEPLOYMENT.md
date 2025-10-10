# Video Processor 部署指南

## 问题诊断

### 根本原因
Video Processor 在 Zeabur 部署失败的核心问题：

1. **缺少系统依赖 FFmpeg**
   - 应用使用 `ffmpeg` 命令提取视频帧 (`src/extractor.py`)
   - 应用使用 `ffprobe` 命令获取视频元数据 (`src/video_utils.py`)
   - 这些是系统级二进制工具，无法通过 `pip install` 安装

2. **默认 Python 环境不包含 FFmpeg**
   - Zeabur 的默认 Python buildpack 只安装 Python 依赖
   - 需要自定义 Dockerfile 来安装系统依赖

## 解决方案

### 1. Dockerfile（已创建）
创建了多阶段 Dockerfile：
- **Stage 1**: 安装 FFmpeg 等系统依赖
- **Stage 2**: 安装 Python 依赖
- **Stage 3**: 组装最终镜像，使用非 root 用户

关键特性：
- ✅ 安装 FFmpeg 和 FFprobe
- ✅ 多阶段构建优化镜像大小
- ✅ 非 root 用户提升安全性
- ✅ 健康检查支持
- ✅ 环境变量配置支持

### 2. .dockerignore（已创建）
优化 Docker 构建：
- 排除虚拟环境、测试文件、IDE 配置
- 加快构建速度
- 减小上下文大小

### 3. zbpack.json（已更新）
简化配置，直接指向 Dockerfile：
```json
{
  "dockerfile": "Dockerfile"
}
```

## 部署步骤

### Zeabur 部署

1. **推送代码到 Git**
   ```bash
   git add Dockerfile .dockerignore zbpack.json
   git commit -m "feat: Add Dockerfile with FFmpeg support for Zeabur deployment"
   git push
   ```

2. **在 Zeabur 中重新部署**
   - Zeabur 会自动检测 `Dockerfile`
   - 使用 Docker 构建而不是默认 Python buildpack
   - FFmpeg 将被正确安装

3. **配置环境变量**
   在 Zeabur 控制台设置：
   ```
   GEMINI_API_KEY=your_gemini_api_key
   R2_ACCOUNT_ID=your_r2_account_id
   R2_ACCESS_KEY_ID=your_r2_access_key
   R2_SECRET_ACCESS_KEY=your_r2_secret_key
   R2_BUCKET_NAME=recipeai-thumbnails
   R2_PUBLIC_URL=https://your-r2-public-url.com
   UVICORN_WORKERS=4  # 根据方案调整
   PORT=8000  # Zeabur 会自动设置
   ```

4. **验证部署**
   部署成功后访问：
   - Health Check: `https://your-app.zeabur.app/health`
   - Ready Check: `https://your-app.zeabur.app/ready`
   - API 文档: `https://your-app.zeabur.app/docs`

### 本地测试（推荐）

在推送前本地验证 Docker 镜像：

```bash
# 构建镜像
docker build -t recipeai-video-processor .

# 运行容器（使用 .env 文件）
docker run -p 8000:8000 --env-file .env recipeai-video-processor

# 或使用 docker-compose（见下方）
docker-compose up
```

测试端点：
```bash
# Health check
curl http://localhost:8000/health

# Ready check（验证 FFmpeg）
curl http://localhost:8000/ready

# 应该返回：
# {"status":"ready","checks":{"ffmpeg":"ok","gemini_api_key":"ok"}}
```

### Docker Compose（可选）

创建 `docker-compose.yml` 用于本地开发：

```yaml
version: '3.8'

services:
  video-processor:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - UVICORN_WORKERS=2
    volumes:
      # 开发时挂载代码（可选）
      - ./src:/app/src
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## 性能优化建议

### Worker 数量配置
根据 Zeabur 方案调整 `UVICORN_WORKERS`：

| Zeabur 方案 | vCPU | 推荐 Workers | 内存考虑 |
|------------|------|-------------|---------|
| Developer  | 2    | 4           | 视频处理占用内存，建议不超过 4 |
| Team       | 4    | 6-8         | 可适当增加并发 |
| Enterprise | 自定义 | vCPU × 2   | 根据负载测试调整 |

### 镜像大小优化
当前 Dockerfile 已包含：
- ✅ 使用 `python:3.11-slim`（而非 `python:3.11`）
- ✅ 多阶段构建
- ✅ 清理 apt 缓存
- ✅ `pip --no-cache-dir`

进一步优化（可选）：
- 使用 `python:3.11-alpine`（但需要编译某些依赖）
- 精确指定 FFmpeg 所需组件

## 故障排查

### 部署失败排查步骤

1. **检查构建日志**
   ```
   应该看到：
   - "Successfully built ..."
   - FFmpeg 安装成功
   - Python 依赖安装成功
   ```

2. **检查运行日志**
   ```
   应该看到：
   - "Starting 愛煮小幫手 Video Processor on 0.0.0.0:8000"
   - "Gemini API key configured: True"
   - "CPU cores detected: X, starting Y workers"
   ```

3. **验证 FFmpeg**
   访问 `/ready` 端点，检查：
   ```json
   {
     "status": "ready",
     "checks": {
       "ffmpeg": "ok",
       "gemini_api_key": "ok"
     }
   }
   ```

### 常见问题

**Q: 构建时间过长**
- Zeabur 首次构建需要下载 FFmpeg，约 2-3 分钟
- 后续构建会使用缓存，更快

**Q: 内存不足**
- 减少 `UVICORN_WORKERS`
- 视频处理占用内存，考虑升级方案

**Q: FFmpeg 版本问题**
- 当前使用 Debian 官方仓库版本（经过测试）
- 如需特定版本，修改 Dockerfile 中的安装命令

## 回滚方案

如果新部署有问题，快速回滚：

1. **使用旧代码**
   ```bash
   git revert HEAD
   git push
   ```

2. **临时禁用 Dockerfile**
   删除 `zbpack.json` 中的 dockerfile 配置
   （但会回到原问题，只能用于紧急）

## 下一步

部署成功后：
1. ✅ 监控日志确认 FFmpeg 工作正常
2. ✅ 测试视频分析功能
3. ✅ 根据负载调整 Worker 数量
4. ✅ 设置监控和告警（Zeabur Metrics）

## 参考

- [Zeabur Docker 部署文档](https://zeabur.com/docs/deploy/dockerfile)
- [FFmpeg 官方文档](https://ffmpeg.org/documentation.html)
- [Uvicorn Worker 配置](https://www.uvicorn.org/deployment/#running-with-gunicorn)

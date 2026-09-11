---
name: docker-compose
description: Docker / Docker Compose 管理技能 — 编写 Dockerfile、编排多容器服务、管理镜像和容器生命周期、查看日志、网络配置、健康检查、数据卷管理。
category: devops
---

# Docker & Docker Compose

## Dockerfile 编写模板

### Python 应用
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Node.js 应用
```dockerfile
FROM node:22-alpine
WORKDIR /app
COPY package*.json .
RUN npm ci --only=production
COPY . .
CMD ["node", "index.js"]
```

### 多阶段构建
```dockerfile
# Build stage
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json . && npm ci
COPY . . && npm run build

# Runtime stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
```

## Docker Compose 编排

### 基础结构
```yaml
version: '3.8'
services:
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      - DB_HOST=db
    depends_on: [db]
    networks: [app-net]
  
  db:
    image: postgres:16-alpine
    volumes: [pgdata:/var/lib/postgresql/data]
    environment:
      POSTGRES_DB: trading
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready"]
      interval: 10s

volumes:
  pgdata:

networks:
  app-net:
```

### 常用命令
```bash
# 启动（后台）
docker compose up -d
# 重建并启动
docker compose up -d --build
# 查看日志
docker compose logs -f app
# 进入容器
docker compose exec app bash
# 查看状态
docker compose ps
# 查看资源使用
docker stats
# 停止并清理
docker compose down -v
```

### 健康检查模式
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

## 网络操作
```bash
# 查看网络
docker network ls
# 自定义网络（容器间通过服务名通信）
docker network create my-net
# 端口映射检查
docker port container_name
# 容器内网络诊断
docker exec app ping db
```

## 数据卷管理
```bash
# 创建卷
docker volume create data-vol
# 查看卷
docker volume ls
# 备份卷
docker run --rm -v data-vol:/data -v .:/backup alpine tar czf /backup/backup.tar.gz /data
```

## 常见坑点
- Windows 上 Docker Desktop 默认使用 WSL2，注意 `/mnt/c/...` 路径映射问题
- `depends_on` 只控制启动顺序，不等服务就绪 → 需配合 healthcheck + condition
- 敏感信息用 `.env` 文件 + `${VAR}` 引用，不要硬编码在 compose 文件
- 日志不要无限增长，配置 `logging.driver` 和 `logging.options.max-size`

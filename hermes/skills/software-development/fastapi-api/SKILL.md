---
name: fastapi-api
description: FastAPI 后端 API 开发技能模板 — 路由设计、请求验证（Pydantic）、依赖注入、中间件、异步数据库、认证鉴权、API 文档。适用于快速搭建 RESTful 微服务或 WebSocket 服务。
category: software-development
---

# FastAPI Backend API

## 基础骨架
```python
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Trading API", version="1.0.0")

# 启动/关闭事件
@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    await close_db()
```

## 请求/响应模型
```python
class OrderRequest(BaseModel):
    symbol: str
    side: str  # BUY / SELL
    quantity: float
    price: Optional[float] = None  # None = 市价单

class OrderResponse(BaseModel):
    order_id: str
    symbol: str
    status: str
    executed_qty: float
    avg_price: float

@app.post("/orders", response_model=OrderResponse)
async def create_order(order: OrderRequest):
    # 下单逻辑
    return OrderResponse(...)
```

## 依赖注入模式
```python
# 数据库会话
async def get_db():
    async with async_session() as session:
        yield session

# 认证
async def verify_token(auth: str = Header(...)):
    if not auth.startswith("Bearer "):
        raise HTTPException(401)
    return decode_token(auth[7:])

@app.get("/portfolio")
async def get_portfolio(
    user: dict = Depends(verify_token),
    db = Depends(get_db)
):
    ...
```

## 路由组织
```python
# app/main.py
from fastapi import APIRouter
router = APIRouter(prefix="/api/v1/trades", tags=["trades"])

# app/main.py - 注册
app.include_router(trades.router)
app.include_router(analysis.router)
```

## 中间件
```python
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# CORS
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

# 自定义（请求耗时记录）
class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        logger.info(f"{request.url.path} took {time.time()-start:.3f}s")
        return response
```

## 异步数据库（SQLAlchemy + asyncpg）
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/db"
engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession)
Base = declarative_base()
```

## WebSocket
```python
@app.websocket("/ws/prices/{symbol}")
async def price_ws(websocket: WebSocket, symbol: str):
    await websocket.accept()
    async for price in price_stream(symbol):
        await websocket.send_json({"symbol": symbol, "price": price})
```

## 错误处理
```python
class AppException(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg

@app.exception_handler(AppException)
async def app_exc_handler(request, exc: AppException):
    return JSONResponse(status_code=exc.code, content={"error": exc.msg})
```

## 启动与文档
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# 自动文档：http://localhost:8000/docs (Swagger)
#            http://localhost:8000/redoc (ReDoc)
```

## 注意事项
- Pydantic v2 验证比 v1 快 5-10 倍，优先用 `from pydantic import BaseModel`
- 路径参数顺序重要：固定路径放前面，带参数路径放后面
- 敏感端点（下单/撤单）务必加认证中间件
- 用 `BackgroundTasks` 处理非关键异步逻辑（日志、通知等）

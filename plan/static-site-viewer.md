# 计划：本地静态网页浏览 Markdown 文档

## 背景

result 目录下有 12 个知识库的 Markdown 文档和本地图片附件，需要一个本地 Web 服务来浏览这些内容，支持树形目录导航和图片加载。

## 方案概述

用 Python（FastAPI）实现一个轻量本地 HTTP 服务器，实时将 MD 文件渲染为 HTML 页面，左侧树形目录导航，右侧文档内容区域。

## 技术选型

- **后端**：FastAPI + uvicorn（ASGI 异步服务器）
- **模板**：Jinja2
- **MD 渲染**：mistune（服务端渲染 MD → HTML）
- **代码高亮**：highlight.js CDN（前端自动识别语言）
- **前端样式**：GitHub 风格 Markdown 阅读样式
- **搜索**：全文搜索，服务端遍历 MD 文件内容匹配关键词
- **目录树**：服务端实时扫描 result 目录结构，生成 JSON，前端渲染为可折叠树
- **图片**：服务器直接托管 result 目录，MD 中的相对路径自动可访问

## 实现步骤

### 1. 添加依赖

`pyproject.toml` 新增：fastapi、uvicorn、jinja2、mistune

### 2. 创建服务器脚本 `serve.py`

- 参数：`--port`（默认从 9000 开始自动检测可用端口）、`--dir`（默认 `./result`）
- 启动 uvicorn 服务器

### 3. API 路由设计

| 路由 | 功能 |
|------|------|
| `GET /` | 返回主页 HTML（侧边栏 + 内容区） |
| `GET /api/tree` | 实时扫描返回目录结构 JSON |
| `GET /api/doc?path=<path>` | 读取 MD 文件，实时渲染为 HTML 片段 |
| `GET /api/search?q=<keyword>` | 全文搜索，返回匹配文档列表和摘要 |
| `GET /files/{path}` | 托管 result 目录下所有文件（图片等） |
| `GET /static/{path}` | 静态资源（CSS/JS） |

### 4. 前端页面

- **布局**：左侧固定侧边栏（目录树 + 搜索框），右侧自适应内容区
- **目录树**：可折叠，按知识库分组，点击加载文档
- **搜索**：侧边栏顶部搜索框，输入关键词后调用搜索 API，显示匹配结果列表
- **文档渲染**：服务端返回 HTML 片段，前端插入内容区
- **图片路径**：渲染时将相对路径改写为 `/files/` 绝对路径
- **代码高亮**：加载 highlight.js CDN，页面渲染后自动高亮
- **样式**：GitHub 风格 Markdown 样式

### 5. 文件结构

```
YuQueToMD/
├── serve.py              # 服务器入口
├── templates/
│   └── index.html        # 主页模板
├── static/
│   ├── style.css         # 样式
│   └── app.js            # 前端交互逻辑
```

## 实时更新机制

服务器不预生成静态 HTML，所有渲染都在请求时实时完成：

- **目录树实时刷新**：每次请求 `/api/tree` 时重新扫描 result 目录
- **文档实时渲染**：每次点击文档时实时读取 MD 并渲染
- **无缓存设计**：新增/修改文件后刷新页面即可看到，无需重启服务器

## 启动方式

```bash
uv run python serve.py
# 自动从 9000 端口开始寻找可用端口
# 浏览器打开 http://localhost:9000
```

## 验证方式

1. 启动服务器，浏览器打开首页
2. 左侧目录树正确显示所有知识库和子目录
3. 点击文档，右侧正确渲染 Markdown 内容
4. 文档中的图片正确加载显示
5. 代码块有语法高亮
6. 搜索关键词能返回匹配文档
7. 往 result 目录新增一个 MD 文件，刷新页面后侧边栏立即出现

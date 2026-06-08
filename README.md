<div align="center">

# YuQueToMD

**语雀知识库导出 & 本地阅读器**

[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![GitHub stars](https://img.shields.io/github/stars/Lvan826199/YuQueToMD?style=flat&logo=github)](https://github.com/Lvan826199/YuQueToMD)
[![Gitee](https://img.shields.io/badge/Gitee-repo-red?logo=gitee)](https://gitee.com/xiaozai-van-liu/YuQueToMD)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

Author: **梦无矶** | 公众号: **梦无矶测开实录**

[GitHub](https://github.com/Lvan826199/YuQueToMD) · [Gitee](https://gitee.com/xiaozai-van-liu/YuQueToMD)

</div>

---

## 📋 目录

- [功能特性](#-功能特性)
- [环境要求](#-环境要求)
- [快速开始](#-快速开始)
- [参数说明](#-参数说明)
- [输出结构](#-输出结构)
- [本地浏览文档](#-本地浏览文档)
- [注意事项](#-注意事项)
- [开发说明](#-开发说明)
- [许可证](#-许可证)

---

## ✨ 功能特性

**Markdown 转换**

- 将语雀导出的 `.lakebook` 文件批量转换为 `.md` 文件
- 按语雀知识库目录层级生成输出目录
- 自动清理不适合作为文件名的特殊字符
- 可选下载远程图片到本地 `attachments/` 目录

**本地文档浏览器**

- 左侧树形目录导航，中文数字自然排序（一、二、三...）
- 右侧文档大纲，可拖拽调整宽度，滚动时自动高亮当前章节
- 全文搜索，关键词高亮定位跳转
- 搜索框一键清空
- GitHub 风格 Markdown 渲染
- 代码块深色主题（Atom One Dark）+ 语法高亮 + 一键复制
- 在线编辑 Markdown 文档（EasyMDE 编辑器，实时预览，自动保存 + Ctrl+S）
- 图片自动加载本地附件
- 刷新页面保持当前阅读位置
- 实时渲染，新增或修改文件后刷新即可看到，无需重启服务器
- 所有前端资源本地化，无需外网

---

## 📦 环境要求

- Python 3.9+
- [uv](https://docs.astral.sh/uv/) 包管理器

---

## 🚀 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 导出语雀知识库

1. 进入语雀知识库设置页面
2. 点击「导出」
3. 下载导出的 `.lakebook` 文件

### 3. 转换为 Markdown

```bash
# 基础转换
uv run python yuqueToMD.py /path/to/book.lakebook /path/to/output

# 同时下载图片到本地
uv run python yuqueToMD.py /path/to/book.lakebook /path/to/output --download-image
```

### 4. 浏览文档

```bash
uv run python serve.py
# 自动检测可用端口，浏览器打开提示地址
```

---

## 🖥️ 参数说明

### yuqueToMD.py

```text
usage: yuqueToMD.py [-h] [--download-image] lakebook output
```

| 参数 | 说明 |
| --- | --- |
| `lakebook` | 语雀导出的 `.lakebook` 文件路径 |
| `output` | Markdown 文件输出目录 |
| `--download-image` | 下载远程图片并改写为本地路径 |

### serve.py

| 参数 | 说明 |
| --- | --- |
| `--port` | 指定端口号（默认自动从 9000 开始检测） |
| `--dir` | 指定文档目录（默认 `./result`） |

---

## 📁 输出结构

```text
output/
├── 文档一.md
├── 一级目录/
│   ├── 文档二.md
│   └── attachments/
│       └── 文档二_001.png
└── 二级目录/
    └── 文档三.md
```

启用 `--download-image` 后，图片下载到对应文档所在目录下的 `attachments/` 文件夹。

---

## 📖 本地浏览文档

启动内置 Web 服务器：

```bash
uv run python serve.py
```

服务器自动从 9000 端口开始寻找可用端口，浏览器打开提示地址即可阅读。

---

## ⚠️ 注意事项

- 输出目录不存在时会自动创建
- 使用 `--download-image` 需要能访问文档中的图片地址
- 图片下载失败会自动重试 3 次，仍失败则保留远程 URL 并记录到 `FAILED_IMAGES.md`
- 文件名中的特殊字符（`/ \ ? * < > | " : ( )`）会被替换为 `_`
- 自动修复语雀 CDN 图片 URL 中重复 `?x-oss-process` 参数的问题
- 图片响应头无可识别 `Content-Type` 时，本地文件可能没有扩展名
- `.lakebook` 文件损坏或格式不完整时可能无法转换

---

## 🛠️ 开发说明

```bash
uv sync
uv run python yuqueToMD.py --help
uv run python serve.py
```

项目依赖声明在 `pyproject.toml`，使用 uv 管理环境和锁文件。

---

## 📄 许可证

MIT License

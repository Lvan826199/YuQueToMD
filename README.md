<div align="center">

<img src="static/mwj-logo.svg" width="80" height="80" alt="MWJ Docs">

# YuQueToMD

**梦无矶的知识库 · 本地阅读器**

[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Release](https://img.shields.io/github/v/release/Lvan826199/YuQueToMD?logo=github)](https://github.com/Lvan826199/YuQueToMD/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/Lvan826199/YuQueToMD?style=flat&logo=github)](https://github.com/Lvan826199/YuQueToMD)
[![Gitee](https://img.shields.io/badge/Gitee-repo-red?logo=gitee)](https://gitee.com/xiaozai-van-liu/YuQueToMD)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

Author: **梦无矶** | 公众号: **梦无矶测开实录**

[GitHub](https://github.com/Lvan826199/YuQueToMD) · [Gitee](https://gitee.com/xiaozai-van-liu/YuQueToMD)

当前版本：**v1.4.0** · [更新日志](CHANGELOG.md)

</div>

---

## 📋 目录

- [功能特性](#-功能特性)
- [环境要求](#-环境要求)
- [快速开始](#-快速开始)
- [参数说明](#-参数说明)
- [输出结构](#-输出结构)
- [本地浏览文档](#-本地浏览文档)
- [移动端阅读](#-移动端阅读)
- [注意事项](#-注意事项)
- [打包为可执行文件](#-打包为可执行文件免-python-环境运行)
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

- **通用目录加载**：exe 可放到任意目录旁，自动发现并加载文档
- **多目录支持**：检测到多个目录时显示选择界面，一键切换
- **多格式文件预览**：
  - 📝 Markdown：可编辑（EasyMDE 编辑器，实时预览，自动保存）
  - 🖼 图片：居中预览（支持 .png/.jpg/.gif/.svg/.webp 等）
  - 📕 PDF：iframe 嵌入预览，浏览器原生支持
  - 📄 纯文本：代码高亮预览（.txt/.json/.yaml/.py/.js 等）
  - 📎 其他格式：提示本地打开
- 左侧树形目录导航，中文数字自然排序（一、二、三...），不同文件类型显示不同图标
- 右侧文档大纲，可拖拽调整宽度，滚动时自动高亮当前章节，打开文章自动展开
- 全文搜索，关键词高亮定位跳转，搜索包含纯文本文件
- 搜索框一键清空
- GitHub 风格 Markdown 渲染
- 代码块深色主题（Atom One Dark）+ 语法高亮 + 一键复制
- 图片粘贴/拖拽自动上传，按 `{文档名}_{序号}.{扩展名}` 命名
- 保存时自动检测未引用的孤立图片，确认后删除
- 目录树右键菜单：新建文件夹、新建 Markdown 文件、删除（二次确认）
- 操作成功/失败 Toast 提示
- 用系统编辑器打开文件 / 打开文件所在目录
- 图片自动加载本地附件
- 刷新页面保持当前阅读位置
- 点击侧边栏 logo 回到首页
- 实时渲染，新增或修改文件后刷新即可看到，无需重启服务器
- 所有前端资源本地化，无需外网
- 支持打包为 exe，免 Python 环境运行，带自定义 logo 图标

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

### 停止服务 / 释放端口

如果端口被占用或需要停止服务：

**Windows：**

```bash
# 查找占用端口的进程（以 9000 为例）
netstat -ano | findstr :9000

# 杀掉对应 PID 的进程
taskkill /F /PID <PID>
```

**macOS / Linux：**

```bash
# 查找占用端口的进程
lsof -i :9000

# 杀掉对应进程
kill -9 <PID>
```

或者直接在启动服务的终端按 `Ctrl+C` 停止。

---

## 📱 移动端阅读

如需在手机或平板上阅读文档，推荐使用 **Obsidian + 坚果云 Nutstore Sync 插件** 方案，无需开发 App，配置完成后多端自动同步。

详见：[移动端阅读方案文档](doc/移动端阅读方案-Obsidian+坚果云.md)

---

## ⚠️ 注意事项

- 输出目录不存在时会自动创建
- 使用 `--download-image` 需要能访问文档中的图片地址
- 图片下载失败会自动重试 3 次，仍失败则保留远程 URL 并记录到 `FAILED_IMAGES.md`
- 文件名中的特殊字符（`/ \ ? * < > | " : ( )`）会被替换为 `_`
- 自动修复语雀 CDN 图片 URL 中重复 `?x-oss-process` 参数的问题
- 图片响应头无可识别 `Content-Type` 时，本地文件可能没有扩展名
- `.lakebook` 文件损坏或格式不完整时可能无法转换
- 网页上传支持 PNG、JPEG、GIF、WebP，单张图片最大 20MB
- Markdown 中的原始 HTML 默认按文本显示，避免本地文档执行脚本
- lakebook 解压会拒绝符号链接、越界路径和异常体积的归档

---

## 📦 打包为可执行文件（免 Python 环境运行）

可以将文档浏览器打包为单个可执行文件，在没有 Python 环境的电脑上直接使用。

### 打包步骤

```bash
uv sync --group dev
uv run python scripts/build_release.py
```

| 平台 | 产物 | 大小 |
|------|------|------|
| Windows | `dist/MWJDocs-v<版本号>.exe` | ~16MB |
| macOS | `dist/MWJDocs-v<版本号>` | ~20MB |

Windows 发布脚本会自动读取 `version.py`，构建并校验版本化 EXE；校验成功后才会删除仓库根目录及 `dist/` 中的旧版本，并生成 `dist/SHA256SUMS.txt`。完整规则见[发布与打包规则](doc/发布与打包规则.md)。

> 注意：Windows EXE 必须在 Windows 上构建，不支持交叉编译。macOS 打包需在 Mac 上直接运行 `uv run pyinstaller serve.spec --noconfirm`。

### 使用方式

将可执行文件放到文档目录旁边即可：

**Windows：**

```text
任意目录/
├── MWJDocs-v1.4.0.exe
└── 我的文档/          # 可以是任意名称
    ├── 笔记A/
    ├── 笔记B/
    └── ...
```

双击当前版本的 `MWJDocs-v1.4.0.exe` 即可启动。

**多目录支持：**

```text
任意目录/
├── MWJDocs-v1.4.0.exe
├── result/            # 语雀导出的文档
├── MyNotes/          # 个人笔记
└── WorkDocs/         # 工作文档
```

启动后会显示目录选择界面，点击卡片选择要加载的目录。

**macOS：**

```text
任意目录/
├── MWJDocs-v1.4.0
└── 我的文档/
    ├── 笔记A/
    └── ...
```

```bash
# 首次使用需赋予执行权限
chmod +x MWJDocs-v1.4.0
# 启动
./MWJDocs-v1.4.0
```

如果 macOS 提示「无法打开，因为无法验证开发者」，在系统设置 → 隐私与安全 → 点击「仍要打开」即可。

### 命令行参数

```bash
# Windows
MWJDocs-v1.4.0.exe --port 9000 --dir ./my_docs
MWJDocs-v1.4.0.exe --version

# macOS / Linux
./MWJDocs-v1.4.0 --port 9000 --dir ./my_docs
```

| 参数 | 说明 |
|------|------|
| `--port` | 指定端口号（默认自动从 9000 检测） |
| `--dir` | 指定文档目录（默认可执行文件同级的 `result/`） |
| `--version` | 显示当前版本 |

### 注意事项

- 必须在目标平台上打包（Windows 打包 exe，macOS 打包 macOS 可执行文件）
- exe 会自动发现同级目录中的文档，无需固定命名为 `result`
- 检测到多个目录时，启动后会显示选择界面
- 没有文档目录时，会自动创建 `docs/` 目录
- 也可以用 `--dir` 参数指定文档路径
- 关闭终端窗口即停止服务
- 编辑功能（图片上传、保存）在打包模式下同样可用

---

## 🛠️ 开发说明

```bash
uv sync
uv run python yuqueToMD.py --help
uv run python serve.py
uv run python -m unittest discover -s tests -v
```

项目依赖声明在 `pyproject.toml`，使用 uv 管理环境和锁文件。

正式发布前请遵循[发布与打包规则](doc/发布与打包规则.md)，不要手工重命名构建产物。

---

## 📄 许可证

MIT License

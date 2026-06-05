# YuQueToMD

> Author: 梦无矶 | 公众号: 梦无矶测开实录

YuQueToMD 是一个用于将语雀导出的 `.lakebook` 文件转换为 Markdown 文件的命令行工具。转换后的目录结构会尽量保持与语雀知识库目录一致，也可以选择把文档中的图片下载到本地附件目录。

## 功能特性

- 将语雀导出的 `.lakebook` 文件批量转换为 `.md` 文件
- 按语雀知识库目录层级生成输出目录
- 自动清理不适合作为文件名的特殊字符
- 可选下载远程图片到本地 `attachments/` 目录
- 本地 Web 服务器浏览转换后的文档（树形导航、全文搜索、文档大纲、代码高亮）
- 使用 `uv` 管理 Python 环境和依赖

## 环境要求

- Python 3.9 或更高版本
- uv

## 安装依赖

在项目根目录执行：

```bash
uv sync
```

`uv sync` 会根据 `pyproject.toml` 安装依赖，并生成或更新 `uv.lock`。

## 使用方法

### 1. 导出语雀知识库

1. 进入语雀知识库设置页面
2. 点击「导出」
3. 下载导出的 `.lakebook` 文件

### 2. 转换为 Markdown

基础转换命令：

```bash
uv run python yuqueToMD.py /path/to/book.lakebook /path/to/output
```

如果希望同时下载文档中的图片到本地：

```bash
uv run python yuqueToMD.py /path/to/book.lakebook /path/to/output --download-image
```

查看命令帮助：

```bash
uv run python yuqueToMD.py --help
```

## 参数说明

```text
usage: yuqueToMD.py [-h] [--download-image] lakebook output
```

| 参数 | 说明 |
| --- | --- |
| `lakebook` | 语雀导出的 `.lakebook` 文件路径 |
| `output` | Markdown 文件输出目录 |
| `--download-image` | 下载文档中的远程图片，并将 Markdown 图片地址改写为本地路径 |
| `-h, --help` | 显示命令帮助 |

## 输入与输出

### 输入

输入文件是语雀导出的 `.lakebook` 文件。例如：

```text
/path/to/book.lakebook
```

### 输出

输出目录会按照语雀知识库目录结构生成 Markdown 文件。例如：

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

启用 `--download-image` 后，图片会下载到对应文档所在目录下的 `attachments/` 文件夹，并在 Markdown 中引用为相对路径。

## 注意事项

- 如果输出目录不存在，程序会自动创建。
- 使用 `--download-image` 时需要能够访问文档中的图片地址。
- 如果图片响应头没有可识别的 `Content-Type`，生成的本地图片文件名可能没有扩展名。
- 转换结果依赖语雀导出包中的目录和文档数据；如果 `.lakebook` 文件损坏或格式不完整，程序可能无法转换。

## 本地浏览文档

转换完成后，可以启动内置的 Web 服务器在浏览器中浏览文档：

```bash
uv run python serve.py
```

服务器会自动从 9000 端口开始寻找可用端口，启动后在浏览器打开提示的地址即可。

支持的功能：

- 左侧树形目录导航，可折叠展开各知识库
- 右侧文档大纲，可拖拽调整宽度，滚动时自动高亮当前位置
- 全文搜索，输入关键词即时返回匹配文档和摘要
- GitHub 风格 Markdown 渲染，代码块语法高亮
- 图片自动加载本地附件
- 实时渲染，新增或修改文件后刷新页面即可看到，无需重启服务器

可选参数：

| 参数 | 说明 |
| --- | --- |
| `--port` | 指定端口号（默认自动从 9000 开始检测可用端口） |
| `--dir` | 指定文档目录（默认 `./result`） |

## 开发说明

本项目依赖集中声明在 `pyproject.toml` 中，推荐使用 uv 进行开发和运行：

```bash
uv sync
uv run python yuqueToMD.py --help
```

当前项目没有单独的自动化测试用例；修改后可优先通过帮助命令和真实 `.lakebook` 样例转换进行验证。

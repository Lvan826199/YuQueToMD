# 计划：扫描并修复缺失图片资源

## 背景

result 目录中转换后的 MD 文件存在图片资源缺失问题：
- 88 个远程 URL 未下载到本地
- 443 个引用了本地路径但文件不存在

## 分析

缺失分三类：
1. `./attachments/xxx` — 转换时下载失败的图片，源 URL 可以从 lakebook 中找回重新下载
2. `images/xxx` — 原始语雀文档中使用的相对路径引用，需要回溯原始 HTML 找到真实 URL
3. 远程 URL — MD 中直接内嵌了远程链接（未转为本地），需要下载到本地并改写路径

## 实现方案

编写一个独立脚本 `fix_images.py`：

### 步骤 1：扫描 result 目录所有 MD 文件
- 找出所有 `![](path)` 和 `<img src="path">` 引用
- 区分：远程 URL（http/https）/ 本地路径缺失

### 步骤 2：对远程 URL 图片
- 下载到对应 MD 文件的 `attachments/` 目录
- 改写 MD 中的 URL 为本地相对路径
- 重试 3 次

### 步骤 3：对本地路径缺失的图片
- 回溯对应的 lakebook，解析原始 HTML 找到图片真实 URL
- 下载到正确的本地路径
- 重试 3 次

### 步骤 4：记录失败
- 所有重试 3 次仍失败的图片记录到 `result/FAILED_IMAGES.md`
- 格式：文件路径 | 图片 URL | 失败原因

## 启动方式

```bash
uv run python fix_images.py
```

## 输出

- 修复后的 MD 文件（远程 URL 改写为本地路径）
- 下载到本地的图片文件
- `result/FAILED_IMAGES.md` 记录失败项

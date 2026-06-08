# 移动端阅读方案：Obsidian + 坚果云

本方案适用于希望在手机/平板上阅读本地知识库文档的用户，**无需开发 App**，基于 Obsidian 和坚果云官方插件实现多端同步阅读。

## 整体流程

```
PC：YuQueToMD 导出 MD 文件
        ↓
Obsidian（PC）安装 Nutstore Sync 插件 → 同步到坚果云 （可选，也可使用坚果云直接同步）
        ↓
Obsidian（Android / iOS）安装 Nutstore Sync 插件 → 读取文件
```

---

## 准备工作

- 坚果云账号（[官网注册](https://www.jianguoyun.com/)，免费版每月上传 1GB / 下载 3GB，阅读场景够用）
- [Obsidian](https://obsidian.md/) 桌面版（Windows / macOS）
- Obsidian 移动版（Android / iOS，均可从官网或应用商店下载）

---

## 步骤一：PC 端配置

### 1. 创建 Obsidian Vault

打开 Obsidian，新建一个 Vault，将目录指向 YuQueToMD 的输出目录（即 `result/` 或你自定义的输出路径）。

> 也可以先建一个空 Vault，再把 `result/` 里的文件复制进去。

### 2. 安装 Nutstore Sync 插件

1. 进入 Obsidian → **设置** → **社区插件**
2. 关闭「安全模式」
3. 点击「浏览」，搜索 `Nutstore Sync`
4. 安装并启用

### 3. 登录坚果云并开始同步

1. 在插件设置里点击「登录坚果云」，用坚果云账号授权（单点登录，无需手动填写 WebDAV 地址）
2. 选择要同步的远程目录（建议新建一个专用目录，如 `obsidian-vault/`）
3. 点击「立即同步」，等待上传完成

---

## 步骤二：移动端配置（Android / iOS 相同）

### 1. 安装 Obsidian

从官网下载 APK 或从 Google Play / App Store 安装。

### 2. 创建 Vault 并安装插件

1. 打开 Obsidian，新建一个空 Vault
2. 进入设置 → 社区插件 → 安装 `Nutstore Sync`
3. 登录同一个坚果云账号
4. 选择与 PC 端相同的远程目录
5. 触发同步，等待下载完成

完成后即可在手机上浏览全部文档，包括图片、表格、代码块。

---

## 注意事项

### 图片路径兼容性

YuQueToMD 使用 `--download-image` 参数时，图片保存在文档同级的 `attachments/` 目录下，路径格式为相对路径（如 `attachments/xxx.png`）。这与 Obsidian 的默认附件处理方式兼容，图片可以正常显示。

若图片不显示，在 Obsidian 设置 → **文件与链接** → **附件文件夹路径** 中，将路径设置为 `attachments`。

### 同步冲突

移动端为纯阅读场景，不在手机上编辑文件，可以避免同步冲突。如需在多端编辑，Nutstore Sync 插件提供了冲突合并策略，具体见插件文档。

### 坚果云免费版限制

| 类型 | 限制 |
|------|------|
| 每月上传流量 | 1 GB |
| 每月下载流量 | 3 GB |
| 存储空间 | 1 GB（可通过邀请获得更多） |

纯阅读场景（只在 PC 上传、手机下载）基本不会触及限制。

---

## 更新文档

每次在 PC 上重新导出并转换后，重新触发 Obsidian PC 端同步即可，手机端打开 Obsidian 后会自动拉取最新内容。

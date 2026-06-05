# coding=utf-8
# Author: 梦无矶
# 公众号: 梦无矶测开实录
"""
扫描 result 目录，修复缺失的图片资源：
1. 远程 URL 图片 -> 下载到本地 attachments 并改写 MD
2. 本地 attachments 路径缺失 -> 从 lakebook 原始 HTML 中找回 URL 重新下载
3. images/ 路径缺失 -> 从 lakebook 原始 HTML 中找回 URL 重新下载

用法: uv run python fix_images.py
"""
import json
import os
import re
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import requests
import yaml

BASE_DIR = Path(__file__).parent
RESULT_DIR = BASE_DIR / "result"
LAKEBOOK_DIR = BASE_DIR / "YuQueDocument"
FAILED_LOG = RESULT_DIR / "FAILED_IMAGES.md"

MAX_RETRIES = 3

content_type_to_ext = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/svg+xml": ".svg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def main():
    print("=== 扫描 result 目录中的图片引用 ===")
    issues = scan_result_dir()
    print(f"发现 {len(issues)} 个图片问题")

    if not issues:
        print("没有需要修复的图片")
        return

    lakebook_cache = load_all_lakebooks()

    failed = []
    fixed = 0

    for issue in issues:
        success = fix_issue(issue, lakebook_cache)
        if success:
            fixed += 1
        elif issue["type"] == "missing_local":
            failed.append(issue)

    print(f"\n=== 完成 ===")
    print(f"修复成功: {fixed}")
    print(f"修复失败: {len(failed)}")

    if failed:
        write_failed_log(failed)
        print(f"失败记录已写入: {FAILED_LOG}")


def scan_result_dir():
    issues = []
    for md_file in RESULT_DIR.rglob("*.md"):
        if md_file.name == "FAILED_IMAGES.md":
            continue
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        md_dir = md_file.parent

        for m in re.finditer(r'!\[[^\]]*\]\(([^)\s]+)', content):
            img_ref = m.group(1).strip('"').strip("'")
            classify_issue(issues, md_file, md_dir, img_ref)

        for m in re.finditer(r'src=["\']([^"\']+)["\']', content):
            img_ref = m.group(1).strip()
            classify_issue(issues, md_file, md_dir, img_ref)

    return issues


def classify_issue(issues, md_file, md_dir, img_ref):
    if not img_ref or "{{" in img_ref or img_ref.endswith(".js") or img_ref.endswith(".css"):
        return

    if img_ref.startswith("http"):
        if is_image_url(img_ref):
            issues.append({
                "type": "remote",
                "md_file": md_file,
                "img_ref": img_ref,
            })
    else:
        clean_ref = img_ref.split(" ")[0].strip('"')
        full_path = (md_dir / clean_ref).resolve()
        if not full_path.exists():
            issues.append({
                "type": "missing_local",
                "md_file": md_file,
                "img_ref": img_ref,
                "expected_path": full_path,
            })


def is_image_url(url):
    lower = url.lower()
    img_exts = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico")
    if any(lower.split("?")[0].endswith(ext) for ext in img_exts):
        return True
    if "image" in lower or "img" in lower or "pic" in lower:
        return True
    return False


def load_all_lakebooks():
    cache = {}
    for lb_file in LAKEBOOK_DIR.glob("*.lakebook"):
        print(f"加载 lakebook: {lb_file.name}")
        try:
            docs = extract_lakebook_docs(lb_file)
            cache[lb_file.stem] = docs
        except Exception as e:
            print(f"  [WARN] 加载失败: {e}")
    return cache


def extract_lakebook_docs(lb_path):
    docs = {}
    with tempfile.TemporaryDirectory(prefix="lb_") as tmp:
        with tarfile.open(lb_path) as tar:
            try:
                tar.extractall(tmp, filter="data")
            except TypeError:
                tar.extractall(tmp)

        repo_dir = None
        for root, dirs, files in os.walk(tmp):
            if "$meta.json" in files:
                repo_dir = root
                break
        if not repo_dir:
            return docs

        meta = json.loads(Path(os.path.join(repo_dir, "$meta.json")).read_text(encoding="utf-8"))
        toc_str = json.loads(meta.get("meta", "{}")).get("book", {}).get("tocYml", "")
        toc = yaml.safe_load(toc_str) or []

        for item in toc:
            url = item.get("url", "")
            title = item.get("title", "")
            if not url or item.get("type") != "DOC":
                continue
            json_path = os.path.join(repo_dir, url + ".json")
            if os.path.exists(json_path):
                doc_data = json.loads(Path(json_path).read_text(encoding="utf-8"))
                html = doc_data.get("doc", {}).get("body", "") or doc_data.get("doc", {}).get("body_asl", "")
                docs[title] = html

    return docs


def fix_issue(issue, lakebook_cache):
    if issue["type"] == "remote":
        return fix_remote(issue)
    else:
        return fix_missing_local(issue, lakebook_cache)


def fix_remote(issue):
    md_file = issue["md_file"]
    img_url = issue["img_ref"]
    md_dir = md_file.parent

    attachments_dir = md_dir / "attachments"
    attachments_dir.mkdir(exist_ok=True)

    file_name = download_image(img_url, attachments_dir, md_file.stem)
    if not file_name:
        return False

    local_path = f"./attachments/{file_name}"
    content = md_file.read_text(encoding="utf-8", errors="ignore")
    content = content.replace(img_url, local_path)
    md_file.write_text(content, encoding="utf-8")
    return True


def fix_missing_local(issue, lakebook_cache):
    md_file = issue["md_file"]
    img_ref = issue["img_ref"]
    expected_path = issue.get("expected_path")

    img_url = find_image_url_in_lakebooks(md_file, img_ref, lakebook_cache)
    if not img_url:
        return False

    if expected_path:
        target_dir = expected_path.parent
    else:
        target_dir = md_file.parent / "attachments"

    target_dir.mkdir(parents=True, exist_ok=True)

    file_name = download_image(img_url, target_dir, None, expected_path)
    if not file_name:
        return False
    return True


def find_image_url_in_lakebooks(md_file, img_ref, lakebook_cache):
    rel_path = md_file.relative_to(RESULT_DIR)
    top_dir = rel_path.parts[0] if rel_path.parts else ""

    for lb_name, docs in lakebook_cache.items():
        if top_dir and lb_name != top_dir:
            continue
        for title, html in docs.items():
            if not html:
                continue
            clean_ref = Path(img_ref.split(" ")[0].strip('"')).name
            for m in re.finditer(r'src=["\']([^"\']+)["\']', html):
                src = m.group(1)
                if clean_ref in src or similar_match(clean_ref, src):
                    if src.startswith("http"):
                        return src
    return None


def similar_match(local_name, url):
    url_name = url.split("/")[-1].split("?")[0]
    if local_name in url_name or url_name in local_name:
        return True
    return False


def fix_url(url):
    if url.count("?x-oss-process") > 1:
        idx = url.index("?x-oss-process")
        second = url.index("?x-oss-process", idx + 1)
        url = url[:second]
    return url


def download_image(url, target_dir, prefix=None, exact_path=None):
    url = fix_url(url)
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "").split(";")[0].lower()
            ext = content_type_to_ext.get(content_type, "")

            if exact_path:
                target_path = exact_path
            else:
                if not ext:
                    url_path = url.split("?")[0]
                    for e in content_type_to_ext.values():
                        if url_path.endswith(e):
                            ext = e
                            break
                base = prefix or "img"
                existing = list(target_dir.glob(f"{base}_*"))
                no = len(existing) + 1
                file_name = f"{base}_{no:03d}{ext}"
                target_path = target_dir / file_name

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(resp.content)
            print(f"  [OK] {url[:80]}...")
            return target_path.name

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
            else:
                print(f"  [FAIL] {url[:80]}... ({e})")
                return None
    return None


def write_failed_log(failed):
    lines = ["# 图片下载失败记录\n\n"]
    lines.append("| MD 文件 | 图片引用 | 类型 |\n")
    lines.append("| --- | --- | --- |\n")
    for issue in failed:
        md_rel = issue["md_file"].relative_to(RESULT_DIR).as_posix()
        img_ref = issue["img_ref"][:100]
        issue_type = issue["type"]
        lines.append(f"| {md_rel} | {img_ref} | {issue_type} |\n")
    FAILED_LOG.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

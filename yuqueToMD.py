# coding=utf-8
# Author: 梦无矶
# 公众号: 梦无矶测开实录
import argparse
import json
import os
import sys
import tarfile
import tempfile
import time

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from requests import get
import yaml


TYPE_TITLE = "TITLE"
TYPE_DOC = "DOC"
META_JSON = "$meta.json"

DEFAULT_HEADING_STYLE = "ATX"
DEFAULT_CODE_LANGUAGE = "python"
MAX_RETRIES = 3

failed_images = []

content_type_to_extension = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/svg+xml": ".svg",
    "image/png": ".png",
    "image/webp": ".webp",
}

reserved_file_names = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def sanitizer_file_name(name):
    name = name.replace("/", "_")
    name = name.replace("\\", "_")
    name = name.replace(" ", "_")
    name = name.replace("?", "_")
    name = name.replace("*", "_")
    name = name.replace("<", "_")
    name = name.replace(">", "_")
    name = name.replace("|", "_")
    name = name.replace('"', "_")
    name = name.replace(":", "_")
    name = name.replace("(", "_")
    name = name.replace(")", "_")
    name = name.strip(". ")
    if not name:
        return "未命名"
    if name.upper() in reserved_file_names:
        return name + "_"
    return name


def unique_path_name(base_dir, name, suffix="", used_paths=None):
    candidate = name
    index = 1
    while True:
        candidate_path = os.path.join(base_dir, candidate + suffix)
        is_used = used_paths is not None and candidate_path in used_paths
        if not os.path.exists(candidate_path) and not is_used:
            if used_paths is not None:
                used_paths.add(candidate_path)
            return candidate
        candidate = "%s_%d" % (name, index)
        index = index + 1


def find_repo_dir(random_tmp_dir):
    for root, dirs, files in os.walk(random_tmp_dir):
        if META_JSON in files:
            return root
    return ""


def read_toc(random_tmp_dir):
    # 读取元数据文件
    with open(os.path.join(random_tmp_dir, META_JSON), "r", encoding="utf-8") as f:
        meta_file_str = json.load(f)

    meta_str = meta_file_str.get("meta", "")
    meta = json.loads(meta_str)
    toc_str = meta.get("book", {}).get("tocYml", "")
    return yaml.safe_load(toc_str) or []


def extract_repos(repo_dir, output, toc, download_image):
    last_level = 0
    last_sanitized_title = ""
    path_prefixed = []
    used_paths = set()
    for item in toc:
        t = item["type"]
        url = str(item.get("url", ""))
        current_level = item.get("level", 0)
        title = str(item.get("title", ""))
        if not title:
            continue

        if current_level > last_level:
            path_prefixed = path_prefixed + [last_sanitized_title]
        elif current_level < last_level:
            diff = last_level - current_level
            path_prefixed = path_prefixed[0:-diff]

        output_dir_path = os.path.join(output, *path_prefixed)
        suffix = ".md" if t == TYPE_DOC else ""
        sanitized_title = unique_path_name(
            output_dir_path,
            sanitizer_file_name(title),
            suffix,
            used_paths,
        )

        if t == TYPE_DOC:
            os.makedirs(output_dir_path, exist_ok=True)
            raw_path = os.path.join(repo_dir, url + ".json")
            with open(raw_path, "r", encoding="utf-8") as raw_file:
                doc_str = json.load(raw_file)
            html = doc_str["doc"]["body"] or doc_str["doc"]["body_asl"]

            if download_image:
                html = download_images_and_patch_html(
                    output_dir_path, sanitized_title, html
                )

            output_path = os.path.join(output_dir_path, sanitized_title + ".md")
            markdown = md(
                html,
                heading_style=DEFAULT_HEADING_STYLE,
                code_language=DEFAULT_CODE_LANGUAGE,
                code_language_callback=get_code_language,
            )
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(pretty_md(markdown))

        last_sanitized_title = sanitized_title
        last_level = current_level


def download_images_and_patch_html(output_dir_path, sanitized_title, html):
    bs = BeautifulSoup(html, "html.parser")
    images = bs.find_all("img")
    if not images:
        return html

    attachments_dir_path = os.path.join(output_dir_path, "attachments")
    os.makedirs(attachments_dir_path, exist_ok=True)
    no = 1
    for image in images:
        src = image.get("src")
        if not src:
            continue

        src = fix_image_url(src)
        print("Download %s" % src)

        success = False
        for attempt in range(MAX_RETRIES):
            try:
                resp = get(src, timeout=30)
                resp.raise_for_status()
                success = True
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1)
                else:
                    print("  [FAIL] %s (retried %d times)" % (e, MAX_RETRIES))

        if not success:
            md_path = os.path.join(output_dir_path, sanitized_title + ".md")
            failed_images.append((md_path, src))
            continue

        content_type = resp.headers.get("Content-Type", "").split(";", 1)[0].lower()
        file_name = sanitized_title + "_%03d%s" % (
            no,
            content_type_to_extension.get(content_type, ""),
        )
        attachments_file_path = os.path.join(attachments_dir_path, file_name)
        with open(attachments_file_path, "wb") as f:
            f.write(resp.content)
        no = no + 1
        image["src"] = "./attachments/" + file_name
    return str(bs)


def fix_image_url(url):
    if url.count("?x-oss-process") > 1:
        idx = url.index("?x-oss-process")
        second = url.index("?x-oss-process", idx + 1)
        url = url[:second]
    return url


def write_failed_log(output_dir):
    if not failed_images:
        return
    log_path = os.path.join(output_dir, "FAILED_IMAGES.md")
    existing = []
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            existing = f.readlines()

    with open(log_path, "w", encoding="utf-8") as f:
        if not existing:
            f.write("# 图片下载失败记录\n\n")
            f.write("| MD 文件 | 图片 URL |\n")
            f.write("| --- | --- |\n")
        else:
            f.writelines(existing)

        for md_path, url in failed_images:
            f.write("| %s | %s |\n" % (md_path, url))

    print("\n[WARN] %d images failed, logged to %s" % (len(failed_images), log_path))


def verify_and_fix_images(output_dir):
    """扫描输出目录，修复远程 URL 图片引用（下载到本地并改写路径）"""
    import re
    from pathlib import Path

    output_path = Path(output_dir)
    fixed = 0

    for md_file in output_path.rglob("*.md"):
        if md_file.name == "FAILED_IMAGES.md":
            continue
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        md_dir = md_file.parent
        original = content

        remote_refs = re.findall(r'!\[[^\]]*\]\((https?://[^)\s]+)\)', content)
        for img_url in remote_refs:
            if not is_likely_image(img_url):
                continue
            img_url_fixed = fix_image_url(img_url)
            attachments_dir = md_dir / "attachments"
            attachments_dir.mkdir(exist_ok=True)
            file_name = try_download(img_url_fixed, attachments_dir, md_file.stem)
            if file_name:
                content = content.replace(img_url, "./attachments/" + file_name)
                fixed += 1
            else:
                failed_images.append((str(md_file), img_url))

        local_refs = re.findall(r'!\[[^\]]*\]\((\./attachments/[^)\s]+|attachments/[^)\s]+)\)', content)
        for ref in local_refs:
            clean = ref.split(" ")[0].strip('"')
            full = (md_dir / clean).resolve()
            if not full.exists():
                failed_images.append((str(md_file), ref))

        if content != original:
            md_file.write_text(content, encoding="utf-8")

    print("校验完成，修复 %d 个远程图片引用" % fixed)


def is_likely_image(url):
    lower = url.lower().split("?")[0]
    exts = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp")
    return any(lower.endswith(e) for e in exts) or "image" in lower


def try_download(url, target_dir, prefix):
    for attempt in range(MAX_RETRIES):
        try:
            resp = get(url, timeout=30)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "").split(";", 1)[0].lower()
            ext = content_type_to_extension.get(content_type, "")
            if not ext:
                url_path = url.split("?")[0]
                for e in content_type_to_extension.values():
                    if url_path.endswith(e):
                        ext = e
                        break
            existing = list(target_dir.glob(prefix + "_*"))
            no = len(existing) + 1
            file_name = "%s_%03d%s" % (prefix, no, ext)
            (target_dir / file_name).write_bytes(resp.content)
            return file_name
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
    return None


def get_code_language(element):
    language = element.get("data-language") or element.get("data-lang")
    if language:
        return language

    for class_name in element.get("class", []):
        if class_name.startswith("language-"):
            return class_name.replace("language-", "", 1)

    code_element = element.find("code")
    if code_element:
        language = code_element.get("data-language") or code_element.get("data-lang")
        if language:
            return language
        for class_name in code_element.get("class", []):
            if class_name.startswith("language-"):
                return class_name.replace("language-", "", 1)

    return DEFAULT_CODE_LANGUAGE


def pretty_md(text: str) -> str:
    output = text

    lines = output.split("\n")
    for i in range(len(lines)):
        lines[i] = lines[i].rstrip()
    output = "\n".join(lines)

    for i in range(50):
        output = output.replace("\n\n\n", "\n\n")
        if "\n\n\n" not in output:
            break

    return output


def main():
    parser = argparse.ArgumentParser(description="Convert Yuque doc to markdown")
    parser.add_argument("lakebook", help="Lakebook file")
    parser.add_argument("output", help="Output directory")
    parser.add_argument(
        "--download-image", help="Download images to local", action="store_true"
    )
    args = parser.parse_args()
    if not os.path.exists(args.lakebook):
        print("Lakebook file not found: " + args.lakebook)
        sys.exit(1)
    os.makedirs(args.output, exist_ok=True)

    # 解压 lakebook 文件
    with tempfile.TemporaryDirectory(prefix="lakebook_") as random_tmp_dir:
        extract_tar(args.lakebook, random_tmp_dir)
        # 检测临时目录中的知识库目录
        repo_dir = find_repo_dir(random_tmp_dir)
        if not repo_dir:
            print(".lakebook file is invalid")
            sys.exit(1)

        toc = read_toc(repo_dir)
        print("Total " + str(len(toc)) + " files")

        extract_repos(repo_dir, args.output, toc, args.download_image)

    if args.download_image:
        print("\n=== 校验图片引用 ===")
        verify_and_fix_images(args.output)

    write_failed_log(args.output)


# 解压 tar 格式文件
def extract_tar(tar_file, target_dir):
    if not os.path.exists(target_dir):
        os.mkdir(target_dir)
    target_dir_abs = os.path.abspath(target_dir)
    with tarfile.open(tar_file) as tar:
        for name in tar.getnames():
            target_path = os.path.abspath(os.path.join(target_dir, name))
            if os.path.commonpath([target_dir_abs, target_path]) != target_dir_abs:
                raise ValueError("Invalid path in tar file: " + name)
            try:
                tar.extract(name, target_dir, filter="data")
            except TypeError:
                tar.extract(name, target_dir)


if __name__ == "__main__":
    main()

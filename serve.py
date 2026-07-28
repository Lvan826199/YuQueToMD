# coding=utf-8
# Author: 梦无矶
# 公众号: 梦无矶测开实录
import argparse
import asyncio
import html as html_lib
import os
import platform
import re
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote, urlparse

import mistune
import uvicorn
from fastapi import FastAPI, Request, Query, Body, File, UploadFile, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware
from version import __version__

import sys
import webbrowser

BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
EXE_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else BASE_DIR

SKIP_DIRS = {
    "_internal", "static", "templates", "tests", "__pycache__",
    "build", "dist", ".venv", "plan", "doc",
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico"}
PDF_EXTS = {".pdf"}
TEXT_EXTS = {".txt", ".json", ".yaml", ".yml", ".toml", ".xml", ".csv", ".log", ".ini", ".conf",
             ".sh", ".bat", ".py", ".js", ".ts", ".go", ".java", ".c", ".cpp", ".h", ".rs",
             ".html", ".css", ".sql", ".r", ".lua", ".rb", ".kt", ".swift", ".dart"}
MD_EXTS = {".md"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_NODE_NAME_LENGTH = 180
SEARCH_CACHE_TTL_SECONDS = 5.0
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

MARKDOWN_RENDERER = mistune.create_markdown(escape=True)
_SEARCH_CACHE_BY_ROOT = {}
_SEARCH_CACHE_LOCK = threading.Lock()


def resolve_within(root: Path, path: str = "", allow_root: bool = True) -> Optional[Path]:
    """Resolve a user-provided path and ensure it stays inside root."""
    if not isinstance(path, (str, os.PathLike)):
        return None
    root_resolved = root.resolve()
    candidate = (root_resolved / path).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    if not allow_root and candidate == root_resolved:
        return None
    return candidate


def atomic_write_text(path: Path, content: str) -> None:
    """Write text without exposing a partially truncated destination file."""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def validate_node_name(name: str) -> Optional[str]:
    if not isinstance(name, str):
        return None
    name = name.strip()
    if not name or name in {".", ".."} or len(name) > MAX_NODE_NAME_LENGTH:
        return None
    if any(ord(char) < 32 for char in name) or re.search(r'[\\/:*?"<>|]', name):
        return None
    if name.endswith((" ", ".")):
        return None
    if name.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        return None
    return name


def next_attachment_number(attachments_dir: Path, doc_stem: str) -> int:
    pattern = re.compile(rf"^{re.escape(doc_stem)}_(\d+)(?:\.[^.]*)?$")
    numbers = []
    if attachments_dir.exists():
        for entry in attachments_dir.iterdir():
            if entry.is_file():
                match = pattern.match(entry.name)
                if match:
                    numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def referenced_attachment_names(md_dir: Path, current_path: Optional[Path] = None,
                                current_content: Optional[str] = None) -> set:
    attachments_dir = md_dir / "attachments"
    if not attachments_dir.is_dir():
        return set()
    all_attachment_names = {
        entry.name for entry in attachments_dir.iterdir() if entry.is_file()
    }
    contents = []
    for md_file in md_dir.iterdir():
        if not md_file.is_file() or md_file.suffix.lower() != ".md":
            continue
        if current_path is not None and md_file.resolve() == current_path.resolve():
            contents.append(current_content or "")
            continue
        try:
            contents.append(md_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            # A file we cannot inspect must not make deletion less conservative.
            return all_attachment_names
    combined = "\n".join(contents)
    return {name for name in all_attachment_names if name in combined}


def is_valid_image_data(data: bytes, extension: str) -> bool:
    signatures = {
        ".png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": lambda value: value.startswith(b"\xff\xd8\xff"),
        ".gif": lambda value: value.startswith((b"GIF87a", b"GIF89a")),
        ".webp": lambda value: len(value) >= 12 and value[:4] == b"RIFF" and value[8:12] == b"WEBP",
    }
    validator = signatures.get(extension)
    return bool(data) and validator is not None and validator(data)


def write_attachment_exclusive(attachments_dir: Path, doc_stem: str,
                               extension: str, data: bytes) -> str:
    attachments_dir.mkdir(exist_ok=True)
    while True:
        number = next_attachment_number(attachments_dir, doc_stem)
        file_name = f"{doc_stem}_{number:03d}{extension}"
        file_path = attachments_dir / file_name
        try:
            with file_path.open("xb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            return file_name
        except FileExistsError:
            continue
        except Exception:
            if file_path.exists():
                file_path.unlink()
            raise


def invalidate_search_cache(root: Path) -> None:
    with _SEARCH_CACHE_LOCK:
        _SEARCH_CACHE_BY_ROOT.pop(root.resolve(), None)


def classify_file(suffix: str) -> str:
    s = suffix.lower()
    if s in MD_EXTS:
        return "markdown"
    if s in IMAGE_EXTS:
        return "image"
    if s in PDF_EXTS:
        return "pdf"
    if s in TEXT_EXTS:
        return "text"
    return "other"


def discover_dirs() -> list[Path]:
    candidates = []
    try:
        for entry in EXE_DIR.iterdir():
            if not entry.is_dir():
                continue
            if entry.name.startswith(".") or entry.name in SKIP_DIRS:
                continue
            candidates.append(entry)
    except PermissionError:
        pass
    return sorted(candidates, key=lambda d: d.name.lower())


def get_default_result_dir() -> Path:
    candidates = discover_dirs()
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        default = EXE_DIR / "docs"
        default.mkdir(exist_ok=True)
        return default
    for c in candidates:
        if c.name == "result":
            return c
    return candidates[0]


RESULT_DIR: Path = get_default_result_dir()
MULTI_DIR_MODE: bool = len(discover_dirs()) > 1


def search_files(root: Path, query: str) -> list:
    root = root.resolve()
    keyword = query.lower()
    searchable_exts = MD_EXTS | TEXT_EXTS
    results = []

    with _SEARCH_CACHE_LOCK:
        state = _SEARCH_CACHE_BY_ROOT.setdefault(
            root, {"last_scan": 0.0, "files": {}}
        )
        cache = state["files"]
        if time.monotonic() - state["last_scan"] >= SEARCH_CACHE_TTL_SECONDS:
            seen = set()
            for file_path in root.rglob("*"):
                try:
                    relative = file_path.relative_to(root)
                    if "attachments" in relative.parts or not file_path.is_file():
                        continue
                    if file_path.suffix.lower() not in searchable_exts:
                        continue
                    safe_path = resolve_within(root, relative.as_posix())
                    if safe_path is None:
                        continue
                    stat = safe_path.stat()
                    seen.add(safe_path)
                    cached = cache.get(safe_path)
                    if not cached or cached[0] != stat.st_mtime_ns or cached[1] != stat.st_size:
                        content = safe_path.read_text(encoding="utf-8")
                        cache[safe_path] = (
                            stat.st_mtime_ns, stat.st_size, content, content.lower(),
                            safe_path.relative_to(root).as_posix(),
                        )
                except (OSError, UnicodeError, ValueError):
                    continue
            for cached_path in list(cache):
                if cached_path not in seen:
                    cache.pop(cached_path, None)
            state["last_scan"] = time.monotonic()

        for safe_path, cached in cache.items():
            content, lower_content, relative_path = cached[2], cached[3], cached[4]
            if keyword in lower_content:
                idx = lower_content.index(keyword)
                start = max(0, idx - 40)
                end = min(len(content), idx + len(query) + 60)
                results.append({
                    "path": relative_path,
                    "title": safe_path.stem,
                    "snippet": content[start:end].replace("\n", " "),
                    "file_type": classify_file(safe_path.suffix),
                })
                if len(results) >= 50:
                    break
    return results


app = FastAPI(title="MWJ Docs", version=__version__)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["127.0.0.1", "localhost", "[::1]"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        origin_host = urlparse(origin).hostname if origin else None
        if origin_host and origin_host not in {"127.0.0.1", "localhost", "::1"}:
            return JSONResponse({"error": "cross-origin request rejected"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"error": "cross-origin request rejected"}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: http: https:; frame-src 'self'; object-src 'none'; "
        "base-uri 'none'; form-action 'self'; connect-src 'self'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/files/{path:path}", name="files")
async def files(path: str):
    root = RESULT_DIR.resolve()
    file_path = resolve_within(root, path, allow_root=False)
    if file_path is None:
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not file_path.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    headers = {}
    if file_path.suffix.lower() in {".html", ".htm", ".svg", ".xml"}:
        headers["Content-Security-Policy"] = (
            "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:"
        )
    return FileResponse(file_path, headers=headers)


@app.get("/api/tree")
async def tree():
    root = RESULT_DIR.resolve()
    return JSONResponse(await asyncio.to_thread(build_tree, root, root))


@app.get("/api/doc")
async def doc(path: str = Query(...)):
    root = RESULT_DIR.resolve()
    file_path = resolve_within(root, path, allow_root=False)
    if file_path is None:
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not file_path.is_file() or file_path.suffix.lower() != ".md":
        return JSONResponse({"error": "not found"}, status_code=404)

    try:
        content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
    except UnicodeError:
        return JSONResponse({"error": "file is not UTF-8"}, status_code=422)
    html = MARKDOWN_RENDERER(content)

    doc_dir = file_path.parent.relative_to(root).as_posix()
    html = rewrite_image_paths(html, doc_dir)

    return JSONResponse({"html": html, "title": file_path.stem})


@app.get("/api/search")
async def search(q: str = Query(..., min_length=1, max_length=200)):
    root = RESULT_DIR.resolve()
    return JSONResponse(await asyncio.to_thread(search_files, root, q))


@app.get("/api/raw")
async def raw(path: str = Query(...)):
    root = RESULT_DIR.resolve()
    file_path = resolve_within(root, path, allow_root=False)
    if file_path is None:
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not file_path.is_file() or file_path.suffix.lower() != ".md":
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
    except UnicodeError:
        return JSONResponse({"error": "file is not UTF-8"}, status_code=422)
    return JSONResponse({"content": content, "path": file_path.relative_to(root).as_posix()})


@app.post("/api/save")
async def save(data: dict = Body(...)):
    path = data.get("path", "")
    content = data.get("content", "")
    if not path or not isinstance(content, str):
        return JSONResponse({"error": "invalid save payload"}, status_code=400)
    root = RESULT_DIR.resolve()
    file_path = resolve_within(root, path, allow_root=False)
    if file_path is None:
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not file_path.is_file() or file_path.suffix.lower() != ".md":
        return JSONResponse({"error": "not found"}, status_code=404)
    await asyncio.to_thread(atomic_write_text, file_path, content)
    await asyncio.to_thread(invalidate_search_cache, root)
    return JSONResponse({"ok": True})


@app.post("/api/open-file")
async def open_file(data: dict = Body(...)):
    """用系统默认编辑器打开 MD 文件（跨平台：Windows/macOS/Linux）"""
    path = data.get("path", "")
    if not path:
        return JSONResponse({"error": "path required"}, status_code=400)
    file_path = resolve_within(RESULT_DIR, path, allow_root=False)
    if file_path is None:
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not file_path.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        if platform.system() == "Windows":
            os.startfile(str(file_path))
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", str(file_path)])
        else:  # Linux
            subprocess.run(["xdg-open", str(file_path)])
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse({"ok": True})


@app.post("/api/open-folder")
async def open_folder(data: dict = Body(...)):
    """在文件管理器中打开文件所在目录并选中文件（跨平台：Windows/macOS/Linux）"""
    path = data.get("path", "")
    if not path:
        return JSONResponse({"error": "path required"}, status_code=400)
    file_path = resolve_within(RESULT_DIR, path, allow_root=False)
    if file_path is None:
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not file_path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        if platform.system() == "Windows":
            subprocess.run(["explorer", "/select,", str(file_path)])
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", "-R", str(file_path)])
        else:  # Linux
            subprocess.run(["xdg-open", str(file_path.parent)])
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse({"ok": True})


@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...), doc_path: str = Form(...)):
    """上传图片到对应文档的 attachments 目录，自动按 {文档名}_{序号}.{扩展名} 命名"""
    if not doc_path:
        return JSONResponse({"error": "doc_path required"}, status_code=400)
    md_file = resolve_within(RESULT_DIR, doc_path, allow_root=False)
    if md_file is None:
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not md_file.is_file() or md_file.suffix.lower() != ".md":
        return JSONResponse({"error": "document not found"}, status_code=404)

    md_dir = md_file.parent
    doc_stem = md_file.stem
    attachments_dir = md_dir / "attachments"

    ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
               "image/webp": ".webp"}
    content_type = (file.content_type or "").split(";", 1)[0].lower()
    ext = ext_map.get(content_type)
    if ext is None:
        return JSONResponse({"error": "unsupported image type"}, status_code=415)

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return JSONResponse({"error": "image is too large"}, status_code=413)
    if not is_valid_image_data(data, ext):
        return JSONResponse({"error": "invalid image data"}, status_code=415)

    file_name = await asyncio.to_thread(
        write_attachment_exclusive, attachments_dir, doc_stem, ext, data
    )

    rel_path = "./attachments/" + file_name
    return JSONResponse({"url": rel_path, "filename": file_name})


@app.post("/api/create-file")
async def create_file(data: dict = Body(...)):
    dir_path = data.get("dir", "")
    name = validate_node_name(data.get("name", ""))
    if name is None:
        return JSONResponse({"error": "invalid name"}, status_code=400)
    if not name.lower().endswith(".md"):
        name += ".md"
    name = validate_node_name(name)
    if name is None:
        return JSONResponse({"error": "invalid name"}, status_code=400)
    root = RESULT_DIR.resolve()
    target_dir = resolve_within(root, dir_path)
    if target_dir is None or not target_dir.is_dir():
        return JSONResponse({"error": "invalid path"}, status_code=400)
    file_path = resolve_within(root, (target_dir / name).relative_to(root).as_posix(), allow_root=False)
    if file_path is None:
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if file_path.exists():
        return JSONResponse({"error": "already exists"}, status_code=400)
    stem = Path(name).stem
    await asyncio.to_thread(atomic_write_text, file_path, f"# {stem}\n")
    await asyncio.to_thread(invalidate_search_cache, root)
    rel_path = file_path.relative_to(root).as_posix()
    return JSONResponse({"ok": True, "path": rel_path})


@app.post("/api/create-dir")
async def create_dir(data: dict = Body(...)):
    dir_path = data.get("dir", "")
    name = validate_node_name(data.get("name", ""))
    if name is None:
        return JSONResponse({"error": "invalid name"}, status_code=400)
    root = RESULT_DIR.resolve()
    target_dir = resolve_within(root, dir_path)
    if target_dir is None or not target_dir.is_dir():
        return JSONResponse({"error": "invalid path"}, status_code=400)
    new_dir = resolve_within(root, (target_dir / name).relative_to(root).as_posix(), allow_root=False)
    if new_dir is None:
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if new_dir.exists():
        return JSONResponse({"error": "already exists"}, status_code=400)
    new_dir.mkdir()
    return JSONResponse({"ok": True})


@app.post("/api/delete-node")
async def delete_node(data: dict = Body(...)):
    """删除文件或文件夹（文件夹递归删除）"""
    path = data.get("path", "")
    if not path:
        return JSONResponse({"error": "path required"}, status_code=400)
    target = resolve_within(RESULT_DIR, path, allow_root=False)
    if target is None:
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not target.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        if target.is_dir():
            import shutil
            shutil.rmtree(target)
        else:
            target.unlink()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    await asyncio.to_thread(invalidate_search_cache, RESULT_DIR)
    return JSONResponse({"ok": True})


@app.post("/api/check-orphan-images")
async def check_orphan_images(data: dict = Body(...)):
    """检查文档 attachments 中未被引用的孤立图片"""
    path = data.get("path", "")
    content = data.get("content", "")
    if not isinstance(path, str) or not path or not isinstance(content, str):
        return JSONResponse({"orphans": []})
    md_file = resolve_within(RESULT_DIR, path, allow_root=False)
    if md_file is None or not md_file.is_file() or md_file.suffix.lower() != ".md":
        return JSONResponse({"orphans": []})
    att_dir = md_file.parent / "attachments"
    if not att_dir.is_dir():
        return JSONResponse({"orphans": []})
    referenced = await asyncio.to_thread(
        referenced_attachment_names, md_file.parent, md_file, content
    )
    orphans = sorted(
        entry.name for entry in att_dir.iterdir()
        if entry.is_file() and entry.name not in referenced
    )
    return JSONResponse({"orphans": orphans})


@app.post("/api/delete-images")
async def delete_images(data: dict = Body(...)):
    """删除指定文档 attachments 目录中的图片"""
    path = data.get("path", "")
    files = data.get("files", [])
    if not isinstance(path, str) or not path or not isinstance(files, list) or not files:
        return JSONResponse({"ok": False})
    md_file = resolve_within(RESULT_DIR, path, allow_root=False)
    if md_file is None or not md_file.is_file() or md_file.suffix.lower() != ".md":
        return JSONResponse({"error": "invalid path"}, status_code=400)
    att_dir = md_file.parent / "attachments"
    if not att_dir.is_dir():
        return JSONResponse({"ok": True, "deleted": 0, "skipped": 0})
    referenced = await asyncio.to_thread(referenced_attachment_names, md_file.parent)
    deleted = 0
    skipped = 0
    for name in files:
        if not isinstance(name, str) or Path(name).name != name or name in referenced:
            skipped += 1
            continue
        target = resolve_within(att_dir, name, allow_root=False)
        if target is not None and target.parent == att_dir.resolve() and target.is_file():
            await asyncio.to_thread(target.unlink)
            deleted += 1
        else:
            skipped += 1
    return JSONResponse({"ok": True, "deleted": deleted, "skipped": skipped})


@app.get("/api/dirs")
async def list_dirs():
    active = RESULT_DIR.resolve()

    def describe_dirs():
        candidates = discover_dirs()
        result = []
        for directory in candidates:
            try:
                file_count = sum(1 for entry in directory.rglob("*") if entry.is_file())
            except OSError:
                file_count = 0
            result.append({
                "name": directory.name,
                "file_count": file_count,
                "active": directory.resolve() == active,
            })
        return candidates, result

    candidates, result = await asyncio.to_thread(describe_dirs)
    return JSONResponse({"dirs": result, "multi": len(candidates) > 1})


@app.post("/api/set-dir")
async def set_dir(data: dict = Body(...)):
    global RESULT_DIR
    name = data.get("name", "")
    if not isinstance(name, str) or not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    candidates = {directory.name: directory.resolve() for directory in discover_dirs()}
    target = candidates.get(name)
    if target is None or not target.is_dir():
        return JSONResponse({"error": "invalid dir"}, status_code=400)
    RESULT_DIR = target
    return JSONResponse({"ok": True, "dir": name})


@app.get("/api/file-preview")
async def file_preview(path: str = Query(...)):
    root = RESULT_DIR.resolve()
    file_path = resolve_within(root, path, allow_root=False)
    if file_path is None:
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not file_path.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)

    file_type = classify_file(file_path.suffix)
    name = file_path.name
    relative_path = file_path.relative_to(root).as_posix()
    file_url = "/files/" + quote(relative_path, safe="/")

    if file_type == "markdown":
        try:
            content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
        except UnicodeError:
            return JSONResponse({"error": "file is not UTF-8"}, status_code=422)
        html = MARKDOWN_RENDERER(content)
        doc_dir = file_path.parent.relative_to(root).as_posix()
        html = rewrite_image_paths(html, doc_dir)
        return JSONResponse({"type": "markdown", "html": html, "title": file_path.stem, "name": name})

    if file_type == "image":
        return JSONResponse({"type": "image", "url": file_url, "name": name})

    if file_type == "pdf":
        return JSONResponse({"type": "pdf", "url": file_url, "name": name})

    if file_type == "text":
        try:
            content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
        except (OSError, UnicodeError):
            return JSONResponse({"type": "other", "name": name})
        lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript", ".go": "go",
                    ".java": "java", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
                    ".xml": "xml", ".html": "xml", ".css": "css", ".sql": "sql",
                    ".sh": "bash", ".bat": "bash", ".toml": "ini", ".ini": "ini",
                    ".rs": "rust", ".c": "c", ".cpp": "cpp", ".h": "c",
                    ".rb": "ruby", ".lua": "lua", ".kt": "kotlin", ".swift": "swift", ".dart": "dart"}
        lang = lang_map.get(file_path.suffix.lower(), "")
        return JSONResponse({"type": "text", "content": content, "name": name, "lang": lang})

    return JSONResponse({"type": "other", "name": name})


CN_NUM_MAP = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
              "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15, "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20}
CN_NUM_RE = re.compile(r'^([一二三四五六七八九十]+)[、.．]')
DIGIT_RE = re.compile(r'^(\d+)')


def natural_sort_key(name: str):
    m = CN_NUM_RE.match(name)
    if m:
        return (0, CN_NUM_MAP.get(m.group(1), 99), name.lower())
    m = DIGIT_RE.match(name)
    if m:
        return (0, int(m.group(1)), name.lower())
    return (1, 0, name.lower())


def build_tree(dir_path: Path, root: Optional[Path] = None,
               visited: Optional[set] = None) -> list:
    root = (root or dir_path).resolve()
    resolved_dir = dir_path.resolve()
    try:
        resolved_dir.relative_to(root)
    except ValueError:
        return []
    visited = visited or set()
    if resolved_dir in visited:
        return []
    visited.add(resolved_dir)

    items = []
    try:
        entries = sorted(resolved_dir.iterdir(), key=lambda e: (e.is_file(), natural_sort_key(e.name)))
    except OSError:
        return items

    for entry in entries:
        if entry.name.startswith(".") or entry.name == "attachments":
            continue
        try:
            safe_entry = entry.resolve()
            safe_entry.relative_to(root)
        except (OSError, ValueError):
            continue
        if safe_entry.is_dir():
            children = build_tree(safe_entry, root, visited)
            items.append({
                "name": entry.name,
                "type": "dir",
                "children": children,
            })
        else:
            if not safe_entry.is_file():
                continue
            file_type = classify_file(safe_entry.suffix)
            rel_path = safe_entry.relative_to(root).as_posix()
            display_name = safe_entry.stem if file_type == "markdown" else safe_entry.name
            items.append({
                "name": display_name,
                "type": "file",
                "file_type": file_type,
                "path": rel_path,
            })
    return items


def rewrite_image_paths(html: str, doc_dir: str) -> str:
    encoded_dir = "" if doc_dir in {"", "."} else quote(doc_dir, safe="/") + "/"
    pattern = re.compile(r'''src=(["'])(?:\./)?attachments/([^"']+)\1''', re.IGNORECASE)

    def replace(match):
        quote_char = match.group(1)
        attachment = quote(unquote(html_lib.unescape(match.group(2))), safe="/")
        return f"src={quote_char}/files/{encoded_dir}attachments/{attachment}{quote_char}"

    return pattern.sub(replace, html)


def find_available_port(start: int = 9000) -> int:
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serve markdown docs locally")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--port", type=int, default=0, help="Port (default: auto from 9000)")
    parser.add_argument("--dir", type=str, default="", help="Docs directory")
    args = parser.parse_args()

    if args.dir:
        RESULT_DIR = Path(args.dir).resolve()
        if not RESULT_DIR.is_dir():
            print(f"Directory not found: {RESULT_DIR}")
            raise SystemExit(1)

    port = args.port if args.port else find_available_port()
    print(f"Serving docs from: {RESULT_DIR}")
    print(f"Open http://localhost:{port}")
    webbrowser.open(f"http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)

# coding=utf-8
# Author: 梦无矶
# 公众号: 梦无矶测开实录
import argparse
import os
import platform
import re
import socket
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

import mistune
import uvicorn
from fastapi import FastAPI, Request, Query, Body, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import sys
import webbrowser

BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
EXE_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else BASE_DIR

SKIP_DIRS = {"_internal", "static", "templates", "__pycache__", "build", "dist", ".venv", "plan", "doc"}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico"}
PDF_EXTS = {".pdf"}
TEXT_EXTS = {".txt", ".json", ".yaml", ".yml", ".toml", ".xml", ".csv", ".log", ".ini", ".conf",
             ".sh", ".bat", ".py", ".js", ".ts", ".go", ".java", ".c", ".cpp", ".h", ".rs",
             ".html", ".css", ".sql", ".r", ".lua", ".rb", ".kt", ".swift", ".dart"}
MD_EXTS = {".md"}


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.mount("/files", StaticFiles(directory=str(RESULT_DIR)), name="files")
    yield


app = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/tree")
async def tree():
    return JSONResponse(build_tree(RESULT_DIR))


@app.get("/api/doc")
async def doc(path: str = Query(...)):
    file_path = (RESULT_DIR / path).resolve()
    if not str(file_path).startswith(str(RESULT_DIR.resolve())):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not file_path.exists() or not file_path.suffix == ".md":
        return JSONResponse({"error": "not found"}, status_code=404)

    content = file_path.read_text(encoding="utf-8")
    html = mistune.html(content)

    doc_dir = Path(path).parent.as_posix()
    html = rewrite_image_paths(html, doc_dir)

    return JSONResponse({"html": html, "title": file_path.stem})


@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    results = []
    keyword = q.lower()
    searchable_exts = MD_EXTS | TEXT_EXTS
    for f in RESULT_DIR.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in searchable_exts:
            continue
        if f.parent.name == "attachments":
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue
        if keyword in content.lower():
            rel_path = f.relative_to(RESULT_DIR).as_posix()
            idx = content.lower().index(keyword)
            start = max(0, idx - 40)
            end = min(len(content), idx + len(q) + 60)
            snippet = content[start:end].replace("\n", " ")
            results.append({
                "path": rel_path,
                "title": f.stem,
                "snippet": snippet,
                "file_type": classify_file(f.suffix),
            })
        if len(results) >= 50:
            break
    return JSONResponse(results)


@app.get("/api/raw")
async def raw(path: str = Query(...)):
    file_path = (RESULT_DIR / path).resolve()
    if not str(file_path).startswith(str(RESULT_DIR.resolve())):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not file_path.exists() or not file_path.suffix == ".md":
        return JSONResponse({"error": "not found"}, status_code=404)
    content = file_path.read_text(encoding="utf-8")
    return JSONResponse({"content": content, "path": path})


@app.post("/api/save")
async def save(data: dict = Body(...)):
    path = data.get("path", "")
    content = data.get("content", "")
    if not path:
        return JSONResponse({"error": "path required"}, status_code=400)
    file_path = (RESULT_DIR / path).resolve()
    if not str(file_path).startswith(str(RESULT_DIR.resolve())):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not file_path.exists() or not file_path.suffix == ".md":
        return JSONResponse({"error": "not found"}, status_code=404)
    file_path.write_text(content, encoding="utf-8")
    return JSONResponse({"ok": True})


@app.post("/api/open-file")
async def open_file(data: dict = Body(...)):
    """用系统默认编辑器打开 MD 文件（跨平台：Windows/macOS/Linux）"""
    path = data.get("path", "")
    if not path:
        return JSONResponse({"error": "path required"}, status_code=400)
    file_path = (RESULT_DIR / path).resolve()
    if not str(file_path).startswith(str(RESULT_DIR.resolve())):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not file_path.exists():
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
    file_path = (RESULT_DIR / path).resolve()
    if not str(file_path).startswith(str(RESULT_DIR.resolve())):
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
    md_file = (RESULT_DIR / doc_path).resolve()
    if not str(md_file).startswith(str(RESULT_DIR.resolve())):
        return JSONResponse({"error": "invalid path"}, status_code=400)

    md_dir = md_file.parent
    doc_stem = md_file.stem
    attachments_dir = md_dir / "attachments"
    attachments_dir.mkdir(exist_ok=True)

    ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
               "image/webp": ".webp", "image/svg+xml": ".svg"}
    ext = ext_map.get(file.content_type, "")
    if not ext:
        name_lower = (file.filename or "").lower()
        for e in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
            if name_lower.endswith(e):
                ext = e
                break
        if not ext:
            ext = ".png"

    existing = list(attachments_dir.glob(doc_stem + "_*"))
    no = len(existing) + 1
    file_name = "%s_%03d%s" % (doc_stem, no, ext)

    data = await file.read()
    (attachments_dir / file_name).write_bytes(data)

    rel_path = "./attachments/" + file_name
    return JSONResponse({"url": rel_path, "filename": file_name})


@app.post("/api/create-file")
async def create_file(data: dict = Body(...)):
    dir_path = data.get("dir", "")
    name = data.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    if not name.endswith(".md"):
        name += ".md"
    target_dir = (RESULT_DIR / dir_path).resolve() if dir_path else RESULT_DIR.resolve()
    if not str(target_dir).startswith(str(RESULT_DIR.resolve())):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    file_path = (target_dir / name).resolve()
    if not str(file_path).startswith(str(RESULT_DIR.resolve())):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if file_path.exists():
        return JSONResponse({"error": "already exists"}, status_code=400)
    stem = Path(name).stem
    file_path.write_text(f"# {stem}\n", encoding="utf-8")
    rel_path = file_path.relative_to(RESULT_DIR).as_posix()
    return JSONResponse({"ok": True, "path": rel_path})


@app.post("/api/create-dir")
async def create_dir(data: dict = Body(...)):
    dir_path = data.get("dir", "")
    name = data.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    target_dir = (RESULT_DIR / dir_path).resolve() if dir_path else RESULT_DIR.resolve()
    if not str(target_dir).startswith(str(RESULT_DIR.resolve())):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    new_dir = (target_dir / name).resolve()
    if not str(new_dir).startswith(str(RESULT_DIR.resolve())):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if new_dir.exists():
        return JSONResponse({"error": "already exists"}, status_code=400)
    new_dir.mkdir(parents=True)
    return JSONResponse({"ok": True})


@app.post("/api/delete-node")
async def delete_node(data: dict = Body(...)):
    """删除文件或文件夹（文件夹递归删除）"""
    path = data.get("path", "")
    if not path:
        return JSONResponse({"error": "path required"}, status_code=400)
    target = (RESULT_DIR / path).resolve()
    if not str(target).startswith(str(RESULT_DIR.resolve())):
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
    return JSONResponse({"ok": True})


@app.post("/api/check-orphan-images")
async def check_orphan_images(data: dict = Body(...)):
    """检查文档 attachments 中未被引用的孤立图片"""
    path = data.get("path", "")
    content = data.get("content", "")
    if not path:
        return JSONResponse({"orphans": []})
    md_file = (RESULT_DIR / path).resolve()
    if not str(md_file).startswith(str(RESULT_DIR.resolve())):
        return JSONResponse({"orphans": []})
    att_dir = md_file.parent / "attachments"
    if not att_dir.exists():
        return JSONResponse({"orphans": []})
    orphans = []
    for f in att_dir.iterdir():
        if f.is_file() and f.name not in content and ("./attachments/" + f.name) not in content:
            orphans.append(f.name)
    return JSONResponse({"orphans": orphans})


@app.post("/api/delete-images")
async def delete_images(data: dict = Body(...)):
    """删除指定文档 attachments 目录中的图片"""
    path = data.get("path", "")
    files = data.get("files", [])
    if not path or not files:
        return JSONResponse({"ok": False})
    md_file = (RESULT_DIR / path).resolve()
    if not str(md_file).startswith(str(RESULT_DIR.resolve())):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    att_dir = md_file.parent / "attachments"
    deleted = 0
    for name in files:
        target = (att_dir / name).resolve()
        if str(target).startswith(str(att_dir.resolve())) and target.exists():
            target.unlink()
            deleted += 1
    return JSONResponse({"ok": True, "deleted": deleted})


@app.get("/api/dirs")
async def list_dirs():
    candidates = discover_dirs()
    result = []
    for d in candidates:
        file_count = sum(1 for _ in d.rglob("*") if _.is_file())
        result.append({"name": d.name, "file_count": file_count, "active": d == RESULT_DIR})
    return JSONResponse({"dirs": result, "multi": len(candidates) > 1})


@app.post("/api/set-dir")
async def set_dir(data: dict = Body(...)):
    global RESULT_DIR
    name = data.get("name", "")
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    target = (EXE_DIR / name).resolve()
    if not target.is_dir() or not str(target).startswith(str(EXE_DIR.resolve())):
        return JSONResponse({"error": "invalid dir"}, status_code=400)
    RESULT_DIR = target
    app.routes[:] = [r for r in app.routes if getattr(r, "name", None) != "files"]
    app.mount("/files", StaticFiles(directory=str(RESULT_DIR)), name="files")
    return JSONResponse({"ok": True, "dir": name})


@app.get("/api/file-preview")
async def file_preview(path: str = Query(...)):
    file_path = (RESULT_DIR / path).resolve()
    if not str(file_path).startswith(str(RESULT_DIR.resolve())):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not file_path.exists() or file_path.is_dir():
        return JSONResponse({"error": "not found"}, status_code=404)

    file_type = classify_file(file_path.suffix)
    name = file_path.name
    file_url = "/files/" + Path(path).as_posix()

    if file_type == "markdown":
        content = file_path.read_text(encoding="utf-8")
        html = mistune.html(content)
        doc_dir = Path(path).parent.as_posix()
        html = rewrite_image_paths(html, doc_dir)
        return JSONResponse({"type": "markdown", "html": html, "title": file_path.stem, "name": name})

    if file_type == "image":
        return JSONResponse({"type": "image", "url": file_url, "name": name})

    if file_type == "pdf":
        return JSONResponse({"type": "pdf", "url": file_url, "name": name})

    if file_type == "text":
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, Exception):
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


def build_tree(dir_path: Path) -> list:
    items = []
    try:
        entries = sorted(dir_path.iterdir(), key=lambda e: (e.is_file(), natural_sort_key(e.name)))
    except PermissionError:
        return items

    for entry in entries:
        if entry.name.startswith(".") or entry.name == "attachments":
            continue
        if entry.is_dir():
            children = build_tree(entry)
            items.append({
                "name": entry.name,
                "type": "dir",
                "children": children,
            })
        else:
            file_type = classify_file(entry.suffix)
            rel_path = entry.relative_to(RESULT_DIR).as_posix()
            display_name = entry.stem if file_type == "markdown" else entry.name
            items.append({
                "name": display_name,
                "type": "file",
                "file_type": file_type,
                "path": rel_path,
            })
    return items


def rewrite_image_paths(html: str, doc_dir: str) -> str:
    html = html.replace('src="./attachments/', f'src="/files/{doc_dir}/attachments/')
    html = html.replace("src='./attachments/", f"src='/files/{doc_dir}/attachments/")
    html = html.replace('src="attachments/', f'src="/files/{doc_dir}/attachments/')
    html = html.replace("src='attachments/", f"src='/files/{doc_dir}/attachments/")
    return html


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
    parser.add_argument("--port", type=int, default=0, help="Port (default: auto from 9000)")
    parser.add_argument("--dir", type=str, default="", help="Docs directory")
    args = parser.parse_args()

    if args.dir:
        RESULT_DIR = Path(args.dir).resolve()
        if not RESULT_DIR.exists():
            print(f"Directory not found: {RESULT_DIR}")
            raise SystemExit(1)

    port = args.port if args.port else find_available_port()
    print(f"Serving docs from: {RESULT_DIR}")
    print(f"Open http://localhost:{port}")
    webbrowser.open(f"http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)

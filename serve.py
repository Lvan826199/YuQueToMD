# coding=utf-8
# Author: 梦无矶
# 公众号: 梦无矶测开实录
import argparse
import os
import re
import socket
from contextlib import asynccontextmanager
from pathlib import Path

import mistune
import uvicorn
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).parent
DEFAULT_RESULT_DIR = BASE_DIR / "result"

RESULT_DIR: Path = DEFAULT_RESULT_DIR


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
    for md_file in RESULT_DIR.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        if keyword in content.lower():
            rel_path = md_file.relative_to(RESULT_DIR).as_posix()
            idx = content.lower().index(keyword)
            start = max(0, idx - 40)
            end = min(len(content), idx + len(q) + 60)
            snippet = content[start:end].replace("\n", " ")
            results.append({
                "path": rel_path,
                "title": md_file.stem,
                "snippet": snippet,
            })
        if len(results) >= 50:
            break
    return JSONResponse(results)


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
            if children:
                items.append({
                    "name": entry.name,
                    "type": "dir",
                    "children": children,
                })
        elif entry.suffix == ".md":
            rel_path = entry.relative_to(RESULT_DIR).as_posix()
            items.append({
                "name": entry.stem,
                "type": "file",
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
    parser.add_argument("--dir", type=str, default=str(DEFAULT_RESULT_DIR), help="Docs directory")
    args = parser.parse_args()

    RESULT_DIR = Path(args.dir).resolve()
    if not RESULT_DIR.exists():
        print(f"Directory not found: {RESULT_DIR}")
        raise SystemExit(1)

    port = args.port if args.port else find_available_port()
    print(f"Serving docs from: {RESULT_DIR}")
    print(f"Open http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)

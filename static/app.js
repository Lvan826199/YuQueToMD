// Author: 梦无矶 | 公众号: 梦无矶测开实录
const treeNav = document.getElementById("tree-nav");
const docContent = document.getElementById("doc-content");
const searchInput = document.getElementById("search-input");
const searchResults = document.getElementById("search-results");
const searchClear = document.getElementById("search-clear");
const outlineNav = document.getElementById("outline-nav");
const contentEl = document.querySelector(".content");

let searchTimer = null;
let currentDocPath = null;
let easyMDE = null;
let autoSaveTimer = null;

async function loadTree() {
    const resp = await fetch("/api/tree");
    const data = await resp.json();
    treeNav.innerHTML = renderTree(data);
}

function renderTree(items) {
    let html = "";
    for (const item of items) {
        if (item.type === "dir") {
            html += `<div class="tree-item tree-dir">
                <div class="tree-label">${escapeHtml(item.name)}</div>
                <div class="tree-children">${renderTree(item.children)}</div>
            </div>`;
        } else {
            html += `<div class="tree-item tree-file" data-path="${escapeHtml(item.path)}">${escapeHtml(item.name)}</div>`;
        }
    }
    return html;
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

treeNav.addEventListener("click", (e) => {
    const label = e.target.closest(".tree-label");
    if (label) {
        label.parentElement.classList.toggle("open");
        return;
    }
    const file = e.target.closest(".tree-file");
    if (file) {
        loadDoc(file.dataset.path);
        document.querySelectorAll(".tree-file.active").forEach(el => el.classList.remove("active"));
        file.classList.add("active");
    }
});

async function loadDoc(path, highlight) {
    currentDocPath = path;
    const resp = await fetch(`/api/doc?path=${encodeURIComponent(path)}`);
    const data = await resp.json();
    if (data.error) {
        docContent.innerHTML = `<p style="color:red;">${data.error}</p>`;
        return;
    }
    docContent.innerHTML = `<div class="doc-toolbar"><button class="edit-btn" id="edit-btn">编辑</button><button class="open-file-btn" id="open-file-btn">用编辑器打开</button><button class="open-folder-btn" id="open-folder-btn">打开文件夹</button></div>` + data.html;
    document.title = data.title + " - MWJ Docs";
    location.hash = encodeURIComponent(path);
    docContent.querySelectorAll("pre code").forEach((block) => {
        if (block.className === "language-plain") {
            block.className = "";
        }
        hljs.highlightElement(block);
    });
    addCopyButtons();
    contentEl.scrollTop = 0;
    buildOutline();
    document.getElementById("edit-btn").addEventListener("click", () => enterEditMode(path));
    document.getElementById("open-file-btn").addEventListener("click", () => openLocal(path, "file"));
    document.getElementById("open-folder-btn").addEventListener("click", () => openLocal(path, "folder"));
    if (highlight) {
        setTimeout(() => scrollToHighlight(highlight), 100);
    }
}

function scrollToHighlight(keyword) {
    const walker = document.createTreeWalker(docContent, NodeFilter.SHOW_TEXT);
    const lowerKw = keyword.toLowerCase();
    while (walker.nextNode()) {
        const node = walker.currentNode;
        if (node.textContent.toLowerCase().includes(lowerKw)) {
            const el = node.parentElement;
            if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "center" });
                const mark = document.createElement("mark");
                mark.style.background = "#fff3a8";
                const idx = node.textContent.toLowerCase().indexOf(lowerKw);
                const range = document.createRange();
                range.setStart(node, idx);
                range.setEnd(node, idx + keyword.length);
                range.surroundContents(mark);
                setTimeout(() => { mark.style.background = "transparent"; }, 3000);
            }
            break;
        }
    }
}

function addCopyButtons() {
    docContent.querySelectorAll("pre").forEach((pre) => {
        const btn = document.createElement("button");
        btn.className = "copy-btn";
        btn.textContent = "复制";
        btn.addEventListener("click", () => {
            const code = pre.querySelector("code");
            navigator.clipboard.writeText(code ? code.textContent : pre.textContent).then(() => {
                btn.textContent = "已复制";
                setTimeout(() => { btn.textContent = "复制"; }, 2000);
            });
        });
        pre.style.position = "relative";
        pre.appendChild(btn);
    });
}

searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    const q = searchInput.value.trim();
    searchClear.style.display = q ? "block" : "none";
    if (!q) {
        searchResults.style.display = "none";
        treeNav.style.display = "";
        return;
    }
    searchTimer = setTimeout(() => doSearch(q), 300);
});

searchClear.addEventListener("click", () => {
    searchInput.value = "";
    searchClear.style.display = "none";
    searchResults.style.display = "none";
    treeNav.style.display = "";
});

async function doSearch(q) {
    const resp = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const results = await resp.json();
    if (results.length === 0) {
        searchResults.innerHTML = `<div style="padding:12px;color:#57606a;">未找到匹配内容</div>`;
    } else {
        searchResults.innerHTML = results.map(r => `
            <div class="search-item" data-path="${escapeHtml(r.path)}">
                <div class="title">${escapeHtml(r.title)}</div>
                <div class="snippet">${escapeHtml(r.snippet)}</div>
            </div>
        `).join("");
    }
    searchResults.style.display = "block";
    treeNav.style.display = "none";
}

searchResults.addEventListener("click", (e) => {
    const item = e.target.closest(".search-item");
    if (item) {
        loadDoc(item.dataset.path, searchInput.value.trim());
    }
});

searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        searchInput.value = "";
        searchClear.style.display = "none";
        searchResults.style.display = "none";
        treeNav.style.display = "";
    }
});

loadTree();

if (location.hash) {
    const path = decodeURIComponent(location.hash.slice(1));
    if (path) loadDoc(path);
}

function buildOutline() {
    const headings = docContent.querySelectorAll("h1, h2, h3, h4, h5, h6");
    if (headings.length === 0) {
        outlineNav.innerHTML = '<div style="padding:8px;color:#57606a;font-size:12px;">无标题</div>';
        return;
    }
    let html = "";
    headings.forEach((h, i) => {
        const id = "heading-" + i;
        h.id = id;
        const level = parseInt(h.tagName[1]);
        const text = h.textContent.trim();
        html += `<a class="outline-item" data-level="${level}" data-id="${id}" title="${escapeHtml(text)}">${escapeHtml(text)}</a>`;
    });
    outlineNav.innerHTML = html;
}

outlineNav.addEventListener("click", (e) => {
    const item = e.target.closest(".outline-item");
    if (!item) return;
    const target = document.getElementById(item.dataset.id);
    if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        outlineNav.querySelectorAll(".outline-item.active").forEach(el => el.classList.remove("active"));
        item.classList.add("active");
    }
});

contentEl.addEventListener("scroll", () => {
    const headings = docContent.querySelectorAll("[id^='heading-']");
    if (headings.length === 0) return;
    let current = null;
    for (const h of headings) {
        const rect = h.getBoundingClientRect();
        if (rect.top <= 80) current = h.id;
        else break;
    }
    if (current) {
        outlineNav.querySelectorAll(".outline-item.active").forEach(el => el.classList.remove("active"));
        const active = outlineNav.querySelector(`[data-id="${current}"]`);
        if (active) {
            active.classList.add("active");
            active.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }
});

const outlinePanel = document.getElementById("outline-panel");
const resizeHandle = document.getElementById("outline-resize-handle");

resizeHandle.addEventListener("mousedown", (e) => {
    e.preventDefault();
    resizeHandle.classList.add("dragging");
    const startX = e.clientX;
    const startWidth = outlinePanel.offsetWidth;

    function onMove(e) {
        const delta = startX - e.clientX;
        const newWidth = Math.min(500, Math.max(140, startWidth + delta));
        outlinePanel.style.width = newWidth + "px";
    }

    function onUp() {
        resizeHandle.classList.remove("dragging");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
});

async function enterEditMode(path) {
    const resp = await fetch(`/api/raw?path=${encodeURIComponent(path)}`);
    const data = await resp.json();
    if (data.error) return;

    document.body.classList.add("editing");
    docContent.innerHTML = `<div class="doc-toolbar">
        <button class="save-btn" id="save-btn">保存</button>
        <button class="done-btn" id="done-btn">完成</button>
        <button class="cancel-btn" id="cancel-btn">取消</button>
        <button class="exit-btn" id="exit-btn">退出编辑</button>
        <span class="save-status" id="save-status"></span>
    </div><textarea id="editor-area"></textarea>`;

    const textarea = document.getElementById("editor-area");
    textarea.value = data.content;

    easyMDE = new EasyMDE({
        element: textarea,
        spellChecker: false,
        autofocus: true,
        status: false,
        minHeight: "calc(100vh - 160px)",
        uploadImage: true,
        imageUploadFunction: (file, onSuccess, onError) => {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("doc_path", path);
            fetch("/api/upload-image", { method: "POST", body: formData })
                .then(r => r.json())
                .then(data => {
                    if (data.url) onSuccess(data.url);
                    else onError(data.error || "上传失败");
                })
                .catch(e => onError(e.message));
        },
        imageAccept: "image/png, image/jpeg, image/gif, image/webp, image/svg+xml",
        toolbar: [
            {name: "bold", action: EasyMDE.toggleBold, className: "fa fa-bold", title: "加粗"},
            {name: "italic", action: EasyMDE.toggleItalic, className: "fa fa-italic", title: "斜体"},
            {name: "heading", action: EasyMDE.toggleHeadingSmaller, className: "fa fa-header", title: "标题"},
            "|",
            {name: "quote", action: EasyMDE.toggleBlockquote, className: "fa fa-quote-left", title: "引用"},
            {name: "unordered-list", action: EasyMDE.toggleUnorderedList, className: "fa fa-list-ul", title: "无序列表"},
            {name: "ordered-list", action: EasyMDE.toggleOrderedList, className: "fa fa-list-ol", title: "有序列表"},
            "|",
            {name: "link", action: EasyMDE.drawLink, className: "fa fa-link", title: "链接"},
            {name: "image", action: EasyMDE.drawImage, className: "fa fa-picture-o", title: "图片"},
            {name: "upload-image", action: EasyMDE.drawUploadedImage, className: "fa fa-upload", title: "上传图片"},
            {name: "code", action: EasyMDE.toggleCodeBlock, className: "fa fa-code", title: "代码块"},
            {name: "table", action: EasyMDE.drawTable, className: "fa fa-table", title: "表格"},
            "|",
            {name: "preview", action: EasyMDE.togglePreview, className: "fa fa-eye no-disable", title: "预览"},
            {name: "side-by-side", action: EasyMDE.toggleSideBySide, className: "fa fa-columns no-disable no-mobile", title: "分栏预览"},
            {name: "fullscreen", action: EasyMDE.toggleFullScreen, className: "fa fa-arrows-alt no-disable no-mobile", title: "全屏"},
            "|",
            {name: "save", action: () => saveDoc(path), className: "fa fa-floppy-o", title: "保存 (Ctrl+S)"},
            {name: "exit", action: () => exitEditMode(path), className: "fa fa-times-circle", title: "退出编辑"},
        ],
    });

    setTimeout(() => EasyMDE.toggleSideBySide(easyMDE), 100);

    easyMDE.codemirror.on("change", () => {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(() => saveDoc(path), 2000);
    });

    document.getElementById("save-btn").addEventListener("click", () => saveDoc(path));
    document.getElementById("done-btn").addEventListener("click", () => exitEditMode(path));
    document.getElementById("cancel-btn").addEventListener("click", () => cancelEdit(path));
    document.getElementById("exit-btn").addEventListener("click", () => cancelEdit(path));

    document.addEventListener("keydown", editorKeyHandler);
}

function editorKeyHandler(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (currentDocPath) saveDoc(currentDocPath);
    }
}

async function saveDoc(path) {
    if (!easyMDE) return;
    const content = easyMDE.value();
    const statusEl = document.getElementById("save-status");
    try {
        const resp = await fetch("/api/save", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({path, content}),
        });
        const data = await resp.json();
        if (data.ok) {
            statusEl.textContent = "已保存";
            statusEl.style.color = "#2da44e";
        } else {
            statusEl.textContent = "保存失败";
            statusEl.style.color = "#cf222e";
        }
    } catch {
        statusEl.textContent = "保存失败";
        statusEl.style.color = "#cf222e";
    }
    setTimeout(() => { statusEl.textContent = ""; }, 2000);
}

function exitEditMode(path) {
    document.removeEventListener("keydown", editorKeyHandler);
    document.body.classList.remove("editing");
    if (easyMDE) {
        easyMDE.toTextArea();
        easyMDE = null;
    }
    clearTimeout(autoSaveTimer);
    loadDoc(path);
}

function cancelEdit(path) {
    document.removeEventListener("keydown", editorKeyHandler);
    document.body.classList.remove("editing");
    clearTimeout(autoSaveTimer);
    if (easyMDE) {
        easyMDE.toTextArea();
        easyMDE = null;
    }
    loadDoc(path);
}

async function openLocal(path, type) {
    const endpoint = type === "file" ? "/api/open-file" : "/api/open-folder";
    try {
        await fetch(endpoint, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({path}),
        });
    } catch {}
}

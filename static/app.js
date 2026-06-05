const treeNav = document.getElementById("tree-nav");
const docContent = document.getElementById("doc-content");
const searchInput = document.getElementById("search-input");
const searchResults = document.getElementById("search-results");
const outlineNav = document.getElementById("outline-nav");
const contentEl = document.querySelector(".content");

let searchTimer = null;

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

async function loadDoc(path) {
    const resp = await fetch(`/api/doc?path=${encodeURIComponent(path)}`);
    const data = await resp.json();
    if (data.error) {
        docContent.innerHTML = `<p style="color:red;">${data.error}</p>`;
        return;
    }
    docContent.innerHTML = data.html;
    document.title = data.title + " - YuQue Docs";
    hljs.highlightAll();
    contentEl.scrollTop = 0;
    buildOutline();
}

searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    const q = searchInput.value.trim();
    if (!q) {
        searchResults.style.display = "none";
        treeNav.style.display = "";
        return;
    }
    searchTimer = setTimeout(() => doSearch(q), 300);
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
        loadDoc(item.dataset.path);
    }
});

searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        searchInput.value = "";
        searchResults.style.display = "none";
        treeNav.style.display = "";
    }
});

loadTree();

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
        if (active) active.classList.add("active");
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

// ============================================================
// SONORA — Frontend Logic
// ============================================================

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

let currentAnalysis = null;
let selectedUrls = new Set();
let inspectedTrack = null;
let libraryItems = [];

const VIEW_TITLES = {
  downloader: "Downloader",
  settings: "Storage & Lyrics",
  downloads: "Downloads",
  library: "My Library"
};

const VIEW_SUBS = {
  downloader: "Preview Spotify playlists, albums and tracks before downloading",
  settings: "Choose where music and optional lyrics are saved",
  downloads: "Monitor current and recent download tasks",
  library: "Browse downloaded music and lyrics"
};

// Navigation
$$(".nav-item").forEach(el => {
  el.addEventListener("click", (e) => {
    e.preventDefault();
    $$(".nav-item").forEach(n => n.classList.remove("active"));
    $$(".view").forEach(v => v.classList.remove("active"));
    el.classList.add("active");
    const view = el.dataset.view;
    $(`#view-${view}`).classList.add("active");
    
    $("#pageTitle").textContent = VIEW_TITLES[view] || "SONORA";
    $("#pageTitle").nextElementSibling.textContent = VIEW_SUBS[view] || "";
    
    if (view === "library") loadLibrary();
    if (view === "downloads") loadDownloads();
    if (view === "settings") loadSettings();
  });
});

function toast(msg, isErr) {
  const t = document.createElement("div");
  t.className = "toast";
  t.style.position = "fixed";
  t.style.bottom = "24px";
  t.style.right = "24px";
  t.style.background = isErr ? "#ef4444" : "#10b981";
  t.style.color = isErr ? "#fff" : "#000";
  t.style.padding = "12px 20px";
  t.style.borderRadius = "8px";
  t.style.fontWeight = "600";
  t.style.zIndex = "9999";
  t.style.boxShadow = "0 10px 25px rgba(0,0,0,0.5)";
  t.style.fontSize = "13px";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

function fmtDuration(sec) {
  sec = Math.round(sec || 0);
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Input Handling
$("#sampleBtn").addEventListener("click", () => {
  $("#urlInput").value = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M";
});

async function analyzeUrl() {
  const url = $("#urlInput").value.trim();
  if (!url) return toast("Paste a Spotify URL first", true);
  
  const btn = $("#analyzeBtn");
  btn.disabled = true;
  btn.innerHTML = "READING TRACKS...";
  $("#analysisResult").innerHTML = `<div class="analysis-loading">Reading playlist track details…</div>`;
  $("#activityCard").style.display = "none";
  
  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Analysis failed");
    
    currentAnalysis = data;
    selectedUrls = new Set(data.tracks.map(t => t.url));
    inspectedTrack = data.tracks[0] || null;
    renderAnalysis(data);
    toast(`Found ${data.total_tracks} tracks`);
  } catch (err) {
    $("#analysisResult").innerHTML = `<div style="color:#ef4444; padding:16px; background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.2); border-radius:8px; font-size:12px;">${escapeHtml(err.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg> PREVIEW TRACKS`;
  }
}

$("#analyzeBtn").addEventListener("click", analyzeUrl);
$("#urlInput").addEventListener("keydown", event => {
  if (event.key === "Enter") analyzeUrl();
});

function renderAnalysis(data) {
  const html = `
    <div class="analysis-grid">
      <div class="playlist-panel">
        <div class="playlist-head">
          <img class="playlist-cover" src="${data.cover_url || ''}" alt="">
          <div class="playlist-info">
            <div class="playlist-badge">${escapeHtml((data.type || "spotify").toUpperCase())}</div>
            <div class="playlist-name">${escapeHtml(data.title)}</div>
            <div class="playlist-meta">${escapeHtml(data.owner)} · ${data.total_tracks} tracks · ${fmtDuration(data.total_duration)}</div>
          </div>
          <div class="playlist-actions">
            <button id="clearBtn">Clear</button>
            <button id="selectAllBtn">Deselect All</button>
            <button class="btn-analyze" id="downloadBtn" style="height:34px; padding:0 16px; font-size:11px;">
              Download (${selectedUrls.size})
            </button>
          </div>
        </div>
        <div class="track-list" id="trackList">
          ${data.tracks.map((t, i) => `
            <div class="track-row selected ${inspectedTrack?.url === t.url ? 'inspected' : ''}" data-url="${t.url}">
              <div class="track-num">${String(i+1).padStart(2, '0')}</div>
              <input type="checkbox" class="track-check" data-url="${t.url}" checked>
              <img class="track-cover" src="${t.cover_url || ''}" alt="">
              <div class="track-info">
                <div class="track-title">${escapeHtml(t.name)}</div>
                <div class="track-artist">${escapeHtml(t.artist)}</div>
              </div>
              <div class="track-status">Ready</div>
              <div class="track-dur">${fmtDuration(t.duration)}</div>
            </div>
          `).join("")}
        </div>
        <div class="bulk-bar">
          <div class="bulk-info"><strong>${selectedUrls.size}</strong> of ${data.tracks.length} selected</div>
        </div>
      </div>
      <div class="inspector" id="inspector">
        ${renderInspector(inspectedTrack)}
      </div>
    </div>
  `;
  
  $("#analysisResult").innerHTML = html;
  
  // Re-bind events
  $$("#trackList .track-check").forEach(cb => {
    cb.addEventListener("click", e => e.stopPropagation());
    cb.addEventListener("change", () => {
      const u = cb.dataset.url;
      cb.checked ? selectedUrls.add(u) : selectedUrls.delete(u);
      cb.closest(".track-row").classList.toggle("selected", cb.checked);
      $(".bulk-info").innerHTML = `<strong>${selectedUrls.size}</strong> of ${data.tracks.length} selected`;
      $("#downloadBtn").innerHTML = `Download (${selectedUrls.size})`;
    });
  });
  
  $$("#trackList .track-row").forEach(row => {
    row.addEventListener("click", () => {
      inspectedTrack = data.tracks.find(t => t.url === row.dataset.url);
      $$("#trackList .track-row").forEach(r => r.classList.remove("inspected"));
      row.classList.add("inspected");
      $("#inspector").innerHTML = renderInspector(inspectedTrack);
    });
  });

  $("#clearBtn").addEventListener("click", () => {
    $("#analysisResult").innerHTML = "";
    $("#activityCard").style.display = "block";
    currentAnalysis = null;
  });

  $("#selectAllBtn").addEventListener("click", () => {
    const allSel = selectedUrls.size === data.tracks.length;
    selectedUrls = allSel ? new Set() : new Set(data.tracks.map(t => t.url));
    $$("#trackList .track-check").forEach(cb => {
      cb.checked = !allSel;
      cb.closest(".track-row").classList.toggle("selected", !allSel);
    });
    $("#selectAllBtn").textContent = allSel ? "Select All" : "Deselect All";
    $(".bulk-info").innerHTML = `<strong>${selectedUrls.size}</strong> of ${data.tracks.length} selected`;
    $("#downloadBtn").innerHTML = `Download (${selectedUrls.size})`;
  });

  $("#downloadBtn").addEventListener("click", startDownload);
}

function renderInspector(t) {
  if (!t) return `<div class="inspector-empty">Select a track to inspect.</div>`;
  return `
    <div class="inspector-head">
      <div class="inspector-title">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
        Track Inspector
      </div>
      <div class="inspector-tag">Metadata</div>
    </div>
    <div class="inspector-track">
      <img src="${t.cover_url || ''}" alt="">
      <div>
        <div class="name">${escapeHtml(t.name)}</div>
        <div class="artist">${escapeHtml(t.artist)}</div>
        <div class="album">${escapeHtml(t.album_name)}</div>
      </div>
    </div>
    <div class="inspector-rows">
      <div class="inspector-row"><span class="k">Duration</span><span class="v">${fmtDuration(t.duration)}</span></div>
      <div class="inspector-row"><span class="k">Year</span><span class="v">${t.year || "—"}</span></div>
      <div class="inspector-row"><span class="k">Track No.</span><span class="v">${t.track_number || "—"}</span></div>
      <div class="inspector-row"><span class="k">Explicit</span><span class="v">${t.explicit ? "Yes" : "No"}</span></div>
    </div>
  `;
}

async function startDownload() {
  if (!selectedUrls.size) return toast("Select at least one track", true);
  const urls = Array.from(selectedUrls);
  try {
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    
    toast(`Download started`);
    $("#chipSpeed").textContent = "Active";
    $("#chipSpeed").style.color = "var(--green)";
    streamProgress(data.task_id);
    document.querySelector('[data-view="downloads"]').click();
  } catch (err) { toast(err.message, true); }
}

function streamProgress(taskId) {
  const es = new EventSource(`/api/downloads/${taskId}/stream`);
  let done = 0, total = 0;
  
  es.onmessage = (e) => {
    const evt = JSON.parse(e.data);
    if (evt.type === "started") total = evt.total;
    if (evt.type === "track_start") loadDownloads();
    if (evt.type === "track_done" || evt.type === "track_failed") {
      done++;
      loadDownloads();
      loadRecentActivity();
      if (done === total) {
        es.close();
        $("#chipSpeed").textContent = "Idle";
        $("#chipSpeed").style.color = "var(--green)";
        loadDownloads();
      }
    }
    if (evt.type === "finished") {
       es.close();
       $("#chipSpeed").textContent = "Idle";
       loadDownloads();
    }
  };
}

// Loaders
async function loadDownloads() {
  const res = await fetch("/api/downloads");
  const data = await res.json();
  $("#downloadsList").innerHTML = data.length ? data.map(t => `
    <div class="download-task">
      <div>
        <div class="task-title">Download task <span>${escapeHtml(t.id)}</span></div>
        <div class="task-meta">${t.completed} of ${t.total} complete · ${t.failed} failed${t.current_track ? ` · ${escapeHtml(t.current_track)}` : ""}</div>
        <div class="task-progress"><span style="width:${Math.min(100, t.percentage)}%"></span></div>
        ${(t.errors || []).length ? `<div class="task-errors">${t.errors.map(error => `<div>${escapeHtml(error)}</div>`).join("")}</div>` : ""}
      </div>
      <div class="task-status ${escapeHtml(t.status)}">${escapeHtml(t.status)}</div>
    </div>
  `).join("") : `<div class="activity-empty">No tasks yet.</div>`;
}

async function loadRecentActivity() {
  const res = await fetch("/api/downloads");
  const data = await res.json();
  const recent = data.slice(-3).reverse();
  $("#activityBody").innerHTML = recent.length ? recent.map(task => `
    <div class="recent-task">
      <div>
        <div class="recent-task-title">${escapeHtml(task.current_track || "Spotify download")}</div>
        <div class="recent-task-meta">${task.completed} of ${task.total} tracks complete · ${task.failed} failed</div>
      </div>
      <span class="task-status ${escapeHtml(task.status)}">${escapeHtml(task.status)}</span>
    </div>
  `).join("") : `<div class="activity-empty">Your recent download tasks will appear here.</div>`;
}

async function loadLibrary() {
  const res = await fetch("/api/library");
  libraryItems = await res.json();
  renderLibrary($("#libSearch").value);
}

function renderLibrary(query = "") {
  const term = query.trim().toLowerCase();
  const items = libraryItems.filter(it =>
    `${it.title} ${it.artist} ${it.album}`.toLowerCase().includes(term)
  );
  $("#libraryList").innerHTML = items.length ? items.map(it => `
    <div class="library-row">
      <div>
        <div class="library-title">${escapeHtml(it.title)}</div>
        <div class="library-artist">${escapeHtml(it.artist)}</div>
      </div>
      <div class="library-duration">${fmtDuration(it.duration)}</div>
    </div>
  `).join("") : `<div class="activity-empty">${term ? "No matching music found." : "No music found."}</div>`;
}

$("#libSearch").addEventListener("input", event => renderLibrary(event.target.value));
$("#libRefresh").addEventListener("click", loadLibrary);

async function loadSettings() {
  const res = await fetch("/api/settings");
  const data = await res.json();
  $("#musicDirDisplay").textContent = data.music_dir || "Not selected";
  $("#lyricsDirDisplay").textContent = data.lyrics_dir || "Not selected";
  if (data.music_dir) {
    const parts = data.music_dir.split(/[\\/]/);
    $("#chipDir").textContent = parts[parts.length - 1] || data.music_dir;
    $("#statDir").textContent = data.music_dir;
  }
}

$("#pickMusicBtn").addEventListener("click", async () => {
  const btn = $("#pickMusicBtn");
  btn.disabled = true; btn.textContent = "...";
  try {
    const res = await fetch("/api/settings/select-music-directory", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message);
    $("#musicDirDisplay").textContent = data.path;
    const parts = data.path.split(/[\\/]/);
    $("#chipDir").textContent = parts[parts.length - 1] || data.path;
    $("#statDir").textContent = data.path;
    toast("Music directory saved");
  } catch (err) { toast(err.message, true); }
  finally { btn.disabled = false; btn.textContent = "Browse"; }
});

$("#pickLyricsBtn").addEventListener("click", async () => {
  const btn = $("#pickLyricsBtn");
  btn.disabled = true; btn.textContent = "...";
  try {
    const res = await fetch("/api/settings/select-lyrics-directory", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message);
    $("#lyricsDirDisplay").textContent = data.path;
    toast("Lyrics directory saved");
  } catch (err) { toast(err.message, true); }
  finally { btn.disabled = false; btn.textContent = "Browse"; }
});

// Terminal
function initTerminal() {
  const out = $("#terminalOutput");
  const es = new EventSource("/api/logs/stream");
  
  es.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      if (!d.line) return;
      
      const timeMatch = d.line.match(/^(\d{2}:\d{2}:\d{2})/);
      const time = timeMatch ? timeMatch[1] : new Date().toLocaleTimeString('en-US', {hour12: false});
      const msg = d.line.replace(/^\d{2}:\d{2}:\d{2}\s*/, '');
      
      let type = "info";
      if (msg.includes("[INFO]")) type = "info";
      if (msg.includes("[ERROR]")) type = "error";
      if (msg.includes("spotdl") || msg.includes("[task")) type = "python";
      
      const cleanMsg = msg.replace(/\[.*?\]\s*/, '');
      
      const row = document.createElement("div");
      row.className = "log-row";
      row.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-badge ${type}">${type.toUpperCase()}</span>
        <span class="log-msg ${type}">${escapeHtml(cleanMsg)}</span>
      `;
      
      out.appendChild(row);
      out.scrollTop = out.scrollHeight;
      
      const count = out.children.length;
      $("#logCount").textContent = `${count} entries`;
      while (out.children.length > 200) out.firstElementChild.remove();
    } catch (_) {}
  };

  $("#clearTerminalBtn").addEventListener("click", () => {
    out.innerHTML = "";
    $("#logCount").textContent = "0 entries";
  });
}

initTerminal();
loadSettings();
loadRecentActivity();
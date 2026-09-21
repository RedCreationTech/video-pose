from __future__ import annotations

INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>Video Pose 现场控制台</title>
  <link rel="stylesheet" href="/console/style.css">
  <script defer src="/console/app.js"></script>
</head>
<body>
  <header class="topbar">
    <div>
      <div class="eyebrow">VIDEO POSE EDGE</div>
      <h1>动作规范检测现场控制台</h1>
    </div>
    <div class="badges">
      <span id="connectionBadge" class="badge neutral">未连接</span>
      <span id="roleBadge" class="badge neutral">-</span>
      <span id="versionBadge" class="badge neutral">version -</span>
    </div>
  </header>

  <main class="layout">
    <section class="panel auth-panel">
      <div class="section-head">
        <div>
          <h2>连接与鉴权</h2>
          <p>Bearer Token 只保存在当前页面内存中, 不写入 URL 或 localStorage.</p>
        </div>
      </div>
      <div class="form-row">
        <label class="grow">Bearer Token
          <input id="tokenInput" type="password" autocomplete="off" placeholder="认证关闭时可留空">
        </label>
        <button id="connectBtn" class="primary">连接</button>
        <button id="disconnectBtn" class="secondary">断开</button>
      </div>
      <div id="notice" class="notice hidden"></div>
    </section>

    <section class="kpi-grid">
      <article class="kpi"><span>生产 Readiness</span><strong id="readyKpi">-</strong><small id="readyDetail">等待连接</small></article>
      <article class="kpi"><span>当前 Session</span><strong id="sessionKpi">-</strong><small id="sessionDetail">无数据</small></article>
      <article class="kpi"><span>当前评分</span><strong id="scoreKpi">-</strong><small id="passDetail">无评估</small></article>
      <article class="kpi"><span>同步 P99</span><strong id="syncKpi">-</strong><small id="syncDetail">无同步数据</small></article>
    </section>

    <section class="panel alert-panel">
      <div class="section-head">
        <div>
          <h2>现场告警</h2>
          <p>START BLOCKER 显示当前开工阻塞项, QUALITY INCIDENT 显示运行中质量违规.</p>
        </div>
        <div class="button-row">
          <span id="alertCount" class="badge neutral">0</span>
          <button id="clearAlertsBtn" class="secondary">清除本地事件</button>
        </div>
      </div>
      <div id="alertsList" class="alert-list empty-state">当前没有告警.</div>
    </section>

    <section class="panel cameras-panel">
      <div class="section-head">
        <div>
          <h2>四路摄像头</h2>
          <p>状态, FPS, 重连计数, Capture backend, Timestamp source 与最新同步快照.</p>
        </div>
        <button id="refreshSnapshotsBtn" class="secondary">刷新快照</button>
      </div>
      <div id="cameraGrid" class="camera-grid empty-state">连接后显示摄像头.</div>
    </section>

    <section class="two-col">
      <article class="panel">
        <div class="section-head">
          <div><h2>Session 控制</h2><p>正式开工前必须通过 Readiness Gate.</p></div>
        </div>
        <div class="form-stack">
          <label>操作员 ID<input id="operatorInput" type="text" maxlength="128" placeholder="operator-001"></label>
          <label>Session ID, 可选<input id="sessionIdInput" type="text" maxlength="128" placeholder="留空自动生成"></label>
        </div>
        <div class="button-row">
          <button id="startBtn" class="primary">开始 Session</button>
          <button id="stopBtn" class="success">正常结束</button>
          <button id="abortBtn" class="danger">中止</button>
        </div>
        <div id="currentSession" class="detail-box">无活动 Session.</div>
      </article>

      <article class="panel">
        <div class="section-head">
          <div><h2>Readiness Gate</h2><p>相机, 同步, 模型, Evidence, Audit, DB, 存储与标定.</p></div>
        </div>
        <div id="readinessList" class="check-list empty-state">暂无数据.</div>
      </article>
    </section>

    <section class="two-col">
      <article class="panel">
        <div class="section-head">
          <div><h2>实时评估</h2><p>步骤状态, 违规, Score 与 PASS/FAIL.</p></div>
        </div>
        <div id="evaluationSummary" class="detail-box">暂无评估.</div>
        <div class="split-list">
          <div><h3>步骤</h3><div id="stepsList" class="compact-list"></div></div>
          <div><h3>违规</h3><div id="violationsList" class="compact-list"></div></div>
        </div>
      </article>

      <article class="panel">
        <div class="section-head">
          <div><h2>运行健康</h2><p>处理队列, 资源, Evidence, Audit 和文件系统.</p></div>
        </div>
        <div id="runtimeHealth" class="health-grid empty-state">暂无数据.</div>
      </article>
    </section>

    <section class="two-col">
      <article class="panel">
        <div class="section-head">
          <div><h2>Release Identity</h2><p>软件, Git, Image, 模型与配置发布指纹.</p></div>
        </div>
        <div id="releaseIdentity" class="detail-box">暂无数据.</div>
      </article>

      <article class="panel">
        <div class="section-head">
          <div><h2>Persistence</h2><p>数据库连接与 Audit → SQL 完整性分别显示.</p></div>
          <button id="reconcileBtn" class="secondary">执行对账</button>
        </div>
        <div id="persistenceHealth" class="detail-box">暂无权限或数据.</div>
      </article>
    </section>

    <section class="panel">
      <div class="section-head">
        <div><h2>Pending Review</h2><p>复核自动违规. Confirm/Dismiss 不删除原始自动判定.</p></div>
        <span id="reviewCount" class="badge neutral">0</span>
      </div>
      <div id="reviewsList" class="review-list empty-state">暂无待复核数据.</div>
    </section>

    <section class="two-col operations-lower">
      <article class="panel">
        <div class="section-head">
          <div>
            <h2>Session 历史</h2>
            <p>最近完成或中止的 Session. 点击后加载完整结果和 Evidence.</p>
          </div>
          <span id="historyCount" class="badge neutral">0</span>
        </div>
        <div id="historyList" class="history-list empty-state">暂无历史 Session.</div>
      </article>

      <article class="panel">
        <div class="section-head">
          <div>
            <h2>Crash Recovery</h2>
            <p>没有 final.json 的残缺 Session 必须显式恢复为 ABORTED.</p>
          </div>
          <span id="incompleteCount" class="badge neutral">0</span>
        </div>
        <div id="incompleteList" class="history-list empty-state">暂无残缺 Session.</div>
      </article>
    </section>

    <section class="panel evidence-panel">
      <div class="section-head">
        <div>
          <h2>Evidence Explorer</h2>
          <p id="selectedSessionLabel">从 Session 历史选择一条记录.</p>
        </div>
        <button id="reloadEvidenceBtn" class="secondary">刷新证据</button>
      </div>
      <div id="historicalDetail" class="detail-box">尚未选择 Session.</div>
      <div id="evidenceGrid" class="evidence-grid empty-state">暂无证据.</div>
    </section>
  </main>

  <footer>
    <span>Video Pose Edge Console</span>
    <span id="lastRefresh">尚未刷新</span>
  </footer>
</body>
</html>"""

STYLE_CSS = r""":root {
  --bg:#0a1017;--panel:#111a24;--panel2:#162230;--line:#26384b;
  --text:#e8eef5;--muted:#8fa3b7;--cyan:#42c7ef;--green:#47d487;
  --amber:#f0b84e;--red:#ff6d76;--shadow:0 14px 36px rgba(0,0,0,.24);
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 12% 0%,rgba(66,199,239,.08),transparent 32rem),var(--bg);color:var(--text);min-height:100vh}
button,input{font:inherit}button{cursor:pointer;color:var(--text);border:1px solid transparent;border-radius:6px;padding:9px 12px;background:#223143}button:hover:not(:disabled){filter:brightness(1.12)}button:disabled{opacity:.35;cursor:not-allowed}
.topbar{min-height:82px;padding:16px 28px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:20;backdrop-filter:blur(16px);background:rgba(10,16,23,.93)}
.eyebrow{color:var(--cyan);letter-spacing:.18em;font-size:11px;font-weight:800}h1{margin:3px 0 0;font-size:22px;font-weight:650}h2{margin:0;font-size:17px}h3{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}p{margin:5px 0 0;color:var(--muted);font-size:12px}
.badges,.button-row,.form-row{display:flex;gap:8px;align-items:end}.layout{max-width:1600px;margin:0 auto;padding:22px}.panel{background:linear-gradient(180deg,rgba(22,34,48,.9),rgba(17,26,36,.97));border:1px solid var(--line);border-radius:10px;padding:16px;box-shadow:var(--shadow)}
.auth-panel,.cameras-panel,.two-col{margin-bottom:12px}.section-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:14px}.form-row .grow{flex:1}.form-stack{display:grid;gap:10px;margin-bottom:12px}label{color:var(--muted);font-size:12px;display:grid;gap:6px}
input{color:var(--text);background:#0a121a;border:1px solid #31465b;border-radius:6px;padding:9px 10px;outline:none}input:focus{border-color:var(--cyan);box-shadow:0 0 0 2px rgba(66,199,239,.12)}
.primary{background:#087da4;border-color:#159dc8}.success{background:#18754a;border-color:#269761}.danger{background:#8f3038;border-color:#b3404a}.secondary{border-color:#3a4f65;background:#1a2735}
.badge{display:inline-flex;align-items:center;min-height:25px;padding:3px 9px;border-radius:999px;border:1px solid var(--line);font-size:11px;white-space:nowrap}.badge.good{color:#9af0bc;border-color:#307b52;background:#163925}.badge.bad{color:#ffb0b4;border-color:#89444c;background:#3d2025}.badge.warn{color:#ffd98d;border-color:#806532;background:#3b3018}.badge.neutral{color:#bac8d5;background:#18232f}
.notice{margin-top:12px;padding:9px 11px;border-radius:6px;background:#142233}.notice.error{border-left:3px solid var(--red)}.hidden{display:none!important}
.alert-panel{margin-bottom:12px}.alert-list{display:grid;gap:7px}.alert-row{display:grid;grid-template-columns:auto 1fr auto;gap:9px;align-items:start;padding:9px;border:1px solid #2b3d50;border-radius:7px;background:#0d161f}.alert-row.blocker{border-left:3px solid var(--amber)}.alert-row.incident{border-left:3px solid var(--red)}.alert-message{font-size:12px;font-weight:650}.alert-detail{color:var(--muted);font-size:11px;margin-top:2px;overflow-wrap:anywhere}.alert-time{font-size:10px;color:#6f8295;white-space:nowrap}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}.kpi{background:#101a24;border:1px solid var(--line);border-radius:8px;padding:14px}.kpi span,.kpi small{display:block;color:var(--muted)}.kpi strong{display:block;font-size:26px;margin:4px 0}
.camera-grid{display:grid;grid-template-columns:repeat(4,minmax(220px,1fr));gap:10px}.camera-card{border:1px solid var(--line);background:#0c151e;border-radius:8px;overflow:hidden}.camera-head{display:flex;justify-content:space-between;padding:10px}.camera-title{font-weight:700}.camera-meta{white-space:pre-line;color:var(--muted);font-size:11px;line-height:1.55;padding:0 10px 10px}.camera-image{width:100%;aspect-ratio:16/9;display:block;object-fit:cover;background:repeating-linear-gradient(135deg,#111c27,#111c27 10px,#14212d 10px,#14212d 20px)}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:12px}.detail-box{background:#0b141d;border:1px solid #233649;border-radius:7px;padding:10px;color:#c6d2dd;font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;margin-top:10px}.check-list,.compact-list,.review-list{display:grid;gap:7px}.check-row,.compact-row{display:grid;grid-template-columns:auto 1fr;gap:8px;align-items:start;padding:8px;border:1px solid #24384b;border-radius:6px;background:#0d161f}.check-name{font-weight:650}.check-detail{color:var(--muted);font-size:11px;overflow-wrap:anywhere}.indicator{width:9px;height:9px;border-radius:50%;margin-top:4px;background:var(--muted)}.indicator.good{background:var(--green);box-shadow:0 0 8px rgba(71,212,135,.5)}.indicator.bad{background:var(--red);box-shadow:0 0 8px rgba(255,109,118,.45)}
.split-list{display:grid;grid-template-columns:1fr 1fr;gap:10px}.health-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.health-item{background:#0d161f;border:1px solid #24384b;border-radius:6px;padding:9px}.health-item span{display:block;color:var(--muted);font-size:11px}.health-item strong{display:block;margin-top:3px;overflow-wrap:anywhere}
.review-row{border:1px solid #2a3e51;border-radius:7px;background:#0d161f;padding:10px;display:grid;grid-template-columns:1fr auto;gap:12px}.review-actions{display:flex;gap:6px;align-items:center}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.empty-state{color:var(--muted);padding:15px;text-align:center}
.operations-lower{margin-top:12px}.history-list{display:grid;gap:7px;max-height:360px;overflow:auto}.history-row{border:1px solid #26394c;border-radius:7px;background:#0d161f;padding:9px;display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center}.history-row button{padding:6px 9px}.history-title{font-size:12px;font-weight:700}.history-meta{font-size:11px;color:var(--muted);margin-top:3px;overflow-wrap:anywhere}.evidence-panel{margin-top:12px}.evidence-grid{display:grid;grid-template-columns:repeat(2,minmax(260px,1fr));gap:10px;margin-top:10px}.evidence-card{border:1px solid #26394c;border-radius:8px;background:#0d161f;padding:10px}.evidence-head{display:flex;justify-content:space-between;gap:8px;margin-bottom:8px}.evidence-timeline{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:8px;margin:10px 0}.evidence-timeline input[type="range"]{width:100%;accent-color:var(--cyan);padding:0;border:0;background:transparent}.timeline-edge,.timeline-time{font-size:10px;color:var(--muted);white-space:nowrap}.timeline-time{min-width:72px;text-align:right}.evidence-images{display:grid;grid-template-columns:repeat(2,1fr);gap:6px}.evidence-thumb{width:100%;aspect-ratio:16/9;object-fit:cover;background:#111b26;border:1px solid #233649;border-radius:5px}.evidence-caption{font-size:10px;color:var(--muted);margin-top:3px}.danger-text{color:var(--red)}
footer{max-width:1600px;margin:0 auto;padding:14px 22px 24px;display:flex;justify-content:space-between;color:#64788d;font-size:11px}
@media(max-width:1050px){.camera-grid,.kpi-grid{grid-template-columns:repeat(2,1fr)}.two-col{grid-template-columns:1fr}}
@media(max-width:650px){.topbar{position:static;padding:14px;align-items:flex-start;gap:10px}.badges{flex-wrap:wrap;justify-content:flex-end}.layout{padding:10px}.camera-grid,.kpi-grid,.evidence-grid{grid-template-columns:1fr}.form-row{align-items:stretch;flex-direction:column}.split-list,.health-grid{grid-template-columns:1fr}.review-row,.history-row,.alert-row{grid-template-columns:1fr}}"""

APP_JS = r""""use strict";

var state = {
  token: "",
  principal: null,
  currentSession: null,
  connected: false,
  refreshing: false,
  snapshots: new Map(),
  evidenceUrls: new Map(),
  evidenceRenderVersions: new Map(),
  selectedSessionId: null,
  socket: null,
  realtimeRetry: null,
  realtimeRefresh: null,
  readinessFailures: [],
  qualityIncidents: [],
  qualityIncidentKeys: new Set(),
  timer: null,
  tick: 0
};

function el(id) { return document.getElementById(id); }
function clearNode(target) { while (target.firstChild) target.removeChild(target.firstChild); }
function makeNode(tag, className, text) {
  var item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined && text !== null) item.textContent = String(text);
  return item;
}
function makeBadge(text, kind) { return makeNode("span", "badge " + (kind || "neutral"), text); }
function setText(id, value) { el(id).textContent = value === null || value === undefined ? "-" : String(value); }
function permissions() { return new Set((state.principal && state.principal.permissions) || []); }
function can(permission) { return !state.principal || permissions().has(permission); }
function kind(value) {
  if (["READY","ONLINE","PASS","COMPLETED"].indexOf(value) >= 0) return "good";
  if (["DEGRADED","RECONNECTING","DIRTY","PARTIAL","WARN"].indexOf(value) >= 0) return "warn";
  if (["FAIL","FAILED","ABORTED"].indexOf(value) >= 0) return "bad";
  return "neutral";
}
function truncate(value, size) {
  var text = value === null || value === undefined ? "" : String(value);
  var limit = size || 18;
  return text.length <= limit ? text : text.slice(0, limit) + "…";
}
function showNotice(message, isError) {
  var target = el("notice");
  target.textContent = message;
  target.className = "notice" + (isError ? " error" : "");
}
function authHeaders(withJson) {
  var headers = {};
  if (state.token) headers.Authorization = "Bearer " + state.token;
  if (withJson) headers["Content-Type"] = "application/json";
  return headers;
}
async function api(path, options) {
  var opts = options || {};
  var response = await fetch(path, {
    method: opts.method || "GET",
    body: opts.body,
    cache: "no-store",
    headers: Object.assign({}, authHeaders(Boolean(opts.body)), opts.headers || {})
  });
  if (response.status === 401) {
    disconnect("Token 无效或已过期.");
    throw new Error("unauthorized");
  }
  if (!response.ok) {
    var detail = String(response.status) + " " + response.statusText;
    try {
      var payload = await response.json();
      detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail || payload);
    } catch (_) {}
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}
async function optionalApi(path, permission) {
  if (!can(permission)) return null;
  try { return await api(path); }
  catch (error) {
    if (String(error.message) !== "unauthorized") console.warn(path, error);
    return null;
  }
}
function applyPermissions() {
  var connected = state.connected;
  el("startBtn").disabled = !connected || !can("session:start");
  el("stopBtn").disabled = !connected || !can("session:control");
  el("abortBtn").disabled = !connected || !can("session:control");
  el("refreshSnapshotsBtn").disabled = !connected || !can("camera:read");
  el("reconcileBtn").disabled = !connected || !can("persistence:repair");
}
async function connect() {
  state.token = el("tokenInput").value.trim();
  try {
    state.principal = await api("/api/v1/auth/me");
    state.connected = true;
    el("connectionBadge").textContent = "已连接";
    el("connectionBadge").className = "badge good";
    el("roleBadge").textContent = state.principal.role || "DEV";
    applyPermissions();
    await refreshAll(true);
    startPolling();
    startRealtime();
    showNotice("已连接: " + (state.principal.subject || "development"), false);
  } catch (error) {
    state.connected = false;
    showNotice("连接失败: " + error.message, true);
  }
}
function disconnect(message) {
  state.connected = false;
  state.principal = null;
  state.token = "";
  el("tokenInput").value = "";
  el("connectionBadge").textContent = "未连接";
  el("connectionBadge").className = "badge neutral";
  el("roleBadge").textContent = "-";
  stopPolling();
  stopRealtime();
  revokeSnapshots();
  applyPermissions();
  showNotice(message || "已断开.", true);
}
function startPolling() {
  stopPolling();
  state.timer = setInterval(function () {
    if (!document.hidden) refreshAll(false);
  }, 2000);
}
function stopPolling() {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
}
function stopRealtime() {
  if (state.realtimeRetry) clearTimeout(state.realtimeRetry);
  if (state.realtimeRefresh) clearTimeout(state.realtimeRefresh);
  state.realtimeRetry = null;
  state.realtimeRefresh = null;
  if (state.socket) {
    state.socket.onclose = null;
    state.socket.close();
  }
  state.socket = null;
}
async function startRealtime() {
  if (!state.connected || !can("realtime:read")) return;
  stopRealtime();
  try {
    var issued = await api("/api/v1/auth/realtime-ticket", {method:"POST"});
    var scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    var url = scheme + "//" + window.location.host +
      "/api/v1/realtime?ticket=" + encodeURIComponent(issued.ticket);
    var socket = new WebSocket(url);
    state.socket = socket;
    socket.onopen = function () {
      el("connectionBadge").textContent = "已连接 · 实时";
    };
    socket.onmessage = function (event) {
      try {
        var envelope = JSON.parse(event.data);
        if (envelope.type === "runtime.update") {
          captureRealtimeIncidents(envelope.payload || {});
          scheduleRealtimeRefresh();
        }
      } catch (_) {}
    };
    socket.onclose = function () {
      if (!state.connected) return;
      el("connectionBadge").textContent = "已连接 · 重连实时";
      state.realtimeRetry = setTimeout(startRealtime, 1500);
    };
    socket.onerror = function () {
      socket.close();
    };
  } catch (error) {
    if (state.connected) {
      state.realtimeRetry = setTimeout(startRealtime, 2500);
    }
  }
}
function scheduleRealtimeRefresh() {
  if (state.realtimeRefresh) return;
  state.realtimeRefresh = setTimeout(async function () {
    state.realtimeRefresh = null;
    var results = await Promise.all([
      optionalApi("/api/v1/sessions/current/evaluation", "session:read"),
      optionalApi("/api/v1/runtime/health", "runtime:read"),
      optionalApi("/api/v1/sessions/current", "session:read")
    ]);
    renderEvaluation(results[0]);
    if (results[1]) renderHealth(results[1]);
    renderSession(results[2]);
  }, 80);
}
async function refreshAll(forceSnapshots) {
  if (!state.connected || state.refreshing) return;
  state.refreshing = true;
  state.tick += 1;
  try {
    var results = await Promise.all([
      optionalApi("/api/v1/sessions/readiness", "runtime:read"),
      optionalApi("/api/v1/runtime/health", "runtime:read"),
      optionalApi("/api/v1/sessions/current", "session:read"),
      optionalApi("/api/v1/sessions/current/evaluation", "session:read"),
      optionalApi("/api/v1/runtime/version", "runtime:read"),
      optionalApi("/api/v1/cameras", "camera:read"),
      optionalApi("/api/v1/runtime/persistence", "persistence:read"),
      optionalApi("/api/v1/reviews/pending?limit=50", "violation:review"),
      optionalApi("/api/v1/sessions?limit=30", "session:read"),
      optionalApi(
        "/api/v1/runtime/persistence/incomplete-sessions",
        "persistence:read"
      )
    ]);
    if (results[0]) renderReadiness(results[0]);
    if (results[1]) renderHealth(results[1]);
    renderSession(results[2]);
    renderEvaluation(results[3]);
    if (results[4]) renderVersion(results[4]);
    if (results[5]) {
      renderCameras(results[5]);
      if (forceSnapshots || state.tick % 3 === 0) refreshSnapshots();
    }
    if (results[6]) renderPersistence(results[6]);
    renderReviews(results[7] || []);
    renderHistory(results[8] || []);
    renderIncomplete(results[9] || []);
    setText("lastRefresh", "最后刷新 " + new Date().toLocaleTimeString());
  } finally {
    state.refreshing = false;
  }
}
function renderReadiness(payload) {
  setText("readyKpi", payload.ready ? "READY" : "NOT READY");
  el("readyKpi").style.color = payload.ready ? "var(--green)" : "var(--red)";
  var failed = (payload.checks || []).filter(function (item) { return !item.passed; }).length;
  setText("readyDetail", String(failed) + " 项未通过");
  state.readinessFailures = (payload.checks || []).filter(function (item) {
    return !item.passed;
  });
  renderAlerts();
  var target = el("readinessList");
  clearNode(target);
  target.className = "check-list";
  (payload.checks || []).forEach(function (check) {
    var row = makeNode("div", "check-row");
    row.appendChild(makeNode("span", "indicator " + (check.passed ? "good" : "bad")));
    var body = makeNode("div");
    body.appendChild(makeNode("div", "check-name", check.name));
    body.appendChild(makeNode("div", "check-detail", check.detail));
    row.appendChild(body);
    target.appendChild(row);
  });
  if (!(payload.checks || []).length) {
    target.className = "check-list empty-state";
    target.textContent = "无 Readiness 检查项.";
  }
}
function renderHealth(payload) {
  var runtime = payload.runtime || {};
  var sync = payload.sync || null;
  setText("syncKpi", sync ? Number(sync.skew_p99_ms || 0).toFixed(1) + " ms" : "-");
  if (sync) {
    var ratio = Number(sync.miss_total || 0) / Math.max(Number(sync.reference_frames_total || 1), 1) * 100;
    setText("syncDetail", "miss " + ratio.toFixed(2) + "%");
  } else {
    setText("syncDetail", "无同步数据");
  }
  var items = [
    ["Processing P99", Number(runtime.processing_latency_p99_ms || 0).toFixed(1) + " ms"],
    ["Queue", String(runtime.queue_depth || 0) + " / " + String(runtime.queue_capacity || 0)],
    ["RSS", Number(runtime.current_rss_mb || 0).toFixed(0) + " MB"],
    ["GPU Reserved", Number(runtime.gpu_reserved_mb || 0).toFixed(0) + " MB"],
    ["Threads", runtime.current_thread_count === null || runtime.current_thread_count === undefined ? "-" : runtime.current_thread_count],
    ["Open FDs", runtime.current_open_fds === null || runtime.current_open_fds === undefined ? "-" : runtime.current_open_fds],
    ["Audit", payload.audit ? payload.audit.status : "-"],
    ["Evidence", payload.evidence ? String(payload.evidence.errors_total || 0) + " errors / " + String(payload.evidence.dropped_total || 0) + " drops" : "-"]
  ];
  var target = el("runtimeHealth");
  clearNode(target);
  target.className = "health-grid";
  items.forEach(function (pair) {
    var box = makeNode("div", "health-item");
    box.appendChild(makeNode("span", "", pair[0]));
    box.appendChild(makeNode("strong", "", pair[1]));
    target.appendChild(box);
  });
}
function renderSession(current) {
  state.currentSession = current;
  if (!current) {
    setText("sessionKpi", "IDLE");
    setText("sessionDetail", "无活动 Session");
    el("currentSession").textContent = "无活动 Session.";
    return;
  }
  setText("sessionKpi", current.status || "RUNNING");
  setText("sessionDetail", truncate(current.session_id, 20));
  el("currentSession").textContent =
    "Session: " + current.session_id + "\nOperator: " + (current.operator_id || "-") +
    "\nOperation: " + current.operation + "\nStarted: " + current.started_at +
    "\nTrace: " + (current.trace_id || "-");
}
function renderEvaluation(evaluation) {
  if (!evaluation) {
    setText("scoreKpi", "-");
    setText("passDetail", "暂无评估");
    el("evaluationSummary").textContent = "暂无评估.";
    clearNode(el("stepsList"));
    clearNode(el("violationsList"));
    return;
  }
  setText("scoreKpi", Number(evaluation.score || 0).toFixed(1));
  setText("passDetail", evaluation.passed ? "PASS" : "FAIL");
  el("passDetail").style.color = evaluation.passed ? "var(--green)" : "var(--red)";
  el("evaluationSummary").textContent =
    "Result: " + (evaluation.passed ? "PASS" : "FAIL") +
    " | Score: " + evaluation.score +
    "\nViolations: " + String((evaluation.violations || []).length);

  var steps = el("stepsList");
  clearNode(steps);
  (evaluation.steps || []).forEach(function (step) {
    var row = makeNode("div", "compact-row");
    row.appendChild(makeBadge(step.state || "-", kind(step.state)));
    row.appendChild(makeNode("div", "", (step.code || "-") + "  " + (step.event_id || "")));
    steps.appendChild(row);
  });

  var violations = el("violationsList");
  clearNode(violations);
  (evaluation.violations || []).forEach(function (item) {
    var row = makeNode("div", "compact-row");
    row.appendChild(makeBadge(item.severity || "?", item.severity === "CRITICAL" ? "bad" : "warn"));
    row.appendChild(makeNode("div", "", (item.rule_id || item.type || "-") + " · " + (item.message || "")));
    violations.appendChild(row);
  });
}
function renderCameras(cameras) {
  var target = el("cameraGrid");
  clearNode(target);
  target.className = "camera-grid";
  cameras.forEach(function (camera) {
    var card = makeNode("article", "camera-card");
    var head = makeNode("div", "camera-head");
    head.appendChild(makeNode("div", "camera-title", camera.position + " · " + camera.camera_id));
    head.appendChild(makeBadge(camera.state, kind(camera.state)));
    card.appendChild(head);

    var image = makeNode("img", "camera-image");
    image.alt = camera.position + " camera";
    image.dataset.cameraId = camera.camera_id;
    card.appendChild(image);

    var meta =
      "FPS " + Number(camera.fps || 0).toFixed(1) +
      "\nReconnect " + String(camera.reconnect_total || 0) +
      "\n" + (camera.capture_backend || "-") + " / " + (camera.timestamp_source || "-");
    card.appendChild(makeNode("div", "camera-meta mono", meta));
    target.appendChild(card);
  });
}
async function refreshSnapshots() {
  if (!state.connected || !can("camera:read")) return;
  var images = Array.from(document.querySelectorAll(".camera-image[data-camera-id]"));
  await Promise.all(images.map(async function (image) {
    var cameraId = image.dataset.cameraId;
    try {
      var response = await fetch(
        "/api/v1/cameras/" + encodeURIComponent(cameraId) + "/snapshot.jpg?quality=70",
        {headers: authHeaders(false), cache: "no-store"}
      );
      if (!response.ok) return;
      var blob = await response.blob();
      var url = URL.createObjectURL(blob);
      var old = state.snapshots.get(cameraId);
      if (old) URL.revokeObjectURL(old);
      state.snapshots.set(cameraId, url);
      image.src = url;
    } catch (_) {}
  }));
}
function revokeSnapshots() {
  state.snapshots.forEach(function (url) { URL.revokeObjectURL(url); });
  state.snapshots.clear();
}
function renderVersion(payload) {
  setText("versionBadge", "v" + (payload.application_version || "?"));
  var runtime = payload.runtime_fingerprint || {};
  el("releaseIdentity").textContent =
    "Version: " + (payload.application_version || "-") +
    "\nGit: " + (payload.git_sha || "-") +
    "\nImage: " + (payload.image_digest || "-") +
    "\nModel Release: " + (runtime.model_release_id || "-") +
    "\nRelease Fingerprint: " + (payload.release_fingerprint || "-");
}
function renderPersistence(payload) {
  var recon = payload.reconciliation || {};
  el("persistenceHealth").textContent =
    "Configured: " + String(payload.configured) +
    "\nConnectivity: " + (payload.status || "-") +
    "\nWrite errors: " + String(payload.write_errors_total === undefined ? "-" : payload.write_errors_total) +
    "\nRead errors: " + String(payload.read_errors_total === undefined ? "-" : payload.read_errors_total) +
    "\nReconciliation: " + (recon.status || "-") +
    "\nRepaired: " + String(recon.repaired_count === undefined ? "-" : recon.repaired_count) +
    " / Failed: " + String(recon.failed_count === undefined ? "-" : recon.failed_count);
}
function renderReviews(reviews) {
  var target = el("reviewsList");
  clearNode(target);
  setText("reviewCount", reviews.length);
  if (!reviews.length) {
    target.className = "review-list empty-state";
    target.textContent = "暂无待复核数据.";
    return;
  }
  target.className = "review-list";
  reviews.forEach(function (review) {
    var row = makeNode("article", "review-row");
    var body = makeNode("div");
    body.appendChild(makeNode("div", "camera-title",
      (review.severity || "-") + " · " + (review.rule_id || "-") + " · " + (review.step_code || "-")));
    body.appendChild(makeNode("div", "check-detail mono",
      "Session " + review.session_id + "\nEvent " + review.event_id +
      "\nEvidence " + String((review.evidence || []).length)));
    row.appendChild(body);

    var actions = makeNode("div", "review-actions");
    var confirm = makeNode("button", "success", "确认违规");
    var dismiss = makeNode("button", "secondary", "误报");
    confirm.addEventListener("click", function () { reviewViolation(review, "CONFIRMED"); });
    dismiss.addEventListener("click", function () { reviewViolation(review, "DISMISSED"); });
    actions.appendChild(confirm);
    actions.appendChild(dismiss);
    row.appendChild(actions);
    target.appendChild(row);
  });
}
function captureRealtimeIncidents(payload) {
  (payload.rule_updates || []).forEach(function (update) {
    (update.new_violations || []).forEach(function (violation) {
      var severe = violation.type === "SYSTEM_QUALITY" ||
        violation.severity === "CRITICAL" ||
        violation.severity === "MAJOR";
      if (!severe) return;
      var key =
        String(violation.rule_id || violation.type || "unknown") +
        "|" + String(violation.event_id || "no-event");
      if (state.qualityIncidentKeys.has(key)) return;
      state.qualityIncidentKeys.add(key);
      state.qualityIncidents.unshift({
        key: key,
        ruleId: violation.rule_id || violation.type || "QUALITY",
        severity: violation.severity || "CRITICAL",
        type: violation.type || "QUALITY",
        eventId: violation.event_id || "-",
        message: violation.message || "Runtime quality incident",
        timestamp: new Date().toLocaleTimeString()
      });
      if (state.qualityIncidents.length > 100) {
        var removed = state.qualityIncidents.pop();
        if (removed) state.qualityIncidentKeys.delete(removed.key);
      }
    });
  });
  renderAlerts();
}
function renderAlerts() {
  var target = el("alertsList");
  clearNode(target);
  var blockers = state.readinessFailures || [];
  var incidents = state.qualityIncidents || [];
  setText("alertCount", blockers.length + incidents.length);

  blockers.forEach(function (check) {
    var row = makeNode("div", "alert-row blocker");
    row.appendChild(makeBadge("START BLOCKER", "warn"));
    var body = makeNode("div");
    body.appendChild(makeNode("div", "alert-message", check.name));
    body.appendChild(makeNode("div", "alert-detail", check.detail || ""));
    row.appendChild(body);
    row.appendChild(makeNode("span", "alert-time", "CURRENT"));
    target.appendChild(row);
  });

  incidents.forEach(function (incident) {
    var row = makeNode("div", "alert-row incident");
    row.appendChild(makeBadge(
      "QUALITY INCIDENT",
      incident.severity === "CRITICAL" ? "bad" : "warn"
    ));
    var body = makeNode("div");
    body.appendChild(makeNode(
      "div",
      "alert-message",
      incident.ruleId + " · " + incident.severity
    ));
    body.appendChild(makeNode(
      "div",
      "alert-detail",
      incident.message + " · Event " + incident.eventId
    ));
    row.appendChild(body);
    row.appendChild(makeNode("span", "alert-time", incident.timestamp));
    target.appendChild(row);
  });

  if (!blockers.length && !incidents.length) {
    target.className = "alert-list empty-state";
    target.textContent = "当前没有告警.";
  } else {
    target.className = "alert-list";
  }
}
function clearLocalAlerts() {
  state.qualityIncidents = [];
  state.qualityIncidentKeys.clear();
  renderAlerts();
}

function renderHistory(sessions) {
  var target = el("historyList");
  clearNode(target);
  setText("historyCount", sessions.length);
  if (!sessions.length) {
    target.className = "history-list empty-state";
    target.textContent = "暂无历史 Session.";
    return;
  }
  target.className = "history-list";
  sessions.forEach(function (session) {
    var row = makeNode("div", "history-row");
    var body = makeNode("div");
    body.appendChild(makeNode(
      "div",
      "history-title",
      (session.status || "-") + " · " + truncate(session.session_id, 28)
    ));
    var passed = session.passed === true ? "PASS" :
      (session.passed === false ? "FAIL" : "-");
    body.appendChild(makeNode(
      "div",
      "history-meta mono",
      "Operator " + (session.operator_id || "-") +
      " · Score " + (session.final_score === null || session.final_score === undefined ? "-" : session.final_score) +
      " · " + passed +
      "\nStarted " + (session.started_at || "-")
    ));
    row.appendChild(body);
    var open = makeNode("button", "secondary", "查看");
    open.addEventListener("click", function () {
      openHistoricalSession(session.session_id);
    });
    row.appendChild(open);
    target.appendChild(row);
  });
}
function renderIncomplete(items) {
  var target = el("incompleteList");
  clearNode(target);
  setText("incompleteCount", items.length);
  if (!items.length) {
    target.className = "history-list empty-state";
    target.textContent = "暂无残缺 Session.";
    return;
  }
  target.className = "history-list";
  items.forEach(function (item) {
    var row = makeNode("div", "history-row");
    var body = makeNode("div");
    body.appendChild(makeNode(
      "div",
      "history-title danger-text",
      "INCOMPLETE · " + truncate(item.session_id, 28)
    ));
    body.appendChild(makeNode(
      "div",
      "history-meta mono",
      "Operation " + item.operation +
      " · Updates " + item.update_count +
      "\nStarted " + item.started_at
    ));
    row.appendChild(body);
    var recover = makeNode("button", "danger", "恢复为 ABORTED");
    recover.disabled = !can("persistence:repair");
    recover.addEventListener("click", function () {
      recoverIncomplete(item.session_id);
    });
    row.appendChild(recover);
    target.appendChild(row);
  });
}
async function openHistoricalSession(sessionId) {
  state.selectedSessionId = sessionId;
  setText("selectedSessionLabel", "Session " + sessionId);
  try {
    var detail = await api(
      "/api/v1/sessions/" + encodeURIComponent(sessionId)
    );
    renderHistoricalDetail(detail);
    await loadSessionEvidence(sessionId);
  } catch (error) {
    showNotice("加载 Session 失败: " + error.message, true);
  }
}
function renderHistoricalDetail(detail) {
  var session = detail.session || {};
  var actions = detail.actions || [];
  var violations = detail.violations || [];
  var steps = detail.steps || [];
  el("historicalDetail").textContent =
    "Status: " + (session.status || "-") +
    " · Score: " + (session.final_score === null || session.final_score === undefined ? "-" : session.final_score) +
    " · Result: " + (session.passed === true ? "PASS" : (session.passed === false ? "FAIL" : "-")) +
    "\nActions: " + actions.length +
    " · Steps: " + steps.length +
    " · Violations: " + violations.length +
    "\nRelease: " + ((session.metadata_json || {}).release_fingerprint || "-");
}
async function loadSessionEvidence(sessionId) {
  revokeEvidenceUrls();
  var target = el("evidenceGrid");
  clearNode(target);
  if (!can("evidence:read")) {
    target.className = "evidence-grid empty-state";
    target.textContent = "当前角色没有 Evidence 读取权限.";
    return;
  }
  try {
    var manifests = await api(
      "/api/v1/sessions/" + encodeURIComponent(sessionId) + "/evidence"
    );
    renderEvidence(manifests || []);
  } catch (error) {
    target.className = "evidence-grid empty-state";
    target.textContent = "Evidence 加载失败: " + error.message;
  }
}
function renderEvidence(manifests) {
  var target = el("evidenceGrid");
  clearNode(target);
  if (!manifests.length) {
    target.className = "evidence-grid empty-state";
    target.textContent = "该 Session 暂无 Evidence.";
    return;
  }
  target.className = "evidence-grid";
  manifests.forEach(function (manifest) {
    var card = makeNode("article", "evidence-card");
    var head = makeNode("div", "evidence-head");
    var title = makeNode(
      "div",
      "history-title",
      (manifest.status || "-") + " · " + (manifest.rule_id || "-")
    );
    head.appendChild(title);
    head.appendChild(makeBadge(
      manifest.review_status || "UNREVIEWED",
      manifest.review_status === "CONFIRMED" ? "bad" :
        (manifest.review_status === "DISMISSED" ? "good" : "warn")
    ));
    card.appendChild(head);
    card.appendChild(makeNode(
      "div",
      "history-meta mono",
      "Evidence " + manifest.evidence_id +
      "\nStep " + manifest.step_code +
      " · Event " + manifest.event_id
    ));

    var timeline = makeNode("div", "evidence-timeline");
    timeline.appendChild(makeNode("span", "timeline-edge", "PRE"));
    var slider = makeNode("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = "100";
    slider.step = "1";
    slider.value = "50";
    slider.setAttribute(
      "aria-label",
      "Evidence timeline for " + manifest.evidence_id
    );
    timeline.appendChild(slider);
    var timeLabel = makeNode("span", "timeline-time mono", "-");
    timeline.appendChild(timeLabel);
    card.appendChild(timeline);

    var images = makeNode("div", "evidence-images");
    card.appendChild(images);
    target.appendChild(card);

    var timer = null;
    slider.addEventListener("input", function () {
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () {
        renderEvidenceMoment(
          manifest,
          Number(slider.value),
          images,
          timeLabel
        );
      }, 70);
    });
    renderEvidenceMoment(manifest, 50, images, timeLabel);
  });
}
function closestEvidenceImages(manifest, targetMs) {
  var grouped = new Map();
  (manifest.images || []).forEach(function (image) {
    if (!grouped.has(image.camera_id)) grouped.set(image.camera_id, []);
    grouped.get(image.camera_id).push(image);
  });
  var selected = [];
  grouped.forEach(function (images, cameraId) {
    var closest = null;
    var distance = Number.POSITIVE_INFINITY;
    images.forEach(function (image) {
      var current = Math.abs(Number(image.timestamp_ms) - targetMs);
      if (current < distance) {
        distance = current;
        closest = image;
      }
    });
    if (closest) {
      selected.push({
        cameraId: cameraId,
        image: closest
      });
    }
  });
  selected.sort(function (left, right) {
    return left.cameraId.localeCompare(right.cameraId);
  });
  return selected;
}
async function renderEvidenceMoment(
  manifest,
  percentage,
  target,
  timeLabel
) {
  var start = Number(manifest.normalized_start_ms || 0);
  var end = Number(manifest.normalized_end_ms || start);
  var targetMs = start + (end - start) * percentage / 100;
  timeLabel.textContent =
    Math.round(targetMs) + " ms · " + String(Math.round(percentage)) + "%";

  var version = (state.evidenceRenderVersions.get(manifest.evidence_id) || 0) + 1;
  state.evidenceRenderVersions.set(manifest.evidence_id, version);
  target.className = "evidence-images empty-state";
  target.textContent = "加载 " + Math.round(targetMs) + " ms ...";

  var selections = closestEvidenceImages(manifest, targetMs);
  var results = await Promise.all(
    selections.map(async function (selection) {
      var item = await fetchEvidenceImage(
        manifest,
        selection.image,
        selection.cameraId
      );
      return {
        cameraId: selection.cameraId,
        image: selection.image,
        blob: item
      };
    })
  );

  if (
    state.evidenceRenderVersions.get(manifest.evidence_id) !== version
  ) {
    return;
  }

  clearNode(target);
  target.className = "evidence-images";
  results.forEach(function (result) {
    if (!result.blob) return;
    var key = manifest.evidence_id + ":" + result.cameraId;
    var old = state.evidenceUrls.get(key);
    if (old) URL.revokeObjectURL(old);
    var url = URL.createObjectURL(result.blob);
    state.evidenceUrls.set(key, url);

    var wrapper = makeNode("div");
    var img = makeNode("img", "evidence-thumb");
    img.src = url;
    img.alt = result.cameraId + " evidence";
    wrapper.appendChild(img);
    wrapper.appendChild(makeNode(
      "div",
      "evidence-caption mono",
      result.cameraId + " · " +
      Math.round(result.image.timestamp_ms) + " ms"
    ));
    target.appendChild(wrapper);
  });
  if (!target.childNodes.length) {
    target.className = "evidence-images empty-state";
    target.textContent = "该时间点无可读取证据帧.";
  }
}
async function fetchEvidenceImage(
  manifest,
  image,
  cameraId
) {
  try {
    var path =
      "/api/v1/sessions/" + encodeURIComponent(manifest.session_id) +
      "/evidence/" + encodeURIComponent(manifest.evidence_id) +
      "/files/" + encodeURIComponent(cameraId) +
      "/" + encodeURIComponent(image.filename);
    var response = await fetch(path, {
      headers: authHeaders(false),
      cache: "no-store"
    });
    if (!response.ok) return null;
    return response.blob();
  } catch (_) {
    return null;
  }
}
function revokeEvidenceUrls() {
  state.evidenceUrls.forEach(function (url) {
    URL.revokeObjectURL(url);
  });
  state.evidenceUrls.clear();
  state.evidenceRenderVersions.clear();
}
async function recoverIncomplete(sessionId) {
  var reason = window.prompt(
    "请输入恢复原因. 该 Session 将被固定恢复为 ABORTED:",
    "Edge host/process unclean termination"
  );
  if (!reason || !reason.trim()) return;
  if (!window.confirm(
    "确认将 " + sessionId + " 恢复为 ABORTED 并追加 SYSTEM-QUALITY-RECOVERY?"
  )) return;
  try {
    await api(
      "/api/v1/runtime/persistence/incomplete-sessions/" +
      encodeURIComponent(sessionId) + "/recover",
      {
        method: "POST",
        body: JSON.stringify({reason: reason.trim()})
      }
    );
    showNotice("Crash Recovery 完成: " + sessionId, false);
    await refreshAll(false);
  } catch (error) {
    showNotice("Crash Recovery 失败: " + error.message, true);
  }
}

async function startSession() {
  var body = {};
  var operatorId = el("operatorInput").value.trim();
  var sessionId = el("sessionIdInput").value.trim();
  if (operatorId) body.operator_id = operatorId;
  if (sessionId) body.session_id = sessionId;
  try {
    var result = await api("/api/v1/sessions", {method:"POST", body:JSON.stringify(body)});
    showNotice("Session 已启动: " + result.session_id, false);
    await refreshAll(true);
  } catch (error) {
    showNotice("启动失败: " + error.message, true);
  }
}
async function finishSession(action) {
  if (!state.currentSession || !state.currentSession.session_id) {
    showNotice("当前没有活动 Session.", true);
    return;
  }
  if (action === "abort" && !window.confirm("确认中止当前 Session?")) return;
  try {
    await api(
      "/api/v1/sessions/" + encodeURIComponent(state.currentSession.session_id) + "/" + action,
      {method:"POST"}
    );
    showNotice(action === "stop" ? "Session 已正常结束." : "Session 已中止.", false);
    await refreshAll(true);
  } catch (error) {
    showNotice("操作失败: " + error.message, true);
  }
}
async function reconcile() {
  try {
    var result = await api("/api/v1/runtime/persistence/reconcile", {method:"POST"});
    showNotice(
      "对账完成: repaired " + result.repaired_count + ", failed " + result.failed_count,
      false
    );
    await refreshAll(false);
  } catch (error) {
    showNotice("对账失败: " + error.message, true);
  }
}
async function reviewViolation(review, decision) {
  try {
    await api(
      "/api/v1/sessions/" + encodeURIComponent(review.session_id) +
      "/violations/" + encodeURIComponent(review.id) + "/review",
      {
        method:"POST",
        body:JSON.stringify({
          decision:decision,
          comment:"Reviewed in Video Pose Edge Console"
        })
      }
    );
    showNotice(decision === "CONFIRMED" ? "已确认违规." : "已标记误报.", false);
    await refreshAll(false);
  } catch (error) {
    showNotice("复核失败: " + error.message, true);
  }
}
window.addEventListener("DOMContentLoaded", function () {
  el("connectBtn").addEventListener("click", connect);
  el("disconnectBtn").addEventListener("click", function () { disconnect("已断开."); });
  el("startBtn").addEventListener("click", startSession);
  el("stopBtn").addEventListener("click", function () { finishSession("stop"); });
  el("abortBtn").addEventListener("click", function () { finishSession("abort"); });
  el("refreshSnapshotsBtn").addEventListener("click", refreshSnapshots);
  el("reconcileBtn").addEventListener("click", reconcile);
  el("clearAlertsBtn").addEventListener("click", clearLocalAlerts);
  el("reloadEvidenceBtn").addEventListener("click", function () {
    if (state.selectedSessionId) {
      loadSessionEvidence(state.selectedSessionId);
    }
  });
  el("tokenInput").addEventListener("keydown", function (event) {
    if (event.key === "Enter") connect();
  });
  applyPermissions();
});
window.addEventListener("beforeunload", function () {
  stopPolling();
  stopRealtime();
  revokeSnapshots();
  revokeEvidenceUrls();
});"""

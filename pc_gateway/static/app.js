// PC 网关前端单页应用入口：负责路由渲染、接口调用、WebSocket 实时数据和训练交互。
﻿// 前端可访问的页面路由，后端会统一返回同一个 index.html。
const ROUTES = ["/login", "/dashboard", "/training", "/history", "/debug"];
const TOKEN_KEY = "smartFitnessAccessToken";
const TOKEN_EXP_KEY = "smartFitnessAccessTokenExpiry";
const SENSOR_HISTORY_LIMIT = 160;
const USER_AUTO_LABEL = "user_auto_training";
const NON_TRAINING_LABELS = new Set([USER_AUTO_LABEL]);

// 模型内部标签到中文界面文案的映射。
const LABEL_TEXT = {
  idle: "静止",
  squat_standard: "深蹲-标准",
  squat_wrong: "深蹲-错误",
  bench_standard: "卧推-标准",
  bench_wrong: "卧推-错误",
  user_auto_training: "自动识别训练",
};

// 把用户输入的中文动作名归一化到训练标签。
const LABEL_ALIASES = {
  "静止": "idle",
  "站立": "idle",
  "待机": "idle",
  "深蹲": "squat_standard",
  "标准深蹲": "squat_standard",
  "深蹲标准": "squat_standard",
  "深蹲_标准": "squat_standard",
  "深蹲错误": "squat_wrong",
  "错误深蹲": "squat_wrong",
  "深蹲_错误": "squat_wrong",
  "深蹲纠错": "squat_wrong",
  "卧推": "bench_standard",
  "标准卧推": "bench_standard",
  "卧推标准": "bench_standard",
  "卧推_标准": "bench_standard",
  "卧推错误": "bench_wrong",
  "错误卧推": "bench_wrong",
  "卧推_错误": "bench_wrong",
  "卧推纠错": "bench_wrong",
};

const TRAINING_ACTION_TEXT = {
  idle: "站立校准",
  squat_standard: "深蹲训练",
  squat_wrong: "深蹲纠错训练",
  bench_standard: "卧推训练",
  bench_wrong: "卧推纠错训练",
  user_auto_training: "自动识别训练",
};

// 不同动作的佩戴与采集提示，训练页会按实时识别结果切换。
const TRAINING_GUIDES = {
  user_auto_training: "开始前请先确认 IMU 与柔性传感器固定牢靠。训练时系统会根据动作识别结果，自动切换深蹲或卧推的佩戴提示。",
  idle: "站立准备：保持自然站立 1 到 2 秒，IMU 与柔性传感器保持固定不晃动，用于建立本次训练的稳定基线。",
  squat_standard: "深蹲佩戴：建议固定在左腿膝关节外侧附近或护膝外侧，板面朝外且方向固定；柔性传感器跨过左膝前外侧，弯曲方向跟随膝关节。整批深蹲数据保持同一位置，采集前自然站立 1 到 2 秒。",
  squat_wrong: "深蹲纠错佩戴：沿用标准深蹲佩戴位置，不要换腿或换方向。第一版错误样本建议只采一种错误，例如膝盖明显内扣，动作节奏尽量与标准样本一致。",
  bench_standard: "卧推佩戴：建议选择同一侧发力手臂，IMU 固定在肘外侧附近或前臂近肘外侧，板面朝外且方向固定；柔性传感器跨过肘关节外侧或后外侧，随屈肘伸肘自然弯曲，避免贴在肘窝内侧。",
  bench_wrong: "卧推纠错佩戴：沿用标准卧推佩戴位置，不要左右手臂切换。第一版错误样本建议只采一种错误，例如肘部外展过大，保持重量和节奏尽量一致。",
};

const ROUTE_SUBTITLE = {
  "/login": "账号登录与注册",
  "/dashboard": "训练概览与进步反馈",
  "/training": "动作识别与实时纠正",
  "/history": "历史报告与趋势分析",
  "/debug": "开发者工具与模型维护",
};

// 全局前端状态：缓存认证、设备、实时数据、训练任务和页面列表。
const state = {
  auth: {
    token: localStorage.getItem(TOKEN_KEY),
    tokenExpiry: localStorage.getItem(TOKEN_EXP_KEY),
    user: null,
    mode: "register",
  },
  labels: [],
  labelCounts: {},
  devices: [],
  status: null,
  inference: null,
  evaluation: null,
  advanced: null,
  report: null,
  userSummary: null,
  dbStatus: null,
  lists: { sessions: [], evaluations: [], models: [], reports: [] },
  recordings: [],
  trainingJob: null,
  latestPacket: null,
  packetKey: "",
  sensorHistory: [],
  socket: null,
  selectedLabels: null,
  debugRecordViewType: "list",
  debugRecordActionType: "view",
  debugAutoReload: null,
  repCounter: { count: 0, family: "idle", phases: [] },
};

// 常用 DOM 查询快捷函数。
const $ = (id) => document.getElementById(id);

// 读取当前浏览器路径，非法路径回退到登录页。
function currentRoute() {
  return ROUTES.includes(window.location.pathname) ? window.location.pathname : "/login";
}

// 安全写入文本内容，目标元素不存在时静默跳过。
function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value ?? "";
}

function setHtml(id, value) {
  const el = $(id);
  if (el) el.innerHTML = value ?? "";
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

// 规范化动作标签并套用中文别名。
function canonicalLabel(label) {
  const normalized = String(label || "").trim().toLowerCase().replace(/[\s-]+/g, "_").replace(/_+/g, "_").replace(/^_+|_+$/g, "");
  const compact = normalized.replaceAll("_", "");
  return LABEL_ALIASES[normalized] || LABEL_ALIASES[compact] || normalized;
}

function canonicalLabels(labels) {
  return Array.from(new Set(safeArray(labels).map(canonicalLabel).filter(Boolean)));
}

function canonicalLabelCounts(counts) {
  const merged = {};
  Object.entries(counts || {}).forEach(([label, count]) => {
    const canonical = canonicalLabel(label);
    if (!canonical) return;
    merged[canonical] = Number(merged[canonical] || 0) + Number(count || 0);
  });
  Object.keys(LABEL_TEXT).forEach((label) => {
    if (merged[label] === undefined) merged[label] = Number(counts?.[label] || 0);
  });
  return merged;
}

function trainableLabels() {
  return canonicalLabels(state.labels).filter((label) => !NON_TRAINING_LABELS.has(label) && Number(state.labelCounts?.[label] || 0) > 0);
}

function captureLabels() {
  return canonicalLabels([...Object.keys(LABEL_TEXT), ...safeArray(state.labels)])
    .filter((label) => !NON_TRAINING_LABELS.has(label))
    .sort();
}

// 在标签列表变化后保留仍然可训练的勾选项。
function syncSelectedLabels({ selectAllOnFirstLoad = false } = {}) {
  const validLabels = safeArray(state.labels);
  const validSet = new Set(validLabels);
  const selectable = trainableLabels();
  const selectableSet = new Set(selectable);
  if (!Array.isArray(state.selectedLabels)) {
    state.selectedLabels = selectAllOnFirstLoad ? [...selectable] : [];
    return;
  }
  state.selectedLabels = state.selectedLabels.filter((label) => validSet.has(label) && selectableSet.has(label));
}

function labelText(label) {
  const canonical = canonicalLabel(label);
  return LABEL_TEXT[canonical] || String(label || "-");
}

function trainingActionText(label) {
  return TRAINING_ACTION_TEXT[label] || labelText(label);
}

function trainingWearGuide(label) {
  const family = actionFamily(label);
  if (TRAINING_GUIDES[label]) return TRAINING_GUIDES[label];
  if (family === "squat") return TRAINING_GUIDES.squat_standard;
  if (family === "bench") return TRAINING_GUIDES.bench_standard;
  return TRAINING_GUIDES[label] || "该动作的佩戴方案还未完成标定。建议先保持 IMU 与柔性传感器固定牢靠、方向一致，完成多组测试后再确定标准贴法。";
}

function refreshTrainingActionGuide() {
  const liveLabel = state.inference?.latestPrediction?.label || state.evaluation?.actionLabel || USER_AUTO_LABEL;
  const guideLabel = liveLabel === "idle" && !state.status?.recording ? USER_AUTO_LABEL : liveLabel;
  setText("trainingLabelBadge", liveLabel === USER_AUTO_LABEL ? "等待自动识别" : labelText(liveLabel));
  setText("trainingWearGuide", trainingWearGuide(guideLabel));
}

function riskText(risk) {
  if (risk === "low") return "低";
  if (risk === "medium") return "中";
  if (risk === "high") return "高";
  return "待评估";
}

// 把后端时间字符串格式化为中文本地时间。
function formatDateTime(value) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString("zh-CN", { hour12: false });
}

function formatMinutes(value) {
  const minutes = Number(value || 0);
  if (!Number.isFinite(minutes)) return "0 分钟";
  return `${minutes >= 10 ? minutes.toFixed(0) : minutes.toFixed(1)} 分钟`;
}

// 根据训练时长和次数估算热量，用于首页展示。
function estimateCalories(minutes, reps = 0) {
  return Math.max(0, Math.round(Number(minutes || 0) * 5.5 + Number(reps || 0) * 0.35));
}

function isLoggedIn() {
  return Boolean(state.auth.token && state.auth.user);
}

// 通过 History API 切换页面并重新渲染。
function navigate(route, replace = false) {
  const target = ROUTES.includes(route) ? route : "/login";
  window.history[replace ? "replaceState" : "pushState"]({}, "", target);
  renderAll();
}

// 认证头生成器：登录后把 token 放进 Authorization: Bearer 中。
// 后端 /api/auth/me、/api/report/user-summary 等需要身份的接口会读取这个请求头。
function authHeaders() {
  return state.auth.token ? { Authorization: `Bearer ${state.auth.token}` } : {};
}

// 网页端 HTTP 接口统一入口。
// 所有 fetch 请求都走这里，统一补 Content-Type、认证头，并把后端 detail 错误转成可提示给用户的 Error。
async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) throw new Error(payload?.detail || `${response.status} ${response.statusText}`);
  return payload;
}

// 登录成功后把令牌和过期时间持久化到 localStorage。
function rememberToken(token, expiresAt) {
  state.auth.token = token || null;
  state.auth.tokenExpiry = expiresAt || null;
  token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY);
  expiresAt ? localStorage.setItem(TOKEN_EXP_KEY, expiresAt) : localStorage.removeItem(TOKEN_EXP_KEY);
}

function clearAuth() {
  rememberToken(null, null);
  state.auth.user = null;
  state.userSummary = null;
}

function setAuthMode(mode) {
  state.auth.mode = mode === "login" ? "login" : "register";
  $("authTabRegister")?.classList.toggle("active", state.auth.mode === "register");
  $("authTabLogin")?.classList.toggle("active", state.auth.mode === "login");
  $("registerPanel")?.classList.toggle("hidden", state.auth.mode !== "register");
  $("loginPanel")?.classList.toggle("hidden", state.auth.mode !== "login");
}

function userSessions() {
  const rows = safeArray(state.lists.sessions);
  return isLoggedIn() ? rows.filter((item) => item.userId === state.auth.user.id) : rows;
}

function userEvaluations() {
  const rows = safeArray(state.lists.evaluations);
  return isLoggedIn() ? rows.filter((item) => item.userId === state.auth.user.id) : rows;
}

function packetSignature(packet) {
  if (!packet) return "";
  return `${packet.seq ?? "na"}-${packet.timestampMs ?? "na"}`;
}

// 维护有限长度的实时传感器历史，用于曲线和阶段判断。
function pushPacket(packet) {
  if (!packet) return;
  const signature = packetSignature(packet);
  if (signature === state.packetKey) return;
  state.packetKey = signature;
  state.latestPacket = packet;
  state.sensorHistory.push({ ...packet });
  if (state.sensorHistory.length > SENSOR_HISTORY_LIMIT) {
    state.sensorHistory.splice(0, state.sensorHistory.length - SENSOR_HISTORY_LIMIT);
  }
}

function actionFamily(label) {
  const text = String(label || "");
  if (text.startsWith("squat")) return "squat";
  if (text.startsWith("bench")) return "bench";
  if (text === "idle") return "idle";
  return "general";
}

function getFlexSeries() {
  return state.sensorHistory.map((item) => Number(item.flexIndex || 0));
}

// 仅靠最近弯曲指数推断训练动作阶段。
function deriveLivePhase(label) {
  const family = actionFamily(label);
  const values = getFlexSeries();
  if (family === "idle" || values.length < 4) return { key: "rest", text: "静止" };
  const latest = values[values.length - 1];
  const previous = values[values.length - 4];
  const delta = latest - previous;
  if (family === "squat") {
    if (latest >= 24 && Math.abs(delta) < 2) return { key: "bottom", text: "蹲底控制" };
    if (delta >= 3) return { key: "down", text: "下蹲中" };
    if (delta <= -3) return { key: "up", text: "起身中" };
    return latest < 8 ? { key: "rest", text: "站立准备" } : { key: "transition", text: "动作过渡" };
  }
  if (family === "bench") {
    if (latest >= 18 && Math.abs(delta) < 2) return { key: "bottom", text: "下放底部" };
    if (delta >= 2) return { key: "down", text: "下放中" };
    if (delta <= -2) return { key: "up", text: "推起中" };
    return latest < 6 ? { key: "rest", text: "准备姿态" } : { key: "transition", text: "动作过渡" };
  }
  return { key: "transition", text: "动作进行中" };
}

function resetRepCounter() {
  state.repCounter = { count: 0, family: "idle", phases: [] };
}

// 根据动作阶段序列估算完成次数。
function updateRepCounter(label) {
  const family = actionFamily(label);
  const phase = deriveLivePhase(label);
  if (!["squat", "bench"].includes(family)) {
    state.repCounter.family = family;
    state.repCounter.phases = [];
    return;
  }
  if (state.repCounter.family !== family) {
    state.repCounter.family = family;
    state.repCounter.phases = [];
  }
  const phases = state.repCounter.phases;
  if (phases[phases.length - 1] !== phase.key) phases.push(phase.key);
  if (phases.length > 5) phases.shift();
  const tail = phases.join(">");
  if (tail.includes("down>bottom>up>rest") || tail.includes("down>up>rest")) {
    state.repCounter.count += 1;
    state.repCounter.phases = ["rest"];
  }
}

// 基于后端评分字段生成网页单句提示；该函数只影响展示文案，不修改 EvaluationEngine 的评分结果。
function buildSuggestion(label, evaluation) {
  const family = actionFamily(label);
  const depth = Number(evaluation?.depthScore || 0);
  const stability = Number(evaluation?.stabilityScore || 0);
  const rhythm = Number(evaluation?.rhythmScore || 0);
  const score = Number(evaluation?.standardScore || 0);
  if (family === "idle") return "保持自然站立和稳定佩戴，准备开始下一组训练。";
  if (label === "squat_wrong") {
    // 错误深蹲标签优先显示轨迹纠正；稳定性、深度、节奏阈值只用于选择页面提示文案。
    if (stability < 78) return "检测到深蹲错误模式，优先纠正膝盖内扣，保持膝盖朝向脚尖。";
    if (depth < 70) return "错误深蹲同时存在幅度不足，先稳定下蹲幅度，再控制膝盖轨迹。";
    if (rhythm < 72) return "错误深蹲节奏偏急，放慢下蹲和起身速度，避免膝盖突然内扣。";
    return "当前被识别为深蹲错误，请重点检查膝盖轨迹和下肢稳定性。";
  }
  if (family === "squat") {
    // 标准深蹲按深度、稳定性、节奏三个后端评分字段选择一个最优先的页面提示。
    if (depth < 70) return "下蹲深度不够，继续向后坐髋并保持稳定。";
    if (stability < 72) return "动作稳定性偏弱，注意核心收紧与膝盖方向。";
    if (rhythm < 72) return "节奏控制偏急，建议下蹲和起身都保持匀速。";
    if (score >= 85) return "这一组深蹲完成得不错，继续保持节奏和稳定性。";
    return "继续保持膝盖与脚尖方向一致，注意动作完整度。";
  }
  if (family === "bench") {
    // 卧推复用同一组评分字段，展示文案映射为下放幅度、动作路径和推起节奏。
    if (depth < 70) return "下放幅度偏小，建议保证完整下放行程。";
    if (stability < 72) return "动作路径有些不稳，注意肩部控制和发力轨迹。";
    if (rhythm < 72) return "推起和下放节奏不均匀，建议放慢速度。";
    if (score >= 85) return "本组卧推动作较稳定，可以保持当前节奏。";
    return "注意推起稳定和肩部放松，避免借力。";
  }
  return "开始训练后，这里会显示当前动作的实时纠正建议。";
}
// 根据当前路由切换页面显示和导航高亮。
function renderRoute() {
  const route = currentRoute();
  const pageMap = {
    "/login": "page-login",
    "/dashboard": "page-dashboard",
    "/training": "page-training",
    "/history": "page-history",
    "/debug": "page-debug",
  };
  const activePageId = pageMap[route] || "page-login";
  document.documentElement.setAttribute("data-route", route);
  document.querySelectorAll(".route-page").forEach((page) => {
    const active = page.id === activePageId;
    page.classList.toggle("hidden", !active);
    page.hidden = !active;
    page.style.display = active ? "block" : "none";
  });
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === route);
  });
  setText("topbarSubtitle", ROUTE_SUBTITLE[route]);
}

// 刷新顶部栏的设备状态、账号和页面副标题。
function renderTopbar() {
  const connected = Boolean(state.status?.connected);
  const dot = $("statusDot");
  if (dot) {
    dot.classList.toggle("status-online", connected);
    dot.classList.toggle("status-offline", !connected);
  }
  setText("statusText", connected ? (state.status?.deviceName || "设备已连接") : "未连接设备");
  setText("topbarUserText", isLoggedIn() ? state.auth.user.username : "游客模式");
}

// 渲染登录/注册页和游客入口状态。
function renderAuth() {
  setAuthMode(state.auth.mode);
  setText("authCurrentUser", state.auth.user?.username || "未登录");
  setText("authTokenExpiry", state.auth.tokenExpiry ? formatDateTime(state.auth.tokenExpiry) : "-");
  setText("authStatusTag", isLoggedIn() ? "已登录" : "未登录");
  setText(
    "authHint",
    isLoggedIn()
      ? "当前账号已与训练记录、评估结果和历史报告同步。"
      : "登录后可同步训练记录、评分结果和历史报告。"
  );
}

// 渲染个人首页的训练概览、趋势、近期记录和建议。
function renderDashboard() {
  const sessions = userSessions();
  const evaluations = userEvaluations();
  const latestEvaluation = state.userSummary?.latestEvaluation || evaluations[0] || null;
  const latestSession = state.userSummary?.recentSessions?.[0] || sessions[0] || null;
  const avgScore = Number(
    state.userSummary?.averageScore ??
    (evaluations.length ? evaluations.reduce((sum, item) => sum + Number(item.standardScore || 0), 0) / evaluations.length : 0)
  );

  const now = new Date();
  let todayMinutes = 0;
  let totalMinutes = 0;
  sessions.forEach((item) => {
    totalMinutes += Number(item.durationMs || 0) / 60000;
    if (!item.startedAt) return;
    const date = new Date(item.startedAt);
    if (!Number.isNaN(date.getTime()) && date.toDateString() === now.toDateString()) {
      todayMinutes += Number(item.durationMs || 0) / 60000;
    }
  });

  setText("dashboardTopUserValue", isLoggedIn() ? state.auth.user.username : "游客");
  setText("dashboardHeroUserValue", isLoggedIn() ? `欢迎回来，${state.auth.user.username}` : "欢迎回来，训练访客");
  setText(
    "dashboardHeroSummaryValue",
    isLoggedIn() ? "今天是训练的好时机，坚持科学训练，让每一次进步都看得见！" : "你当前以游客身份浏览平台，可以先查看页面结构和功能入口。"
  );
  setText("dashboardConnectionBadge", state.status?.connected ? "已连接" : "未连接");
  setText("dashboardRecentActionBadge", labelText(latestEvaluation?.actionLabel || "idle"));
  setText("dashboardAverageScoreBadge", Number.isFinite(avgScore) ? avgScore.toFixed(0) : "0");
  setText("dashboardTotalTrainingValue", `${sessions.length || 0} 天`);
  setText("dashboardTotalDurationValue", `${Math.max(0, Number(totalMinutes || 0) / 60).toFixed(1)} 小时`);

  setText("homeModeTag", isLoggedIn() ? "已登录" : "游客模式");
  setText("homeWelcomeValue", isLoggedIn() ? state.auth.user.username : "训练访客");
  setText(
    "homeIntroValue",
    isLoggedIn() ? "登录账号后，训练记录、评分和报告会持续同步到你的个人中心。" : "当前是游客浏览模式，登录后才可以真正开始训练和保存个人记录。"
  );
  setText("homeDurationValue", formatMinutes(todayMinutes));
  setText("homeCaloriesValue", `${estimateCalories(todayMinutes, state.repCounter.count)} kcal`);
  setText("dashboardTodayRepsValue", `${state.repCounter.count} 次`);
  setText("homeActionValue", labelText(latestEvaluation?.actionLabel || "idle"));
  setText("homeScoreValue", latestEvaluation?.standardScore ?? 0);
  setText("dashboardDeviceHint", state.status?.connected ? "设备已连接" : "设备未连接");
  setText("dashboardSuggestedActionValue", labelText((state.labels.find((item) => item !== "idle")) || "squat_standard"));
  setText("homeAdviceValue", buildSuggestion(latestEvaluation?.actionLabel || "idle", latestEvaluation));
  setText("dashboardCompletionValue", `${Math.round(Number(latestEvaluation?.depthScore ?? latestEvaluation?.standardScore ?? 0))}%`);
  setText("dashboardStabilityValue", Number(latestEvaluation?.stabilityScore || 0) >= 80 ? "优秀" : Number(latestEvaluation?.stabilityScore || 0) >= 65 ? "良好" : "待提升");

  const sideRing = document.querySelector(".side-score-ring");
  if (sideRing) {
    const score = Number(latestEvaluation?.standardScore || 0);
    sideRing.style.setProperty("--score-value", String(score));
    sideRing.dataset.scoreLevel = score >= 80 ? "good" : score >= 60 ? "warn" : "low";
  }
  const miniRing = document.querySelector(".mini-score-ring");
  if (miniRing) {
    const score = Number.isFinite(avgScore) ? Math.round(avgScore) : 0;
    miniRing.style.setProperty("--score-value", String(score));
  }

  const trendRows = safeArray(state.userSummary?.scoreTrend).length
    ? safeArray(state.userSummary.scoreTrend).map((item) => ({ label: item.day, value: Number(item.averageScore || 0) }))
    : safeArray(state.report?.dailyTrend).map((item) => ({ label: item.day, value: Math.min(100, Number(item.sessions || 0) * 20) }));

  setHtml(
    "weekTrendBars",
    trendRows.length
      ? trendRows.map((item) => `
          <div class="trend-bar week-trend-card" title="${item.label} 标准度 ${Number(item.value || 0).toFixed(0)} 分">
            <span class="week-trend-score">${Number(item.value || 0).toFixed(0)} 分</span>
            <div class="trend-track"><div class="trend-fill" style="height:${Math.max(8, Math.min(100, Number(item.value || 0)))}%"></div></div>
            <span class="week-trend-date">${item.label}</span>
          </div>
        `).join("")
      : '<p class="empty-copy">暂无本周趋势数据。</p>'
  );

  setText("weekAverageScoreValue", Number.isFinite(avgScore) ? avgScore.toFixed(0) : "0");
  setText("weekSessionCountValue", `${sessions.length} 次`);
  setText("recentActionValue", labelText(latestSession?.label || latestEvaluation?.actionLabel || "-"));
  setText("recentTimeValue", latestSession?.startedAt ? formatDateTime(latestSession.startedAt) : "暂无最近训练时间");
  setText("recentCountValue", `${state.repCounter.count} 次`);
  setText("recentScoreValue", latestEvaluation?.standardScore ?? 0);
  setText("recentRiskValue", riskText(latestEvaluation?.compensationRisk || "unknown"));

  const guideDot = $("guideBleDot");
  if (guideDot) {
    guideDot.classList.toggle("status-online", Boolean(state.status?.connected));
    guideDot.classList.toggle("status-offline", !state.status?.connected);
  }
  setText("guideBleText", state.status?.connected ? "设备已连接，可以开始训练" : "设备未连接");
}

// 渲染训练中心的连接、采集、实时评分和动作指导。
function renderTraining() {
  const deviceSelect = $("deviceSelect");
  if (deviceSelect) {
    const devices = state.devices.length ? state.devices : [{ address: "", displayName: "请先扫描设备" }];
    const current = deviceSelect.value;
    deviceSelect.innerHTML = devices.map((device) => {
      const text = device.displayName || device.local_name || device.name || "Unknown";
      return `<option value="${device.address || ""}">${text}${device.isTargetCandidate ? " [推荐]" : ""}</option>`;
    }).join("");
    const values = devices.map((item) => item.address || "");
    deviceSelect.value = values.includes(current) ? current : values[0];
  }

  const liveLabel = state.inference?.latestPrediction?.label || state.evaluation?.actionLabel || "idle";
  const livePhase = deriveLivePhase(liveLabel);
  const suggestion = buildSuggestion(liveLabel, state.evaluation);
  const connected = Boolean(state.status?.connected);
  const recording = Boolean(state.status?.recording);
  const loggedIn = isLoggedIn();
  const score = Number(state.evaluation?.standardScore || 0);

  const connectDot = $("trainingConnectDot");
  if (connectDot) {
    connectDot.classList.toggle("status-online", connected);
    connectDot.classList.toggle("status-offline", !connected);
  }
  setText("trainingConnectText", connected ? "设备已连接" : "设备未连接");
  setText("trainingSessionTag", recording ? "训练中" : "等待训练");
  setText("trainingDeviceBadge", connected ? (state.status?.deviceName || "已连接") : "未连接");
  setText("trainingRecordBadge", recording ? "训练中" : "未开始");
  refreshTrainingActionGuide();
  setText("trainingActionValue", labelText(liveLabel));
  setText("trainingPhaseValue", livePhase.text);
  setText("trainingScoreValue", score);
  setText("trainingRepCountValue", state.repCounter.count);
  setText("trainingRepHintValue", state.repCounter.count > 0 ? "已识别完整动作循环" : "等待完整动作循环");
  setText("trainingRiskValue", riskText(state.evaluation?.compensationRisk || "unknown"));
  setText("trainingRiskHintValue", state.advanced?.correctionFocus || "开始训练后显示本次动作的主要风险点。");
  setText("trainingSuggestionValue", suggestion);
  setText("trainingDepthValue", state.evaluation?.depthScore ?? 0);
  setText("trainingStabilityValue", state.evaluation?.stabilityScore ?? 0);
  setText("trainingRhythmValue", state.evaluation?.rhythmScore ?? 0);
  setText("trainingLatestActionValue", labelText(liveLabel));
  setText("trainingLatestScoreValue", score);
  setText("trainingLatestAdviceValue", suggestion);
  setText("trainingPacketsValue", state.status?.packetsReceived ?? 0);
  setText(
    "trainingAccessHint",
    loggedIn
      ? "已登录。确认佩戴位置、连接设备，然后直接开始训练，系统会自动识别动作。"
      : "请先登录。游客模式可以浏览训练流程，但不能真正连接设备或开始训练。"
  );
  setText(
    "trainingLabelHint",
    recording
      ? "训练进行中。请按正常节奏完成动作，系统会实时更新识别结果、次数和纠正建议。"
      : "连接设备并确认佩戴稳定后即可开始训练。"
  );
  setText("startRecordingBtn", recording ? "训练进行中..." : "开始训练");
  setText("stopRecordingBtn", recording ? "完成训练并生成报告" : "完成训练");

  const scoreRing = $("scoreRing");
  if (scoreRing) {
    const accent = score >= 80 ? "#2f9d6a" : score < 60 ? "#d75a49" : "#df6d2f";
    const shade = score >= 80 ? "rgba(47,157,106,.18)" : score < 60 ? "rgba(215,90,73,.18)" : "rgba(223,109,47,.18)";
    scoreRing.style.setProperty("--score-value", String(score));
    scoreRing.style.setProperty("--score-accent", accent);
    scoreRing.style.setProperty("--score-shade", shade);
  }

  const riskCard = $("trainingRiskCard");
  if (riskCard) {
    riskCard.dataset.risk = state.evaluation?.compensationRisk || "unknown";
  }

  const scanBtn = $("scanBtn");
  const connectBtn = $("connectBtn");
  const disconnectBtn = $("disconnectBtn");
  const startBtn = $("startRecordingBtn");
  const stopBtn = $("stopRecordingBtn");
  const notesField = $("notesInput");

  if (scanBtn) scanBtn.disabled = !loggedIn;
  if (connectBtn) connectBtn.disabled = !loggedIn || connected;
  if (disconnectBtn) disconnectBtn.disabled = !loggedIn || !connected;
  if (startBtn) startBtn.disabled = !loggedIn || !connected || recording;
  if (stopBtn) stopBtn.disabled = !loggedIn || !recording;
  if (notesField) notesField.disabled = recording;
}
// 渲染历史报告页，展示采集记录和趋势摘要。
function renderHistory() {
  if (!isLoggedIn()) {
    setText("historyProgressValue", "登录后可查看你的历史训练对比");
    setText("historyStabilityProgressValue", "当前为游客模式，尚未绑定个人记录。");
    setHtml("historyRiskList", '<p class="empty-copy">请先登录以查看个人风险统计。</p>');
    setHtml("historySessionList", '<p class="empty-copy">请先登录以查看个人历史训练记录。</p>');
    return;
  }

  const evaluations = userEvaluations();
  const sessions = userSessions();
  const latest = evaluations[0];
  const previous = evaluations[1];

  if (latest && previous) {
    const delta = Number(latest.standardScore || 0) - Number(previous.standardScore || 0);
    const stabilityDelta = Number(latest.stabilityScore || 0) - Number(previous.stabilityScore || 0);
    setText("historyProgressValue", delta === 0 ? "标准度与上次持平" : `标准度比上次${delta > 0 ? "提升" : "下降"}了 ${Math.abs(delta)} 分`);
    setText("historyStabilityProgressValue", stabilityDelta === 0 ? "稳定性与上次持平" : `动作稳定性${stabilityDelta > 0 ? "提高" : "下降"}了 ${Math.abs(stabilityDelta)} 分`);
  } else {
    setText("historyProgressValue", "至少需要两次训练记录");
    setText("historyStabilityProgressValue", "至少需要两次训练记录");
  }

  const issueCounter = {
    "深度不足": evaluations.filter((item) => Number(item.depthScore || 0) < 70).length,
    "稳定性偏弱": evaluations.filter((item) => Number(item.stabilityScore || 0) < 72).length,
    "节奏控制不足": evaluations.filter((item) => Number(item.rhythmScore || 0) < 72).length,
  };

  setHtml(
    "historyRiskList",
    Object.values(issueCounter).some((count) => count > 0)
      ? Object.entries(issueCounter).map(([label, count]) => `
          <div class="risk-item">
            <span>${label}</span>
            <strong>${count} 次</strong>
          </div>
        `).join("")
      : '<p class="empty-copy">本周暂无明显风险统计。</p>'
  );

  setHtml(
    "historySessionList",
    sessions.length
      ? sessions.slice(0, 5).map((session) => {
          const evaluation = evaluations.find((item) => item.sensorSessionId === session.id);
          return `
            <article class="history-session-card">
              <div>
                <strong>${labelText(session.label)}</strong>
                <p>${formatDateTime(session.startedAt)}</p>
              </div>
              <div class="history-session-meta">
                <span>${formatMinutes(Number(session.durationMs || 0) / 60000)}</span>
                <span>${session.rowsWritten || 0} 行</span>
                <strong>${evaluation?.standardScore ?? "-"}</strong>
              </div>
            </article>
          `;
        }).join("")
      : '<p class="empty-copy">暂无历史训练记录。</p>'
  );
}

// 开发者视图：展示和删除本地采集记录。
function renderDebugRecordings() {
  const host = $("debugRecordingsList");
  if (!host) return;

  const rows = safeArray(state.recordings);
  const deleteMode = state.debugRecordActionType === "delete";
  const cardRenderer = (item, timeline = false) => `
    <article class="history-session-card debug-record-card ${deleteMode ? "debug-record-delete" : ""} ${timeline ? "debug-record-timeline-item" : ""}">
      <div>
        <strong>${labelText(item.label || "-")}</strong>
        <p>${formatDateTime(item.startedAtIso || item.startedAt || item.startedAtMs)}</p>
        <p class="small-inline">
          <span>Session:</span>
          <code>${item.sessionId || "-"}</code>
        </p>
      </div>
      <div class="history-session-meta">
        <span>${item.rowsWritten || 0} 行</span>
        <span>${item.stopReason || "未结束"}</span>
        ${deleteMode ? `<button class="danger-btn debug-delete-record-btn" type="button" data-session-id="${item.sessionId}">删除</button>` : `<strong>查看</strong>`}
      </div>
    </article>
  `;

  if (!rows.length) {
    host.innerHTML = '<p class="empty-copy">暂无训练记录。</p>';
    return;
  }

  if (state.debugRecordViewType === "timeline") {
    host.innerHTML = `<div class="debug-record-timeline">${rows.map((item) => cardRenderer(item, true)).join("")}</div>`;
    return;
  }

  host.innerHTML = rows.map((item) => cardRenderer(item)).join("");
}

// 开发者视图：管理标签目录和样本数量。
function renderDebugLabels() {
  const host = $("debugLabelList");
  if (!host) return;

  const labels = safeArray(state.labels).filter((label) => !NON_TRAINING_LABELS.has(label));
  if (!labels.length) {
    host.innerHTML = '<p class="empty-copy">暂无已创建或已采集的标签。</p>';
    return;
  }

  host.innerHTML = labels.map((label) => {
    const count = Number(state.labelCounts?.[label] || 0);
    return `
      <div class="debug-label-item">
        <div>
          <strong>${labelText(label)}</strong>
          <span>${label} · ${count} 组样本</span>
        </div>
        <div class="debug-label-actions">
          <button class="secondary-btn debug-remove-label-model-btn" type="button" data-label="${label}">从模型移除</button>
          <button class="danger-btn debug-delete-label-btn" type="button" data-label="${label}">删除标签</button>
        </div>
      </div>
    `;
  }).join("");
}

function trainingPhaseText(phase) {
  const mapping = {
    idle: "空闲",
    queued: "排队中",
    preparing: "数据预处理中",
    training: "模型训练中",
    reloading: "模型重载中",
    completed: "训练完成",
    failed: "训练失败",
  };
  return mapping[phase] || phase || "空闲";
}

// 渲染模型训练标签复选列表，并标记样本不足的标签。
function renderLabelChecklist() {
  const host = $("debugTrainingLabels");
  if (!host) return;
  syncSelectedLabels();
  const selectableCount = trainableLabels().length;

  host.innerHTML = state.labels.length
    ? state.labels.map((label) => `
        <div
          class="label-check-item ${Number(state.labelCounts?.[label] || 0) <= 0 ? "label-check-item-disabled" : ""}"
          data-label="${label}"
          role="checkbox"
          aria-checked="${state.selectedLabels.includes(label) ? "true" : "false"}"
          tabindex="${Number(state.labelCounts?.[label] || 0) <= 0 ? "-1" : "0"}"
        >
          <input
            type="checkbox"
            value="${label}"
            ${state.selectedLabels.includes(label) ? "checked" : ""}
            ${Number(state.labelCounts?.[label] || 0) <= 0 ? "disabled" : ""}
            tabindex="-1"
          >
          <div class="label-check-copy">
            <span>${labelText(label)}</span>
            <small>${Number(state.labelCounts?.[label] || 0)} 组样本${Number(state.labelCounts?.[label] || 0) <= 0 ? " · 暂不可训练" : ""}</small>
          </div>
        </div>
      `).join("")
    : '<p class="empty-copy">暂无可训练标签。</p>';

  setText("debugTrainingLabelCount", `${state.selectedLabels.length} / ${selectableCount}`);
}

// 按设备像素比初始化画布，保证曲线在高清屏上清晰。
function setupCanvas(id) {
  const canvas = $(id);
  if (!canvas) return null;
  const width = Math.max(260, Math.round(canvas.clientWidth || 320));
  const height = Math.max(180, Math.round(canvas.clientHeight || 220));
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { ctx, width, height };
}

// 绘制单条实时传感器曲线。
function drawChart(id, series) {
  const setup = setupCanvas(id);
  if (!setup) return;
  const { ctx, width, height } = setup;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fffdf9";
  ctx.fillRect(0, 0, width, height);

  if (!state.sensorHistory.length) {
    ctx.fillStyle = "#8a7765";
    ctx.font = "14px Segoe UI";
    ctx.fillText("等待实时数据...", 18, height / 2);
    return;
  }

  const padding = { top: 16, right: 18, bottom: 24, left: 18 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  let min = Infinity;
  let max = -Infinity;

  series.forEach((item) => {
    state.sensorHistory.forEach((packet) => {
      const value = Number(packet[item.key] ?? 0);
      min = Math.min(min, value);
      max = Math.max(max, value);
    });
  });

  if (min === max) {
    min -= 1;
    max += 1;
  }

  ctx.strokeStyle = "rgba(117, 96, 70, 0.12)";
  for (let i = 0; i <= 4; i += 1) {
    const y = padding.top + (plotHeight * i) / 4;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
  }

  series.forEach((item) => {
    ctx.strokeStyle = item.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    state.sensorHistory.forEach((packet, index) => {
      const value = Number(packet[item.key] ?? 0);
      const x = padding.left + (plotWidth * index) / Math.max(1, state.sensorHistory.length - 1);
      const y = padding.top + plotHeight - ((value - min) / (max - min)) * plotHeight;
      if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
}

function drawAllCharts() {
  drawChart("flexRawChart", [
    { key: "flexRawAdc", color: "#df6d2f" },
    { key: "flexRawMv", color: "#2f9d6a" },
  ]);
  drawChart("flexIndexChart", [{ key: "flexIndex", color: "#0f8a9d" }]);
  drawChart("accelChart", [
    { key: "ax", color: "#df6d2f" },
    { key: "ay", color: "#2f9d6a" },
    { key: "az", color: "#7059d8" },
  ]);
  drawChart("gyroChart", [
    { key: "gx", color: "#d75a49" },
    { key: "gy", color: "#ca951f" },
    { key: "gz", color: "#2469d5" },
  ]);
}

// 开发者视图：展示数据库、推理、评估和模型训练状态。
function renderDebugSystemStatus() {
  const enabled = Boolean(state.dbStatus?.enabled);
  setText("debugDatabaseBadge", enabled ? "已启用" : "未启用");
  setText("debugDatabaseStateText", enabled ? "数据库已连接" : "数据库未启用");
  setText("debugModelBadge", state.inference?.modelLoaded ? "已加载" : "未加载");
  setText("debugConnectionBadge", state.status?.connected ? "已连接" : "未连接");
  setText("debugRecordingBadge", state.status?.recording ? "采集中" : "未录制");
}

function renderDebugTrainingPanel() {
  syncSelectedLabels();
  renderDebugSystemStatus();
  renderDebugLabels();
  const connected = Boolean(state.status?.connected);
  const recording = Boolean(state.status?.recording);
  const captureSelect = $("debugCaptureLabelSelect");
  if (captureSelect) {
    const labels = captureLabels();
    const current = captureSelect.value;
    captureSelect.innerHTML = labels.map((label) => `<option value="${label}">${labelText(label)}</option>`).join("");
    captureSelect.value = labels.includes(current) ? current : labels[0] || "";
  }
  const activeSession = state.status?.activeSession || null;
  setText("debugCaptureActiveLabel", activeSession?.label ? labelText(activeSession.label) : "未开始");
  setText("debugCaptureStatusValue", recording ? "采集中" : "未开始");
  setText(
    "debugCaptureHint",
    connected
      ? "设备已连接。这里用于给模型采集带标签的数据，普通用户训练不需要选择标签。"
      : "设备未连接。请先到训练中心扫描并连接设备，再回到这里开始标签采集。"
  );
  if ($("debugStartCaptureBtn")) $("debugStartCaptureBtn").disabled = !connected || recording;
  if ($("debugStopCaptureBtn")) $("debugStopCaptureBtn").disabled = !recording;
  setText("debugTrainingRunValue", state.trainingJob?.running ? "训练中" : "空闲");
  setText("debugTrainingStageValue", trainingPhaseText(state.trainingJob?.phase));
  setText("debugTrainingLastSuccessValue", formatDateTime(state.trainingJob?.lastSuccessAtIso));
  setText(
    "debugTrainingSelectedLabelsValue",
    safeArray(state.trainingJob?.selectedLabels).length
      ? safeArray(state.trainingJob?.selectedLabels).map(labelText).join("、")
      : "暂无"
  );
  setText(
    "debugTrainingSampleCountValue",
    String(safeArray(state.trainingJob?.selectedLabels).reduce((sum, label) => sum + Number(state.labelCounts?.[label] || 0), 0))
  );
  setText("debugTrainingPrepareExitValue", state.trainingJob?.prepareExitCode ?? "-");
  setText("debugTrainingTrainExitValue", state.trainingJob?.trainExitCode ?? "-");
  setText("debugTrainingErrorValue", state.trainingJob?.lastError || "无");

  if ($("debugTrainWindowSize")) $("debugTrainWindowSize").value = state.trainingJob?.windowSize ?? 20;
  if ($("debugTrainStepSize")) $("debugTrainStepSize").value = state.trainingJob?.stepSize ?? 5;
  if ($("debugAutoReloadCheckbox")) {
    $("debugAutoReloadCheckbox").checked = state.debugAutoReload ?? state.trainingJob?.autoReload ?? true;
  }
  if ($("debugRecordViewType")) $("debugRecordViewType").value = state.debugRecordViewType;
  if ($("debugRecordActionType")) $("debugRecordActionType").value = state.debugRecordActionType;

  renderLabelChecklist();
  setText("debugTrainingOutputBox", state.trainingJob?.output || "等待训练日志...");
  renderDebugRecordings();
}

// 开发者视图：展示最新数据包、三轴数据和曲线。
function renderDebugLiveData() {
  const packet = state.latestPacket || {};
  setText("debugPacketBox", state.latestPacket ? JSON.stringify(state.latestPacket, null, 2) : "等待实时数据...");
  setText("debugInferenceBox", state.inference ? JSON.stringify(state.inference, null, 2) : "等待推理状态...");
  setText("debugEvaluationBox", state.evaluation ? JSON.stringify(state.evaluation, null, 2) : "等待评估状态...");
  setText("debugSensorSampleTag", `${state.sensorHistory.length} 点`);
  setText("debugSeqValue", packet.seq ?? "-");
  setText("debugTimestampValue", packet.timestampMs ?? "-");
  setText("debugFlexAdcValue", packet.flexRawAdc ?? "-");
  setText("debugFlexMvValue", packet.flexRawMv ?? "-");
  setText("debugFlexIndexValue", packet.flexIndex ?? "-");
  setText("debugAxValue", packet.ax ?? "-");
  setText("debugAyValue", packet.ay ?? "-");
  setText("debugAzValue", packet.az ?? "-");
  setText("debugGxValue", packet.gx ?? "-");
  setText("debugGyValue", packet.gy ?? "-");
  setText("debugGzValue", packet.gz ?? "-");
  drawAllCharts();
}

function renderDebug() {
  renderDebugTrainingPanel();
  renderDebugLiveData();
}

// 统一触发各页面渲染和图表刷新。
function renderAll() {
  renderRoute();
  renderTopbar();
  renderAuth();
  renderDashboard();
  renderTraining();
  renderHistory();
  renderDebug();
}

// 有令牌时拉取当前用户，否则切回游客/未登录状态。
// 这就是网页“记住登录”的核心流程：localStorage 保存 token，页面刷新后用 /api/auth/me 换回用户信息。
async function loadCurrentUser() {
  if (!state.auth.token) {
    state.auth.user = null;
    state.userSummary = null;
    return;
  }
  try {
    const me = await apiFetch("/api/auth/me");
    state.auth.user = me.user;
    state.userSummary = await apiFetch("/api/report/user-summary");
  } catch {
    clearAuth();
  }
}

// 页面初始化的一次性 HTTP 拉取。
// HTTP 负责拿“当前完整快照”，WebSocket 后续只负责实时更新变化的状态/数据包/预测/评估结果。
async function loadBaseData() {
  const tasks = [
    apiFetch("/api/status").then((payload) => {
      state.status = payload;
      if (payload.latestPacket) pushPacket(payload.latestPacket);
    }),
    apiFetch("/api/labels").then((payload) => {
      state.labels = canonicalLabels(payload.available);
      state.labelCounts = canonicalLabelCounts(payload.counts);
      syncSelectedLabels({ selectAllOnFirstLoad: true });
    }),
    apiFetch("/api/inference/status").then((payload) => { state.inference = payload; }),
    apiFetch("/api/evaluation/status").then((payload) => { state.evaluation = payload; }),
    apiFetch("/api/evaluation/server-status").then((payload) => { state.advanced = payload; }),
    apiFetch("/api/report/summary").then((payload) => { state.report = payload; }),
    apiFetch("/api/database/status").then((payload) => { state.dbStatus = payload; }),
    apiFetch("/api/models/training/status").then((payload) => {
      state.trainingJob = payload;
      if (state.debugAutoReload === null && typeof payload?.autoReload === "boolean") {
        state.debugAutoReload = payload.autoReload;
      }
    }),
    apiFetch("/api/recordings").then((payload) => { state.recordings = safeArray(payload.items); }).catch(() => { state.recordings = []; }),
    apiFetch("/api/database/sessions").then((payload) => { state.lists.sessions = safeArray(payload.items); }).catch(() => { state.lists.sessions = []; }),
    apiFetch("/api/database/evaluations").then((payload) => { state.lists.evaluations = safeArray(payload.items); }).catch(() => { state.lists.evaluations = []; }),
    apiFetch("/api/database/models").then((payload) => { state.lists.models = safeArray(payload.items); }).catch(() => { state.lists.models = []; }),
    apiFetch("/api/database/reports").then((payload) => { state.lists.reports = safeArray(payload.items); }).catch(() => { state.lists.reports = []; }),
    loadCurrentUser(),
  ];
  await Promise.allSettled(tasks);
  renderAll();
}
// 建立实时 WebSocket，并根据后端事件更新前端状态。
// 路径对应后端 api.py 的 @app.websocket("/ws/live")，用于持续接收 BLE 数据、模型预测和动作评估。
function openSocket() {
  if (state.socket) {
    try { state.socket.close(); } catch { }
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${protocol}//${window.location.host}/ws/live`);
  state.socket = socket;

  socket.addEventListener("message", (event) => {
    try {
      const message = JSON.parse(event.data);
      const data = message.data;
      if (message.event === "status") {
        // status：后端网关状态快照，例如设备连接状态、录制状态、最新包。
        state.status = data;
        if (data?.latestPacket) pushPacket(data.latestPacket);
        renderTopbar();
        renderDashboard();
        renderTraining();
        if (currentRoute() === "/debug") {
          renderDebugSystemStatus();
          renderDebugLiveData();
        }
      } else if (message.event === "packet") {
        // packet：ESP32-S3 经 BLE Notify 推上来的单帧传感器数据。
        // 普通用户页只用识别结果；调试模式才会可视化 ax/ay/az/gx/gy/gz/flex 等原始字段。
        pushPacket(data);
        const liveLabel = state.inference?.latestPrediction?.label || state.evaluation?.actionLabel || "idle";
        updateRepCounter(liveLabel);
        renderTraining();
        if (currentRoute() === "/debug") renderDebugLiveData();
      } else if (message.event === "prediction") {
        // prediction：InferenceEngine 对滑窗数据输出的动作识别结果。
        state.inference = {
          ...(state.inference || {}),
          latestPrediction: data,
        };
        updateRepCounter(data?.label || state.evaluation?.actionLabel || "idle");
        renderTraining();
        if (currentRoute() === "/debug") renderDebugLiveData();
      } else if (message.event === "recording_started" || message.event === "recording_stopped") {
        if (currentRoute() === "/debug") renderDebugTrainingPanel();
      } else if (message.event === "error") {
        if (currentRoute() === "/debug") renderDebugLiveData();
      } else if (message.event === "inference_status") {
        state.inference = data;
        renderTraining();
        if (currentRoute() === "/debug") {
          renderDebugSystemStatus();
          renderDebugLiveData();
        }
      } else if (message.event === "evaluation_status") {
        // evaluation_status：EvaluationEngine 输出的标准度评分、动作阶段和纠正建议。
        state.evaluation = data;
        renderTraining();
        if (currentRoute() === "/debug") renderDebugLiveData();
      } else if (message.event === "advanced_evaluation_status") {
        // advanced_evaluation_status：服务端扩展评估模块的状态，用于后续更复杂动作质量分析。
        state.advanced = data;
        renderTraining();
      } else if (message.event === "report_summary") {
        state.report = data;
        renderDashboard();
        renderHistory();
      } else if (message.event === "model_training_status") {
        // model_training_status：后台训练任务状态，用于调试模式显示训练进度和最近成功时间。
        state.trainingJob = data;
        if (currentRoute() === "/debug") renderDebugTrainingPanel();
      } else {
        renderAll();
      }
    } catch (err) {
      console.warn(err);
    }
  });

  socket.addEventListener("close", () => {
    window.setTimeout(openSocket, 2000);
  });
}

// 注册接口流程：先 POST /api/auth/register 创建账号，再自动调用 /api/auth/login 登录。
// 这样新用户注册后会直接进入个人首页，不需要再手动登录一次。
async function registerUser() {
  const username = $("registerUsername")?.value.trim() || "";
  const password = $("registerPassword")?.value || "";
  if (!username || !password) return window.alert("请输入用户名和密码。");
  try {
    await apiFetch("/api/auth/register", { method: "POST", body: JSON.stringify({ username, password }) });
    const payload = await apiFetch("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
    rememberToken(payload.accessToken, payload.expiresAt);
    state.auth.user = payload.user;
    if ($("registerUsername")) $("registerUsername").value = "";
    if ($("registerPassword")) $("registerPassword").value = "";
    await loadBaseData();
    navigate("/dashboard");
  } catch (err) {
    window.alert(err.message);
  }
}

// 登录接口流程：POST /api/auth/login -> 保存 accessToken -> 拉取用户数据 -> 跳转个人首页。
async function loginUser() {
  const username = $("loginIdentity")?.value.trim() || "";
  const password = $("loginPassword")?.value || "";
  if (!username || !password) return window.alert("请输入用户名和密码。");
  try {
    const payload = await apiFetch("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
    rememberToken(payload.accessToken, payload.expiresAt);
    state.auth.user = payload.user;
    await loadBaseData();
    navigate("/dashboard");
  } catch (err) {
    window.alert(err.message);
  }
}

function logoutUser() {
  clearAuth();
  resetRepCounter();
  navigate("/login");
}

// 设备扫描接口：GET /api/devices/scan。
// 浏览器不能直接访问 BLE 设备，所以网页通过 PC 网关间接调用 Bleak 扫描。
async function scanDevices() {
  try {
    const payload = await apiFetch("/api/devices/scan");
    state.devices = safeArray(payload.devices);
    renderTraining();
  } catch (err) {
    window.alert(err.message);
  }
}

// 设备连接接口：POST /api/device/connect。
// 连接成功后后端会订阅 BLE Notify，网页无需轮询硬件。
async function connectDevice() {
  try {
    await apiFetch("/api/device/connect", {
      method: "POST",
      body: JSON.stringify({ address: $("deviceSelect")?.value || null, device_name: "ESP32S3_Fitness_BLE" }),
    });
    state.status = await apiFetch("/api/status");
    renderAll();
  } catch (err) {
    window.alert(err.message);
  }
}

async function disconnectDevice() {
  // 设备断开接口：POST /api/device/disconnect，用于主动释放 BLE 连接。
  try {
    await apiFetch("/api/device/disconnect", { method: "POST" });
    state.status = await apiFetch("/api/status");
    renderAll();
  } catch (err) {
    window.alert(err.message);
  }
}

// 开始采集/训练会话：POST /api/recordings/start。
// 用户训练中心使用自动标签，开发者调试模式才传入具体训练标签。
async function startRecording(label, notes) {
  if (!label) return window.alert("请先选择采集标签。");
  if (!state.status?.connected) return window.alert("请先连接设备，再开始训练或采集数据。");
  if (state.status?.recording) return window.alert("当前已经在采集中，请先结束当前训练或采集。");
  try {
    resetRepCounter();
    await apiFetch("/api/recordings/start", {
      method: "POST",
      body: JSON.stringify({ label, subject_id: isLoggedIn() ? state.auth.user.username : null, notes: notes || null }),
    });
    state.status = await apiFetch("/api/status");
    renderAll();
  } catch (err) {
    window.alert(err.message);
  }
}

async function startUserTraining() {
  const notes = $("notesInput")?.value || "用户端自动识别训练";
  await startRecording(USER_AUTO_LABEL, notes);
}

async function startDeveloperCapture() {
  const label = $("debugCaptureLabelSelect")?.value || "";
  const notes = $("debugCaptureNotesInput")?.value || "开发者标签采集";
  await startRecording(label, notes);
}

async function stopRecording() {
  // 结束采集/训练会话：POST /api/recordings/stop。
  // 后端会关闭当前 SessionRecorder，并刷新本地记录和数据库记录。
  try {
    await apiFetch("/api/recordings/stop", { method: "POST" });
    await loadBaseData();
  } catch (err) {
    window.alert(err.message);
  }
}

async function createLabel() {
  // 新增标签接口：POST /api/labels。
  // 只影响后续采集和训练可选项，不会自动产生训练样本。
  const rawLabel = $("debugNewLabelInput")?.value.trim() || "";
  const label = canonicalLabel(rawLabel);
  if (!label) return window.alert("请输入新的标签名。");
  try {
    const payload = await apiFetch("/api/labels", { method: "POST", body: JSON.stringify({ label }) });
    $("debugNewLabelInput").value = "";
    state.labels = canonicalLabels(payload.labels?.available || []);
    state.labelCounts = canonicalLabelCounts(payload.labels?.counts);
    syncSelectedLabels();
    renderAll();
    window.alert(`标签 ${labelText(payload.label)} 已创建。`);
  } catch (err) {
    window.alert(err.message);
  }
}

async function deleteLabel(label) {
  // 删除标签接口：DELETE /api/labels/{label}。
  // 会删除该标签原始数据，但不会直接修改已经训练好的模型文件。
  if (!label) return;
  const count = Number(state.labelCounts?.[label] || 0);
  const confirmed = window.confirm(
    `确定删除标签“${labelText(label)}”吗？\n\n这会删除该标签下 ${count} 组原始 CSV/JSON 采集数据，并从数据库移除对应会话记录。\n当前已经训练好的模型文件不会自动删除；如果要让模型不再使用这个标签，需要删除后重新训练并重载模型。`
  );
  if (!confirmed) return;

  try {
    const payload = await apiFetch(`/api/labels/${encodeURIComponent(label)}`, { method: "DELETE" });
    state.labels = canonicalLabels(payload.labels?.available || []);
    state.labelCounts = canonicalLabelCounts(payload.labels?.counts);
    syncSelectedLabels();
    await loadBaseData();
    window.alert(`标签已删除：${labelText(label)}。已删除 ${payload.deletedCsv || 0} 个 CSV 和 ${payload.deletedMeta || 0} 个元数据文件。`);
  } catch (err) {
    window.alert(err.message);
  }
}

async function removeLabelFromModel(label) {
  // 从模型移除标签接口：POST /api/models/remove-label。
  // 本质是排除该标签后重新训练一个新模型，而不是直接编辑旧模型内部结构。
  if (!label) return;
  if (state.trainingJob?.running) return window.alert("模型正在训练中，请等待当前训练结束后再操作。");

  const available = trainableLabels();
  if (!available.includes(label)) {
    return window.alert("这个标签当前没有可训练样本，模型训练范围里本来就不会包含它。");
  }

  const remaining = available.filter((item) => item !== label);
  if (remaining.length < 2) {
    return window.alert("移除后剩余可训练标签少于 2 个，无法重新训练分类模型。请至少保留两个有样本的标签。");
  }

  const confirmed = window.confirm(
    `确定要从当前模型中移除“${labelText(label)}”吗？\n\n这不会删除该标签的原始 CSV/JSON 数据，而是用剩余 ${remaining.length} 个标签重新训练模型并自动重载。\n剩余标签：${remaining.map(labelText).join("、")}`
  );
  if (!confirmed) return;

  try {
    state.selectedLabels = remaining;
    state.debugAutoReload = true;
    state.trainingJob = await apiFetch("/api/models/remove-label", {
      method: "POST",
      body: JSON.stringify({
        label,
        window_size: Number($("debugTrainWindowSize")?.value || 20),
        step_size: Number($("debugTrainStepSize")?.value || 5),
        auto_reload: true,
      }),
    });
    renderDebugTrainingPanel();
    window.alert(`已开始重新训练模型，新模型将不包含：${labelText(label)}。`);
  } catch (err) {
    window.alert(err.message);
  }
}

function toggleSelectAllLabels() {
  syncSelectedLabels();
  const allLabels = trainableLabels();
  const selected = safeArray(state.selectedLabels);
  state.selectedLabels = selected.length === allLabels.length ? [] : [...allLabels];
  renderDebugTrainingPanel();
}

function toggleTrainingLabel(label) {
  const count = Number(state.labelCounts?.[label] || 0);
  if (!label || count <= 0) return;

  const selected = new Set(safeArray(state.selectedLabels));
  selected.has(label) ? selected.delete(label) : selected.add(label);
  state.selectedLabels = trainableLabels().filter((item) => selected.has(item));
  renderLabelChecklist();
}

async function resetModelTrainingStatus() {
  try {
    state.trainingJob = await apiFetch("/api/models/training/reset", { method: "POST" });
    state.debugAutoReload = state.trainingJob?.autoReload ?? true;
    renderDebugTrainingPanel();
    window.alert("模型训练状态已清空。");
  } catch (err) {
    window.alert(err.message);
  }
}

// 管理员训练模型接口：POST /api/models/train。
// labels/window_size/step_size 会传给后端，再由后端调用 ml_pipeline 完成训练。
async function startModelTraining() {
  syncSelectedLabels();
  if (!state.selectedLabels.length) return window.alert("请至少选择一个参与训练的标签。");
  try {
    state.trainingJob = await apiFetch("/api/models/train", {
      method: "POST",
      body: JSON.stringify({
        labels: state.selectedLabels,
        window_size: Number($("debugTrainWindowSize")?.value || 20),
        step_size: Number($("debugTrainStepSize")?.value || 5),
        auto_reload: Boolean(state.debugAutoReload ?? $("debugAutoReloadCheckbox")?.checked),
      }),
    });
    renderDebugTrainingPanel();
  } catch (err) {
    window.alert(err.message);
  }
}

async function reloadModel() {
  // 重载模型接口：POST /api/inference/reload。
  // 训练完成后需要让 InferenceEngine 重新读取磁盘上的最新 joblib 模型。
  try {
    await apiFetch("/api/inference/reload", { method: "POST" });
    await loadBaseData();
    window.alert("模型已重载。");
  } catch (err) {
    window.alert(err.message);
  }
}

async function deleteRecording(sessionId) {
  // 删除某次采集记录接口：DELETE /api/recordings/{session_id}。
  // 用于清理误采集或空采集数据。
  if (!sessionId) return;
  const confirmed = window.confirm("确定删除这条训练记录吗？这会同时删除 CSV、JSON 和数据库里的对应记录。");
  if (!confirmed) return;
  try {
    await apiFetch(`/api/recordings/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
    await loadBaseData();
    window.alert("训练记录已删除。");
  } catch (err) {
    window.alert(err.message);
  }
}

// 集中绑定导航、认证、设备、采集、标签和模型训练按钮事件。
function bindEvents() {
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      navigate(link.dataset.route || "/login");
    });
  });
  window.addEventListener("popstate", () => renderAll());
  $("authTabRegister")?.addEventListener("click", () => setAuthMode("register"));
  $("authTabLogin")?.addEventListener("click", () => setAuthMode("login"));
  $("registerBtn")?.addEventListener("click", registerUser);
  $("loginBtn")?.addEventListener("click", loginUser);
  $("logoutBtn")?.addEventListener("click", logoutUser);
  $("enterAsGuestBtn")?.addEventListener("click", () => navigate("/dashboard"));
  $("openDebugBtn")?.addEventListener("click", () => navigate("/debug"));
  $("settingsDebugBtn")?.addEventListener("click", () => navigate("/debug"));
  $("goLoginPageBtn")?.addEventListener("click", () => navigate("/login"));
  $("homeStartTrainingBtn")?.addEventListener("click", () => navigate("/training"));
  $("dashboardPrimaryTrainBtn")?.addEventListener("click", () => navigate("/training"));
  $("dashboardQuickTrainBtn")?.addEventListener("click", () => navigate("/training"));
  $("dashboardOpenHistoryBtn")?.addEventListener("click", () => navigate("/history"));
  $("dashboardOpenHistoryBtnSide")?.addEventListener("click", () => navigate("/history"));
  $("scanBtn")?.addEventListener("click", scanDevices);
  $("connectBtn")?.addEventListener("click", connectDevice);
  $("disconnectBtn")?.addEventListener("click", disconnectDevice);
  $("startRecordingBtn")?.addEventListener("click", startUserTraining);
  $("stopRecordingBtn")?.addEventListener("click", stopRecording);
  $("debugCreateLabelBtn")?.addEventListener("click", createLabel);
  $("debugLabelList")?.addEventListener("click", (event) => {
    const removeButton = event.target.closest(".debug-remove-label-model-btn");
    if (removeButton) {
      event.preventDefault();
      event.stopPropagation();
      removeLabelFromModel(removeButton.dataset.label || "");
      return;
    }

    const button = event.target.closest(".debug-delete-label-btn");
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    deleteLabel(button.dataset.label || "");
  });
  $("debugStartCaptureBtn")?.addEventListener("click", startDeveloperCapture);
  $("debugStopCaptureBtn")?.addEventListener("click", stopRecording);
  $("debugSelectAllLabelsBtn")?.addEventListener("click", toggleSelectAllLabels);
  $("debugRefreshTrainingBtn")?.addEventListener("click", loadBaseData);
  $("debugStartTrainingBtn")?.addEventListener("click", startModelTraining);
  $("debugClearTrainingBtn")?.addEventListener("click", resetModelTrainingStatus);
  $("debugReloadModelBtn")?.addEventListener("click", reloadModel);
  $("debugAutoReloadCheckbox")?.addEventListener("change", (event) => {
    state.debugAutoReload = Boolean(event.target.checked);
    state.trainingJob = {
      ...(state.trainingJob || {}),
      autoReload: state.debugAutoReload,
    };
  });
  $("debugRefreshRecordsBtn")?.addEventListener("click", loadBaseData);
  $("debugRecordViewType")?.addEventListener("change", (event) => {
    state.debugRecordViewType = event.target.value || "list";
    renderDebugRecordings();
  });
  $("debugRecordActionType")?.addEventListener("change", (event) => {
    state.debugRecordActionType = event.target.value || "view";
    renderDebugRecordings();
  });
  $("debugTrainingLabels")?.addEventListener("click", (event) => {
    const card = event.target.closest(".label-check-item");
    if (!card || !event.currentTarget.contains(card)) return;
    event.preventDefault();
    toggleTrainingLabel(card.dataset.label || "");
  });
  $("debugTrainingLabels")?.addEventListener("keydown", (event) => {
    if (event.key !== " " && event.key !== "Enter") return;
    const card = event.target.closest(".label-check-item");
    if (!card || !event.currentTarget.contains(card)) return;
    event.preventDefault();
    toggleTrainingLabel(card.dataset.label || "");
  });
  $("debugRecordingsList")?.addEventListener("click", (event) => {
    const button = event.target.closest(".debug-delete-record-btn");
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    deleteRecording(button.dataset.sessionId || "");
  });
  window.addEventListener("resize", () => {
    if (currentRoute() === "/debug") drawAllCharts();
  });
}

// 页面加载后初始化渲染、绑定事件、拉取数据并连接实时通道。
document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  setAuthMode("register");
  renderAll();
  await loadBaseData();
  openSocket();
});

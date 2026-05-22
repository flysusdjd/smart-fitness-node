# 前端文件逐个详细说明

本文档专门解释项目里的前端相关文件。它包括两部分：

1. 网页端前端：`pc_gateway/static/index.html`、`app.js`、`styles.css`。
2. 安卓端界面资源：`esp32s3/app/src/main/res/` 下的 layout、values、drawable、xml、mipmap 文件。

你答辩时可以这样定义“前端”：

> 本项目的前端分为网页端和手机端。网页端是由 FastAPI 提供静态文件的原生 HTML/CSS/JavaScript 单页应用，手机端是 Android 原生界面 XML 资源配合 Java Activity 逻辑。网页端主要用于 PC 网关控制、训练展示和开发者调试；手机端主要用于移动训练、佩戴说明、语音反馈和个人报告查看。

---

## 1. 前端整体架构

### 1.1 网页端架构

网页端文件位于：

```text
pc_gateway/static/
  index.html
  app.js
  styles.css
```

职责划分：

| 文件 | 职责 |
|---|---|
| `index.html` | 页面结构、路由页面容器、按钮、输入框、数据展示节点 |
| `app.js` | 路由、状态管理、API 请求、WebSocket、渲染、训练逻辑、调试逻辑 |
| `styles.css` | 视觉风格、布局、卡片、响应式、动画、图表容器 |

网页端没有使用 Vue、React 或打包工具，属于：

```text
原生 HTML + 原生 CSS + 原生 JavaScript SPA
```

为什么这样设计：

> 项目重点在硬件、蓝牙、机器学习和实时反馈，前端使用原生技术可以减少依赖和构建复杂度，FastAPI 直接托管静态文件即可运行，适合毕业设计和现场演示。

### 1.2 网页端运行方式

网页不是单独启动的，而是由 PC 网关提供：

```text
pc_gateway/api.py
  -> app.mount("/static", StaticFiles(...))
  -> /login /dashboard /training /history /debug 都返回 index.html
```

浏览器访问：

```text
http://127.0.0.1:8787/login
```

手机浏览器也可以访问电脑局域网地址：

```text
http://电脑局域网IP:8787/login
```

### 1.3 网页端路由

当前网页端有 5 个路由：

| 路由 | 页面 | 面向对象 |
|---|---|---|
| `/login` | 登录/注册页 | 新用户、已有用户 |
| `/dashboard` | 用户个人首页 | 普通用户 |
| `/training` | 训练中心 | 普通用户训练 |
| `/history` | 历史报告 | 普通用户查看结果 |
| `/debug` | 开发者/调试模式 | 开发者、答辩调试 |

### 1.4 普通用户和开发者页面隔离

普通用户页面：

- `/dashboard`
- `/training`
- `/history`

这些页面不展示：

- 原始 ADC。
- 原始 IMU 六轴数组。
- 原始数据包。
- 模型训练日志。
- 标签采集。
- 删除训练数据。

开发者页面：

- `/debug`

这里才展示：

- 数据库状态。
- 模型状态。
- 标签管理。
- 模型训练。
- 训练模型记录。
- 弯曲传感器可视化。
- IMU 六轴可视化。
- 原始 JSON 数据。

答辩说法：

> 我把用户体验和开发者调试隔离开。普通用户只看到训练动作、次数、标准度和建议；开发者调试模式才看到底层传感器和模型维护功能。

---

## 2. `pc_gateway/static/index.html`

### 2.1 文件定位

`index.html` 是网页端的页面骨架。

它负责：

- 引入 `styles.css`。
- 定义顶部导航。
- 定义 5 个页面 section。
- 放置所有需要 JS 更新的 DOM 节点。
- 引入 `app.js`。

它不负责：

- 实时数据计算。
- API 请求。
- WebSocket。
- 页面切换逻辑。

这些都在 `app.js` 中实现。

### 2.2 顶层结构

整体结构可以理解为：

```html
<body>
  <div class="app-shell">
    <header class="topbar">顶部导航与状态</header>
    <main class="route-shell">
      <section id="page-login">登录/注册</section>
      <section id="page-dashboard">个人首页</section>
      <section id="page-training">训练中心</section>
      <section id="page-history">历史报告</section>
      <section id="page-debug">开发者调试模式</section>
    </main>
  </div>
  <script src="/static/app.js"></script>
</body>
```

### 2.3 顶部导航 `topbar`

核心节点：

| id/class | 作用 |
|---|---|
| `.topbar` | 顶部导航容器 |
| `.brand-block` | 左侧品牌区 |
| `.brand-mark` | 橙色 SF 标识 |
| `topbarSubtitle` | 当前页面副标题 |
| `.main-nav` | 页面导航 |
| `statusDot` | 设备连接状态圆点 |
| `statusText` | 设备连接文字 |
| `topbarUserText` | 当前用户或游客模式 |

导航链接：

```html
<a data-route="/login">登录</a>
<a data-route="/dashboard">个人首页</a>
<a data-route="/training">训练中心</a>
<a data-route="/history">历史报告</a>
<button data-route="/debug">设置</button>
```

注意：

> 导航不是传统刷新跳转。点击后由 `app.js` 的 `navigate()` 修改 history，再调用 `renderAll()` 局部切换页面。

### 2.4 登录/注册页 `page-login`

对应路由：

```text
/login
```

主要区域：

| 区域 | 说明 |
|---|---|
| Hero 说明区 | 介绍智能健身训练平台 |
| 登录状态卡片 | 当前账号、token 过期时间、登录提示 |
| 注册/登录表单 | 用户名、密码、按钮 |
| 游客入口 | 不登录也能查看页面 |
| 开发者设置入口 | 进入调试模式 |

关键 DOM：

| id | 作用 |
|---|---|
| `authStatusTag` | 显示已登录/未登录 |
| `authCurrentUser` | 当前用户 |
| `authTokenExpiry` | token 过期时间 |
| `authHint` | 登录提示 |
| `logoutBtn` | 退出登录 |
| `authTabRegister` | 切换注册 |
| `authTabLogin` | 切换登录 |
| `registerPanel` | 注册表单 |
| `registerUsername` | 注册用户名 |
| `registerPassword` | 注册密码 |
| `registerBtn` | 创建账号 |
| `loginPanel` | 登录表单 |
| `loginIdentity` | 登录用户名 |
| `loginPassword` | 登录密码 |
| `loginBtn` | 登录按钮 |
| `enterAsGuestBtn` | 游客进入首页 |
| `openDebugBtn` | 开发者设置 |

交互逻辑在 `app.js`：

- `registerUser()`
- `loginUser()`
- `logoutUser()`
- `setAuthMode()`

### 2.5 个人首页 `page-dashboard`

对应路由：

```text
/dashboard
```

设计目标：

> 像成熟健身平台首页，不展示专业原始数据，只展示用户能理解的训练概览和反馈。

页面主要模块：

| 模块 | 说明 |
|---|---|
| Dashboard Hero | 欢迎回来、训练天数、累计时长、运动设备插画 |
| 今日概览 | 今日训练时长、动作次数、热量、训练状态 |
| 本周标准度 | 平均标准度和趋势柱状图 |
| 最近训练 | 最近一次动作、时间、评分、风险 |
| 开始训练 CTA | 引导用户进入训练中心 |
| 动作库与佩戴说明 | 简化佩戴说明和设备状态 |
| 训练反馈侧栏 | 标准度环形图、纠正建议 |
| 训练小贴士 | 展示训练建议 |

关键 DOM：

| id | 作用 |
|---|---|
| `dashboardTopUserValue` | 右上角用户 |
| `dashboardHeroUserValue` | Hero 欢迎文字 |
| `dashboardHeroSummaryValue` | Hero 描述 |
| `dashboardTotalTrainingValue` | 累计训练天数 |
| `dashboardTotalDurationValue` | 累计训练小时 |
| `homeModeTag` | 登录/游客模式 |
| `homeWelcomeValue` | 首页用户名称 |
| `homeIntroValue` | 首页说明 |
| `homeDurationValue` | 今日训练时长 |
| `dashboardTodayRepsValue` | 今日动作次数 |
| `homeCaloriesValue` | 预估热量 |
| `homeActionValue` | 最近动作 |
| `weekAverageScoreValue` | 本周平均标准度 |
| `dashboardAverageScoreBadge` | 平均标准度徽标 |
| `weekTrendBars` | 趋势柱状图容器 |
| `recentActionValue` | 最近训练动作 |
| `recentTimeValue` | 最近训练时间 |
| `recentScoreValue` | 最近训练评分 |
| `recentRiskValue` | 最近训练风险 |
| `recentCountValue` | 最近动作次数 |
| `homeStartTrainingBtn` | 开始训练按钮 |
| `guideBleDot` | 佩戴说明里的设备状态圆点 |
| `guideBleText` | 设备连接文字 |
| `homeScoreValue` | 侧栏标准度 |
| `dashboardCompletionValue` | 动作完成度 |
| `dashboardStabilityValue` | 稳定性 |
| `homeAdviceValue` | 纠正建议 |

渲染逻辑：

```text
renderDashboard()
```

### 2.6 训练中心 `page-training`

对应路由：

```text
/training
```

设计目标：

> 普通用户进入后，只需要连接设备、查看佩戴说明、开始训练、看实时反馈。

页面主要模块：

| 模块 | 说明 |
|---|---|
| 页面标题 | 训练中心说明 |
| 左侧训练控制 | 佩戴说明、设备连接、备注、开始/结束训练 |
| 右侧实时反馈 | 当前动作、阶段、次数、风险、标准度环形图、文字纠正建议、动作质量指标 |
| 最近识别摘要 | 最新动作、分数、建议 |

关键 DOM：

| id | 作用 |
|---|---|
| `trainingSessionTag` | 训练状态标签 |
| `trainingLabelHint` | 训练提示 |
| `trainingWearGuide` | 根据动作变化的佩戴说明 |
| `trainingConnectDot` | 连接状态圆点 |
| `trainingConnectText` | 连接状态文字 |
| `deviceSelect` | 扫描到的设备列表 |
| `scanBtn` | 扫描设备 |
| `connectBtn` | 连接设备 |
| `disconnectBtn` | 断开设备 |
| `notesInput` | 用户训练备注 |
| `startRecordingBtn` | 开始训练 |
| `stopRecordingBtn` | 完成训练并生成报告 |
| `trainingDeviceBadge` | 当前设备 |
| `trainingLabelBadge` | 当前识别标签 |
| `trainingRecordBadge` | 录制状态 |
| `trainingAccessHint` | 登录权限提示 |
| `trainingActionValue` | 当前动作大字显示 |
| `trainingPhaseValue` | 当前动作阶段 |
| `trainingRepCountValue` | 计数器 |
| `trainingRiskCard` | 风险卡片 |
| `trainingRiskValue` | 风险等级 |
| `trainingPacketsValue` | 接收包数 |
| `trainingRepHintValue` | 计数提示 |
| `scoreRing` | 标准度环形图 |
| `trainingScoreValue` | 标准度数字 |
| `trainingSuggestionValue` | 实时纠正建议 |
| `trainingRiskHintValue` | 风险提示 |
| `trainingDepthValue` | 幅度分 |
| `trainingStabilityValue` | 稳定性分 |
| `trainingRhythmValue` | 节奏分 |
| `trainingLatestActionValue` | 最近动作 |
| `trainingLatestScoreValue` | 最近分数 |
| `trainingLatestAdviceValue` | 最近建议 |

重要逻辑：

- 用户训练用标签 `user_auto_training` 保存，不直接用于模型训练。
- 当前动作由模型推理结果或评估结果决定。
- 佩戴说明会根据当前识别动作变化。
- 动作次数由前端根据阶段变化估算。
- 标准度环形图颜色会根据分数变化。

### 2.7 历史报告页 `page-history`

对应路由：

```text
/history
```

页面目标：

> 显示用户训练趋势、进步情况、风险统计和最近训练记录。

关键 DOM：

| id | 作用 |
|---|---|
| `historyProgressValue` | 标准度与上次对比 |
| `historyStabilityProgressValue` | 稳定性与上次对比 |
| `historyRiskList` | 风险统计 |
| `historySessionList` | 最近训练会话 |

渲染逻辑：

```text
renderHistory()
```

游客逻辑：

> 如果未登录，历史报告不展示个人数据，而是提示登录后查看。

### 2.8 调试模式 `page-debug`

对应路由：

```text
/debug
```

页面目标：

> 给开发者维护模型、采集标签数据、查看传感器原始信息，不面向普通用户。

主要模块：

| 模块 | 说明 |
|---|---|
| 系统状态 | 数据库、模型、设备、录制状态 |
| 标签管理 | 创建标签、删除标签、从模型移除标签 |
| 标签采集 | 开发者选择标签采集训练数据 |
| 训练模型记录 | 按列表或时间线查看采集记录，可切换删除模式 |
| 管理员训练模型 | 勾选标签、设置窗口/步长、训练、重载 |
| 传感器实时可视化 | seq、timestamp、flex、ax/ay/az、gx/gy/gz |
| Canvas 图表 | 弯曲 ADC、电压、弯曲指数、加速度、陀螺仪 |
| 原始 JSON | 推理状态、评估状态、最新包 |

关键 DOM：

| id | 作用 |
|---|---|
| `debugDatabaseBadge` | 数据库状态 |
| `debugModelBadge` | 模型状态 |
| `debugConnectionBadge` | 设备状态 |
| `debugRecordingBadge` | 录制状态 |
| `debugDatabaseStateText` | 数据库文字说明 |
| `debugNewLabelInput` | 新标签输入 |
| `debugCreateLabelBtn` | 创建标签 |
| `debugLabelList` | 标签列表 |
| `debugCaptureLabelSelect` | 开发者采集标签选择 |
| `debugCaptureNotesInput` | 开发者采集备注 |
| `debugStartCaptureBtn` | 开始标签采集 |
| `debugStopCaptureBtn` | 结束标签采集 |
| `debugCaptureActiveLabel` | 当前采集标签 |
| `debugCaptureStatusValue` | 当前采集状态 |
| `debugRecordViewType` | 训练记录显示方式 |
| `debugRecordActionType` | 查看/删除模式 |
| `debugRefreshRecordsBtn` | 刷新记录 |
| `debugRecordingsList` | 训练记录列表 |
| `debugRefreshTrainingBtn` | 刷新模型训练状态 |
| `debugClearTrainingBtn` | 清空训练状态 |
| `debugReloadModelBtn` | 重载模型 |
| `debugTrainingLabelCount` | 已选标签数量 |
| `debugSelectAllLabelsBtn` | 全选/取消 |
| `debugTrainingLabels` | 可训练标签勾选区 |
| `debugTrainWindowSize` | 窗口大小 |
| `debugTrainStepSize` | 步长 |
| `debugAutoReloadCheckbox` | 训练成功后自动重载 |
| `debugTrainingRunValue` | 训练运行状态 |
| `debugTrainingStageValue` | 训练阶段 |
| `debugTrainingLastSuccessValue` | 最近成功时间 |
| `debugTrainingSelectedLabelsValue` | 最近训练标签 |
| `debugTrainingSampleCountValue` | 样本数量 |
| `debugTrainingPrepareExitValue` | 数据预处理退出码 |
| `debugTrainingTrainExitValue` | 模型训练退出码 |
| `debugTrainingErrorValue` | 最近错误 |
| `debugStartTrainingBtn` | 开始训练模型 |
| `debugTrainingOutputBox` | 训练日志 |
| `debugSensorSampleTag` | 当前缓存点数 |
| `debugSeqValue` | 数据包序号 |
| `debugTimestampValue` | 设备时间戳 |
| `debugFlexAdcValue` | 弯曲 ADC |
| `debugFlexMvValue` | 弯曲电压 |
| `debugFlexIndexValue` | 弯曲指数 |
| `debugAxValue` / `debugAyValue` / `debugAzValue` | 加速度 |
| `debugGxValue` / `debugGyValue` / `debugGzValue` | 陀螺仪 |
| `flexRawChart` | ADC 和电压图 |
| `flexIndexChart` | 弯曲指数图 |
| `accelChart` | 加速度图 |
| `gyroChart` | 陀螺仪图 |
| `debugInferenceBox` | 推理状态 JSON |
| `debugEvaluationBox` | 评估状态 JSON |
| `debugPacketBox` | 原始包 JSON |

### 2.9 老师可能问

**问：为什么所有页面都在一个 HTML 里？**

答：

> 这是轻量级单页应用设计。后端只托管一个 `index.html`，前端通过 JS 控制路由和页面显隐。这样不需要复杂前端框架，也方便 FastAPI 直接部署。

**问：HTML 里的很多 id 是干什么的？**

答：

> 这些 id 是数据绑定点。`app.js` 通过 `document.getElementById` 找到节点，把后端实时数据、训练结果和用户信息写进去。

---

## 3. `pc_gateway/static/app.js`

### 3.1 文件定位

`app.js` 是网页端最核心的前端逻辑文件。

它负责：

- 单页路由。
- 全局状态。
- 登录注册。
- Token 保存。
- API 请求封装。
- WebSocket 实时数据。
- 设备扫描连接。
- 用户训练。
- 开发者标签采集。
- 模型训练。
- 训练记录删除。
- 传感器历史缓存。
- 动作次数计数。
- Canvas 图表绘制。
- 页面渲染。
- 事件绑定。

### 3.2 顶部常量

#### `ROUTES`

```js
const ROUTES = ["/login", "/dashboard", "/training", "/history", "/debug"];
```

作用：

- 定义合法前端路由。
- `navigate()` 和 `currentRoute()` 都依赖它。

#### `TOKEN_KEY`、`TOKEN_EXP_KEY`

作用：

- 在 `localStorage` 中保存登录 token 和过期时间。

对应键：

```text
smartFitnessAccessToken
smartFitnessAccessTokenExpiry
```

#### `SENSOR_HISTORY_LIMIT`

```js
const SENSOR_HISTORY_LIMIT = 160;
```

作用：

- 最多缓存 160 个传感器点用于画图。
- 避免长时间运行导致浏览器内存一直增长。

#### `USER_AUTO_LABEL`

```js
const USER_AUTO_LABEL = "user_auto_training";
```

作用：

- 普通用户训练时使用的保存标签。
- 表示这不是人工标注训练样本，而是用户训练记录。

#### `NON_TRAINING_LABELS`

```js
const NON_TRAINING_LABELS = new Set([USER_AUTO_LABEL]);
```

作用：

- 模型训练标签列表中排除普通用户训练标签。

### 3.3 标签文本和标签别名

#### `LABEL_TEXT`

内部标签转中文显示：

| 内部标签 | 中文 |
|---|---|
| `idle` | 静止 |
| `squat_standard` | 深蹲-标准 |
| `squat_wrong` | 深蹲-错误 |
| `bench_standard` | 卧推-标准 |
| `bench_wrong` | 卧推-错误 |
| `user_auto_training` | 自动识别训练 |

#### `LABEL_ALIASES`

用户输入的中文或不同写法转标准标签。

例如：

```text
深蹲 -> squat_standard
深蹲错误 -> squat_wrong
卧推 -> bench_standard
卧推纠错 -> bench_wrong
```

作用：

> 防止前端输入“深蹲”“标准深蹲”“深蹲_标准”时产生多个不同目录。

### 3.4 训练动作文本和佩戴说明

#### `TRAINING_ACTION_TEXT`

把标签转成更像用户产品的动作名称：

| 标签 | 用户看到 |
|---|---|
| `squat_standard` | 深蹲训练 |
| `squat_wrong` | 深蹲纠错训练 |
| `bench_standard` | 卧推训练 |
| `bench_wrong` | 卧推纠错训练 |

#### `TRAINING_GUIDES`

这是前端佩戴说明库。

当前包括：

- 自动识别训练通用说明。
- 静止/站立校准说明。
- 深蹲标准佩戴。
- 深蹲错误采集佩戴。
- 卧推标准佩戴。
- 卧推错误采集佩戴。

重要逻辑：

> 训练中心会根据当前识别到的动作自动切换佩戴说明，而不是让用户手动选择标签。

### 3.5 `ROUTE_SUBTITLE`

作用：

- 顶部导航副标题根据路由变化。

例如：

| 路由 | 副标题 |
|---|---|
| `/login` | 账号登录与注册 |
| `/dashboard` | 训练概览与进步反馈 |
| `/training` | 动作识别与实时纠正 |
| `/history` | 历史报告与趋势分析 |
| `/debug` | 开发者工具与模型维护 |

### 3.6 全局状态 `state`

`state` 是前端的内存状态中心。

字段说明：

| 字段 | 作用 |
|---|---|
| `auth` | 登录 token、过期时间、当前用户、注册/登录 tab |
| `labels` | 后端已有标签 |
| `labelCounts` | 每个标签的样本数 |
| `devices` | 扫描到的 BLE 设备 |
| `status` | 网关状态 |
| `inference` | 模型推理状态 |
| `evaluation` | 基础评估状态 |
| `advanced` | 高级评估状态 |
| `report` | 本地报告摘要 |
| `userSummary` | 当前用户报告摘要 |
| `dbStatus` | 数据库状态 |
| `lists.sessions` | 数据库会话列表 |
| `lists.evaluations` | 数据库评估列表 |
| `lists.models` | 数据库模型版本列表 |
| `lists.reports` | 数据库报告列表 |
| `recordings` | 本地训练记录 JSON |
| `trainingJob` | 当前模型训练任务状态 |
| `latestPacket` | 最新传感器包 |
| `packetKey` | 用于去重的数据包签名 |
| `sensorHistory` | 最近传感器历史，用于画图 |
| `socket` | WebSocket 对象 |
| `selectedLabels` | 调试模式中勾选的训练标签 |
| `debugRecordViewType` | 训练记录显示方式 |
| `debugRecordActionType` | 训练记录查看/删除模式 |
| `debugAutoReload` | 模型训练后是否自动重载 |
| `repCounter` | 前端动作次数计数状态 |

答辩说法：

> 这个项目没有引入 Vue/React，所以我用一个 `state` 对象集中管理前端状态，再通过 render 函数刷新 DOM。

### 3.7 DOM 工具函数

#### `$`

```js
const $ = (id) => document.getElementById(id);
```

作用：

- 简化 DOM 查询。

#### `setText(id, value)`

作用：

- 安全设置文本。
- 如果元素不存在，不报错。

#### `setHtml(id, value)`

作用：

- 安全设置 innerHTML。
- 用于渲染列表、卡片、趋势条等。

#### `safeArray(value)`

作用：

- 如果 value 是数组就返回。
- 否则返回空数组。

避免：

```js
undefined.map(...)
```

这种错误。

### 3.8 标签处理函数

#### `canonicalLabel(label)`

作用：

- 将标签规范化。

步骤：

1. 转字符串。
2. trim。
3. 转小写。
4. 空格和连字符替换成下划线。
5. 多个下划线合并。
6. 去掉首尾下划线。
7. 查 `LABEL_ALIASES`。
8. 返回标准标签。

#### `canonicalLabels(labels)`

作用：

- 批量规范化标签。
- 去重。
- 去空。

#### `canonicalLabelCounts(counts)`

作用：

- 合并不同别名标签的样本数量。

例如：

```text
深蹲_错误 + squat_wrong -> squat_wrong 的总数量
```

#### `trainableLabels()`

作用：

- 返回可以参与模型训练的标签。

条件：

- 不在 `NON_TRAINING_LABELS` 中。
- 样本数大于 0。

#### `captureLabels()`

作用：

- 返回开发者采集时可选标签。

区别：

> 采集标签可以是当前还没有样本的标签；训练标签必须有样本。

#### `syncSelectedLabels()`

作用：

- 保证当前勾选的训练标签仍然合法。
- 如果标签被删除或样本数为 0，会从选中列表移除。

#### `labelText(label)`

作用：

- 标签转中文。

#### `trainingActionText(label)`

作用：

- 标签转训练动作名称。

#### `trainingWearGuide(label)`

作用：

- 根据标签返回佩戴说明。
- 如果具体标签没有说明，会按动作大类 fallback。

#### `refreshTrainingActionGuide()`

作用：

- 根据当前模型识别动作更新训练中心佩戴说明。
- 如果当前是静止且没有训练，则显示通用自动识别说明。

### 3.9 格式化和计算函数

#### `riskText(risk)`

风险英文转中文：

| 输入 | 输出 |
|---|---|
| `low` | 低 |
| `medium` | 中 |
| `high` | 高 |
| 其他 | 待评估 |

#### `formatDateTime(value)`

作用：

- 把时间字符串转成本地中文时间。

#### `formatMinutes(value)`

作用：

- 把分钟数字格式化为 `x 分钟`。

#### `estimateCalories(minutes, reps)`

当前公式：

```js
minutes * 5.5 + reps * 0.35
```

含义：

> 当前只是前端展示用估算，不是医学级热量计算。后续如果要更专业，需要加入体重、性别、年龄、动作 MET 值。

#### `isLoggedIn()`

判断是否有 token 且有用户信息。

### 3.10 路由函数

#### `currentRoute()`

作用：

- 读取 `window.location.pathname`。
- 如果不在合法路由中，就返回 `/login`。

#### `navigate(route, replace=false)`

作用：

- 使用 History API 修改 URL。
- 调用 `renderAll()` 刷新页面。

不是：

```text
window.location.href
```

所以页面不会整页刷新。

### 3.11 API 和认证函数

#### `authHeaders()`

作用：

- 如果有 token，返回：

```js
{ Authorization: `Bearer ${token}` }
```

#### `apiFetch(url, options={})`

统一 API 请求封装。

功能：

1. 自动加 `Content-Type: application/json`。
2. 自动加 Authorization。
3. 解析 JSON。
4. 如果 response 不 ok，抛出错误。

好处：

> 所有 API 调用都走同一套错误处理和 token 注入。

#### `rememberToken(token, expiresAt)`

作用：

- 保存 token 到 state。
- 保存 token 到 localStorage。

#### `clearAuth()`

作用：

- 清空 token。
- 清空用户信息。
- 清空用户报告。

#### `setAuthMode(mode)`

作用：

- 切换注册/登录 tab。
- 控制 `registerPanel` 和 `loginPanel` 显隐。

### 3.12 用户数据过滤函数

#### `userSessions()`

作用：

- 如果已登录，只返回当前用户的 sessions。
- 如果游客，返回全部或本地列表。

#### `userEvaluations()`

作用：

- 如果已登录，只返回当前用户的 evaluations。
- 用于 dashboard 和 history。

### 3.13 实时传感器缓存

#### `packetSignature(packet)`

作用：

- 用 `seq-timestampMs` 生成唯一签名。
- 防止同一数据包重复加入历史。

#### `pushPacket(packet)`

作用：

- 接收最新数据包。
- 去重。
- 保存到 `state.latestPacket`。
- 推入 `state.sensorHistory`。
- 超过 160 个点时删除最旧的数据。

### 3.14 动作类型和次数计数

#### `actionFamily(label)`

把标签分成：

- `squat`
- `bench`
- `idle`
- `general`

#### `getFlexSeries()`

返回最近所有 `flexIndex` 序列。

#### `deriveLivePhase(label)`

作用：

- 根据动作类型和 `flexIndex` 变化判断阶段。

深蹲：

- `down`：下蹲中。
- `bottom`：蹲底控制。
- `up`：起身中。
- `rest`：站立准备。
- `transition`：动作过渡。

卧推：

- `down`：下放中。
- `bottom`：下放底部。
- `up`：推起中。
- `rest`：准备姿态。
- `transition`：动作过渡。

核心依据：

```js
latest - previous
```

也就是最近 flexIndex 的变化方向。

#### `resetRepCounter()`

作用：

- 重置次数计数。

结构：

```js
{ count: 0, family: "idle", phases: [] }
```

#### `updateRepCounter(label)`

作用：

- 根据动作阶段序列判断是否完成一次动作。

计数条件：

```text
down > bottom > up > rest
```

或者：

```text
down > up > rest
```

满足后：

```js
count += 1
```

答辩说法：

> 这是前端轻量计数逻辑，基于阶段变化估算次数。后续可以把计数放到后端或模型中，让多端一致。

### 3.15 纠正建议函数

#### `buildSuggestion(label, evaluation)`

作用：

- 根据动作类别和评估分数生成用户看得懂的建议。

判断依据：

- `depthScore`
- `stabilityScore`
- `rhythmScore`
- `standardScore`
- 动作类别

例如：

- 深蹲深度不足：提示继续向后坐髋。
- 稳定性差：提示核心收紧、膝盖方向。
- 卧推不稳：提示肩部控制和发力轨迹。

### 3.16 页面渲染总入口

#### `renderRoute()`

作用：

- 根据当前 URL 显示对应页面。
- 隐藏其他页面。
- 更新导航 active 状态。
- 更新顶部副标题。

#### `renderTopbar()`

作用：

- 更新设备连接状态。
- 更新当前用户。

#### `renderAuth()`

作用：

- 更新登录页状态。
- 更新 token 过期时间。
- 更新登录提示。

#### `renderDashboard()`

作用：

- 渲染个人首页。

它会计算：

- 当前用户 sessions。
- 当前用户 evaluations。
- 最新评估。
- 最新会话。
- 平均分。
- 今日训练时长。
- 总训练时长。
- 热量估算。
- 周趋势。

并更新：

- 今日概览。
- 本周标准度。
- 最近训练。
- 反馈卡片。
- 佩戴说明状态。

#### `renderTraining()`

作用：

- 渲染训练中心。

它会更新：

- 设备下拉框。
- 当前动作。
- 当前阶段。
- 次数。
- 风险。
- 标准度环形图。
- 佩戴说明。
- 动作质量指标。
- 训练按钮可用状态。

按钮禁用规则：

| 按钮 | 禁用条件 |
|---|---|
| 扫描 | 未登录 |
| 连接 | 未登录或已连接 |
| 断开 | 未登录或未连接 |
| 开始训练 | 未登录、未连接或已训练中 |
| 完成训练 | 未登录或未训练中 |

#### `renderHistory()`

作用：

- 渲染历史报告。

逻辑：

- 未登录：提示登录。
- 已登录：计算最近两次评分差值。
- 统计风险次数。
- 渲染最近 5 条训练记录。

#### `renderDebugRecordings()`

作用：

- 渲染调试模式训练记录。

支持：

- 普通列表。
- 时间线。
- 查看模式。
- 删除模式。

#### `renderDebugLabels()`

作用：

- 渲染标签管理列表。

每个标签包含：

- 中文名称。
- 内部标签名。
- 样本数量。
- 从模型移除按钮。
- 删除标签按钮。

#### `trainingPhaseText(phase)`

把模型训练阶段转中文：

| phase | 中文 |
|---|---|
| `idle` | 空闲 |
| `queued` | 排队中 |
| `preparing` | 数据预处理中 |
| `training` | 模型训练中 |
| `reloading` | 模型重载中 |
| `completed` | 训练完成 |
| `failed` | 训练失败 |

#### `renderLabelChecklist()`

作用：

- 渲染模型训练标签勾选区。
- 样本数为 0 的标签禁用。
- 使用卡片方式模拟 checkbox。

#### `renderDebugSystemStatus()`

作用：

- 更新数据库、模型、连接、录制状态。

#### `renderDebugTrainingPanel()`

作用：

- 渲染整个调试模式训练区域。

包括：

- 标签管理。
- 采集标签选择。
- 训练按钮。
- 自动重载。
- 训练阶段。
- 训练日志。
- 训练记录。

#### `renderDebugLiveData()`

作用：

- 渲染调试模式传感器数据。

包括：

- 最新包 JSON。
- 推理 JSON。
- 评估 JSON。
- seq。
- timestamp。
- flexRawAdc。
- flexRawMv。
- flexIndex。
- ax/ay/az。
- gx/gy/gz。
- 调用 `drawAllCharts()` 画图。

#### `renderDebug()`

组合：

```js
renderDebugTrainingPanel();
renderDebugLiveData();
```

#### `renderAll()`

全量渲染入口。

调用：

- renderRoute。
- renderTopbar。
- renderAuth。
- renderDashboard。
- renderTraining。
- renderHistory。
- renderDebug。

### 3.17 Canvas 图表函数

#### `setupCanvas(id)`

作用：

- 根据 CSS 尺寸设置 canvas 实际像素。
- 适配高分屏 `devicePixelRatio`。
- 返回 ctx、width、height。

#### `drawChart(id, series)`

作用：

- 画一张折线图。

逻辑：

1. 清空画布。
2. 如果没有传感器历史，显示等待数据。
3. 自动计算最小值和最大值。
4. 画水平网格线。
5. 对每个 series 画折线。

#### `drawAllCharts()`

画四张图：

| Canvas | 数据 |
|---|---|
| `flexRawChart` | `flexRawAdc`、`flexRawMv` |
| `flexIndexChart` | `flexIndex` |
| `accelChart` | `ax`、`ay`、`az` |
| `gyroChart` | `gx`、`gy`、`gz` |

### 3.18 数据加载函数

#### `loadCurrentUser()`

作用：

- 如果有 token，调用：

```text
/api/auth/me
/api/report/user-summary
```

- 如果失败，清空登录状态。

#### `loadBaseData()`

作用：

- 并行加载前端所需基础数据。

请求包括：

- `/api/status`
- `/api/labels`
- `/api/inference/status`
- `/api/evaluation/status`
- `/api/evaluation/server-status`
- `/api/report/summary`
- `/api/database/status`
- `/api/models/training/status`
- `/api/recordings`
- `/api/database/sessions`
- `/api/database/evaluations`
- `/api/database/models`
- `/api/database/reports`
- 当前用户信息。

使用：

```js
Promise.allSettled(tasks)
```

原因：

> 某些接口失败时，不影响其他数据加载。例如数据库未启用，也不应该导致整个页面崩掉。

### 3.19 WebSocket 函数

#### `openSocket()`

作用：

- 连接 `/ws/live`。
- 接收实时后端事件。
- 根据事件更新 state 和局部页面。

协议选择：

```js
window.location.protocol === "https:" ? "wss:" : "ws:"
```

事件处理：

| event | 作用 |
|---|---|
| `status` | 更新网关状态 |
| `packet` | 更新最新传感器包和图表 |
| `prediction` | 更新模型预测 |
| `recording_started` | 调试页刷新采集状态 |
| `recording_stopped` | 调试页刷新采集状态 |
| `error` | 调试页显示错误 |
| `inference_status` | 更新推理状态 |
| `evaluation_status` | 更新评估状态 |
| `advanced_evaluation_status` | 更新高级评估 |
| `report_summary` | 更新报告 |
| `model_training_status` | 更新模型训练状态 |

断线重连：

```js
socket.addEventListener("close", () => {
  window.setTimeout(openSocket, 2000);
});
```

### 3.20 用户操作函数

#### `registerUser()`

作用：

- 注册账号。
- 注册成功后立即登录。
- 保存 token。
- 加载数据。
- 跳转个人首页。

这是你之前要求的：

> 注册成功直接进入，不用再手动登录。

#### `loginUser()`

作用：

- 登录。
- 保存 token。
- 加载数据。
- 进入个人首页。

#### `logoutUser()`

作用：

- 清空 token。
- 重置计数器。
- 跳转登录页。

### 3.21 设备操作函数

#### `scanDevices()`

调用：

```text
GET /api/devices/scan
```

更新：

```js
state.devices
```

#### `connectDevice()`

调用：

```text
POST /api/device/connect
```

发送：

```js
{
  address: deviceSelect.value,
  device_name: "ESP32S3_Fitness_BLE"
}
```

#### `disconnectDevice()`

调用：

```text
POST /api/device/disconnect
```

### 3.22 训练和采集函数

#### `startRecording(label, notes)`

通用采集入口。

前置检查：

- label 不能为空。
- 设备必须连接。
- 当前不能已经在采集中。

调用：

```text
POST /api/recordings/start
```

发送：

- label。
- subject_id。
- notes。

#### `startUserTraining()`

普通用户训练入口。

调用：

```js
startRecording(USER_AUTO_LABEL, notes)
```

重点：

> 用户训练不需要选择标签，统一保存为自动识别训练记录。

#### `startDeveloperCapture()`

开发者标签采集入口。

从调试模式选择：

```js
debugCaptureLabelSelect
```

然后调用 `startRecording(label, notes)`。

#### `stopRecording()`

调用：

```text
POST /api/recordings/stop
```

停止后重新加载基础数据。

### 3.23 网页端反馈说明

当前网页端训练中心只展示文字纠正建议和动作质量指标。

网页端不再提供语音开关，原因是 PC 网页更适合做训练可视化、报告展示和开发者调试；语音反馈保留在安卓端和后续设备端，更符合用户训练时不盯着电脑屏幕的使用场景。

### 3.24 标签和模型函数

#### `createLabel()`

作用：

- 创建新标签。
- 调用 `/api/labels`。
- 更新标签列表。

#### `deleteLabel(label)`

作用：

- 删除标签和对应 CSV/JSON。
- 删除数据库对应会话。
- 不会自动改变已有模型。

弹窗会提醒：

> 当前已经训练好的模型文件不会自动删除；如果要让模型不再使用这个标签，需要删除后重新训练并重载模型。

#### `removeLabelFromModel(label)`

作用：

- 从模型中移除某标签。

本质：

> 不删除原始数据，而是用剩余标签重新训练模型。

#### `toggleSelectAllLabels()`

作用：

- 全选或取消所有可训练标签。

#### `toggleTrainingLabel(label)`

作用：

- 切换某个标签是否参与训练。
- 样本数为 0 的标签不允许选。

#### `resetModelTrainingStatus()`

调用：

```text
POST /api/models/training/reset
```

作用：

- 清空模型训练状态。

#### `startModelTraining()`

调用：

```text
POST /api/models/train
```

发送：

- labels。
- window_size。
- step_size。
- auto_reload。

#### `reloadModel()`

调用：

```text
POST /api/inference/reload
```

作用：

- 让后端重新加载最新模型文件。

#### `deleteRecording(sessionId)`

调用：

```text
DELETE /api/recordings/{sessionId}
```

作用：

- 删除某次训练记录对应的 CSV、JSON 和数据库记录。

### 3.25 事件绑定 `bindEvents()`

这是所有按钮点击和页面事件绑定的集中位置。

绑定内容：

- 导航点击。
- 浏览器后退/前进。
- 注册/登录 tab。
- 注册按钮。
- 登录按钮。
- 退出登录。
- 游客进入。
- 进入调试模式。
- 首页开始训练。
- 历史报告按钮。
- 扫描设备。
- 连接设备。
- 断开设备。
- 开始训练。
- 结束训练。
- 更新训练反馈。
- 创建标签。
- 删除标签。
- 从模型移除标签。
- 开发者采集。
- 模型训练。
- 重载模型。
- 训练记录视图切换。
- 训练记录删除。
- 标签勾选。
- 窗口大小变化时重绘图表。

其中调试模式列表采用事件委托：

```js
debugLabelList.addEventListener("click", ...)
debugTrainingLabels.addEventListener("click", ...)
debugRecordingsList.addEventListener("click", ...)
```

为什么：

> 调试列表会频繁重新渲染，如果每次给每个按钮单独绑定事件，容易丢事件或重复绑定。事件委托只绑定父容器，更稳定。

### 3.26 页面启动

最后：

```js
document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  setAuthMode("register");
  renderAll();
  await loadBaseData();
  openSocket();
});
```

启动顺序：

1. 绑定事件。
2. 默认注册模式。
3. 初始渲染。
4. 加载后端数据。
5. 打开 WebSocket。

### 3.27 老师可能问

**问：为什么不用 Vue/React？**

答：

> 当前项目核心难点在硬件、BLE、模型和后端，前端用原生 SPA 可以降低依赖，直接由 FastAPI 托管，部署和调试更简单。

**问：前端计数准不准？**

答：

> 当前次数是基于 flexIndex 阶段变化的轻量计数，适合演示和原型。后续可以把计数逻辑移动到后端，结合模型和更多传感器提高准确性。

**问：调试模式为什么有原始数据？**

答：

> 原始数据对开发者很重要，比如确认传感器是否工作、是否饱和、模型输入是否正常。但普通用户不需要这些，所以只放在调试模式。

---

## 4. `pc_gateway/static/styles.css`

### 4.1 文件定位

`styles.css` 是网页端完整视觉系统。

它负责：

- 全局颜色。
- 字体。
- 背景。
- 顶部导航。
- 卡片。
- 表单。
- 按钮。
- 首页布局。
- 训练页布局。
- 历史页布局。
- 调试页布局。
- 图表样式。
- 响应式适配。
- 动画效果。

### 4.2 全局变量 `:root`

文件顶部使用 CSS 变量定义设计系统。

常见变量类型：

| 类型 | 说明 |
|---|---|
| 主色 | 活力橙 |
| 辅助色 | 健康绿 |
| 背景色 | 米白、浅暖色 |
| 文字色 | 深棕/黑 |
| 边框色 | 浅米色 |
| 阴影 | 柔和阴影 |
| 圆角 | 大圆角卡片 |

答辩说法：

> 我用 CSS 变量统一颜色和视觉风格，后续如果要改主题，只需要集中改变量。

### 4.3 全局布局

#### `body`

负责：

- 页面背景。
- 字体。
- 默认文字颜色。
- 去掉默认 margin。

#### `body::before` 和 `body::after`

作用：

- 做背景氛围光和渐变装饰。
- 避免页面是纯白背景。

#### `.app-shell`

网页最外层容器。

作用：

- 控制最大宽度。
- 控制页面左右间距。

#### `.route-shell`

页面内容容器。

#### `.route-page` 和 `.route-page.hidden`

作用：

- 控制 SPA 页面显隐。
- `.hidden` 强制隐藏。

### 4.4 顶部导航样式

相关选择器：

- `.topbar`
- `.brand-block`
- `.brand-mark`
- `.brand-title`
- `.brand-subtitle`
- `.main-nav`
- `.nav-link`
- `.nav-link.active`
- `.nav-button-link`
- `.topbar-side`
- `.topbar-status`
- `.status-dot`
- `.status-online`
- `.status-offline`
- `.user-pill`

设计特点：

- 顶部导航是圆角白色胶囊卡片。
- 当前路由高亮。
- 在线状态用绿色圆点。
- 离线状态用灰色圆点。
- 设置按钮保留为导航入口，但语义上进入开发者/调试模式。

### 4.5 通用组件样式

#### 卡片

相关：

- `.hero-card`
- `.panel`
- `.dashboard-hero`
- `.stat-card`
- `.summary-item`
- `.guide-card`
- `.risk-item`
- `.history-session-card`
- `.label-check-item`
- `.chart-card`

共同特点：

- 大圆角。
- 浅色背景。
- 柔和阴影。
- 内部留白较大。
- 边框很浅。

#### 按钮

相关：

- `button`
- `.secondary-btn`
- `.ghost-btn`
- `.danger-btn`
- `.text-btn`
- `.settings-btn`

语义：

| 样式 | 用途 |
|---|---|
| 默认按钮 | 主要操作，例如开始训练 |
| `.secondary-btn` | 次要正向操作 |
| `.ghost-btn` | 弱化操作 |
| `.danger-btn` | 删除、结束、危险操作 |
| `.text-btn` | 文本链接按钮 |

#### 表单

相关：

- `.field`
- `.checkbox-field`
- input
- select
- textarea

设计：

- 大圆角输入框。
- 边框浅。
- 聚焦时有主色反馈。

### 4.6 登录页样式

相关：

- `.login-layout`
- `.hero-panel`
- `.auth-card`
- `.auth-tabs`
- `.auth-tab`
- `.auth-tab.active`
- `.auth-panel`
- `.auth-meta`

设计逻辑：

- 左侧介绍平台。
- 右侧登录注册。
- 注册和登录用 tab 切换。
- 状态信息放在 auth meta 中。

### 4.7 首页 Dashboard 样式

相关：

- `.dashboard-topline`
- `.dashboard-layout`
- `.dashboard-main-column`
- `.dashboard-side-column`
- `.dashboard-hero`
- `.dashboard-hero-copy`
- `.dashboard-hero-metrics`
- `.dashboard-hero-art`
- `.art-orbit`
- `.art-leaf`
- `.art-device-cube`
- `.art-fabric`
- `.art-chip`
- `.art-ribbon`
- `.art-signal`
- `.dashboard-grid`
- `.profile-summary`
- `.today-metric-grid`
- `.weekly-score-card`
- `.mini-score-ring`
- `.compact-trend`
- `.dashboard-recent-summary`
- `.recent-row`
- `.dashboard-cta-card`
- `.feedback-card`
- `.side-score-ring`
- `.coach-card`
- `.dashboard-guide-panel`

视觉目标：

> 让首页看起来像成熟的运动健康平台，而不是实验室监控台。

首页插画是 CSS 画出来的：

- 植物叶子。
- 设备小方块。
- 训练布料。
- 传感器芯片。
- 信号波纹。

不是图片文件，所以不用额外资源。

### 4.8 训练中心样式

相关：

- `.training-grid`
- `.training-side`
- `.training-main`
- `.training-summary`
- `.training-feedback-grid`
- `.training-score-strip`
- `.training-mode-card`
- `.training-step-card`
- `.step-index`
- `.score-ring`
- `.score-ring-inner`

布局：

- 左侧：流程、连接、按钮。
- 右侧：实时反馈、环形分数、建议。

`score-ring` 使用 CSS 变量控制进度：

```css
--score-value
--score-accent
--score-shade
```

JS 会根据评分修改这些变量。

### 4.9 历史报告样式

相关：

- `.history-grid`
- `.risk-list`
- `.risk-item`
- `.history-session-list`
- `.history-session-card`
- `.history-session-meta`

展示：

- 进步分析。
- 风险统计。
- 最近训练记录。

### 4.10 调试模式样式

相关：

- `.debug-grid`
- `.debug-label-list`
- `.debug-label-item`
- `.debug-label-actions`
- `.debug-record-card`
- `.debug-collapsible-panel`
- `.debug-collapse-summary`
- `.debug-record-toolbar`
- `.debug-record-timeline`
- `.debug-record-timeline-item`
- `.label-checklist`
- `.label-check-item`
- `.label-check-item-disabled`
- `.training-admin-grid`
- `.debug-live-grid`
- `.debug-live-card`
- `.debug-axis-card`
- `.debug-axis-grid`
- `.debug-axis-values`
- `#debugTrainingOutputBox`
- `#debugPacketBox`
- `#debugInferenceBox`
- `#debugEvaluationBox`

调试模式特点：

- 信息密度更高。
- 支持标签卡片。
- 支持训练记录折叠和时间线。
- 支持原始 JSON 显示。
- 支持图表卡片。

### 4.11 标签勾选样式

相关：

```css
.label-check-item
.label-check-item input
.label-check-copy
.label-check-item:hover
.label-check-item:has(input:checked)
.label-check-item-disabled
```

设计重点：

- 整个卡片可点击。
- checkbox 本身不直接响应 pointer，避免和卡片点击重复触发。
- 选中时用边框和背景高亮。
- 样本数为 0 的标签灰掉并不可选。

这对应之前修复过的：

> 勾选要点很多次才能勾上的问题。

### 4.12 Canvas 图表样式

相关：

- `.chart-card`
- `.chart-card canvas`
- `.chart-card .small-label`

图表本身由 `app.js` 的 Canvas API 绘制，CSS 负责卡片容器和尺寸。

### 4.13 响应式布局

文件底部有多个媒体查询：

```css
@media (max-width: 1200px)
@media (max-width: 980px)
@media (max-width: 720px)
```

作用：

- 大屏：多列布局。
- 中屏：减少列数。
- 小屏：卡片纵向堆叠。
- 导航和按钮适配窄屏。

答辩说法：

> 网页前端做了响应式设计，在电脑浏览器和较窄窗口下都能正常展示。

### 4.14 老师可能问

**问：你这个页面为什么看起来不像传统后台？**

答：

> 因为项目定位是智能健身训练平台，所以普通用户端采用运动健康产品风格；专业数据放到调试模式，避免首页像实验室监控台。

**问：样式怎么统一？**

答：

> 通过 `:root` CSS 变量统一颜色、圆角、阴影和背景，所有组件复用同一套视觉语言。

---

## 5. 安卓端界面资源总览

安卓端前端资源位于：

```text
esp32s3/app/src/main/res/
```

主要目录：

| 目录 | 作用 |
|---|---|
| `layout/` | 页面布局 XML |
| `values/` | 文案、颜色、主题 |
| `values-night/` | 夜间主题 |
| `drawable/` | 背景、卡片、按钮、图标形状 |
| `mipmap-anydpi/` | 启动图标引用 |
| `xml/` | 备份和数据导出规则 |

安卓界面不是网页 HTML，而是原生 Android XML 布局。

---

## 6. `activity_auth.xml`

路径：

```text
esp32s3/app/src/main/res/layout/activity_auth.xml
```

### 6.1 文件定位

这是安卓 App 的登录/注册页面布局。

对应 Java：

```text
AuthActivity.java
```

### 6.2 页面功能

用户在这个页面可以：

- 填写 PC 网关后端地址。
- 输入用户名。
- 输入密码。
- 注册账号。
- 登录账号。
- 游客浏览。

### 6.3 关键控件

| id | 作用 |
|---|---|
| `tvAuthStatus` | 当前认证状态提示 |
| `tvAuthHint` | 登录/注册说明 |
| `etBackendUrl` | 后端地址输入框 |
| `etAuthUsername` | 用户名输入框 |
| `etAuthPassword` | 密码输入框 |
| `btnRegister` | 注册按钮 |
| `btnLogin` | 登录按钮 |
| `btnGuest` | 游客浏览按钮 |

### 6.4 和网页端的关系

安卓端填写的后端地址应该是：

```text
http://电脑局域网IP:8787
```

它调用的后端接口和网页一致：

- `/api/auth/register`
- `/api/auth/login`
- `/api/auth/me`

所以手机和电脑账号互通。

### 6.5 老师可能问

**问：为什么手机要填服务器地址？**

答：

> 当前 PC 网关运行在本机电脑上，手机需要通过局域网 IP 找到电脑后端。正式部署到云服务器后，可以把地址固定在配置里。

---

## 7. `activity_main.xml`

路径：

```text
esp32s3/app/src/main/res/layout/activity_main.xml
```

### 7.1 文件定位

这是安卓 App 主页面布局。

对应 Java：

```text
MainActivity.java
```

它相当于手机端的单页应用容器，通过不同页面容器的显隐切换：

- 首页。
- 训练。
- 指导。
- 报告。
- 设置。
- 调试模式。

### 7.2 首页区域

关键 id：

| id | 作用 |
|---|---|
| `pageHome` | 首页容器 |
| `tvStatus` | 连接/训练状态 |
| `tvAccountMode` | 登录模式 |
| `tvAccountUser` | 当前用户 |
| `tvAccountBackend` | 后端地址 |

首页目标：

> 展示当前账号、后端、设备状态和训练概览，避免显示过多原始数据。

### 7.3 训练区域

关键 id：

| id | 作用 |
|---|---|
| `pageTraining` | 训练页容器 |
| `etActionLabel` | 本地记录名或标签输入 |
| `btnScan` | 扫描 BLE 设备 |
| `btnDisconnect` | 断开设备 |
| `btnStartRecord` | 开始训练 |
| `btnStopRecord` | 结束训练 |
| `tvEvalAction` | 当前动作 |
| `tvEvalPhase` | 当前阶段 |
| `tvEvalScore` | 标准度评分 |
| `tvEvalRisk` | 风险等级 |
| `tvVoiceStatus` | 语音状态 |
| `tvEvalSuggestion` | 纠正建议 |
| `btnVoiceToggle` | 语音开关 |

训练页目标：

> 手机端不做模型训练，主要做轻量级动作识别、实时评分、建议和语音反馈展示。

### 7.4 佩戴指导区域

关键 id：

| id | 作用 |
|---|---|
| `pageGuide` | 佩戴说明和动作指导页 |

内容来自 `strings.xml` 中的佩戴说明文本。

主要说明：

- 深蹲传感器放哪里。
- 卧推传感器放哪里。
- 动作要点。
- 设备状态检查。

### 7.5 报告区域

关键 id：

| id | 作用 |
|---|---|
| `pageReport` | 报告页容器 |
| `tvRecordStatus` | 训练记录状态 |
| `tvRecordCount` | 采样点数 |
| `tvRecordFile` | 本地保存文件 |

报告页当前更偏本地训练摘要，后续可以继续接入后端历史报告。

### 7.6 设置和调试区域

关键 id：

| id | 作用 |
|---|---|
| `pageSettings` | 设置页 |
| `btnToggleDebug` | 打开/关闭调试模式 |
| `btnSwitchAccount` | 切换账号 |
| `layoutDebugSection` | 调试模式区域 |
| `tvSequence` | 数据包序号 |
| `tvTimestamp` | 时间戳 |
| `tvAcceleration` | 加速度 |
| `tvGyroscope` | 陀螺仪 |
| `tvFlexAdc` | 弯曲 ADC |
| `tvFlexMv` | 弯曲电压 |
| `tvFlexIndex` | 弯曲指数 |
| `tvRawPacket` | 原始包 |

设计原则：

> 原始传感器数据默认隐藏在设置里的调试模式，普通用户不直接看到。

### 7.7 底部导航

关键 id：

| id | 作用 |
|---|---|
| `btnNavHome` | 首页 |
| `btnNavTraining` | 训练 |
| `btnNavGuide` | 指导 |
| `btnNavReport` | 报告 |
| `btnNavSettings` | 设置 |

这对应你后来要求的：

> 手机端不要把所有内容都堆在一个页面，而是要像正常 App 一样有页面切换和菜单栏。

### 7.8 老师可能问

**问：手机端和网页端页面逻辑一样吗？**

答：

> 大方向一致，都是登录、首页、训练、指导、报告、设置/调试。但手机端更强调移动训练和语音反馈，网页端更适合模型训练和开发者调试。

---

## 8. `strings.xml`

路径：

```text
esp32s3/app/src/main/res/values/strings.xml
```

### 8.1 文件定位

这是安卓端文案集中管理文件。

它包含：

- App 名称。
- 登录页文案。
- 按钮文案。
- 首页文案。
- 训练页文案。
- 佩戴说明。
- 历史报告。
- 设置和调试。
- 蓝牙状态。
- 录制状态。
- 动作评估文案。
- 语音反馈文案。

### 8.2 为什么文案不直接写在 XML 里

好处：

1. 统一管理中文文案。
2. 后续方便修改。
3. 支持国际化。
4. Java 代码可以通过 `R.string.xxx` 复用。

### 8.3 主要文案分组

| 前缀 | 说明 |
|---|---|
| `auth_` | 登录注册页面 |
| `account_` | 账号和设备 |
| `home_` | 首页 |
| `training_` | 训练中心 |
| `evaluation_` / `eval_` | 实时评估 |
| `record_` | 训练记录 |
| `guide_` | 佩戴说明 |
| `history_` | 历史报告 |
| `settings_` | 设置 |
| `debug_` | 调试模式 |
| `btn_` | 按钮 |
| `nav_` | 底部导航 |
| `metric_` | 传感器指标 |
| `status_` | BLE 状态 |

### 8.4 注意编码

如果在某些工具中看到中文乱码，优先检查：

- 文件是否以 UTF-8 保存。
- Android Studio 是否按 UTF-8 打开。
- Gradle 编译资源是否正常。

答辩时不必主动提乱码，除非老师看到源码问。

---

## 9. `colors.xml`

路径：

```text
esp32s3/app/src/main/res/values/colors.xml
```

### 9.1 文件定位

安卓端颜色资源文件。

用于统一：

- 主色橙色。
- 健康绿。
- 背景色。
- 文字色。
- 卡片色。
- 风险色。

### 9.2 为什么使用颜色资源

答辩说法：

> 安卓端颜色统一放在 `colors.xml`，布局 XML 和主题都引用这里，方便保持手机端和网页端视觉一致。

---

## 10. `themes.xml` 和 `values-night/themes.xml`

路径：

```text
esp32s3/app/src/main/res/values/themes.xml
esp32s3/app/src/main/res/values-night/themes.xml
```

### 10.1 文件定位

安卓主题配置。

作用：

- 设置 App 使用 Material 风格。
- 设置状态栏颜色。
- 设置导航栏颜色。
- 控制亮色/暗色主题。

### 10.2 `values-night`

这是 Android 夜间模式资源目录。

当系统处于深色模式时，Android 会优先读取：

```text
values-night/themes.xml
```

### 10.3 老师可能问

**问：网页和手机视觉怎么统一？**

答：

> 网页用 CSS 变量，安卓用 colors 和 themes，两个端都围绕活力橙、健康绿、浅暖背景、大圆角卡片设计。

---

## 11. `drawable/*.xml`

这些文件是安卓端界面形状资源。

它们不是业务逻辑，而是 UI 视觉素材。

### 11.1 文件逐个说明

| 文件 | 作用 |
|---|---|
| `app_background.xml` | App 全局背景，通常是浅色或渐变背景 |
| `auth_chip_green.xml` | 登录页绿色标签背景 |
| `auth_chip_orange.xml` | 登录页橙色标签背景 |
| `auth_orange_badge.xml` | 登录页橙色 SF 标识背景 |
| `auth_sync_surface.xml` | 登录页同步说明卡片背景 |
| `bottom_nav_surface.xml` | 底部导航栏背景 |
| `debug_surface.xml` | 调试模式区域背景 |
| `hero_surface.xml` | 首页 Hero 卡片背景 |
| `ic_launcher_background.xml` | App 启动图标背景 |
| `ic_launcher_foreground.xml` | App 启动图标前景 |
| `live_feedback_surface.xml` | 实时反馈卡片背景 |
| `metric_surface.xml` | 指标卡片背景 |
| `nav_button_bg.xml` | 底部导航按钮选中背景 |
| `panel_surface.xml` | 通用面板卡片背景 |
| `step_number_surface.xml` | 步骤编号圆形背景 |
| `workflow_step_surface.xml` | 训练流程步骤卡片背景 |

### 11.2 这些文件一般包含什么

通常是：

```xml
<shape>
  <solid />
  <corners />
  <stroke />
  <padding />
</shape>
```

或 vector 图形。

### 11.3 老师可能问

**问：安卓界面的圆角卡片怎么做的？**

答：

> 主要通过 `drawable` 里的 shape XML 实现，例如 `panel_surface.xml`、`metric_surface.xml`、`hero_surface.xml`，布局文件中设置为 background。

---

## 12. `mipmap-anydpi/ic_launcher.xml` 和 `ic_launcher_round.xml`

路径：

```text
esp32s3/app/src/main/res/mipmap-anydpi/ic_launcher.xml
esp32s3/app/src/main/res/mipmap-anydpi/ic_launcher_round.xml
```

### 12.1 文件定位

安卓启动图标配置。

作用：

- 定义普通图标。
- 定义圆形图标。
- 引用 foreground 和 background drawable。

答辩时一般不用细讲。

---

## 13. `xml/backup_rules.xml` 和 `data_extraction_rules.xml`

路径：

```text
esp32s3/app/src/main/res/xml/backup_rules.xml
esp32s3/app/src/main/res/xml/data_extraction_rules.xml
```

### 13.1 文件定位

Android 系统备份和数据导出规则。

作用：

- 控制哪些 App 数据可以备份。
- 控制哪些数据可以被系统迁移或导出。

这些是 Android Studio 项目模板中常见配置，不是本项目核心业务。

### 13.2 老师可能问

**问：这些 xml 和你的业务有关吗？**

答：

> 不是核心业务，属于 Android 项目基础配置。真正界面主要在 `layout`、`drawable`、`values`，业务逻辑在 Java Activity。

---

## 14. 网页端和安卓端前端的区别

| 对比项 | 网页端 | 安卓端 |
|---|---|---|
| 技术 | HTML/CSS/JavaScript | Android XML + Java |
| 运行位置 | PC 网关浏览器 | 手机 App |
| 页面切换 | History API + DOM 显隐 | Java 控制 View 显隐 |
| 实时数据 | WebSocket 从 PC 网关接收 | BLE 直接接收或后端同步 |
| 模型训练 | 调试模式支持 | 不支持 |
| 原始数据 | `/debug` 显示 | 设置里的调试模式显示 |
| 语音 | 不提供用户侧语音开关，显示文字建议 | Android TextToSpeech |
| 用户系统 | 调用 FastAPI | 调用同一 FastAPI |

---

## 15. 老师可能刁难的问题与回答

### 15.1 为什么前端不用框架？

答：

> 当前项目核心是硬件采集、BLE、机器学习和实时反馈。前端使用原生 HTML/CSS/JS，可以减少依赖和构建流程，FastAPI 直接托管静态文件就能运行。对于毕业设计原型来说更稳定、部署更简单。

### 15.2 没有 Vue/React，状态怎么管理？

答：

> 我在 `app.js` 中用一个统一的 `state` 对象管理前端状态，包括用户、设备、模型、评估、传感器历史和训练任务。数据变化后调用对应 render 函数更新 DOM。

### 15.3 WebSocket 在前端起什么作用？

答：

> WebSocket 用于实时接收后端推送的传感器数据、推理结果、评估结果和模型训练状态。相比轮询，延迟更低，也更适合实时训练反馈。

### 15.4 为什么调试模式里显示原始数据，首页不显示？

答：

> 首页面向普通用户，只显示动作、次数、评分和建议；原始 ADC、IMU 和模型日志属于开发者信息，放在调试模式可以降低用户理解成本。

### 15.5 删除标签和从模型移除标签按钮有什么区别？

答：

> 删除标签会删除该标签下的原始 CSV/JSON 采集数据和数据库会话；从模型移除标签不会删除原始数据，而是用剩余标签重新训练模型，让新模型不再预测这个标签。

### 15.6 为什么手机端也有调试模式？

答：

> 手机端普通页面不展示专业数据，但在设备调试时需要确认 BLE 数据、弯曲 ADC、IMU 六轴是否正常，所以把这些内容隐藏在设置里的调试模式中。

### 15.7 前端的次数计数是后端算的吗？

答：

> 当前网页端次数是前端根据 flexIndex 阶段变化估算的，属于轻量逻辑。后续可以把计数放到后端或模型中，使网页和手机端结果完全一致。

### 15.8 热量是怎么来的？

答：

> 当前热量是前端估算值，公式是训练分钟数乘以一个系数，再加动作次数修正。它用于展示趋势，不是医学级计算。后续可以加入体重、年龄、性别和动作 MET 值。

### 15.9 手机端和网页端账号为什么能互通？

答：

> 因为它们都调用同一个 FastAPI 后端认证接口，并使用同一个 MySQL 数据库保存用户和 token。

### 15.10 为什么 `index.html` 里 id 很多？

答：

> 因为这是原生 JS 前端，id 相当于数据绑定点。`app.js` 根据后端数据找到对应 id，把实时状态和训练结果写进去。

---

## 16. 最建议你背熟的前端文件

如果时间有限，优先背：

| 文件 | 必背原因 |
|---|---|
| `pc_gateway/static/app.js` | 前端所有交互和数据流核心 |
| `pc_gateway/static/index.html` | 页面结构和用户/调试模式分区 |
| `pc_gateway/static/styles.css` | UI 设计和响应式布局 |
| `activity_main.xml` | 手机端主界面结构 |
| `activity_auth.xml` | 手机端账号登录和后端地址 |
| `strings.xml` | 手机端文案和语音/状态提示 |

一句话背法：

> `index.html` 放页面，`app.js` 管逻辑，`styles.css` 管样式；安卓端 `activity_auth.xml` 管登录，`activity_main.xml` 管主界面，`strings/colors/drawable` 管文案和视觉。

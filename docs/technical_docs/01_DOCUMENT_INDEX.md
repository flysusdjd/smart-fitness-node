# 技术文档总目录

这个文件夹用于统一存放项目说明、技术答辩、采集规范、数据库说明和工具使用文档。

统一目录位置：

```text
C:\Users\flysusdjd\Documents\New project 3\docs\technical_docs
```

文件已经按推荐阅读顺序加了数字前缀。Windows 文件夹里按“名称”排序后，从上到下就是建议阅读顺序。

---

## 文档清单

| 顺序 | 文档文件 | 主要内容 | 什么时候看 | 答辩/检查重点 |
|---:|---|---|---|---|
| 1 | `01_DOCUMENT_INDEX.md` | 当前总目录，说明 17 份技术文档的用途和阅读顺序 | 打开文档文件夹后先看 | 快速知道该看哪份文档 |
| 2 | `02_FINAL_CHECK_DEMO_SCRIPT.md` | 最终检查现场演示脚本，包含启动、登录、训练、报告、调试模式、手机端和异常补救 | 检查当天照着演示 | 回答“现场怎么展示项目”“如果设备/网页/手机出问题怎么补救” |
| 3 | `03_TEACHER_QA_CHEATSHEET.md` | 老师高频追问速查表，包含短答、展开和注意事项 | 最后一天快速背 | 快速回答机器学习、硬件、BLE、数据库、前端、安卓、局限性等问题 |
| 4 | `04_PROJECT_TECHNICAL_DEFENSE_GUIDE.md` | 项目总架构、设备端、PC 网关、网页端、安卓端、机器学习、数据库、技术栈、完成度、老师问答 | 最终检查前系统理解项目 | 回答“项目整体怎么实现”“设备端/服务端/网关怎么区分”“当前完成了哪些功能” |
| 5 | `05_PYTHON_FILES_DETAILED_GUIDE.md` | 每个 `.py` 文件的详细说明，包括 `api.py`、`service.py`、`inference.py`、`evaluation.py`、数据库和训练脚本 | 老师问后端代码时看 | 回答“每个 Python 文件干什么”“模型训练流程怎么走”“实时数据怎么处理” |
| 6 | `06_FRONTEND_FILES_DETAILED_GUIDE.md` | 网页端 `index.html/app.js/styles.css` 和安卓 XML 界面资源的详细说明 | 老师问前端、页面逻辑、UI 结构时看 | 回答“前端页面怎么组织”“WebSocket 怎么更新页面”“手机端和网页端怎么对应” |
| 7 | `07_DATA_COLLECTION_PROTOCOL.md` | 数据采集规范、传感器佩戴、标签命名、采集注意事项 | 采新动作数据前看 | 回答“怎么保证训练数据规范”“为什么采集时佩戴位置要一致” |
| 8 | `08_FIRST_COLLECTION_PLAN.md` | 第一版数据采集计划，包括先采什么、怎么采、每类样本目标 | 需要重新补采数据时看 | 回答“第一阶段数据怎么来的”“为什么先做 idle 和 squat_standard” |
| 9 | `09_ML_PIPELINE_README.md` | 机器学习流水线快速说明，数据目录、准备数据、训练模型命令 | 想快速运行模型训练时看 | 回答“训练模型的命令是什么”“模型文件生成在哪里” |
| 10 | `10_PC_GATEWAY_README.md` | PC 网关快速说明，包括依赖、启动、API、BLE 连接 | 想快速启动网页和网关时看 | 回答“PC 网关怎么启动”“网关负责什么” |
| 11 | `11_TOOLS_README.md` | PowerShell 工具脚本说明，包括编译 ESP32、启动网关、训练模型 | 不想手输长命令时看 | 回答“项目有哪些辅助脚本”“如何一键启动或训练” |
| 12 | `12_MYSQL_BACKEND_SETUP.md` | MySQL 后端接入、环境变量、数据库初始化说明 | 数据库连接异常或重新配置电脑时看 | 回答“数据库怎么接入”“后端怎么连接 MySQL” |
| 13 | `13_NAVICAT_MYSQL_SETUP.md` | Navicat 连接 MySQL、建库、查看表的操作说明 | 用 Navicat 查看数据库时看 | 回答“怎么可视化查看用户、会话、报告数据” |
| 14 | `14_MIDTERM_FRAMEWORK_PLAN.md` | 中期检查时规划的系统功能框架和七点目标对应关系 | 回顾项目目标和阶段规划时看 | 回答“中期到最终补了哪些功能”“七个目标怎么拆解” |
| 15 | `15_ANDROID_APP_CODE_GUIDE.md` | 安卓端 Java 代码详细说明，包括登录、主界面、BLE、语音、本地会话和页面切换 | 老师问手机端代码实现时看 | 回答“安卓页面怎么切换”“手机怎么连设备”“`setOnClickListener`、`Intent`、`SharedPreferences` 是什么” |
| 16 | `16_ESP32_INO_CODE_GUIDE.md` | ESP32-S3 固件详细说明，包括 MPU6050、柔性传感器、BLE 服务、Notify、校准和平滑 | 老师问硬件固件代码时看 | 回答“ESP32 是怎么采集并发数据的”“为什么用 BLE Notify”“弯曲指数怎么计算” |
| 17 | `17_CODE_TECHNICAL_DEEP_DIVE_AND_STRICT_QA.md` | 整个项目的代码难点深挖、技术原理、语法解释和严格答辩问答 | 最终检查前冲刺复习时看 | 回答“从代码角度讲整个项目”“老师细问某个函数、某种技术、某段链路时怎么答” |

---

## 推荐复习顺序

1. 先看 `01_DOCUMENT_INDEX.md`，确认所有文档位置和用途。
2. 再看 `02_FINAL_CHECK_DEMO_SCRIPT.md`，先把现场演示流程跑顺。
3. 再看 `03_TEACHER_QA_CHEATSHEET.md`，背老师高频追问。
4. 再看 `04_PROJECT_TECHNICAL_DEFENSE_GUIDE.md`，建立完整系统架构。
5. 老师问后端代码时看 `05_PYTHON_FILES_DETAILED_GUIDE.md`。
6. 老师问页面和安卓端时看 `06_FRONTEND_FILES_DETAILED_GUIDE.md`。
7. 补采新动作数据前看 `07_DATA_COLLECTION_PROTOCOL.md` 和 `08_FIRST_COLLECTION_PLAN.md`。
8. 训练模型前看 `09_ML_PIPELINE_README.md`。
9. 启动网关和脚本操作看 `10_PC_GATEWAY_README.md` 和 `11_TOOLS_README.md`。
10. 数据库演示或排错看 `12_MYSQL_BACKEND_SETUP.md` 和 `13_NAVICAT_MYSQL_SETUP.md`。
11. 老师如果追问安卓端代码，补看 `15_ANDROID_APP_CODE_GUIDE.md`。
12. 老师如果追问 ESP32 固件代码，补看 `16_ESP32_INO_CODE_GUIDE.md`。
13. 最后冲刺时重点看 `17_CODE_TECHNICAL_DEEP_DIVE_AND_STRICT_QA.md`，它是专门应对严格代码追问的。
14. 有空再回看 `14_MIDTERM_FRAMEWORK_PLAN.md`，用于讲项目从中期到最终版的扩展。

---

## 快速定位表

| 老师问题 | 优先打开 |
|---|---|
| 现场演示顺序怎么走？ | `02_FINAL_CHECK_DEMO_SCRIPT.md` |
| 老师追问怎么快速回答？ | `03_TEACHER_QA_CHEATSHEET.md` |
| 你的项目整体架构是什么？ | `04_PROJECT_TECHNICAL_DEFENSE_GUIDE.md` |
| 设备端、手机端、服务端怎么区分？ | `04_PROJECT_TECHNICAL_DEFENSE_GUIDE.md` |
| 每个 Python 文件是干什么的？ | `05_PYTHON_FILES_DETAILED_GUIDE.md` |
| `service.py` 为什么是核心？ | `05_PYTHON_FILES_DETAILED_GUIDE.md` |
| 模型训练原理是什么？ | `05_PYTHON_FILES_DETAILED_GUIDE.md`、`09_ML_PIPELINE_README.md` |
| 网页前端页面怎么组织？ | `06_FRONTEND_FILES_DETAILED_GUIDE.md` |
| 手机端界面文件在哪里？ | `06_FRONTEND_FILES_DETAILED_GUIDE.md` |
| 数据采集怎么保证规范？ | `07_DATA_COLLECTION_PROTOCOL.md` |
| 第一版采集了哪些数据？ | `08_FIRST_COLLECTION_PLAN.md` |
| MySQL 怎么接入？ | `12_MYSQL_BACKEND_SETUP.md` |
| Navicat 怎么连接？ | `13_NAVICAT_MYSQL_SETUP.md` |
| 网关怎么启动？ | `10_PC_GATEWAY_README.md`、`11_TOOLS_README.md` |
| 模型怎么训练？ | `09_ML_PIPELINE_README.md`、`11_TOOLS_README.md` |
| 安卓 Java 代码怎么讲？ | `15_ANDROID_APP_CODE_GUIDE.md` |
| ESP32 固件代码怎么讲？ | `16_ESP32_INO_CODE_GUIDE.md` |
| 老师严格追问代码难点怎么办？ | `17_CODE_TECHNICAL_DEEP_DIVE_AND_STRICT_QA.md` |

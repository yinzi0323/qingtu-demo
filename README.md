# 晴途 AI 心理健康平台 Demo

一个采用 Streamlit 构建的移动端小程序风格交互原型。包含首页、AI 量表、情绪对话、个人健康档案、医生问诊和正向社区六大页面。

V3 加入首页搜索、页面平滑动画、Supabase Auth 邮箱注册登录、PostgreSQL 公网持久化与 RLS 用户隔离；医生选择后会直接进入独立咨询页。

V4 扩展社区第四分类、表情反应、细分话题与里程碑勋章，并加入 ADHD 任务拆解/番茄钟、睡眠记录/白噪音、服药提醒/副作用记录、复诊 PDF、心理科普和匿名互助房间。

V5 将心情趋势改为真实记录的每日平均值（北京时间 00:00 分日），并支持当日记录次数提示、按日期查看心情/测评/AI 对话、心情备注、可编辑的每日行动与长期便签、更多助眠声音，以及互助房间消息身份配色。

## V5 数据库升级

更新到 V5 后，请先打开 Supabase 项目的 **SQL Editor**，新建查询，完整粘贴并运行 `supabase_v5_migration.sql`。该脚本只新增心情备注字段和个人行动/便签表，不会删除现有记录，可重复执行。

> 重要：本项目只用于产品原型演示，不提供医疗诊断、治疗或紧急救援。演示中的医生信息、响应时间、趋势数据均为虚构示例。

## 在 PyCharm 中运行

1. 用 PyCharm 打开 `qingtu-ai-demo` 文件夹。
2. 打开 **Settings / Project / Python Interpreter**，选择 **Add Interpreter / Add Local Interpreter / Virtualenv**。
3. Base interpreter 建议选择 Python 3.10–3.13，创建 `.venv`（不建议使用尚未被部分可视化依赖完整支持的 Python 3.14）。
4. 打开 PyCharm 底部 Terminal，执行：

   ```bash
   python -m pip install -r requirements.txt
   python -m streamlit run app.py
   ```

5. 浏览器通常会自动打开 `http://localhost:8501`。建议用浏览器开发者工具切换到约 390×844 的手机视图。

Windows 也可以双击 `run_windows.bat`（需先确保 Python 已加入 PATH），脚本会创建虚拟环境并安装依赖。

## 页面结构和主要交互

| 页面 | 核心内容 | 主要按钮与反馈/跳转 |
|---|---|---|
| 首页 | 心情天气、快捷陪伴、微行动、危机提示 | “记录此刻心情”给出保存反馈；四个快捷按钮分别跳转测评、对话、档案、问诊 |
| AI 量表 | SDS、SAS、ASRS-6，逐题单选及报告 | “提交并生成情绪报告”校验完整性、评分、展示环图并写入历史；“带着结果去 AI 对话”跳转对话 |
| 情绪对话 | 焦虑、低落、ADHD、拖延四种支持模式 | 发送后获得本地规则回复；“清空对话”清除会话；“保存到健康档案”给出保存反馈 |
| 健康档案 | 情绪折线图、概览指标、病历上传、历史测评 | “确认保存文件记录”显示记录结果；“去完成一次测评”跳转量表 |
| 医生问诊 | 医生列表、专长、评分、图文咨询与报告上传 | “选择医生”展开表单；“提交咨询申请”校验描述与授权并显示等待接诊状态 |
| 正向社区 | 匿名动态、康复打卡、暖心故事 | “送一个拥抱”更新计数；“AI 安全检查并发布”过滤危机、联系方式及攻击性内容后发布 |

所有页面底部均可通过 6 个导航按钮切换。隐私说明和非医疗诊断声明位于每页底部，危机相关页面提供醒目安全提示。

## 原型数据与隐私

- 数据仅存放在 Streamlit 当前会话内，刷新或服务重启后可能丢失。
- 上传文件只读取文件名用于交互演示，不写入磁盘，不发送给第三方。
- AI 对话是可解释的本地关键词/场景规则，不调用真实大模型。
- 已接入用户认证与 RLS 数据隔离；正式医疗场景仍需专业量表授权审查、医生资质核验、人工内容审核、危机转介、文件私有存储及数据合规评估。

## 项目结构

```text
qingtu-ai-demo/
├─ .streamlit/config.toml   # 主题与服务配置
├─ app.py                   # 六页面及全部交互逻辑
├─ feature_pages.py         # 专注、睡眠、药物、简报、科普与互助房间
├─ pdf_report.py            # 中文复诊简报 PDF 生成器
├─ styles.css               # 移动端小程序视觉样式
├─ supabase_like_function.sql # 社区点赞数据库函数
├─ supabase_v4_migration.sql  # V4 新表、字段及 RLS 策略
├─ requirements.txt         # Python 依赖
├─ run_windows.bat          # Windows 一键启动
└─ README.md                # 使用说明
```

## Supabase 配置

在 Streamlit Cloud Secrets 或本地 `.streamlit/secrets.toml` 中配置 `SUPABASE_URL` 和 `SUPABASE_KEY`。只能使用 publishable/anon key，禁止使用 secret/service_role key。数据库需先创建 README 所述五张表与 RLS 策略，并执行 `supabase_like_function.sql`。所有私人查询同时受应用过滤和数据库 RLS 保护。

升级 V4 时，必须先在 Supabase SQL Editor 执行一次 `supabase_v4_migration.sql`，再上传新版 `app.py`、`feature_pages.py`、`pdf_report.py`、`requirements.txt` 和 `styles.css`。否则新页面会因数据表不存在而报错。

番茄钟和白噪音在浏览器当前页面内运行；网页关闭后无法后台提醒。任务拆解、睡眠建议和社区二层引导当前使用本地规则，已经预留为后续大模型生成层的替换位置。

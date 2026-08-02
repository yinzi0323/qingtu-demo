from datetime import date, datetime, timedelta
from pathlib import Path
import re

import altair as alt
import pandas as pd
import streamlit as st
from supabase import create_client
from feature_pages import focus_page, sleep_page, medication_page, report_page, knowledge_page, room_page

st.set_page_config(page_title="晴途", page_icon="🌤️", layout="centered", initial_sidebar_state="collapsed")
with open(Path(__file__).with_name("styles.css"), encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

PAGES = ["首页", "AI量表", "情绪对话", "健康档案", "医生问诊", "正向社区"]
ICONS = ["🏠", "📝", "💬", "📊", "🩺", "🌱"]
def get_supabase():
    if "supabase_client" not in st.session_state:
        st.session_state.supabase_client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    return st.session_state.supabase_client

def user_id(): return st.session_state.auth_user.id

def insert_own(table, data):
    return get_supabase().table(table).insert({**data,"user_id":user_id()}).execute().data

def fetch_own(table, **filters):
    q=get_supabase().table(table).select("*").eq("user_id",user_id())
    for key,value in filters.items(): q=q.eq(key,value)
    return q.order("created_at",desc=True).execute().data

def delete_own(table, row_id):
    return get_supabase().table(table).delete().eq("id",row_id).eq("user_id",user_id()).execute()

def auth_screen():
    st.markdown('<div class="hero"><h2>欢迎来到晴途 🌤️</h2><div>登录后，你的记录会安全地保存在云端，并与其他用户隔离。</div></div>',unsafe_allow_html=True)
    login_tab,signup_tab=st.tabs(["登录","注册"])
    with login_tab:
        with st.form("login_form"):
            email=st.text_input("邮箱",key="login_email")
            password=st.text_input("密码",type="password",key="login_password")
            login=st.form_submit_button("登录晴途",type="primary")
        if login:
            try:
                result=get_supabase().auth.sign_in_with_password({"email":email.strip(),"password":password})
                st.session_state.auth_user=result.user; st.success("登录成功"); st.rerun()
            except Exception: st.error("登录失败，请检查邮箱、密码或邮箱验证状态。")
    with signup_tab:
        with st.form("signup_form"):
            email=st.text_input("注册邮箱",key="signup_email")
            password=st.text_input("设置密码（至少 8 位）",type="password",key="signup_password")
            confirm=st.text_input("再次输入密码",type="password")
            agree=st.checkbox("我已阅读隐私声明和非医疗诊断声明")
            signup=st.form_submit_button("创建账号",type="primary")
        if signup:
            if len(password)<8 or password!=confirm or not agree: st.error("请设置至少 8 位且两次一致的密码，并确认声明。")
            else:
                try:
                    result=get_supabase().auth.sign_up({"email":email.strip(),"password":password})
                    if result.session:
                        st.session_state.auth_user=result.user; st.success("注册成功"); st.rerun()
                    else: st.success("注册成功，请前往邮箱点击验证链接后再登录。")
                except Exception: st.error("注册失败。该邮箱可能已注册，或请求过于频繁。")
    safety(); footer()

SCALES = {
    "SDS 抑郁自评量表": {
        "short": "SDS", "questions": [
            "我感到情绪沮丧、郁闷", "我觉得一天中早晨最好", "我有想哭或哭出来", "我夜间睡眠不好",
            "我吃饭像平时一样多", "我的性功能正常", "我感到体重减轻", "我为便秘烦恼",
            "我的心跳比平时快", "我无故感到疲劳", "我的头脑像往常一样清楚", "我做事情像平时一样容易",
            "我坐卧不安，难以保持平静", "我对未来感到有希望", "我比平时更容易激怒", "我觉得决定事情很容易",
            "我感到自己是有用和不可缺少的人", "我的生活很有意义", "假若我死了别人会过得更好", "我仍喜爱自己平时喜爱的东西"],
        "reverse": {2,5,6,11,12,14,16,17,18,20}, "bands": [(52,"当前困扰较轻"),(62,"可能存在轻度困扰"),(72,"可能存在中度困扰"),(999,"困扰程度较高，建议寻求专业支持")]
    },
    "SAS 焦虑自评量表": {
        "short": "SAS", "questions": [
            "我比平常容易紧张和着急", "我无缘无故感到害怕", "我容易心里烦乱或惊恐", "我觉得我可能要发疯",
            "我觉得一切都很好，不会发生不幸", "我的手脚发抖打颤", "我因头痛、颈痛和背痛而苦恼", "我感觉容易衰弱和疲乏",
            "我觉得心平气和，容易安静坐着", "我觉得心跳得很快", "我因阵阵头晕而苦恼", "我有晕倒发作或觉得要晕倒",
            "我呼气、吸气都感到容易", "我的手脚麻木和刺痛", "我因胃痛和消化不良而苦恼", "我常常要小便",
            "我的手脚常常干燥温暖", "我脸红发热", "我容易入睡且一夜睡得很好", "我做噩梦"],
        "reverse": {5,9,13,17,19}, "bands": [(49,"当前焦虑体验较轻"),(59,"可能存在轻度焦虑体验"),(69,"可能存在中度焦虑体验"),(999,"焦虑体验较强，建议寻求专业支持")]
    },
    "成人 ADHD 自评筛查（ASRS-6）": {
        "short": "ASRS-6", "questions": [
            "任务最困难的部分完成后，常难以收尾", "做需要组织规划的任务时，常难以理清头绪", "常忘记约会或应做的事情",
            "面对需要大量思考的任务时，会回避或拖延", "长时间坐着时会手脚不停动", "常感到过度活跃，像被马达驱动"],
        "reverse": set(), "bands": [(9,"当前特征不突出"),(14,"存在一些注意力或执行功能困扰"),(999,"特征较突出，建议进一步接受专业评估")]
    }
}
OPTIONS = ["没有或很少", "少部分时间", "相当多时间", "绝大部分时间"]

def init_state():
    defaults = {"page":"首页", "chat":[], "consults":[]}
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

def go(page): st.session_state.page = page
def card(title, body, tags=""):
    tag_html = "".join(f'<span class="tag">{x}</span>' for x in tags.split("|") if x)
    st.markdown(f'<div class="card"><b>{title}</b><div class="muted">{body}</div>{tag_html}</div>', unsafe_allow_html=True)
def safety():
    st.markdown('<div class="danger">🛟 如果你正有伤害自己或他人的想法，请立即联系当地急救电话（中国大陆 120/110）、前往最近急诊，或联系可信赖的人陪伴。请勿独自承担。</div>', unsafe_allow_html=True)
def footer():
    with st.expander("隐私与使用说明"):
        st.write("本 Demo 默认仅在当前浏览器会话中保存输入，不会主动上传至外部服务。正式产品应采用加密、最小化采集、访问审计及明确授权机制。")
        st.warning("晴途提供心理健康教育与自我觉察支持，不构成医疗诊断、治疗建议或紧急救援服务。量表结果仅供参考。")
    st.markdown('<div class="footer-note">晴途 · 每一步，都算向晴天靠近</div>', unsafe_allow_html=True)

def home():
    st.markdown('<div class="hero"><h2>早上好，愿你今天轻一点 🌤️</h2><div>此刻的感受值得被看见。先从一次温柔的自我照顾开始。</div></div>', unsafe_allow_html=True)
    mood = st.select_slider("今天的心情天气", ["暴雨","阴天","多云","微晴","晴朗"], value="微晴")
    if st.button("记录此刻心情", type="primary"):
        insert_own("moods",{"mood":mood})
        st.session_state["today_mood"] = mood; st.toast(f"已记录：{mood}，下次打开仍会保留")
    with st.form("home_search", border=False):
        s1,s2=st.columns([5,1])
        query=s1.text_input("搜索",label_visibility="collapsed",placeholder="搜索测评、医生、社区与功能……")
        search=s2.form_submit_button("🔍",help="搜索并打开结果页")
    if search:
        if query.strip(): st.session_state.search_query=query.strip(); go("搜索结果"); st.rerun()
        else: st.warning("请输入想搜索的内容。")
    st.subheader("快捷陪伴")
    c1,c2 = st.columns(2)
    with c1:
        if st.button("📝 开始测评"): go("AI量表"); st.rerun()
        if st.button("📊 查看档案"): go("健康档案"); st.rerun()
    with c2:
        if st.button("💬 找 AI 聊聊"): go("情绪对话"); st.rerun()
        if st.button("🩺 咨询医生"): go("医生问诊"); st.rerun()
    st.subheader("今日微行动")
    card("60 秒呼吸练习", "吸气 4 秒 · 停留 2 秒 · 呼气 6 秒，重复 5 次。", "舒缓焦虑|随时可做")
    card("给自己的便签", "“我不必今天解决所有事情，只需要走好下一小步。”", "自我关怀")
    st.subheader("晴途工具箱")
    tools=[("⏱️ ADHD 专注助手","专注助手"),("🌙 睡眠改善","睡眠助手"),("💊 药物打卡","药物打卡"),("📄 复诊简报","复诊简报"),("📚 心理科普","科普知识库"),("🫶 互助房间","互助房间")]
    for i in range(0,len(tools),2):
        cols=st.columns(2)
        for col,(label,target) in zip(cols,tools[i:i+2]):
            if col.button(label,key=f"tool_{target}"): go(target); st.rerun()
    safety()

def assessment():
    st.title("AI 量表测评")
    st.caption("选择最近一至两周最符合你的情况。可随时退出，答案仅用于生成本次报告。")
    name = st.selectbox("选择量表", list(SCALES))
    scale = SCALES[name]
    with st.form("scale_form"):
        answers=[]
        for i,q in enumerate(scale["questions"],1):
            answers.append(st.radio(f"{i}. {q}", OPTIONS, index=None, horizontal=False, key=f"{scale['short']}_{i}"))
        submitted = st.form_submit_button("提交并生成情绪报告", type="primary")
    if submitted:
        if any(a is None for a in answers): st.error("还有题目未作答，请完成全部题目后提交。")
        else:
            raw=0
            for i,a in enumerate(answers,1):
                v=OPTIONS.index(a)+1
                raw += 5-v if i in scale["reverse"] else v
            score = round(raw*1.25) if scale["short"] in {"SDS","SAS"} else raw
            level = next(label for cutoff,label in scale["bands"] if score<=cutoff)
            result={"date":date.today().isoformat(),"scale":scale["short"],"score":score,"level":level}
            insert_own("assessments",{"scale":scale["short"],"score":score,"level":level})
            st.success("报告已生成，并已加入历史测评")
            st.subheader("你的情绪晴雨图")
            max_score=100 if scale["short"] in {"SDS","SAS"} else 24
            df=pd.DataFrame({"项目":["本次得分","可用空间"],"数值":[score,max(0,max_score-score)]})
            chart=alt.Chart(df).mark_arc(innerRadius=55,cornerRadius=8).encode(theta="数值",color=alt.Color("项目",scale=alt.Scale(range=["#6EA8B7","#E8EFEA"]),legend=None)).properties(height=230)
            st.altair_chart(chart,use_container_width=True)
            st.metric("本次参考得分", f"{score} / {max_score}", level)
            st.info("建议：记录触发情境、保持规律睡眠与饮食；若困扰持续两周以上、明显影响生活，建议咨询精神科或心理专业人员。")
            if st.button("带着结果去 AI 对话"):
                st.session_state.chat.append({"role":"assistant","text":f"我看到你刚完成了 {scale['short']}，结果提示“{level}”。你最想先聊哪一部分？"}); go("情绪对话"); st.rerun()
            safety()

def ai_reply(text, mode):
    if re.search(r"自杀|不想活|伤害自己|结束生命|杀人", text):
        return "我很在意你现在的安全。请先远离可能伤害你的物品，立即联系 120/110 或前往最近急诊，并请一位可信赖的人现在陪着你。你可以只回复我：‘我现在安全’或‘我需要帮助’。"
    if mode=="焦虑舒缓": return "听起来你的身体和思绪都绷得很紧。我们先不解决全部问题：双脚踩地，慢慢呼气 6 秒。然后告诉我，此刻最担心发生的具体事情是什么？"
    if mode=="低落陪伴": return "谢谢你把这份沉重说出来。低落时，完成很小的事也需要力气。今天能做到的最小照顾是什么——喝水、拉开窗帘，还是给信任的人发一句话？"
    if mode=="ADHD 专注拆解": return "我们把目标缩成一个 10 分钟动作：①只写出下一步；②移开一个干扰物；③设 10 分钟计时；④结束后决定继续或休息。把任务发我，我帮你拆成三小步。"
    return "先把任务变轻：写下结果 → 选一个 5 分钟能开始的动作 → 设定结束时间。今天追求‘可启动’，不追求完美。你的任务和截止时间是什么？"

def chat():
    st.title("AI 情绪对话")
    st.caption("温柔倾听 · 认知梳理 · 小步行动（原型为本地规则回复，未连接外部 AI）")
    mode=st.segmented_control("选择陪伴模式",["焦虑舒缓","低落陪伴","ADHD 专注拆解","拖延任务规划"],default="焦虑舒缓")
    for m in st.session_state.chat:
        with st.chat_message(m["role"]): st.write(m["text"])
    prompt=st.chat_input("说说此刻发生了什么……")
    if prompt:
        st.session_state.chat += [{"role":"user","text":prompt},{"role":"assistant","text":ai_reply(prompt,mode)}]
        st.rerun()
    c1,c2=st.columns(2)
    if c1.button("清空对话"):
        st.session_state.chat=[]; st.toast("本次对话已清空"); st.rerun()
    if c2.button("保存到健康档案"):
        summary="\n".join(f"{m['role']}: {m['text']}" for m in st.session_state.chat[-6:]) or "空白对话"
        insert_own("notes",{"category":"AI对话摘要","content":summary})
        st.toast("已持久保存本次对话摘要")
    safety()

def records():
    st.title("个人健康档案")
    st.caption("你拥有自己的健康数据；以下均为 Demo 会话内数据。")
    dates=[date.today()-timedelta(days=i) for i in range(6,-1,-1)]
    values=[3,2,3,4,3,4,4]
    mood_df=pd.DataFrame({"日期":dates,"心情指数":values})
    st.altair_chart(alt.Chart(mood_df).mark_line(point=True,color="#6EA8B7").encode(x=alt.X("日期:T",title=None),y=alt.Y("心情指数:Q",scale=alt.Scale(domain=[1,5])),tooltip=["日期:T","心情指数"]).properties(height=220),use_container_width=True)
    c1,c2,c3=st.columns(3)
    c1.metric("连续记录","7 天"); c2.metric("平均心情","3.3 / 5"); c3.metric("本周睡眠","6.8h")
    st.subheader("病历与报告")
    files=st.file_uploader("上传病历、处方或检查报告",type=["pdf","png","jpg","jpeg"],accept_multiple_files=True,help="单文件不超过 20MB；Demo 仅显示文件名")
    if files and st.button("确认保存文件记录",type="primary"):
        st.session_state["medical_files"]=[f.name for f in files]; st.success(f"已记录 {len(files)} 个文件（Demo 不做云端上传）")
    st.subheader("心情记录")
    moods=fetch_own("moods")
    if moods:
        for row in moods:
            a,b=st.columns([5,1]); a.write(f"{row['created_at'][:16]}　**{row['mood']}**")
            if b.button("删除",key=f"del_mood_{row['id']}"):
                delete_own("moods",row['id']); st.toast("心情记录已删除"); st.rerun()
    else: st.info("暂无心情记录。")
    st.subheader("历史测评")
    assessments=fetch_own("assessments")
    if assessments:
        for row in assessments:
            a,b=st.columns([5,1]); a.write(f"{row['created_at'][:10]}　**{row['scale']} · {row['score']} 分**　{row['level']}")
            if b.button("删除",key=f"del_assess_{row['id']}"):
                delete_own("assessments",row['id']); st.toast("测评记录已删除"); st.rerun()
    else: st.info("还没有测评记录。完成任一量表后会显示在这里。")
    notes=fetch_own("notes")
    if notes:
        st.subheader("保存的记录")
        for row in notes:
            with st.expander(f"{row['category']} · {row['created_at'][:16]}"):
                st.write(row["content"])
                if st.button("删除这条记录",key=f"del_note_{row['id']}"):
                    delete_own("notes",row['id']); st.rerun()
    if st.button("去完成一次测评"): go("AI量表"); st.rerun()

def doctors():
    st.title("医生问诊")
    st.caption("医生信息为原型演示；正式服务须完成资质核验与互联网诊疗合规接入。")
    docs=[("林医生","精神科 · 12 年","擅长焦虑、抑郁与睡眠问题","4.9"),("周医生","心理治疗师 · 9 年","擅长 CBT、情绪与压力管理","4.8"),("陈医生","精神科 · 8 年","擅长成人 ADHD 与执行功能","4.9")]
    for i,(n,title,spec,rating) in enumerate(docs):
        st.markdown(f'<div class="card"><b>👩‍⚕️ {n}</b> <span class="tag">★ {rating}</span><div>{title}</div><div class="muted">{spec}</div></div>',unsafe_allow_html=True)
        if st.button(f"选择 {n} · 发起图文咨询",key=f"doc{i}"):
            st.session_state.selected_doc=n; go("咨询医生"); st.rerun()
    safety()

def consultation():
    doctor=st.session_state.get("selected_doc")
    if not doctor: go("医生问诊"); st.rerun()
    if st.button("← 返回医生列表"): go("医生问诊"); st.rerun()
    st.title(f"与{doctor}咨询")
    st.markdown('<div class="notice">已进入独立咨询页面。请尽量描述持续时间、生活影响和希望获得的帮助。</div>',unsafe_allow_html=True)
    with st.form("consult"):
        concern=st.text_area("主要困扰",height=150,placeholder="请描述你的情况……")
        report=st.file_uploader("上传测评/病历报告（可选）",type=["pdf","png","jpg","jpeg"])
        consent=st.checkbox("我已阅读隐私说明并同意为本次咨询提供上述资料")
        ok=st.form_submit_button("提交咨询申请",type="primary")
    if ok:
        if not concern.strip() or not consent: st.error("请填写主要困扰并确认授权。")
        else:
            insert_own("consults",{"doctor":doctor,"concern":concern.strip(),"report_name":report.name if report else None,"status":"等待接诊"})
            st.success("咨询已保存并提交。Demo 状态：等待接诊。")
    history=fetch_own("consults",doctor=doctor)
    if history:
        st.subheader("咨询记录")
        for row in history:
            a,b=st.columns([5,1]); a.write(f"{row['created_at'][:16]}　{row['status']}｜{row['concern'][:35]}")
            if b.button("删除",key=f"del_consult_{row['id']}"):
                delete_own("consults",row['id']); st.rerun()
    safety()

def community():
    st.title("正向社区")
    st.caption("匿名、友善、非评判。分享经验，不替代专业建议。")
    mood_count=len(fetch_own("moods")); focus_count=len(fetch_own("focus_sessions")) if "auth_user" in st.session_state else 0
    badges=[]
    if mood_count>=3: badges.append("🌤️ 情绪觉察新星")
    if mood_count>=7: badges.append("🌈 七日坚持")
    if focus_count>=3: badges.append("🎯 专注行动派")
    if badges: st.markdown("我的里程碑："+" ".join(f'<span class="tag">{b}</span>' for b in badges),unsafe_allow_html=True)
    tab1,tab2,tab3,tab4=st.tabs(["全部","康复打卡","暖心故事","互助交流"])
    def show(filter_name=None):
        posts=get_supabase().table("posts").select("*").order("created_at",desc=True).execute().data
        for p in posts:
            if filter_name and p["topic"]!=filter_name: continue
            reactions=get_supabase().table("post_reactions").select("emoji,user_id").eq("post_id",p["id"]).execute().data
            counts={e:sum(1 for r in reactions if r["emoji"]==e) for e in ["🤍","🌤️","💪","🫂"]}
            card(f"匿名晴友 · {p['topic']}",p["content"],f"{p.get('subtopic','康复感悟')}")
            cols=st.columns(4)
            for col,emoji in zip(cols,["🤍","🌤️","💪","🫂"]):
                if col.button(f"{emoji} {counts[emoji]}",key=f"react_{filter_name}_{p['id']}_{emoji}"):
                    mine=[r for r in reactions if r["emoji"]==emoji and r["user_id"]==user_id()]
                    q=get_supabase().table("post_reactions")
                    if mine: q.delete().eq("post_id",p["id"]).eq("user_id",user_id()).eq("emoji",emoji).execute()
                    else: q.insert({"post_id":p["id"],"user_id":user_id(),"emoji":emoji}).execute()
                    st.rerun()
            if p["user_id"]==user_id() and st.button("删除我的帖子",key=f"del_post_{filter_name}_{p['id']}"):
                delete_own("posts",p['id']); st.toast("帖子已删除"); st.rerun()
    with tab1: show()
    with tab2: show("康复打卡")
    with tab3: show("暖心故事")
    with tab4: show("互助交流")
    st.subheader("匿名发布")
    with st.form("post"):
        topic=st.selectbox("内容分类",["康复打卡","暖心故事","互助交流"])
        subtopic=st.selectbox("细分话题",["服药日常","学生适配","职场适配","亲子相处","康复感悟","焦虑互助","抑郁陪伴","ADHD 同行"])
        text=st.text_area("想分享什么？",max_chars=500,placeholder="记录一个小进步，或留下一句温暖的话……")
        post=st.form_submit_button("AI 安全检查并发布",type="primary")
    if post:
        banned=r"自杀方法|买药渠道|联系方式|加微信|辱骂|人肉|诊断你"
        crisis=r"不想活|自杀|伤害自己|结束生命"
        if re.search(crisis,text): st.error("检测到可能的危机表达，内容暂未公开。请优先联系 120/110、附近急诊或可信赖的人。")
        elif re.search(banned,text): st.error("内容含联系方式、攻击性表达或不安全建议，请修改后再发布。")
        elif len(text.strip())<5: st.warning("再多写一点吧，至少 5 个字。")
        else:
            supportive=""
            if re.search(r"很累|撑不住|没人理解|好难受",text): supportive="\n\n🌤️ 晴途提醒：谢谢你说出来。你可以进入“互助房间”或“情绪对话”，让这份感受被继续接住。"
            insert_own("posts",{"topic":topic,"subtopic":subtopic,"content":text.strip()+supportive,"likes":0}); st.success("已匿名发布，并通过双层安全检查"); st.rerun()

def search_results():
    query=st.session_state.get("search_query","")
    if st.button("← 返回首页"): go("首页"); st.rerun()
    st.title("搜索结果")
    with st.form("result_search",border=False):
        c1,c2=st.columns([5,1]); new_q=c1.text_input("搜索内容",value=query,label_visibility="collapsed"); again=c2.form_submit_button("🔍")
    if again and new_q.strip(): st.session_state.search_query=new_q.strip(); st.rerun()
    catalog=[
        ("SDS 抑郁自评量表","了解近期低落体验","AI量表"),("SAS 焦虑自评量表","了解近期焦虑体验","AI量表"),
        ("成人 ADHD 筛查","注意力与执行功能自评","AI量表"),("焦虑舒缓对话","呼吸练习与情绪梳理","情绪对话"),
        ("个人健康档案","心情、测评和保存记录","健康档案"),("医生问诊","精神科与心理咨询","医生问诊"),
        ("康复打卡与暖心故事","匿名正向社区","正向社区")]
    results=[x for x in catalog if query.lower() in (x[0]+x[1]+x[2]).lower()]
    if not results: st.info(f"没有找到与“{query}”相关的内容，可以尝试“焦虑”“医生”“测评”等关键词。")
    for i,(title,desc,target) in enumerate(results):
        card(title,desc,target)
        if st.button(f"打开 {title}",key=f"search_{i}"): go(target); st.rerun()

init_state()
try: get_supabase()
except Exception:
    st.error("未找到有效的 Supabase 配置。请在 Streamlit Secrets 中设置 SUPABASE_URL 和 SUPABASE_KEY。")
    st.stop()
if "auth_user" not in st.session_state:
    auth_screen(); st.stop()
st.markdown("<div class='muted'>🌤️ 晴途 QINGTU · 心理健康陪伴</div>",unsafe_allow_html=True)
top1,top2=st.columns([4,1])
top1.caption(f"已登录：{st.session_state.auth_user.email}")
if top2.button("退出"):
    get_supabase().auth.sign_out(); st.session_state.pop("auth_user",None); st.session_state.pop("supabase_client",None); st.rerun()
page=st.session_state.page
feature_args=(get_supabase(),user_id(),go)
routes={"首页":home,"AI量表":assessment,"情绪对话":chat,"健康档案":records,"医生问诊":doctors,"正向社区":community,"搜索结果":search_results,"咨询医生":consultation,
        "专注助手":lambda:focus_page(*feature_args),"睡眠助手":lambda:sleep_page(*feature_args),"药物打卡":lambda:medication_page(*feature_args),
        "复诊简报":lambda:report_page(get_supabase(),user_id(),st.session_state.auth_user.email,go),"科普知识库":lambda:knowledge_page(go),"互助房间":lambda:room_page(*feature_args)}
routes[page]()
footer()
st.divider()
cols=st.columns(6)
for col,p,icon in zip(cols,PAGES,ICONS):
    if col.button(f"{icon}\n{p.replace('AI','')}",key=f"nav_{p}",type="primary" if page==p else "secondary"):
        go(p); st.rerun()

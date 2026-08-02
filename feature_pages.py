from io import BytesIO
from datetime import date, datetime
import html

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pdf_report import build_visit_pdf
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def _insert(sb, uid, table, data):
    return sb.table(table).insert({**data, "user_id": uid}).execute()


def _own(sb, uid, table):
    return sb.table(table).select("*").eq("user_id", uid).order("created_at", desc=True).execute().data


def _split_task(text):
    parts = [p.strip() for p in text.replace("；", "。").replace("，", "。").split("。") if p.strip()]
    if not parts:
        return []
    result=[]
    for p in parts[:6]:
        if any(k in p for k in ["论文","报告","方案"]):
            result += [f"明确{p}的交付要求", f"收集并整理{p}所需资料", f"完成{p}的最小初稿", f"检查并提交{p}"]
        else: result.append(p)
    return result[:8]


def focus_page(sb, uid, go):
    if st.button("← 返回首页"): go("首页"); st.rerun()
    st.title("ADHD 任务拆解与番茄专注")
    st.caption("把庞大任务变成 10–25 分钟可启动的小步骤。当前为本地智能拆解，后续可替换为大模型。")
    with st.form("task_split"):
        task=st.text_area("输入让你感到畏难的任务",placeholder="例如：两周后提交毕业论文，现在资料很乱，不知道如何开始")
        minutes=st.slider("每个专注块",10,25,15)
        split=st.form_submit_button("拆成可开始的小步骤",type="primary")
    if split:
        steps=_split_task(task)
        if not steps: st.warning("请先输入任务。")
        else:
            for i,step in enumerate(steps,1):
                _insert(sb,uid,"focus_tasks",{"title":task[:80],"step_text":step,"position":i,"minutes":minutes,"completed":False})
            st.success(f"已拆成 {len(steps)} 步，并保存到专注计划"); st.rerun()
    tasks=sb.table("focus_tasks").select("*").eq("user_id",uid).eq("completed",False).order("created_at").order("position").execute().data
    st.subheader("下一步，只做这一小块")
    for row in tasks:
        c1,c2=st.columns([4,1]); c1.write(f"**{row['step_text']}**　{row['minutes']} 分钟")
        if c2.button("完成",key=f"done_task_{row['id']}"):
            sb.table("focus_tasks").update({"completed":True}).eq("id",row["id"]).eq("user_id",uid).execute();
            _insert(sb,uid,"focus_sessions",{"task_id":row["id"],"minutes":row["minutes"]}); st.toast("完成得很好，这一小步很重要"); st.rerun()
    components.html("""
    <div style="font-family:sans-serif;text-align:center;background:#fffdf8;border:1px solid #dcebed;border-radius:20px;padding:18px;color:#315f69">
      <div id="clock" style="font-size:44px;font-weight:700">15:00</div>
      <input id="mins" type="number" min="1" max="60" value="15" style="width:60px;padding:8px;border-radius:10px;border:1px solid #b9d8dd">
      <button onclick="start()" style="padding:9px 18px;border:0;border-radius:12px;background:#6ea8b7;color:white">开始</button>
      <button onclick="pause()" style="padding:9px 18px;border:1px solid #b9d8dd;border-radius:12px;background:white">暂停</button>
      <button onclick="reset()" style="padding:9px 18px;border:1px solid #b9d8dd;border-radius:12px;background:white">重置</button>
      <div style="font-size:12px;color:#70888d;margin-top:8px">计时在当前页面运行；到点会发出提示音。</div>
    </div><script>
    let timer=null,left=900; const clock=document.getElementById('clock');
    function paint(){clock.innerText=String(Math.floor(left/60)).padStart(2,'0')+':'+String(left%60).padStart(2,'0')}
    function start(){if(timer)return;if(left<=0)reset();timer=setInterval(()=>{left--;paint();if(left<=0){pause();alert('专注完成！起身喝水，休息一下吧。')}},1000)}
    function pause(){clearInterval(timer);timer=null} function reset(){pause();left=parseInt(document.getElementById('mins').value||15)*60;paint()}
    </script>""",height=190)
    sessions=_own(sb,uid,"focus_sessions")
    if sessions:
        df=pd.DataFrame(sessions); df["日期"]=pd.to_datetime(df["created_at"]).dt.date; daily=df.groupby("日期")["minutes"].sum().reset_index()
        st.subheader("每日专注报表"); st.bar_chart(daily.set_index("日期"),color="#6EA8B7")


def sleep_page(sb, uid, go):
    if st.button("← 返回首页"): go("首页"); st.rerun()
    st.title("睡眠监测与改善")
    with st.form("sleep_log"):
        log_date=st.date_input("日期",date.today()); latency=st.number_input("入睡用时（分钟）",0,300,30)
        awakenings=st.number_input("夜间惊醒次数",0,20,1); duration=st.number_input("总睡眠时长（小时）",0.0,16.0,7.0,.5)
        morning=st.select_slider("晨起状态",["非常疲惫","疲惫","一般","较好","精神充足"],value="一般")
        save=st.form_submit_button("保存并生成改善建议",type="primary")
    if save:
        _insert(sb,uid,"sleep_logs",{"log_date":log_date.isoformat(),"latency_minutes":latency,"awakenings":awakenings,"duration_hours":duration,"morning_state":morning})
        st.success("睡眠记录已保存")
    logs=_own(sb,uid,"sleep_logs")
    if logs:
        latest=logs[0]; tips=[]
        if latest["latency_minutes"]>30: tips.append("睡前 1 小时降低灯光亮度，并把担忧写到纸上，告诉自己明天再处理。")
        if latest["awakenings"]>=2: tips.append("夜间醒来不要反复看时间；若约 20 分钟仍清醒，可离床做安静活动，困倦后再返回。")
        if float(latest["duration_hours"])<7: tips.append("尝试固定起床时间，每次仅把上床时间提前 15 分钟。")
        st.subheader("今晚的小方案"); st.info("\n\n".join(tips or ["当前记录较平稳，继续保持固定起床时间，并观察一周趋势。"]))
        df=pd.DataFrame(logs); df["log_date"]=pd.to_datetime(df["log_date"]); st.line_chart(df.set_index("log_date")[["duration_hours"]],color="#6EA8B7")
    st.subheader("助眠声音")
    components.html("""<div style="font-family:system-ui;text-align:center">
    <select id="sound" style="padding:10px;border:1px solid #bdd8dc;border-radius:12px;margin-right:8px">
      <option value="white">柔和白噪音</option><option value="pink">粉红噪音</option>
      <option value="rain">细雨声</option><option value="ocean">缓慢海浪</option><option value="night">森林夜声</option>
    </select><button id="b" onclick="toggle()" style="padding:11px 20px;border:0;border-radius:15px;background:#6ea8b7;color:white">▶ 播放</button>
    </div><script>
    let ctx,src,gain,filter,lfo,on=false;
    function toggle(){if(!on){ctx=new AudioContext();let size=ctx.sampleRate*3,buf=ctx.createBuffer(1,size,ctx.sampleRate),d=buf.getChannelData(0),kind=sound.value,last=0;
      for(let i=0;i<size;i++){let w=Math.random()*2-1;if(kind==='pink'){last=.985*last+.15*w;d[i]=last*.35}else d[i]=w*.18}
      src=ctx.createBufferSource();src.buffer=buf;src.loop=true;gain=ctx.createGain();gain.gain.value=.28;filter=ctx.createBiquadFilter();
      if(kind==='rain'){filter.type='highpass';filter.frequency.value=1200}else if(kind==='ocean'){filter.type='lowpass';filter.frequency.value=650}else if(kind==='night'){filter.type='bandpass';filter.frequency.value=2400;gain.gain.value=.12}else{filter.type='lowpass';filter.frequency.value=kind==='pink'?1800:5000}
      src.connect(filter).connect(gain).connect(ctx.destination);
      if(kind==='ocean'){lfo=ctx.createOscillator();let lg=ctx.createGain();lfo.frequency.value=.09;lg.gain.value=.18;lfo.connect(lg).connect(gain.gain);lfo.start()}
      src.start();on=true;b.innerText='■ 停止';sound.disabled=true
    }else{src.stop();if(lfo)lfo.stop();ctx.close();on=false;b.innerText='▶ 播放';sound.disabled=false}}
    </script>""",height=80)


def medication_page(sb, uid, go):
    if st.button("← 返回首页"): go("首页"); st.rerun()
    st.title("药物打卡与反应记录")
    st.warning("仅用于记录，不提供药物诊断或擅自停药建议。调整药物或剂量前请联系开药医生。")
    with st.expander("＋ 添加每日服药提醒",expanded=False):
        with st.form("med_schedule"):
            s_name=st.text_input("药物名称",key="schedule_name"); s_dose=st.text_input("医嘱剂量",key="schedule_dose")
            s_time=st.time_input("每日提醒时间"); add=st.form_submit_button("保存提醒")
        if add and s_name.strip():
            _insert(sb,uid,"medication_schedules",{"medicine_name":s_name.strip(),"dose":s_dose.strip(),"reminder_time":s_time.isoformat(timespec="minutes"),"active":True}); st.success("提醒已保存"); st.rerun()
    schedules=_own(sb,uid,"medication_schedules"); now=datetime.now().strftime("%H:%M")
    for s in schedules:
        c1,c2=st.columns([5,1]); c1.write(f"⏰ {str(s['reminder_time'])[:5]}　**{s['medicine_name']}**　{s['dose'] or ''}")
        if now==str(s["reminder_time"])[:5]: st.warning(f"到服药提醒时间：{s['medicine_name']}。请严格按医嘱服用。")
        if c2.button("删除",key=f"del_schedule_{s['id']}"):
            sb.table("medication_schedules").delete().eq("id",s["id"]).eq("user_id",uid).execute(); st.rerun()
    with st.form("med_log"):
        name=st.text_input("药物名称"); dose=st.text_input("本次剂量",placeholder="例如：遵医嘱填写")
        taken=st.checkbox("本次已按医嘱服用"); reaction=st.text_area("身体反应或不适（可选）")
        severity=st.select_slider("不适程度",[0,1,2,3,4,5],value=0)
        save=st.form_submit_button("保存服药记录",type="primary")
    if save:
        if not name.strip(): st.error("请填写药物名称。")
        else: _insert(sb,uid,"medication_logs",{"medicine_name":name.strip(),"dose":dose.strip(),"taken":taken,"reaction":reaction.strip(),"severity":severity}); st.success("记录已保存")
    logs=_own(sb,uid,"medication_logs")
    for row in logs[:20]:
        with st.expander(f"{row['created_at'][:16]} · {row['medicine_name']} · {'已服用' if row['taken'] else '未服用'}"):
            st.write(f"剂量：{row['dose'] or '未填写'}｜不适程度：{row['severity']}/5")
            st.write(row["reaction"] or "未记录身体反应")
            if row["severity"]>=4: st.error("不适程度较高，请尽快联系开药医生；如出现意识异常、呼吸困难等紧急情况请立即就医。")


def _legacy_build_visit_pdf(email, assessments, moods, sleep, meds):
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light")); buf=BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm)
    styles=getSampleStyleSheet(); title=ParagraphStyle("cn_title",fontName="STSong-Light",fontSize=20,leading=26,alignment=TA_CENTER,textColor=colors.HexColor("#315F69")); body=ParagraphStyle("cn_body",fontName="STSong-Light",fontSize=10.5,leading=16)
    story=[Paragraph("晴途复诊就诊简报",title),Paragraph(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}　账户：{html.escape(email)}",body),Spacer(1,8*mm)]
    sections=[("近期量表",[[x.get("created_at","")[:10],x.get("scale",""),str(x.get("score","")),x.get("level","")] for x in assessments[:8]], ["日期","量表","分数","结果"]),
              ("情绪记录",[[x.get("created_at","")[:10],x.get("mood","")] for x in moods[:10]],["日期","心情"]),
              ("睡眠记录",[[str(x.get("log_date","")),str(x.get("duration_hours","")),str(x.get("awakenings","")),x.get("morning_state","")] for x in sleep[:7]],["日期","时长(h)","惊醒","晨起"]),
              ("服药及身体反应",[[x.get("created_at","")[:10],x.get("medicine_name",""),x.get("dose",""),x.get("reaction","")[:24]] for x in meds[:10]],["日期","药物","剂量","反应"])]
    for heading,rows,headers in sections:
        story += [Paragraph(heading,ParagraphStyle("h",parent=body,fontSize=14,leading=20,textColor=colors.HexColor("#315F69"))),Spacer(1,2*mm)]
        if rows:
            table=Table([headers]+rows,repeatRows=1,colWidths=[(A4[0]-36*mm)/len(headers)]*len(headers)); table.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),"STSong-Light"),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EAF4F6")),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#C8DADD")),("VALIGN",(0,0),(-1,-1),"TOP"),("FONTSIZE",(0,0),(-1,-1),8.5),("LEADING",(0,0),(-1,-1),12),("PADDING",(0,0),(-1,-1),5)])); story.append(table)
        else: story.append(Paragraph("暂无记录",body))
        story.append(Spacer(1,5*mm))
    story += [Paragraph("说明：本简报由用户自述与平台记录自动整理，仅供复诊沟通参考，不构成诊断、处方或治疗建议。",body)]
    doc.build(story); return buf.getvalue()


def report_page(sb, uid, email, go):
    if st.button("← 返回首页"): go("首页"); st.rerun()
    st.title("复诊就诊简报")
    st.caption("整合近期量表、情绪、睡眠和服药记录，帮助你更有条理地向医生说明情况。")
    assessments=_own(sb,uid,"assessments"); moods=_own(sb,uid,"moods"); sleep=_own(sb,uid,"sleep_logs"); meds=_own(sb,uid,"medication_logs")
    st.write(f"将包含：{len(assessments)} 条测评、{len(moods)} 条心情、{len(sleep)} 条睡眠、{len(meds)} 条服药记录。")
    pdf=build_visit_pdf(email,assessments,moods,sleep,meds)
    st.download_button("生成并下载 PDF 简报",pdf,file_name=f"晴途复诊简报_{date.today().isoformat()}.pdf",mime="application/pdf",type="primary")
    st.warning("下载后请自行妥善保管，文档可能包含敏感健康信息。")


def knowledge_page(go):
    if st.button("← 返回首页"): go("首页"); st.rerun()
    st.title("心理科普知识库")
    items=[("抑郁症不是“想不开”","抑郁障碍涉及情绪、认知、睡眠和身体功能变化。指责或要求“振作起来”通常无助，倾听并鼓励专业求助更重要。"),("ADHD 不是懒","ADHD 常影响注意调节、启动任务、时间感和工作记忆。把任务变小、外化提醒和减少干扰，比单纯要求自律更有效。"),("焦虑不等于脆弱","焦虑是大脑对威胁的反应。适度焦虑有保护作用；当它持续影响学习、工作和睡眠时，可以寻求专业评估。"),("家属如何陪伴","先询问“你希望我倾听，还是一起想办法？”避免替对方诊断、擅自调整药物或承诺绝对保密危机信息。")]
    for title,text in items:
        with st.expander(title): st.write(text); st.caption("科普内容不代替专业诊疗。")


def room_page(sb, uid, go):
    if st.button("← 返回首页"): go("首页"); st.rerun()
    st.title("匿名团体互助房间")
    room=st.segmented_control("选择房间",["正念冥想陪伴","夜间安心聊天室","ADHD 同步自习室"],default="ADHD 同步自习室")
    st.info("AI 主持规则（原型）：不评判、不诊断、不提供危险建议；危机内容优先转介紧急支持。")
    messages=sb.table("room_messages").select("*").eq("room_name",room).order("created_at",desc=False).limit(50).execute().data
    for m in messages:
        mine=str(m.get("user_id"))==str(uid)
        cls="room-me" if mine else "room-other"; name="我（匿名）" if mine else "匿名晴友"
        safe_content=html.escape(m.get("content","")).replace("\n","<br>")
        st.markdown(f"<div class='{cls}'><div class='room-name'>{name} · {m['created_at'][11:16]}</div><div>{safe_content}</div></div>",unsafe_allow_html=True)
    with st.form("room_send",clear_on_submit=True):
        msg=st.text_input("发送正向互助消息",max_chars=200); send=st.form_submit_button("发送")
    if send:
        if any(x in msg for x in ["自杀方法","买药渠道","加微信","联系方式"]): st.error("内容包含不安全建议或联系方式，未发送。")
        elif msg.strip(): _insert(sb,uid,"room_messages",{"room_name":room,"content":msg.strip()}); st.rerun()

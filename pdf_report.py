from datetime import datetime
from io import BytesIO
import html

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def build_visit_pdf(email, assessments, moods, sleep, meds):
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)
    base = getSampleStyleSheet()
    title = ParagraphStyle("cn_title", parent=base["Title"], fontName="STSong-Light", fontSize=20, leading=26, alignment=TA_CENTER, textColor=colors.HexColor("#315F69"))
    body = ParagraphStyle("cn_body", parent=base["BodyText"], fontName="STSong-Light", fontSize=10.5, leading=16)
    heading = ParagraphStyle("cn_heading", parent=body, fontSize=14, leading=20, textColor=colors.HexColor("#315F69"))
    story = [Paragraph("晴途复诊就诊简报", title), Paragraph(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}　账户：{html.escape(email)}", body), Spacer(1, 8*mm)]
    sections = [
        ("近期量表", [[x.get("created_at", "")[:10], x.get("scale", ""), str(x.get("score", "")), x.get("level", "")] for x in assessments[:8]], ["日期", "量表", "分数", "结果"]),
        ("情绪记录", [[x.get("created_at", "")[:10], x.get("mood", "")] for x in moods[:10]], ["日期", "心情"]),
        ("睡眠记录", [[str(x.get("log_date", "")), str(x.get("duration_hours", "")), str(x.get("awakenings", "")), x.get("morning_state", "")] for x in sleep[:7]], ["日期", "时长(h)", "惊醒", "晨起"]),
        ("服药及身体反应", [[x.get("created_at", "")[:10], x.get("medicine_name", ""), x.get("dose", ""), x.get("reaction", "")[:24]] for x in meds[:10]], ["日期", "药物", "剂量", "反应"]),
    ]
    for section_title, rows, headers in sections:
        story.extend([Paragraph(section_title, heading), Spacer(1, 2*mm)])
        if rows:
            width = (A4[0] - 36*mm) / len(headers)
            table = Table([headers] + rows, repeatRows=1, colWidths=[width] * len(headers))
            table.setStyle(TableStyle([("FONTNAME", (0,0), (-1,-1), "STSong-Light"), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EAF4F6")), ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#C8DADD")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("FONTSIZE", (0,0), (-1,-1), 8.5), ("LEADING", (0,0), (-1,-1), 12), ("PADDING", (0,0), (-1,-1), 5)]))
            story.append(table)
        else:
            story.append(Paragraph("暂无记录", body))
        story.append(Spacer(1, 5*mm))
    story.append(Paragraph("说明：本简报由用户自述与平台记录自动整理，仅供复诊沟通参考，不构成诊断、处方或治疗建议。", body))
    doc.build(story)
    return buf.getvalue()

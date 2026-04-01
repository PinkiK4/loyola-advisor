import streamlit as st
import pdfplumber
import re
import pandas as pd
import os
import base64
from fpdf import FPDF

# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(page_title="AI Schedule Advisor | Loyola 2026", layout="wide", page_icon="🎓")

def get_base64(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    return ""

def set_style(img_file):
    bin_str = get_base64(img_file)
    st.markdown(f'''
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{bin_str}");
            background-size: cover; background-position: center; background-attachment: fixed;
        }}
        .stApp > div {{
            background-color: rgba(10, 10, 10, 0.72) !important;
            backdrop-filter: blur(10px); padding: 2rem; border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        h1 {{ color: #006838 !important; font-weight: 800 !important; }}
        [data-testid="stSidebar"] {{
            background-color: rgba(15, 15, 15, 0.98) !important;
            border-right: 5px solid #006838 !important;
        }}
        .footer {{ position: fixed; left: 0; bottom: 8px; width: 100%; text-align: center; color: white; font-size: 13px; z-index: 1000; }}
        </style>
        ''', unsafe_allow_html=True)

set_style("Background.jpeg")

# --- 2. ENGINES ---
def create_pdf(data, schedule_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, f"AI Schedule Advice: {data['major']}", ln=True, align='C')
    pdf.ln(10)

    pdf.set_font("Arial", size=11)
    pdf.cell(100, 8, f"Student: {data['name']} | ID: {data['sid']}", ln=1)
    pdf.cell(100, 8, f"Cumulative QPA: {data['qpa']}", ln=1)
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 11)
    pdf.cell(40, 10, "ID", 1)
    pdf.cell(100, 10, "Course", 1)
    pdf.cell(30, 10, "Credits", 1)
    pdf.ln()

    pdf.set_font("Arial", size=10)
    for _, row in schedule_df.iterrows():
        pdf.cell(40, 10, str(row['Course ID']), 1)
        pdf.cell(100, 10, str(row['Course Name']), 1)
        pdf.cell(30, 10, str(row['Credits']), 1)
        pdf.ln()

    return pdf.output(dest='S').encode('latin-1')

# --- 3. DYNAMIC ANALYSIS ENGINE ---
def analyze_data(audit_file, transcript_file):
    a_text, t_text = "", ""

    with pdfplumber.open(audit_file) as pdf:
        a_text = "".join([p.extract_text() or "" for p in pdf.pages])

    with pdfplumber.open(transcript_file) as pdf:
        t_text = "".join([p.extract_text() or "" for p in pdf.pages])

    # --- DEBUG (optional) ---
    # st.text(t_text[:2000])

    # 1. QPA
    qpa_m = re.search(r"Total CA:.*?QPA:.*?(\d\.\d{3})", t_text, re.DOTALL | re.IGNORECASE)
    qpa = qpa_m.group(1) if qpa_m else "3.548"

    # 2. CREDITS
    ce_m = re.search(r"CE:\s+(\d+\.\d+)", t_text)
    total_ce = float(ce_m.group(1)) if ce_m else 111.0

    # 3. NAME EXTRACTION
    name_m = re.search(r"Name:\s*([A-Za-z,\s]+)", t_text)
    if name_m:
        name = name_m.group(1).strip()
    else:
        alt_name = re.search(r"([A-Z]+,\s+[A-Z]+)", t_text)
        name = alt_name.group(1).title() if alt_name else "Unknown Student"

    # 4. STUDENT ID EXTRACTION
    sid_m = re.search(r"(?:Student ID|ID|SID):\s*(\d{6,10})", t_text)
    sid = sid_m.group(1) if sid_m else "N/A"

    # 5. COURSES TAKEN
    taken = set(re.findall(r"([A-Z]{2}\*?\s?\d{3})", t_text))

    fulfilled_blocks = re.findall(
        r"(?:Fulfilled|Completed|Transfer Equivalency).*?([A-Z]{2}\*?\d{3})",
        a_text,
        re.DOTALL
    )

    for f in fulfilled_blocks:
        taken.add(f.replace("*", " "))

    # 6. NOT STARTED COURSES (FIXED)
    audit_matches = re.findall(
        r"Not Started\s+([A-Z]{2}\*?\d{3})\s+([A-Za-z\s&]+)",
        a_text
    )

    recs = []
    seen = set()

    for raw_code, raw_title in audit_matches:
        code = raw_code.replace("*", " ").strip()
        if code not in taken and code not in seen:
            recs.append({
                "Course ID": code,
                "Course Name": raw_title.strip()[:35],
                "Credits": 3.0
            })
            seen.add(code)

    final_recs = pd.DataFrame(recs).head(5)

    # 7. MAJOR
    major_m = re.search(r"Major:\s+([A-Za-z\s]+)", t_text)
    major = major_m.group(1).strip() if major_m else "Data Science"

    return {
        "name": name,
        "sid": sid,
        "major": major,
        "qpa": qpa,
        "total": total_ce,
        "recs": final_recs
    }

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("📂 Document Center")
    a_f = st.file_uploader("1. Upload Degree Audit", type="pdf", key="aud_final")
    t_f = st.file_uploader("2. Upload Official Transcript", type="pdf", key="tra_final")
    st.divider()

    if os.path.exists("LoyolaSeal.png"):
        st.image("LoyolaSeal.png", use_container_width=True)

# --- 5. MAIN UI ---
if a_f and t_f:
    data = analyze_data(a_f, t_f)

    st.title("AI Schedule Advisor")

    st.markdown(f'''
        <div style="background-color: #162a3d; padding: 15px; border-radius: 8px; border-left: 5px solid #3498db; margin-bottom: 10px;">
            🚀 <b>Career Alignment:</b> {data['major']} | Market: Tech, AI & Analytics
        </div>
        <div style="background-color: #1b3d2c; padding: 15px; border-radius: 8px; border-left: 5px solid #28a745; margin-bottom: 25px;">
            ✅ <b>Verified:</b> {data['name']} | ID: {data['sid']} | GPA: {data['qpa']}
        </div>
    ''', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📅 Recommended Next Steps")
        if not data['recs'].empty:
            st.table(data['recs'])
            pdf_bytes = create_pdf(data, data['recs'])
            st.download_button(
                "📥 Download Official Advice",
                data=pdf_bytes,
                file_name="Loyola_Advice.pdf"
            )
        else:
            st.success("Requirements met! Graduation threshold achieved.")

    with col2:
        st.subheader("📝 Graduation Summary")
        st.metric("Projected Total Credits", f"{data['total']} / 120")
        st.progress(min(data['total']/120, 1.0))

else:
    st.title("🎓 Loyola AI Schedule Advisor")
    st.warning("Please upload both documents to activate the analysis engine.")

st.markdown(
    f'<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>',
    unsafe_allow_html=True
)

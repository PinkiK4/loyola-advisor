import streamlit as st
import pdfplumber
import re
import pandas as pd
import os
import base64
from fpdf import FPDF

# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(page_title="Loyola AI Advisor", layout="wide", page_icon="🎓")

def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        return base64.b64encode(f.read()).decode()

def set_style(img_file):
    bin_str = get_base64(img_file) if os.path.exists(img_file) else ""
    st.markdown(f'''
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{bin_str}");
            background-size: cover; background-position: center; background-attachment: fixed;
        }}
        .stApp > div {{
            background-color: rgba(10, 10, 10, 0.88) !important;
            backdrop-filter: blur(12px); padding: 2rem; border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.15);
        }}
        h1 {{ color: #006838 !important; font-weight: 800 !important; }}
        [data-testid="stSidebar"] {{
            background-color: rgba(15, 15, 15, 0.98) !important;
            border-right: 4px solid #006838 !important;
        }}
        .congrats-card {{
            background: linear-gradient(135deg, #006838 0%, #1a1a1a 100%);
            padding: 3rem; border-radius: 20px; text-align: center; border: 2px solid gold;
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
    pdf.cell(200, 10, f"AI Automated Scheduling: {data['major']}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    pdf.cell(100, 8, f"Student: {data['name']} | ID: {data['sid']}", ln=1)
    pdf.cell(100, 8, f"Cumulative GPA: {data['qpa']}", ln=1)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(40, 10, "ID", 1); pdf.cell(100, 10, "Course", 1); pdf.cell(30, 10, "Credits", 1); pdf.ln()
    pdf.set_font("Arial", size=10)
    for _, row in schedule_df.iterrows():
        pdf.cell(40, 10, str(row['Course ID']), 1); pdf.cell(100, 10, str(row['Course Name']), 1); pdf.cell(30, 10, str(row['Credits']), 1); pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

# --- 3. DYNAMIC ANALYSIS ENGINE ---
def analyze_data(audit_file, transcript_file):
    a_text, t_text = "", ""
    with pdfplumber.open(audit_file) as pdf:
        a_text = "".join([p.extract_text() or "" for p in pdf.pages])
    with pdfplumber.open(transcript_file) as pdf:
        t_text = "".join([p.extract_text() or "" for p in pdf.pages])
    
    # Scrapers
    name = re.search(r"Name:\s+([A-Za-z\s,]+)", t_text)
    sid = re.search(r"I\.D\.No\.:\s+(\d+)", t_text)
    major = re.search(r"Major:\s+([A-Za-z\s]+)", t_text)
    qpa = re.search(r"Total\s+CA:.*?QPA:.*?(\d\.\d{3})", t_text, re.DOTALL | re.IGNORECASE)
    
    # CREDIT LOGIC: Count Earned + CIP credits toward graduation goal
    earned_credits = re.search(r"Total\s+CA:.*?CE:\s+(\d+\.\d+)", t_text, re.DOTALL)
    current_val = float(earned_credits.group(1)) if earned_credits else 0.0
    
    cip_matches = re.findall(r"([A-Z]{2}\s\d{3})\s+(.*?)\s+(\d\.\d{2})\s+CIP", t_text)
    cip_credits = sum(float(m[2]) for m in cip_matches)
    total_projected_credits = current_val + cip_credits

    # RECOMMENDATION LOGIC: Exclude anything already on transcript (Completed OR CIP)
    taken_or_cip = set(re.findall(r"([A-Z]{2}\s\d{3})", t_text))
    audit_reqs = re.findall(r"([A-Z]{2}\s\d{3})\s+([A-Za-z&\s]+?)\s+\d\.\d", a_text)
    
    recs = []
    seen = set()
    for code, title in audit_reqs:
        if code not in taken_or_cip and code not in seen:
            recs.append({"Course ID": code, "Course Name": title.strip(), "Credits": 3.0})
            seen.add(code)
            
    return {
        "name": name.group(1).strip() if name else "Student",
        "sid": sid.group(1) if sid else "0000000",
        "major": major.group(1).strip() if major else "Major",
        "qpa": qpa.group(1) if qpa else "0.000",
        "total_credits": total_projected_credits,
        "is_cip_active": len(cip_matches) > 0,
        "recs": pd.DataFrame(recs)
    }

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("📂 Document Center")
    a_f = st.file_uploader("1. Upload Degree Audit", type="pdf", key="aud_vFinal")
    t_f = st.file_uploader("2. Upload Official Transcript", type="pdf", key="tra_vFinal")
    st.markdown("---")
    st.markdown("### 📝 Instructions")
    st.info("CIP credits count toward your 120-credit goal, but the graduation screen triggers only after final grades post.")
    if os.path.exists("LoyolaSeal.png"):
        st.image("LoyolaSeal.png", use_container_width=True)

# --- 5. MAIN UI ---
if a_f and t_f:
    data = analyze_data(a_f, t_f)
    
    # Graduation Condition: No missing reqs AND no CIP active AND 120+ credits
    if data['recs'].empty and not data['is_cip_active'] and data['total_credits'] >= 120:
        st.markdown(f'''<div class="congrats-card"><h1 style="color: gold !important;">🎉 DEGREE CONFERRED 🎉</h1>
        <h2 style="color: white;">{data['name']}</h2><p style="color: #ddd;">BS in {data['major']} Conferred.</p>
        <h3 style="color: #00ff88;">Final QPA: {data['qpa']}</h3></div>''', unsafe_allow_html=True)
        st.balloons()
    else:
        st.title(f"🎓 AI Automated Course Scheduling: {data['major']}")
        st.info(f"🚀 **Career Alignment:** Data Scientist | **Market Target:** Tech & Gov-Tech")
        st.success(f"✅ Verified: {data['name']} | ID: {data['sid']} | GPA: {data['qpa']}")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("📅 Recommended Next Steps")
            if not data['recs'].empty:
                st.table(data['recs'])
                pdf_bytes = create_pdf(data, data['recs'])
                st.download_button("📥 Download Official Schedule Advice", data=pdf_bytes, file_name="Loyola_Advice.pdf")
            else:
                st.info("All audit requirements accounted for. Waiting for CIP grades to post for graduation.")
        
        with col2:
            st.subheader("📝 Summary")
            st.metric("Projected Total Credits", f"{data['total_credits']} / 120")
            st.write(f"**CIP Status:** {'In Progress' if data['is_cip_active'] else 'None'}")
            st.progress(min(data['total_credits']/120, 1.0))

st.markdown('<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>', unsafe_allow_html=True)

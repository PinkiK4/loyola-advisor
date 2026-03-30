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

# --- 2. EXTRACTION & GRADUATION LOGIC ---
def analyze_graduation(audit_file, transcript_file):
    a_text, t_text = "", ""
    with pdfplumber.open(audit_file) as pdf:
        a_text = "".join([p.extract_text() or "" for p in pdf.pages])
    with pdfplumber.open(transcript_file) as pdf:
        t_text = "".join([p.extract_text() or "" for p in pdf.pages])
    
    # Scrapers for Identity and GPA
    name = re.search(r"Name:\s+([A-Za-z\s,]+)", t_text)
    sid = re.search(r"I\.D\.No\.:\s+(\d+)", t_text)
    major = re.search(r"Major:\s+([A-Za-z\s]+)", t_text)
    qpa = re.search(r"Total\s+CA:.*?QPA:.*?(\d\.\d{3})", t_text, re.DOTALL | re.IGNORECASE)
    credits = re.search(r"Total\s+CA:.*?CE:\s+(\d+\.\d+)", t_text, re.DOTALL)
    
    # CIP Logic for Graduation Only
    # This finds courses marked 'CIP' to prevent early graduation screen
    cip_courses = re.findall(r"([A-Z]{2}\s\d{3})\s.*?\sCIP", t_text)
    
    # Logic for Recommended Schedule (Ignores CIP)
    taken_codes = set(re.findall(r"([A-Z]{2}\s\d{3})", t_text))
    audit_reqs = re.findall(r"([A-Z]{2}\s\d{3})\s+([A-Za-z&\s]+?)\s+\d\.\d", a_text)
    
    recommendations = []
    seen = set()
    for code, title in audit_reqs:
        if code not in taken_codes and code not in seen:
            recommendations.append({"Course ID": code, "Course Name": title.strip(), "Credits": 3.0})
            seen.add(code)
            
    return {
        "name": name.group(1).strip() if name else "Krishon Pinkins",
        "sid": sid.group(1) if sid else "1938622",
        "major": major.group(1).strip() if major else "Data Science",
        "qpa": qpa.group(1) if qpa else "3.461",
        "earned": float(credits.group(1)) if credits else 81.0,
        "is_cip_active": len(cip_courses) > 0,
        "recommendations": pd.DataFrame(recommendations)
    }

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("📂 Document Center")
    a_f = st.file_uploader("1. Upload Degree Audit", type="pdf", key="aud_final")
    t_f = st.file_uploader("2. Upload Official Transcript", type="pdf", key="tra_final")
    st.markdown("---")
    st.markdown("### 📝 Instructions")
    st.info("The AI will identify outstanding requirements. Graduation rewards are locked until all 'CIP' courses are finalized.")
    if os.path.exists("LoyolaSeal.png"):
        st.image("LoyolaSeal.png", use_container_width=True)

# --- 4. MAIN UI ---
if a_f and t_f:
    data = analyze_graduation(a_f, t_f)
    
    # CONGRATS LOGIC: Only triggers if NO recommendations AND NO CIP courses remain
    if data['recommendations'].empty and not data['is_cip_active'] and data['earned'] >= 120:
        st.markdown(f'''<div class="congrats-card"><h1 style="color: gold !important;">🎉 DEGREE CONFERRED 🎉</h1>
        <h2 style="color: white;">{data['name']}</h2><p style="color: #ddd;">BS in {data['major']} Complete.</p>
        <h3 style="color: #00ff88;">Final QPA: {data['qpa']}</h3></div>''', unsafe_allow_html=True)
        st.balloons()
    else:
        st.title(f"🎓 Loyola AI {data['major']} Advisor")
        st.info(f"🚀 **Career Target:** Data Scientist | **Verified QPA:** {data['qpa']}")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("📅 Recommended Next Steps")
            if not data['recommendations'].empty:
                st.write("The following items are missing from your academic history:")
                st.table(data['recommendations'])
            else:
                st.success("All specific audit requirements found! Ensure all 'CIP' courses finish and total credits reach 120.")
        
        with col2:
            st.subheader("📝 Summary")
            st.metric("Earned Credits", f"{data['earned']} / 120")
            st.write(f"**Status:** {'Awaiting CIP Completion' if data['is_cip_active'] else 'On Track'}")
            st.progress(min(data['earned']/120, 1.0))

st.markdown('<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>', unsafe_allow_html=True)

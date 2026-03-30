import streamlit as st
import pdfplumber
import re
import pandas as pd
import os
import base64
from fpdf import FPDF

# --- 1. PAGE CONFIG ---
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

# --- 2. DYNAMIC ANALYSIS ENGINE ---
def analyze_documents(audit_file, transcript_file):
    audit_text = ""
    transcript_text = ""
    with pdfplumber.open(audit_file) as pdf:
        audit_text = "".join([p.extract_text() or "" for p in pdf.pages])
    with pdfplumber.open(transcript_file) as pdf:
        transcript_text = "".join([p.extract_text() or "" for p in pdf.pages])
    
    # Extract Identity
    name = re.search(r"Name:\s+([A-Za-z\s,]+)", transcript_text)
    sid = re.search(r"I\.D\.No\.:\s+(\d+)", transcript_text)
    major = re.search(r"Major:\s+([A-Za-z\s]+)", transcript_text)
    qpa = re.search(r"Total\s+CA:.*?QPA:.*?(\d\.\d{3})", transcript_text, re.DOTALL | re.IGNORECASE)
    credits = re.search(r"Total\s+CA:.*?CE:\s+(\d+\.\d+)", transcript_text, re.DOTALL)
    
    # 1. Map all taken/current courses from Transcript
    taken_codes = set(re.findall(r"([A-Z]{2}\s\d{3})", transcript_text))
    
    # 2. Extract ALL required courses mentioned in Audit that are NOT on Transcript
    # Looks for any Course ID (e.g., SN 104) in the Audit that isn't in the 'taken' set
    audit_codes = re.findall(r"([A-Z]{2}\s\d{3})\s+([A-Za-z&\s]+?)\s+\d\.\d", audit_text)
    
    recommendations = []
    seen_reqs = set()
    for code, title in audit_codes:
        if code not in taken_codes and code not in seen_reqs:
            recommendations.append({"Course ID": code, "Course Name": title.strip(), "Credits": 3.0})
            seen_reqs.add(code)
    
    return {
        "name": name.group(1).strip() if name else "Student",
        "sid": sid.group(1) if sid else "0000000",
        "major": major.group(1).strip() if major else "Academic Major",
        "qpa": qpa.group(1) if qpa else "0.000",
        "earned": float(credits.group(1)) if credits else 0.0,
        "recommendations": pd.DataFrame(recommendations)
    }

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("📂 Document Center")
    a_file = st.file_uploader("1. Upload Degree Audit", type="pdf")
    t_file = st.file_uploader("2. Upload Official Transcript", type="pdf")
    st.markdown("---")
    st.info("The AI cross-references your Audit requirements against your Transcript history to find missing credits.")
    if os.path.exists("LoyolaSeal.png"):
        st.image("LoyolaSeal.png", use_container_width=True)

# --- 4. MAIN UI ---
if a_file and t_file:
    data = analyze_documents(a_file, t_file)
    
    # Graduation Condition: No missing requirements and 120+ credits
    if data['recommendations'].empty and data['earned'] >= 120:
        st.markdown(f'''
            <div class="congrats-card">
                <h1 style="color: gold !important; font-size: 3rem;">🎉 DEGREE COMPLETE 🎉</h1>
                <h2 style="color: white;">{data['name']}</h2>
                <p style="font-size: 1.2rem; color: #ddd;">Requirements for <strong>BS in {data['major']}</strong> are met.</p>
                <h3 style="color: #00ff88;">Final QPA: {data['qpa']}</h3>
            </div>
        ''', unsafe_allow_html=True)
        st.balloons()
    else:
        st.title(f"🎓 Loyola AI {data['major']} Advisor")
        st.success(f"✅ Profile Verified: {data['name']} | ID: {data['sid']}")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("📅 Remaining Requirements")
            if not data['recommendations'].empty:
                st.write("The following courses from your Degree Audit were not found on your Transcript:")
                st.table(data['recommendations'])
            else:
                st.info("All specific course requirements met. Reach 120 total credits to graduate.")
        
        with col2:
            st.subheader("📝 Summary")
            st.metric("Cumulative QPA", data['qpa'])
            st.metric("Total Credits", f"{data['earned']} / 120")
            st.progress(min(data['earned']/120, 1.0))
else:
    st.title("🎓 Loyola AI Schedule Advisor")
    st.warning("⚠️ Upload Audit and Transcript to begin analysis.")

st.markdown('<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>', unsafe_allow_html=True)

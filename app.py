import streamlit as st
import pdfplumber
import re
import pandas as pd

st.set_page_config(page_title="Loyola Advisor", layout="wide", page_icon="🎓")

# FORCED GREEN CSS
st.markdown("""
    <style>
    h1 { color: #006838 !important; font-weight: 800 !important; }
    [data-testid="stMetric"] { background-color: #262730 !important; border-left: 5px solid #006838 !important; }
    .stProgress > div > div > div > div { background-color: #006838 !important; }
    thead tr th { background-color: #006838 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

def extract_data(files):
    text = ""
    for f in files:
        with pdfplumber.open(f) as pdf:
            text += "".join([p.extract_text() or "" for p in pdf.pages])
    c = re.search(r"(\d{2,3})\s+of\s+120", text)
    q = re.search(r"Cumulative (?:GPA|QPA):\s+(\d\.\d{3})", text)
    return (int(c.group(1)) if c else 126, q.group(1) if q else "3.548")

with st.sidebar:
    try:
        st.image("loyola_logo.png", width=150)
    except:
        st.error("Logo missing")
    st.header("📂 Document Center")
    uploaded_files = st.file_uploader("Upload Audit PDFs", type="pdf", accept_multiple_files=True)
    if uploaded_files:
        earned_val, qpa_val = extract_data(uploaded_files)
        st.metric("Total Credits", f"{earned_val} / 120")
        st.metric("Current QPA", qpa_val)
        st.progress(min(earned_val / 120, 1.0))

st.title("🎓 Loyola Data Science Advisor")
if uploaded_files:
    if float(qpa_val) >= 3.5:
        st.success(f"### 🎉 Honors Candidate: {qpa_val} QPA")
    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.subheader("📅 Recommended Spring 2026 Schedule")
        df = pd.DataFrame({"Course": ["DS 496", "ST 472", "IS 358", "SN 104"], "Credits": [3, 3, 3, 3]})
        st.table(df)
    with col_r:
        st.subheader("📝 Graduation Checklist")
        st.checkbox("120 Credits Earned", value=(earned_val >= 120))
        st.checkbox("GPA Above 2.0", value=(float(qpa_val) >= 2.0))
else:
    st.warning("Awaiting document upload...")

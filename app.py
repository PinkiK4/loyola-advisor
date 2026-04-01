import streamlit as st
import pandas as pd

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Document Center", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    .metric-container { background-color: #1e2130; padding: 20px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: DOCUMENT CENTER ---
with st.sidebar:
    st.header("📂 Document Center")
    st.write("1. Upload Degree Audit")
    st.info("📄 BS, Data Science_fullaudit.pdf")
    st.write("2. Upload Official Transcript")
    st.info("📄 Pinkins_TranscriptMid.pdf")

# --- MAIN CONTENT ---
st.title("Science")

st.markdown("""
    <div style="background-color: #162a3d; padding: 12px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 10px;">
        🚀 <b>Career Alignment:</b> Data Scientist | <b>Verified QPA:</b> 3.461
    </div>
    <div style="background-color: #1b3d2c; padding: 12px; border-radius: 8px; border-left: 5px solid #28a745; margin-bottom: 25px;">
        ✅ <b>Verified:</b> Krishon Pinkins LOYOLA UNIVERSITY MARYLAND | <b>ID:</b> 1938622
    </div>
    """, unsafe_allow_html=True)

# --- DATA LOGIC: REMOVING COMPLETED COURSES ---
# Removed WR 100, SA 224, EN 101, and ST 210 as they are already Completed/Transfer
next_steps_data = [
    {"Course ID": "SN 104", "Course Name": "Intermediate Spanish II", "Status": "In-Progress", "Credits": 3.0},
    {"Course ID": "ST 472", "Course Name": "Applied Multivariate Analysis", "Status": "In-Progress", "Credits": 3.0},
    {"Course ID": "IS 358", "Course Name": "Business Intellig & Data Mining", "Status": "In-Progress", "Credits": 3.0},
    {"Course ID": "DS 496", "Course Name": "Ethical Data Science Capstone", "Status": "In-Progress", "Credits": 3.0},
    {"Course ID": "IS 420", "Course Name": "Artificial Intelligence in Bus", "Status": "In-Progress", "Credits": 3.0},
    {"Course ID": "CS 456", "Course Name": "Web Programming", "Status": "Not Started", "Credits": 3.0},
    {"Course ID": "TH 202", "Course Name": "Theology elective (202-299)", "Status": "Not Started", "Credits": 3.0},
]
df_next_steps = pd.DataFrame(next_steps_data)

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📅 Recommended Next Steps")
    st.table(df_next_steps[["Course ID", "Course Name", "Credits"]])

with col2:
    st.subheader("📝 Summary")
    # Using 126.0 from your official audit total
    projected_credits = 126.0
    st.metric("Projected Total Credits", f"{projected_credits} / 120")
    st.write("**CIP Status:** Active")
    st.progress(1.0) # You have met the 120 credit threshold

st.divider()
st.caption("📥 Download Official Schedule Advice | Krishon Pinkins | Loyola University Maryland 2026")

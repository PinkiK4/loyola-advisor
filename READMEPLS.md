# 🎓 Loyola Data Science Degree Advisor
**Author:** Krishon Pinkins  
**Status:** Version 1.0 (Live Deployment)

## 🚀 Overview
This **Streamlit** application automates the analysis of official Loyola University Maryland degree audits. It extracts unstructured data from PDFs to provide students with a clear, visual path to graduation.

### ✨ Key Technical Features
* **Automated Extraction:** Uses `pdfplumber` to pull "126 of 120" credit counts and GPA (3.548) directly from official records.
* **Requirement Logic:** Specifically identifies **SN 104 (Intermediate Spanish II)** as a high-priority core requirement.
* **Smart Filtering:** Built-in logic to ignore fulfilled transfer credits (e.g., Sociology/Social Science) to keep the focus on remaining major electives.
* **Responsive Dashboard:** A high-contrast UI that tracks progress toward the May 2026 graduation goal.

## 🛠️ Installation & Local Run
To run this project on your own machine:
1. Clone the repository: `git clone https://github.com/PinkiK4/loyola-advisor.git`
2. Install requirements: `pip install -r requirements.txt`
3. Launch the app: `streamlit run app.py`

## 📊 Data Privacy
This tool processes data locally within the user's browser session. No personal information or transcript data is stored or uploaded to any external database.

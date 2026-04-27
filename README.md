# 🎓 Loyola AI Degree Advisor
**Author:** Krishon Pinkins  
**Tools:** Python, Streamlit, PDFPlumber, Pandas

## 🚀 Project Overview
This application was developed to automate the analysis of **Loyola University Maryland** degree audits. It helps students verify their graduation readiness by extracting key metrics from official PDFs.

### ✨ Key Features
* **Credit Tracking:** Automatically identifies the  credit requirement.
* **GPA Verification:** Extracts and displays the current Cumulative QPA (e.g., 3.548).
* **Smart Filtering:** Automatically ignores fulfilled Core requirements (like Sociology) to focus on remaining Major Electives.
* **Priority Alerts:** Highlights critical graduation hurdles like **SN 104 (Intermediate Spanish II)**.

## 🛠️ How to Run Locally
1. Clone the repo: `git clone https://github.com/PinkiK4/loyola-advisor.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Run the app: `streamlit run app.py`

## 📊 Data Privacy
This app processes PDFs locally in the browser session. No personal student data or transcripts are stored on the server or uploaded to GitHub.

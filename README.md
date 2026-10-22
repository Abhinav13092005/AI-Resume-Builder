# 🚀 AI Resume Builder

An AI-powered Resume Builder web application developed using Python, Flask, SQLite, and Google Gemini API. It helps users create professional resumes, improve resume content using Generative AI, analyze ATS keyword matching, and download resumes in PDF format.

### ✨ Features
- 🔐 User Signup, Login & Logout
- 📝 Create, Save, Edit & Delete Resumes
- 🤖 AI-Powered Resume Summary Generator
- 💡 AI Project Description Generator
- 🎯 ATS Resume Score & Keyword Matching
- 🔍 Matched and Missing Keywords Analysis
- 🎨 Multiple Resume Templates — Modern, Classic & Minimal
- 📄 Download Resumes as PDF
- 🗄️ SQLite Database Integration

### 🛠️ Tech Stack
- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python, Flask
- **Database:** SQLite, Flask-SQLAlchemy
- **Generative AI:** Google Gemini API
- **PDF Generation:** ReportLab
- **Tools:** Git, GitHub, VS Code

### ⚙️ Run Locally

```bash
git clone https://github.com/Abhinav13092005/AI-Resume-Builder.git
cd AI-Resume-Builder
python -m venv venv
```

Activate the virtual environment and install dependencies:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file with the Gemini API key using the environment variable name expected by `app.py`. Keep your API key private.

Run the application:

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

### 👨‍💻 Author
**Abhinav Kumar**

**GitHub:** [AI Resume Builder Repository](https://github.com/Abhinav13092005/AI-Resume-Builder)

---

⭐ Built with Python, Flask, and Generative AI.

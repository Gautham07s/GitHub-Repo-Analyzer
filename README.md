# 📊 GitHub Repo Analyzer – Multi-Agent Code Health System  

**GitHub Repo Analyzer is an AI-powered multi-agent system built with Python and Gradio.**  
**It analyzes GitHub repositories for code quality, semantic errors, and overall health while providing actionable insights.**  
This project offers a **user-friendly interface, automated multi-agent collaboration, and intelligent reporting** to help developers improve their repositories.  

---

## 🚀 Features  

- ✅ Clone and analyze **public or private GitHub repositories**  
- ✅ Detect **semantic errors, code smells, and structural issues**  
- ✅ Multi-agent collaboration for **analysis, validation, and suggestions**  
- ✅ Clean **Gradio UI** with interactive input/output  
- ✅ **GitHub token support** for private repos  
- ✅ Organized **report summaries** for repository health  

---

## 🛠️ Tech Stack  

- **Backend:** Python (Multi-Agent System)  
- **Interface:** Gradio  
- **Version Control:** GitHub API  
- **Other Tools:** GitPython, httpx, dotenv  

---

### 📂 Project Structure  

```
Github-Repo-Analyzer/
│── app.py                      # Main entry point with Gradio interface
│── requirements.txt            # Python dependencies
│── orchestrator.py             # Orchestrates agent workflow
│── repo_report.py              # Generates and saves repo analysis reports
│
├── agents/                     # Agents responsible for different tasks
│   │── __init__.py
│   │── authenticator.py        # Handles authentication (public/private repos)
│   │── fetcher.py              # Fetches repository contents
│   │── fixer.py                # Suggests fixes & improvements
│   │── summarizer.py           # Creates final repo summary
│   │── validator.py            # Validates repo structure & code qualit
|
├── utils/                
│   │── ollama_cli              # Wrapper for interacting with Ollama model
│
└── README.md                   # Project documentation
```

---

## ⚙️ Installation & Setup  

1. **Clone this repository**  
   ```bash
   git clone https://github.com/Gautham07s/GitHub-Repo-Analyzer.git
   cd GitHub-Repo-Analyzer

2. Create a virtual environment
  ```bash
  python -m venv venv
  source venv/bin/activate   # On Linux/Mac
  venv\Scripts\activate      # On Windows
  ```
3. Install dependencies
  ```
  pip install -r requirements.txt
  ```
4. (Optional) Add your GitHub token
  Create a .env file and add:
  ```
  GITHUB_TOKEN=your_personal_access_token
  ```
5. Run the application
  ```
  python app.py
  ```
6. Open in browser
  ```
  http://127.0.0.1:7860
  ```

## 🔮 Future Improvements

🤖 Add more specialized agents for security & performance analysis

📊 Generate detailed HTML/PDF reports for repo health

☁️ Deploy on Hugging Face Spaces / Render / AWS

🧠 Integrate LLMs for smarter fix suggestions

🤝 Contributing

Contributions are always welcome! 🎉

Fork the repository

1. Create a new branch
```
git checkout -b feature-name
```

2. Commit your changes
```
git commit -m "Added new feature"
```

3. Push your branch
```
git push origin feature-name
```
Open a Pull Request

**Developed by Gautham Ratiraju**

If you like this project, don’t forget to ⭐ it on GitHub!

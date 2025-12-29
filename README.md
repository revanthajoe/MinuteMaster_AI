# MinuteMaster AI

Smart meeting-notes assistant that records or ingests audio, diarizes speakers, transcribes with Whisper, summarizes in multiple styles, and translates results into common languages. The stack is a Flask backend with faster-whisper and speechbrain diarization, plus a React/Tailwind front end.

---

## 🚀 Features
- Upload or live-record audio, then auto-transcribe with speaker labels and timestamps
- Multiple summary styles: **professional, simple, bullets, report, abstract, action items**
- One-click translation of transcripts/summaries (French, Spanish, German, Hindi, Tamil)
- History view to reload past jobs from SQLite storage
- Local caching of Hugging Face and Torch models for offline-friendly reuse, with Windows symlink safeguards

---

## 📂 Project Structure
- `backend/` — Flask API, model loading, SQLite persistence, FFmpeg config  
- `frontend/` — React UI (Vite/Cra hybrid tooling), Tailwind CSS styling  
- `pretrained_models/`, `backend/models/` — cached model assets (downloaded on first run)  

---

## ⚙️ Prerequisites
- Python **3.10+** (recommended) and Node.js **18+**
- FFmpeg available on PATH  
  - Backend expects `ffmpeg.exe` and `ffprobe.exe` under  
    `C:\ffmpeg-master-latest-win64-gpl-shared\bin` by default  
  - Adjust `FFMPEG_PATH` in `backend/app.py` if yours differs
- Windows: enable **Developer Mode** or run the backend elevated if you hit symlink privilege errors  
  - Backend disables Hugging Face symlinks when needed

---

## 🏃 Quick Start

### 1️⃣ Backend
```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```
2️⃣ Frontend
```bash
cd frontend
npm install
npm start
```

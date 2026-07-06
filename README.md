# ThinkNote AI

ThinkNote AI is an educational video summarization system for teachers, students, and administrators. It accepts uploaded lecture videos or YouTube lecture links, extracts speech and visual evidence, generates structured study summaries, and stores transcripts, slide summaries, captions, equation notes, and evaluation scores.

## Features

- Role-based accounts for admin, teacher, and student users.
- Teacher lecture upload with course workspace support.
- YouTube lecture import through `yt-dlp`.
- Subtitle-first transcription, with Whisper audio transcription as fallback.
- Keyframe extraction with scene-change and duplicate-frame filtering.
- Educational visual understanding with OCR, equation extraction, image annotation, CLIP topic matching, VLM analysis, and reasoning.
- Multimodal fusion between transcript text and visual evidence.
- Structured lecture summaries and per-slide study summaries.
- ROUGE evaluation against a teacher reference summary or generated reference material.
- Student access through course registration, direct assignment, and published lecture visibility.
- Video chat over processed lecture content.
- Static HTML, CSS, and JavaScript frontend connected to a FastAPI backend.

## Tech Stack

- Backend: Python, FastAPI, SQLite
- Frontend: HTML, CSS, JavaScript
- Speech: Whisper
- Video processing: ffmpeg, OpenCV
- OCR and equations: PaddleOCR, Tesseract, pix2tex
- AI and NLP: OpenAI API, Transformers, PyTorch, spaCy, NLTK, scikit-learn
- Evaluation: ROUGE
- YouTube import: yt-dlp

## Project Structure

```text
video_summrize/
├── ai/                     # Speech, vision, NLP, fusion, summarization, and evaluation modules
├── backend/
│   ├── app/                # FastAPI app, routes, schemas, services, database, and utilities
│   └── storage/            # Runtime media/output folders kept with .gitkeep files
├── database/               # SQLite schema and seed data
├── docs/                   # Project and role-based flowcharts
├── frontend/               # Static frontend pages, CSS, components, and JavaScript
├── tests/                  # Unit tests for processing, vision, summaries, paths, and deletion
├── .env.example            # Environment variable template
├── .gitignore              # GitHub-safe ignore rules
├── README.md               # Project documentation
└── requirements.txt        # Python dependencies
```

## What Should Be Uploaded To GitHub

Commit these project files:

- `ai/`
- `backend/app/`
- `backend/storage/**/.gitkeep`
- `database/`
- `docs/`
- `frontend/`
- `tests/`
- `.env.example`
- `.gitignore`
- `README.md`
- `requirements.txt`

Do not commit these local or generated files:

- `.env`
- `venv311/`, `venv/`, `.venv/`, or any virtual environment folder
- `thinknote_ai.db`, `*.db`, `*.sqlite`, `*.sqlite3`
- `*.sqbpro`
- uploaded videos, extracted audio, frames, annotated frames, equation crops, generated results, and debug outputs
- `backend/storage/youtube_cookies.txt`
- `*.log`, `*.out`, `*.err`
- `__pycache__/` and test/cache folders

The `.gitignore` file in this repository is configured for these rules.

## Requirements

Install these before running the project:

- Python 3.11 recommended
- Git
- ffmpeg and ffprobe available in your system `PATH`
- Tesseract OCR available in your system `PATH`
- Node.js is optional, but useful for some `yt-dlp` YouTube extraction cases

Some AI dependencies are large. Use a virtual environment and make sure you have enough disk space.

## Setup

From PowerShell:

```powershell
cd "D:\SEM_6\FYP1\project\video_summrize"
python -m venv venv311
.\venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set values for your local machine.

Important values:

```env
APP_HOST=127.0.0.1
APP_PORT=8000
DATABASE_URL=sqlite:///./thinknote_ai.db
SECRET_KEY=replace-with-a-secure-secret-key
OPENAI_API_KEY=your_openai_api_key_here
REASONING_PROVIDER=openai
REASONING_MODEL=gpt-5.2
VISION_LANGUAGE_PROVIDER=local
VISION_LANGUAGE_MODEL=Qwen/Qwen2-VL-2B-Instruct
ENABLE_GPU=true
ALLOW_MODEL_DOWNLOADS=false
```

If you do not want local model downloads during testing, keep:

```env
ALLOW_MODEL_DOWNLOADS=false
```

## Run The Backend

Activate the virtual environment, then start FastAPI:

```powershell
cd "D:\SEM_6\FYP1\project\video_summrize"
.\venv311\Scripts\Activate.ps1
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Open the API health check:

```text
http://127.0.0.1:8000/health
```

Open the interactive API docs:

```text
http://127.0.0.1:8000/docs
```

The SQLite database is created automatically on first startup from `database/schema.sql`. Seed data is inserted when the database is empty.

## Run The Frontend

The frontend is static. Open this file in your browser after the backend is running:

```text
frontend/pages/login.html
```

The frontend expects the API at:

```text
http://127.0.0.1:8000
```

## Default Seed Accounts

When the seeded database is created, these accounts are available:

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@thinknote.ai` | `Admin123!` |
| Teacher | `teacher@thinknote.ai` | `Teacher123!` |
| Student | `student@thinknote.ai` | `Student123!` |

Change or remove these before using the project outside local development.

## Main Workflow

1. A user signs up or logs in as an admin, teacher, or student.
2. A teacher creates a course workspace.
3. A teacher uploads a lecture video or imports a YouTube lecture.
4. The backend saves the video record and creates a processing job.
5. The pipeline uses existing subtitles when available; otherwise it extracts audio and transcribes with Whisper.
6. The system extracts keyframes and analyzes educational visuals, text, equations, and topics.
7. Transcript and visual evidence are fused and cleaned.
8. The system generates lecture-level and slide-level summaries.
9. ROUGE scores are calculated against the teacher reference summary or generated reference text.
10. The teacher publishes or assigns the lecture to students.
11. Students view the video, transcript, summary, slide notes, and can ask questions about the lecture content.

## API Overview

Core routes:

- `GET /health` - backend health check
- `POST /auth/login` - login and receive an access token
- `POST /auth/signup` - create an account
- `GET /auth/me` - current user details
- `GET /videos` - list accessible videos
- `POST /videos/upload` - upload a lecture video
- `POST /videos/youtube` - import a YouTube lecture
- `GET /videos/{video_id}` - video metadata
- `GET /videos/{video_id}/stream` - stream video content
- `POST /videos/{video_id}/assign` - assign video to a student
- `GET /processing/{video_id}` - processing job status
- `GET /results/{video_id}` - transcript, captions, summaries, and evaluation output
- `POST /results/{video_id}/chat` - ask questions about a processed lecture
- `GET /users/workspaces` - teacher workspaces
- `POST /users/workspaces` - create a teacher workspace
- `GET /analytics/overview` - admin analytics overview
- `POST /education/vision/analyze-image` - analyze an educational image

Use `http://127.0.0.1:8000/docs` for the full generated API reference.

## Testing

Run the test suite from the project root:

```powershell
.\venv311\Scripts\Activate.ps1
python -m unittest discover tests
```

Some runtime features require external tools or services, especially ffmpeg, Tesseract, model files, and OpenAI API access. Unit tests are designed to cover important local logic without needing to process a full lecture video every time.

## GitHub Upload Commands

Run these commands from PowerShell after creating an empty GitHub repository:

```powershell
cd "D:\SEM_6\FYP1\project\video_summrize"
git init
git status --ignored
git add .
git status
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git
git push -u origin main
```

If `origin` already exists:

```powershell
git remote set-url origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git
git push -u origin main
```

Replace `YOUR_USERNAME` and `YOUR_REPOSITORY_NAME` with your GitHub account and repository name.

## Notes For Development

- Keep `.env` private and commit only `.env.example`.
- Keep large generated files out of GitHub. Runtime storage folders are preserved with `.gitkeep` files.
- Close DB Browser for SQLite or any other application using `thinknote_ai.db` if uploads fail with a database lock error.
- Do not commit real YouTube cookies or API keys.

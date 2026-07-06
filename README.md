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

## Requirements

Install these before running the project:

- Python 3.11 recommended
- Git
- ffmpeg and ffprobe available in your system `PATH`
- Tesseract OCR available in your system `PATH`
- Node.js is optional, but useful for some `yt-dlp` YouTube extraction cases

Some AI dependencies are large. Use a virtual environment and make sure you have enough disk space.



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

## Why This Product Matters

Lecture videos are valuable, but they are often difficult to review efficiently. Students may need to rewatch long recordings just to find one concept, formula, slide, or explanation. Teachers also spend extra time preparing study notes, checking whether summaries match the intended lesson, and making recorded content easier to reuse.

ThinkNote AI solves this by turning lecture videos into organized study material. It connects the spoken explanation, slide content, visual examples, equations, and generated notes into one learning experience.

## Product Value

- Helps students revise faster by turning long videos into structured summaries, slide notes, transcripts, and searchable learning moments.
- Supports teachers by reducing the manual effort needed to prepare revision material from recorded lectures.
- Improves learning accessibility by giving students multiple ways to understand the same content: video, transcript, summary, visual notes, and chat.
- Preserves educational context by analyzing both audio and visuals instead of relying only on speech transcription.
- Helps courses reuse lecture content more effectively by organizing videos under teacher workspaces and making processed results available to the right students.
- Adds quality awareness through reference summaries and ROUGE evaluation, helping teachers compare generated summaries against expected learning points.

## Target Users

- Teachers who want to convert recorded lectures into student-ready revision material.
- Students who need faster access to key lecture points, explanations, formulas, and examples.
- Administrators who need visibility into uploaded content, processing activity, and learning resources.

## Product Outcome

The goal of ThinkNote AI is not only to summarize a video. The product aims to make lecture recordings easier to study, easier to teach from, and easier to manage as reusable educational resources.





## Notes For Development

<img width="856" height="372" alt="image" src="https://github.com/user-attachments/assets/242e52be-b8c7-4d5c-85bf-ebdc436b6154" />
<img width="856" height="392" alt="image" src="https://github.com/user-attachments/assets/a00671c8-5b4b-48b4-bb6d-2d01e08c85fa" />
<img width="856" height="395" alt="image" src="https://github.com/user-attachments/assets/ecb50625-9507-4796-a2c9-b1c56f3d65d8" />


<img width="856" height="384" alt="image" src="https://github.com/user-attachments/assets/e533d130-3639-4b7f-b7d1-e4516c59f4be" />

PRAGMA foreign_keys = ON;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    course_name TEXT NOT NULL,
    module_week TEXT,
    description TEXT,
    source_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    duration_seconds INTEGER,
    file_size_bytes INTEGER,
    owner_id INTEGER NOT NULL,
    workspace_id INTEGER,
    status TEXT NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'completed', 'review', 'failed')),
    is_published INTEGER NOT NULL DEFAULT 0 CHECK (is_published IN (0, 1)),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id) REFERENCES teacher_workspaces(id) ON DELETE SET NULL
);

CREATE TABLE teacher_workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(teacher_id, name),
    FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE course_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    course_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
    decided_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(teacher_id, student_id, course_name),
    FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE video_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    assigned_by INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(video_id, student_id),
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE processing_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    stage TEXT NOT NULL DEFAULT 'queued' CHECK (
        stage IN (
            'queued',
            'audio_extraction',
            'transcription',
            'frame_extraction',
            'captioning',
            'fusion',
            'nlp',
            'summarization',
            'evaluation',
            'completed',
            'failed'
        )
    ),
    progress_percent REAL NOT NULL DEFAULT 0.00,
    status_message TEXT,
    started_at DATETIME,
    completed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE TABLE transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL UNIQUE,
    raw_text TEXT NOT NULL,
    cleaned_text TEXT,
    language_code TEXT,
    whisper_model TEXT,
    word_count INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE TABLE transcript_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    segment_text TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE TABLE frame_captions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    frame_timestamp_seconds REAL NOT NULL,
    frame_path TEXT,
    annotated_frame_path TEXT,
    caption_text TEXT NOT NULL,
    ocr_text TEXT,
    equations_text TEXT,
    equation_image_paths TEXT,
    equation_source TEXT,
    equation_fallback_notes TEXT,
    visual_type TEXT,
    topic TEXT,
    change_score REAL,
    visual_model TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE TABLE multimodal_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL UNIQUE,
    fused_text TEXT NOT NULL,
    redundancy_removed_text TEXT,
    token_count INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL UNIQUE,
    summary_title TEXT,
    summary_text TEXT NOT NULL,
    structured_summary TEXT,
    llm_model TEXT,
    prompt_version TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE TABLE slide_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    frame_index INTEGER NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    frame_path TEXT,
    annotated_frame_path TEXT,
    caption_text TEXT NOT NULL,
    ocr_text TEXT,
    equations_text TEXT,
    equation_image_paths TEXT,
    equation_source TEXT,
    equation_fallback_notes TEXT,
    visual_type TEXT,
    topic TEXT,
    transcript_text TEXT,
    summary_text TEXT NOT NULL,
    key_points TEXT,
    transcript_excerpt TEXT,
    model_name TEXT,
    prompt_version TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE TABLE evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL UNIQUE,
    reference_summary TEXT,
    rouge_1 REAL,
    rouge_2 REAL,
    rouge_l REAL,
    evaluation_notes TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_videos_owner_id ON videos(owner_id);
CREATE INDEX idx_videos_workspace_id ON videos(workspace_id);
CREATE INDEX idx_videos_status ON videos(status);
CREATE INDEX idx_videos_published ON videos(is_published);
CREATE INDEX idx_teacher_workspaces_teacher_id ON teacher_workspaces(teacher_id);
CREATE INDEX idx_course_registrations_teacher_id ON course_registrations(teacher_id);
CREATE INDEX idx_course_registrations_student_id ON course_registrations(student_id);
CREATE INDEX idx_course_registrations_course_name ON course_registrations(course_name);
CREATE INDEX idx_video_assignments_video_id ON video_assignments(video_id);
CREATE INDEX idx_video_assignments_student_id ON video_assignments(student_id);
CREATE INDEX idx_processing_jobs_video_id ON processing_jobs(video_id);
CREATE INDEX idx_processing_jobs_stage ON processing_jobs(stage);
CREATE INDEX idx_transcript_segments_video_id ON transcript_segments(video_id);
CREATE INDEX idx_transcript_segments_time ON transcript_segments(start_seconds, end_seconds);
CREATE INDEX idx_frame_captions_video_id ON frame_captions(video_id);
CREATE INDEX idx_frame_captions_timestamp ON frame_captions(frame_timestamp_seconds);
CREATE INDEX idx_slide_summaries_video_id ON slide_summaries(video_id);
CREATE INDEX idx_slide_summaries_time ON slide_summaries(start_seconds, end_seconds);

CREATE TRIGGER trg_users_updated_at
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER trg_videos_updated_at
AFTER UPDATE ON videos
FOR EACH ROW
BEGIN
    UPDATE videos SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER trg_teacher_workspaces_updated_at
AFTER UPDATE ON teacher_workspaces
FOR EACH ROW
BEGIN
    UPDATE teacher_workspaces SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER trg_processing_jobs_updated_at
AFTER UPDATE ON processing_jobs
FOR EACH ROW
BEGIN
    UPDATE processing_jobs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER trg_transcripts_updated_at
AFTER UPDATE ON transcripts
FOR EACH ROW
BEGIN
    UPDATE transcripts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER trg_multimodal_outputs_updated_at
AFTER UPDATE ON multimodal_outputs
FOR EACH ROW
BEGIN
    UPDATE multimodal_outputs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER trg_summaries_updated_at
AFTER UPDATE ON summaries
FOR EACH ROW
BEGIN
    UPDATE summaries SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

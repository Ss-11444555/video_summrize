INSERT INTO users (full_name, email, password_hash, role)
VALUES
    ('System Administrator', 'admin@thinknote.ai', 'admin_password_hash_here', 'admin'),
    ('Dr. Sarah Lim', 'teacher@thinknote.ai', 'teacher_password_hash_here', 'teacher'),
    ('Ali Student', 'student@thinknote.ai', 'student_password_hash_here', 'student');

INSERT INTO videos (
    title,
    course_name,
    module_week,
    description,
    source_filename,
    stored_path,
    duration_seconds,
    file_size_bytes,
    owner_id,
    status,
    is_published
)
VALUES
    (
        'Computer Vision Fundamentals: Edge Detection and Image Features',
        'CSC401 Artificial Intelligence',
        'Week 5',
        'Lecture on edge detection, Sobel operator, and Canny method.',
        'cv_edge_detection.mp4',
        'backend/storage/uploads/cv_edge_detection.mp4',
        4680,
        157286400,
        2,
        'completed',
        1
    );

INSERT INTO processing_jobs (video_id, stage, progress_percent, status_message, started_at, completed_at)
VALUES
    (1, 'completed', 100.00, 'Video processed successfully.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO course_registrations (teacher_id, student_id, course_name, status, decided_at)
VALUES
    (2, 3, 'CSC401 Artificial Intelligence', 'accepted', CURRENT_TIMESTAMP);

INSERT INTO transcripts (video_id, raw_text, cleaned_text, language_code, whisper_model, word_count)
VALUES
    (
        1,
        'Today we begin with the intuition behind edge detection...',
        'Today we begin with the intuition behind edge detection...',
        'en',
        'medium',
        950
    );

INSERT INTO frame_captions (video_id, frame_timestamp_seconds, frame_path, caption_text, visual_model)
VALUES
    (1, 260.00, 'backend/storage/frames/frame_260.jpg', 'Educational topic: Image gradients. Summary: The slide explains gradient operators used to detect changes in image intensity.', 'educational-vlm'),
    (1, 1060.00, 'backend/storage/frames/frame_1060.jpg', 'Educational topic: Feature maps. Summary: The diagram shows how image features are transformed through a vision pipeline.', 'educational-vlm'),
    (1, 1868.00, 'backend/storage/frames/frame_1868.jpg', 'Educational topic: Thresholding. Summary: The whiteboard explains how threshold values separate foreground and background pixels.', 'educational-vlm');

INSERT INTO multimodal_outputs (video_id, fused_text, redundancy_removed_text, token_count)
VALUES
    (
        1,
        'The lecturer explains edge detection while slides present mathematical operators and whiteboard notes reinforce thresholding flow.',
        'Edge detection lecture combines spoken explanation with visual operator examples and thresholding notes.',
        210
    );

INSERT INTO summaries (video_id, summary_title, summary_text, structured_summary, llm_model, prompt_version)
VALUES
    (
        1,
        'Edge Detection and Image Features Summary',
        'The lecture introduces edge detection as a method for identifying object boundaries...',
        '{"main_topic":"Edge detection and image features","key_concepts":["gradients","Sobel","Canny","thresholding"],"revision_notes":["Canny is multi-stage","Noise handling matters"]}',
        'gpt-5.4',
        'v1'
    );

INSERT INTO evaluations (video_id, reference_summary, rouge_1, rouge_2, rouge_l, evaluation_notes)
VALUES
    (
        1,
        'Reference summary placeholder for evaluation.',
        0.8100,
        0.6800,
        0.7400,
        'Good overlap with reference educational summary.'
    );

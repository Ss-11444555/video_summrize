(function () {
    const ACTIVE_VIDEO_KEY = "thinknote_active_processing_video_id";
    const LEGACY_LAST_VIDEO_KEY = "thinknote_last_video_id";
    let pollTimer = null;
    let activeVideoId = null;
    let displayedProgress = 0;
    const PIPELINE_STEPS = [
        { key: "uploaded", number: "1" },
        { key: "audio", number: "2" },
        { key: "transcription", number: "3" },
        { key: "captioning", number: "4" },
        { key: "summary", number: "5" }
    ];
    const COMPLETED_VISUAL_STEPS = ["uploaded", "audio", "transcription", "captioning"];
    const PIPELINE_VIEWS = {
        idle: {
            index: "0",
            title: "Ready to Start",
            copy: "Choose a video file or paste a YouTube link to begin processing.",
            status: "Waiting",
            tone: "warning",
            progress: 0,
            activeStep: null,
            completed: [],
            detail: "No active job"
        },
        uploading: {
            index: "1",
            title: "Uploading Lecture",
            copy: "Sending the source lecture to storage.",
            status: "Uploading",
            tone: "processing",
            progress: 4,
            activeStep: "uploaded",
            completed: [],
            detail: "Stage 1 of 5"
        },
        importing: {
            index: "1",
            title: "Importing YouTube Lecture",
            copy: "Sending the YouTube link to the so the lecture can be downloaded and stored.",
            status: "Importing",
            tone: "processing",
            progress: 4,
            activeStep: "uploaded",
            completed: [],
            detail: "Stage 1 of 5"
        },
        queued: {
            index: "1",
            title: "Video Queued",
            copy: "The lecture is stored and waiting for the processing worker.",
            status: "Queued",
            tone: "processing",
            progress: 8,
            activeStep: "uploaded",
            completed: [],
            detail: "Stage 1 of 5"
        },
        audio_extraction: {
            index: "2",
            title: "Audio Extraction",
            copy: "Extracting the lecture audio so speech can be transcribed.",
            status: "Running",
            tone: "processing",
            progress: 25,
            activeStep: "audio",
            completed: ["uploaded"],
            detail: "Stage 2 of 5"
        },
        transcription: {
            index: "3",
            title: "Whisper Transcription",
            copy: "Generating transcript text from the lecture audio.",
            status: "Running",
            tone: "processing",
            progress: 42,
            activeStep: "transcription",
            completed: ["uploaded", "audio"],
            detail: "Stage 3 of 5"
        },
        frame_extraction: {
            index: "4",
            title: "Frame Extraction",
            copy: "Selecting representative video frames for visual analysis.",
            status: "Running",
            tone: "processing",
            progress: 55,
            activeStep: "captioning",
            completed: ["uploaded", "audio", "transcription"],
            detail: "Stage 4 of 5"
        },
        captioning: {
            index: "4",
            title: "Educational Visual Understanding",
            copy: "Running OCR, equation recognition, VLM analysis, CLIP topic matching, and LLM reasoning.",
            status: "Analyzing",
            tone: "processing",
            progress: 68,
            activeStep: "captioning",
            completed: ["uploaded", "audio", "transcription"],
            detail: "Stage 4 of 5"
        },
        fusion: {
            index: "4",
            title: "Transcript and Visual Fusion",
            copy: "Combining transcript content with detected slide and visual concepts.",
            status: "Fusing",
            tone: "processing",
            progress: 76,
            activeStep: "captioning",
            completed: ["uploaded", "audio", "transcription"],
            detail: "Stage 4 of 5"
        },
        nlp: {
            index: "4",
            title: "Content Cleaning",
            copy: "Removing redundancy and preparing cleaner educational text for summarization.",
            status: "Cleaning",
            tone: "processing",
            progress: 82,
            activeStep: "captioning",
            completed: ["uploaded", "audio", "transcription"],
            detail: "Stage 4 of 5"
        },
        summarization: {
            index: "5",
            title: "Summary Generation",
            copy: "Creating the lecture summary and slide-level study notes.",
            status: "Running",
            tone: "processing",
            progress: 90,
            activeStep: "summary",
            completed: COMPLETED_VISUAL_STEPS,
            detail: "Stage 5 of 5"
        },
        evaluation: {
            index: "5",
            title: "ROUGE Evaluation",
            copy: "Evaluating the generated summary with ROUGE-1, ROUGE-2, and ROUGE-L.",
            status: "Evaluating",
            tone: "processing",
            progress: 96,
            activeStep: "summary",
            completed: COMPLETED_VISUAL_STEPS,
            detail: "Stage 5 of 5"
        },
        completed: {
            index: "5",
            title: "Processing Completed",
            copy: "The lecture summary, transcript, slide summaries, and evaluation are ready.",
            status: "Completed",
            tone: "success",
            progress: 100,
            activeStep: null,
            completed: ["uploaded", "audio", "transcription", "captioning", "summary"],
            detail: "Ready to review"
        },
        failed: {
            index: "!",
            title: "Pipeline Failed",
            copy: "stopped processing this lecture. Check the message below and try again.",
            status: "Failed",
            tone: "danger",
            progress: 100,
            activeStep: null,
            completed: [],
            failed: true,
            detail: "Action needed"
        }
    };

    function setFeedback(text, tone) {
        const feedback = document.getElementById("upload-feedback");
        feedback.textContent = text;
        feedback.className = "feedback-banner " + tone;
    }

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }

    function getPipelineView(stage) {
        return PIPELINE_VIEWS[stage] || {
            index: "-",
            title: "Processing Lecture",
            copy: "is processing the lecture.",
            status: "Running",
            tone: "processing",
            progress: 50,
            activeStep: null,
            completed: [],
            detail: "Processing"
        };
    }

    function clampProgress(progress) {
        return Math.max(0, Math.min(100, Number(progress) || 0));
    }

    function updateChecklist(view) {
        const completedSteps = new Set(view.completed || []);
        PIPELINE_STEPS.forEach(function (step) {
            const item = document.querySelector("[data-step='" + step.key + "']");
            if (!item) {
                return;
            }

            let state = "waiting";
            if (completedSteps.has(step.key)) {
                state = "done";
            } else if (view.activeStep === step.key) {
                state = view.failed ? "failed" : "current";
            }

            item.dataset.pipelineState = state;
            const icon = item.querySelector(".pipeline-check-icon");
            if (icon) {
                icon.textContent = step.number;
            }
        });
    }

    function renderPipelineStatus(view, message, allowProgressReset) {
        const requestedProgress = clampProgress(view.progress);
        const progress = allowProgressReset
            ? requestedProgress
            : Math.max(displayedProgress, requestedProgress);
        displayedProgress = progress;
        const status = document.getElementById("pipeline-current-status");
        const fill = document.getElementById("pipeline-overall-fill");
        const card = document.getElementById("pipeline-current-card");
        const copy = message || view.copy;

        setText("pipeline-current-index", view.index);
        setText("pipeline-current-title", view.title);
        setText("pipeline-current-copy", copy);
        setText("pipeline-overall-label", Math.round(progress) + "% complete");
        setText("pipeline-active-detail", view.detail);
        setText("upload-status-copy", copy);

        if (status) {
            status.textContent = view.status;
            status.className = "status-pill " + view.tone;
        }
        if (fill) {
            fill.style.width = progress + "%";
        }
        if (card) {
            card.dataset.pipelineState = view.tone;
        }

        updateChecklist(view);
    }

    function resetProgress() {
        displayedProgress = 0;
        renderPipelineStatus(
            PIPELINE_VIEWS.idle,
            "No active processing job. Start a new upload to monitor the pipeline.",
            true
        );
    }

    function setFormBusy(isBusy) {
        document.querySelectorAll("#upload-form input, #upload-form select, #upload-form textarea, #video-file, #youtube-url, #start-upload-button, #file-picker-button, [data-upload-source]").forEach(function (element) {
            element.disabled = isBusy;
        });

        const button = document.getElementById("start-upload-button");
        if (button) {
            button.classList.toggle("is-hidden", false);
            button.textContent = isBusy ? "Processing..." : "Start Processing";
        }
    }

    function resetUploadForm(uploadSource) {
        const form = document.getElementById("upload-form");
        const fileInput = document.getElementById("video-file");
        const youtubeInput = document.getElementById("youtube-url");
        const fileName = document.getElementById("selected-file-name");
        const startButton = document.getElementById("start-upload-button");

        if (form) {
            form.reset();
        }
        if (fileInput) {
            fileInput.value = "";
        }
        if (youtubeInput) {
            youtubeInput.value = "";
        }
        if (fileName) {
            fileName.textContent = uploadSource === "youtube" ? "No YouTube link entered yet." : "No file selected yet.";
        }
        if (startButton) {
            startButton.classList.add("is-hidden");
            startButton.disabled = true;
        }
    }

    function clearActiveProcessing() {
        activeVideoId = null;
        window.localStorage.removeItem(ACTIVE_VIDEO_KEY);
        if (pollTimer) {
            window.clearTimeout(pollTimer);
            pollTimer = null;
        }
    }

    function finishProcessing(message, tone, uploadSource) {
        clearActiveProcessing();
        setFeedback(message, tone);
        setFormBusy(false);
        resetUploadForm(uploadSource);
    }

    function applyBackendProgress(status) {
        const view = Object.assign({}, getPipelineView(status.stage));
        if (typeof status.progress_percent === "number") {
            view.progress = status.progress_percent;
        }
        renderPipelineStatus(view, status.status_message || view.copy);
    }

    async function pollStatus(videoId) {
        const maxAttempts = 450;
        let attempt = 0;

        async function tick() {
            if (String(activeVideoId) !== String(videoId)) {
                return;
            }

            attempt += 1;
            try {
                const status = await window.ThinkNoteApp.apiRequest("/processing/" + videoId);
                applyBackendProgress(status);
                setFeedback(status.status_message || "Processing update received.", status.stage === "failed" ? "warning" : "info");

                if (status.stage === "completed") {
                    finishProcessing("Video processing completed. Upload form is ready for the next lecture.", "success", document.body.dataset.uploadSource || "file");
                    return;
                }

                if (status.stage === "failed") {
                    finishProcessing(status.status_message || "Processing failed. Upload form is ready to try again.", "warning", document.body.dataset.uploadSource || "file");
                    return;
                }

                if (attempt < maxAttempts) {
                    pollTimer = window.setTimeout(tick, 4000);
                } else {
                    setFeedback("Processing is still running. You can leave this page and open Videos later.", "info");
                    pollTimer = window.setTimeout(tick, 10000);
                }
            } catch (error) {
                clearActiveProcessing();
                setFormBusy(false);
                resetProgress();
                setFeedback(error.message || "Could not fetch processing status. The upload form was reset.", "warning");
            }
        }

        tick();
    }

    function initUpload() {
        if (document.body.dataset.page !== "upload") {
            return;
        }

        const role = window.ThinkNoteApp.getCurrentRole();
        const fileInput = document.getElementById("video-file");
        const fileButton = document.getElementById("file-picker-button");
        const fileName = document.getElementById("selected-file-name");
        const form = document.getElementById("upload-form");
        const guard = document.getElementById("upload-role-guard");
        const youtubeField = document.getElementById("youtube-url-field");
        const youtubeInput = document.getElementById("youtube-url");
        const inputTitle = document.getElementById("upload-input-title");
        const inputCopy = document.getElementById("upload-input-copy");
        const startButton = document.getElementById("start-upload-button");
        let uploadSource = "file";
        window.localStorage.removeItem(LEGACY_LAST_VIDEO_KEY);
        resetProgress();

        if (role !== "teacher") {
            guard.textContent = role === "student"
                ? "Students cannot upload videos. Sign in as a teacher to use this feature."
                : "Admins can inspect upload settings, but only teachers are allowed to submit lecture videos.";
            guard.classList.remove("is-hidden");
            document.querySelectorAll("#upload-form input, #upload-form select, #upload-form textarea, #video-file, #youtube-url, #start-upload-button, #file-picker-button, [data-upload-source]").forEach(function (element) {
                element.disabled = true;
            });
            setFeedback("Upload is disabled for the current role.", "warning");
            return;
        }

        function hasVideoInput() {
            if (uploadSource === "youtube") {
                return Boolean(youtubeInput.value.trim());
            }
            return Boolean(fileInput.files[0]);
        }

        function updateStartButtonAvailability() {
            if (!startButton || activeVideoId) {
                return;
            }

            const canStart = hasVideoInput();
            startButton.classList.toggle("is-hidden", !canStart);
            startButton.disabled = !canStart;
        }

        function setUploadSource(source) {
            uploadSource = source;
            document.body.dataset.uploadSource = source;
            document.querySelectorAll("[data-upload-source]").forEach(function (button) {
                button.classList.toggle("active", button.dataset.uploadSource === source);
            });

            const isYoutube = source === "youtube";
            fileButton.classList.toggle("is-hidden", isYoutube);
            youtubeField.classList.toggle("is-hidden", !isYoutube);
            inputTitle.textContent = isYoutube ? "Paste a YouTube lecture video link" : "Drag and drop your lecture file here";
            inputCopy.textContent = isYoutube
                ? " will download the video, store it in your library, then run the same AI pipeline."
                : "Supported formats: MP4, MOV, MKV. Large lecture videos will be processed in the background.";
            fileName.textContent = isYoutube ? "No YouTube link entered yet." : (fileInput.files[0] ? fileInput.files[0].name : "No file selected yet.");
            updateStartButtonAvailability();
        }

        document.querySelectorAll("[data-upload-source]").forEach(function (button) {
            button.addEventListener("click", function () {
                setUploadSource(button.dataset.uploadSource);
            });
        });

        fileButton.addEventListener("click", function () {
            fileInput.click();
        });

        fileInput.addEventListener("change", function () {
            const file = fileInput.files[0];
            fileName.textContent = file ? file.name : "No file selected yet.";
            updateStartButtonAvailability();
        });

        youtubeInput.addEventListener("input", function () {
            fileName.textContent = youtubeInput.value.trim() ? "YouTube link ready for import." : "No YouTube link entered yet.";
            updateStartButtonAvailability();
        });

        form.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (activeVideoId) {
                return;
            }

            displayedProgress = 0;

            const file = fileInput.files[0];
            const youtubeUrl = youtubeInput.value.trim();
            const referenceSummary = document.getElementById("reference-summary").value.trim();

            if (uploadSource === "file" && !file) {
                setFeedback("Choose a lecture video before uploading.", "warning");
                return;
            }

            if (uploadSource === "youtube" && !youtubeUrl) {
                setFeedback("Paste a YouTube video link before importing.", "warning");
                return;
            }

            if (!referenceSummary) {
                setFeedback("Write a teacher reference summary before uploading.", "warning");
                document.getElementById("reference-summary").focus();
                return;
            }

            const formData = new FormData();
            formData.append("title", document.getElementById("title").value.trim());
            formData.append("course_name", document.getElementById("course").value.trim());
            formData.append("module_week", document.getElementById("week").value.trim());
            formData.append("description", document.getElementById("description").value.trim());
            formData.append("reference_summary", referenceSummary);
            formData.append("is_published", document.getElementById("audience").value === "Students in course" ? "true" : "false");
            if (window.ThinkNoteApp.getActiveWorkspaceId()) {
                formData.append("workspace_id", window.ThinkNoteApp.getActiveWorkspaceId());
            }
            if (uploadSource === "youtube") {
                formData.append("youtube_url", youtubeUrl);
            } else {
                formData.append("video_file", file);
            }

            setFeedback(uploadSource === "youtube" ? "Importing YouTube lecture video..." : "Uploading lecture video ...", "info");
            renderPipelineStatus(
                getPipelineView(uploadSource === "youtube" ? "importing" : "uploading"),
                uploadSource === "youtube" ? "Importing YouTube lecture video..." : "Uploading lecture video to storage..."
            );
            setFormBusy(true);

            try {
                const response = await window.ThinkNoteApp.apiRequest(uploadSource === "youtube" ? "/videos/youtube" : "/videos/upload", {
                    method: "POST",
                    body: formData
                });

                const videoId = response.video.id;
                activeVideoId = String(videoId);
                window.localStorage.setItem(ACTIVE_VIDEO_KEY, String(videoId));
                renderPipelineStatus(getPipelineView("queued"), "Upload received. Monitoring the processing worker...");
                setFeedback((uploadSource === "youtube" ? "YouTube import successful." : "Upload successful.") + " Monitoring processing pipeline...", "success");
                pollStatus(videoId);
            } catch (error) {
                clearActiveProcessing();
                setFormBusy(false);
                updateStartButtonAvailability();
                renderPipelineStatus(getPipelineView("failed"), error.message || (uploadSource === "youtube" ? "YouTube import failed." : "Upload failed."));
                setFeedback(error.message || (uploadSource === "youtube" ? "YouTube import failed." : "Upload failed."), "warning");
            }
        });

        const existingVideoId = window.localStorage.getItem(ACTIVE_VIDEO_KEY);
        if (existingVideoId) {
            activeVideoId = existingVideoId;
            setFormBusy(true);
            pollStatus(existingVideoId);
        } else {
            updateStartButtonAvailability();
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        initUpload();
    });
})();

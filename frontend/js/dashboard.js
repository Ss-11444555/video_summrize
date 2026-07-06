(function () {
    function animateValue(element, targetValue) {
        const numericTarget = Number(String(targetValue).replace(/[^\d.]/g, ""));
        if (Number.isNaN(numericTarget)) {
            element.textContent = targetValue;
            return;
        }

        const hasPercent = String(targetValue).includes("%");
        const hasDecimal = String(targetValue).includes(".");
        const duration = 700;
        const start = performance.now();

        function frame(timestamp) {
            const progress = Math.min((timestamp - start) / duration, 1);
            const currentValue = numericTarget * progress;
            let textValue = hasDecimal ? currentValue.toFixed(2) : Math.round(currentValue).toString();

            if (hasPercent) {
                textValue += "%";
            }

            element.textContent = progress === 1 ? targetValue : textValue;

            if (progress < 1) {
                window.requestAnimationFrame(frame);
            }
        }

        window.requestAnimationFrame(frame);
    }

    function setMetric(index, label, value, copy) {
        window.ThinkNoteApp.setText("metric-label-" + index, label);
        window.ThinkNoteApp.setText("metric-copy-" + index, copy);

        const keyNames = ["primary", "secondary", "tertiary", "quaternary"];
        const valueElement = document.querySelector("[data-metric-key='" + keyNames[index - 1] + "']");
        if (valueElement) {
            animateValue(valueElement, value);
        }
    }

    function setHeroTitle(value) {
        if (document.body.dataset.accessNotice === "true") {
            return;
        }

        window.ThinkNoteApp.setText("dashboard-hero-title", value);
    }

    function statusTone(status) {
        if (status === "completed") {
            return "success";
        }
        if (status === "processing" || status === "uploaded") {
            return "processing";
        }
        if (status === "failed") {
            return "danger";
        }
        return "warning";
    }

    function statusLabel(status) {
        if (status === "completed") {
            return "Ready";
        }
        if (status === "processing" || status === "uploaded") {
            return "Preparing";
        }
        if (status === "failed") {
            return "Unavailable";
        }
        return "Review";
    }

    function formatDate(value) {
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return "Recently added";
        }

        return date.toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric"
        });
    }

    function sortNewest(videos) {
        return videos.slice().sort(function (first, second) {
            return new Date(second.created_at || 0).getTime() - new Date(first.created_at || 0).getTime();
        });
    }

    function studentResultUrl(video) {
        const resultPage = window.ThinkNoteApp.getResultPage("student");
        const course = encodeURIComponent(video.course_name || "");
        const videoId = encodeURIComponent(video.id);
        return resultPage + "?course=" + course + "&video=" + videoId;
    }

    function setStudentStudyNotesLink(videos) {
        const link = document.getElementById("student-open-study-notes");
        if (!link) {
            return;
        }

        const completed = sortNewest(videos.filter(function (video) {
            return video.status === "completed";
        }));

        if (completed.length) {
            link.href = studentResultUrl(completed[0]);
            link.textContent = "Open Study Notes";
            return;
        }

        if (videos.length) {
            link.href = "student-videos.html";
            link.textContent = "Browse Lectures";
            return;
        }

        link.href = "student-courses.html";
        link.textContent = "Find Courses";
    }

    function renderStudentRecentLectures(videos) {
        const list = document.getElementById("student-home-recent-list");
        if (!list) {
            return;
        }

        if (!videos.length) {
            list.innerHTML =
                "<li>" +
                    "<div class='row-between'>" +
                        "<strong>No lectures assigned yet</strong>" +
                        "<span class='status-pill warning'>Empty</span>" +
                    "</div>" +
                    "<p>Register with a teacher to unlock lecture videos and study notes.</p>" +
                "</li>";
            return;
        }

        list.innerHTML = sortNewest(videos).slice(0, 4).map(function (video) {
            const resultUrl = studentResultUrl(video);
            return (
                "<li>" +
                    "<div class='row-between'>" +
                        "<div>" +
                            "<strong>" + video.title + "</strong>" +
                            "<p>" + (video.course_name || "Course") + " | " + formatDate(video.created_at) + "</p>" +
                        "</div>" +
                        "<span class='status-pill " + statusTone(video.status) + "'>" + statusLabel(video.status) + "</span>" +
                    "</div>" +
                    "<div class='student-home-list-action'>" +
                        "<span>" + (video.module_week || "Lecture material") + "</span>" +
                        "<a class='btn-ghost' href='" + resultUrl + "'>" + (video.status === "completed" ? "Open Notes" : "Open Lecture") + "</a>" +
                    "</div>" +
                "</li>"
            );
        }).join("");
    }

    function renderStudentContinueCard(videos) {
        const card = document.getElementById("student-home-continue-card");
        if (!card) {
            return;
        }

        if (!videos.length) {
            card.innerHTML =
                "<span class='eyebrow'>Get Started</span>" +
                "<h3>Find a course</h3>" +
                "<p>Once your course request is approved, lectures and study notes will appear here.</p>" +
                "<a class='btn' href='student-courses.html'>Find Courses</a>";
            return;
        }

        const completed = sortNewest(videos.filter(function (video) {
            return video.status === "completed";
        }));
        const nextVideo = completed[0] || sortNewest(videos)[0];
        const resultUrl = studentResultUrl(nextVideo);

        card.innerHTML =
            "<span class='eyebrow'>" + (nextVideo.status === "completed" ? "Ready Now" : "Next Lecture") + "</span>" +
            "<h3>" + nextVideo.title + "</h3>" +
            "<p>" + (nextVideo.description || "Open this lecture to continue watching and reviewing your study material.") + "</p>" +
            "<div class='student-home-meta-row'>" +
                "<span>" + (nextVideo.course_name || "Course") + "</span>" +
                "<span>" + (nextVideo.module_week || "Lecture") + "</span>" +
            "</div>" +
            "<a class='btn' href='" + resultUrl + "'>" + (nextVideo.status === "completed" ? "Continue Study" : "Open Lecture") + "</a>";
    }

    function renderStudentHome(videos) {
        setStudentStudyNotesLink(videos);
        renderStudentRecentLectures(videos);
        renderStudentContinueCard(videos);
    }

    async function initDashboard() {
        const page = document.body.dataset.page;
        if (page !== "dashboard" && page !== "teacher-dashboard" && page !== "student-dashboard") {
            return;
        }

        const role = window.ThinkNoteApp.getCurrentRole();

        try {
            let videoPath = "/videos";
            if (role === "teacher" && window.ThinkNoteApp.getActiveWorkspaceId()) {
                videoPath += "?workspace_id=" + encodeURIComponent(window.ThinkNoteApp.getActiveWorkspaceId());
            }
            const videos = await window.ThinkNoteApp.apiRequest(videoPath);
            const completedVideos = videos.filter(function (video) {
                return video.status === "completed";
            });
            const publishedVideos = videos.filter(function (video) {
                return video.is_published;
            });
            const processingVideos = videos.filter(function (video) {
                return video.status === "processing" || video.status === "uploaded";
            });

            if (role === "admin") {
                const overview = await window.ThinkNoteApp.apiRequest("/analytics/overview");
                setMetric(1, "Registered Users", String(overview.total_users || 0), "People currently using ThinkNote AI.");
                setMetric(2, "Lecture Videos", String(overview.total_videos || 0), "Videos available in the product library.");
                setMetric(3, "Ready to Study", String(overview.completed_videos || 0), "Lectures with completed notes and learning material.");
                setMetric(
                    4,
                    "Summary Quality",
                    overview.average_rouge_l ? Number(overview.average_rouge_l).toFixed(2) : "0.00",
                    "Average quality score for generated lecture summaries."
                );
                setHeroTitle(overview.total_videos + " lecture videos are available in ThinkNote AI.");
            } else if (role === "teacher") {
                setMetric(1, "My Lectures", String(videos.length), "Videos uploaded to your teaching library.");
                setMetric(2, "Study Notes", String(completedVideos.length), "Lectures with summaries ready to review.");
                setMetric(3, "Published", String(publishedVideos.length), "Lectures students can currently open.");
                setMetric(4, "Preparing", String(processingVideos.length), "Lectures still being prepared for notes.");
                setHeroTitle(completedVideos.length + " lecture summaries are ready " );
            } else {
                setMetric(1, "Study Notes", String(completedVideos.length), "Completed lecture summaries assigned to you.");
                setMetric(2, "My Lectures", String(videos.length), "Lecture videos currently visible to your account.");
                setMetric(3, "Courses", String(new Set(videos.map(function (video) { return video.course_name; })).size), "Course libraries available for study.");
                setMetric(4, "Ready to Open", String(completedVideos.length), "Lectures with notes, captions, and transcripts.");
                setHeroTitle(completedVideos.length + " lecture summaries are ready for study.");
                renderStudentHome(videos);
            }
        } catch (error) {
            if (document.body.dataset.accessNotice !== "true") {
                window.ThinkNoteApp.setText("dashboard-hero-title", "Could not load your Home data.");
                window.ThinkNoteApp.setText("dashboard-hero-description", error.message || "Start the app server and sign in again.");
            }
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        initDashboard();
    });
})();

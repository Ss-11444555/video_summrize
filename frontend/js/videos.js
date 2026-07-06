(function () {
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
            return "Completed";
        }
        if (status === "processing" || status === "uploaded") {
            return "Processing";
        }
        if (status === "failed") {
            return "Failed";
        }
        return "Review Needed";
    }

    function formatInstructorName(name) {
        const value = String(name || "Instructor").trim();
        return /^dr\.?\s/i.test(value) ? value : "Dr. " + value;
    }

    function chipsForVideo(video) {
        const chips = [];
        if (video.status === "completed") {
            chips.push("Transcript Ready", "Summary Ready");
        }
        if (video.status === "processing" || video.status === "uploaded") {
            chips.push("Pipeline Running");
        }
        if (video.is_published) {
            chips.push("Published");
        }
        return chips.length ? chips : ["Stored in Backend"];
    }

    function confirmLectureDeletion(video) {
        return new Promise(function (resolve) {
            const backdrop = document.createElement("div");
            backdrop.className = "delete-dialog-backdrop";
            backdrop.innerHTML =
                "<section class='delete-dialog' role='alertdialog' aria-modal='true' aria-labelledby='delete-dialog-title' aria-describedby='delete-dialog-description'>" +
                    "<div class='delete-dialog-icon' aria-hidden='true'>!</div>" +
                    "<div class='delete-dialog-copy'>" +
                        "<span class='eyebrow'>Permanent Action</span>" +
                        "<h2 id='delete-dialog-title'>Delete this lecture?</h2>" +
                        "<p id='delete-dialog-description'>You are about to permanently delete <strong data-delete-title></strong>.</p>" +
                    "</div>" +
                    "<div class='delete-dialog-details'>" +
                        "<strong>This will remove:</strong>" +
                        "<ul>" +
                            "<li>The uploaded lecture video</li>" +
                            "<li>The transcript and generated summaries</li>" +
                            "<li>The ROUGE evaluation and student assignments</li>" +
                            (
                                video.status === "processing" || video.status === "uploaded"
                                    ? "<li>The active processing task will stop at its next safe checkpoint</li>"
                                    : ""
                            ) +
                        "</ul>" +
                    "</div>" +
                    "<p class='delete-dialog-warning'>This action cannot be undone.</p>" +
                    "<div class='delete-dialog-actions'>" +
                        "<button class='btn-ghost' type='button' data-delete-cancel>Keep Lecture</button>" +
                        "<button class='btn-danger delete-dialog-confirm' type='button' data-delete-confirm>Delete Lecture</button>" +
                    "</div>" +
                "</section>";

            backdrop.querySelector("[data-delete-title]").textContent = '"' + video.title + '"';
            const cancelButton = backdrop.querySelector("[data-delete-cancel]");
            const confirmButton = backdrop.querySelector("[data-delete-confirm]");
            let settled = false;

            function closeDialog(confirmed) {
                if (settled) {
                    return;
                }
                settled = true;
                document.removeEventListener("keydown", handleKeydown);
                backdrop.remove();
                resolve(confirmed);
            }

            function handleKeydown(event) {
                if (event.key === "Escape") {
                    closeDialog(false);
                }
            }

            cancelButton.addEventListener("click", function () {
                closeDialog(false);
            });
            confirmButton.addEventListener("click", function () {
                closeDialog(true);
            });
            backdrop.addEventListener("click", function (event) {
                if (event.target === backdrop) {
                    closeDialog(false);
                }
            });
            document.addEventListener("keydown", handleKeydown);
            document.body.appendChild(backdrop);
            cancelButton.focus();
        });
    }

    async function loadVideoPlayer(video, card, button) {
        const existing = card.querySelector("[data-video-player]");
        if (existing) {
            existing.remove();
            button.textContent = "Watch Video";
            return;
        }

        const session = window.ThinkNoteApp.getSession();
        if (!session || !session.token) {
            const warning = document.createElement("p");
            warning.className = "feedback-banner warning";
            warning.textContent = "Sign in again before watching videos.";
            warning.setAttribute("data-video-player", "true");
            card.appendChild(warning);
            button.textContent = "Watch Video";
            return;
        }

        const streamUrl = window.ThinkNoteApp.API_BASE_URL +
            "/videos/" + video.id + "/stream?access_token=" + encodeURIComponent(session.token);
        const wrapper = document.createElement("div");
        wrapper.className = "video-player-panel";
        wrapper.setAttribute("data-video-player", "true");
        wrapper.innerHTML =
            "<video controls preload='metadata' class='video-player' src='" + streamUrl + "'></video>" +
            "<p class='metric-inline'>" + video.source_filename + "</p>";

        wrapper.querySelector("video").addEventListener("error", function () {
            wrapper.innerHTML =
                "<p class='feedback-banner warning'>Could not load video. uploaded file still exists.</p>";
            button.textContent = "Watch Video";
        });

        card.appendChild(wrapper);
        button.textContent = "Hide Video";
    }

    function toggleAssignmentPanel(video, card, button) {
        const existing = card.querySelector("[data-video-assignment-panel]");
        if (existing) {
            existing.remove();
            button.textContent = "Assign";
            return;
        }

        const panel = document.createElement("div");
        panel.className = "video-assignment-panel";
        panel.setAttribute("data-video-assignment-panel", "true");
        panel.innerHTML =
            "<div class='video-assignment-header'>" +
                "<div>" +
                    "<strong>Assign video access</strong>" +
                    "<span>" + video.course_name + "</span>" +
                "</div>" +
            "</div>" +
            "<div class='video-assignment-section'>" +
                "<div class='video-assignment-section-title'>" +
                    "<strong>One student</strong>" +
                    "<span>Give access by student email.</span>" +
                "</div>" +
                "<div class='video-assignment-email-row'>" +
                "<label class='field'>" +
                    "<span>Student Email</span>" +
                    "<input type='email' data-assignment-email placeholder='student@example.com'>" +
                "</label>" +
                    "<button class='assignment-submit' type='button' data-assign-student>Assign Student</button>" +
                "</div>" +
            "</div>" +
            "<div class='video-assignment-bulk'>" +
                "<button class='assignment-action' type='button' data-assign-course>" +
                    "<strong>Course students</strong>" +
                    "<span>Assign to accepted students in this course.</span>" +
                "</button>" +
                "<button class='assignment-action accent' type='button' data-assign-all>" +
                    "<strong>All active students</strong>" +
                    "<span>Assign without course registration.</span>" +
                "</button>" +
            "</div>" +
            "<p class='feedback-banner info' data-assignment-feedback>Assign this video to one student, accepted students in this course, or every active student.</p>";

        const input = panel.querySelector("[data-assignment-email]");
        const feedback = panel.querySelector("[data-assignment-feedback]");
        const assignStudentButton = panel.querySelector("[data-assign-student]");
        const assignCourseButton = panel.querySelector("[data-assign-course]");
        const assignAllButton = panel.querySelector("[data-assign-all]");

        function setBulkButtonBusy(actionButton, busyText) {
            actionButton.dataset.defaultHtml = actionButton.innerHTML;
            actionButton.disabled = true;
            actionButton.textContent = busyText;
        }

        function restoreBulkButton(actionButton) {
            actionButton.disabled = false;
            if (actionButton.dataset.defaultHtml) {
                actionButton.innerHTML = actionButton.dataset.defaultHtml;
                delete actionButton.dataset.defaultHtml;
            }
        }

        assignStudentButton.addEventListener("click", async function () {
            const studentEmail = input.value.trim();
            if (!studentEmail) {
                feedback.textContent = "Enter the student's email address first.";
                feedback.className = "feedback-banner warning";
                return;
            }

            assignStudentButton.disabled = true;
            assignStudentButton.textContent = "Assigning...";
            try {
                const response = await window.ThinkNoteApp.apiRequest("/videos/" + video.id + "/assign", {
                    method: "POST",
                    body: JSON.stringify({ student_email: studentEmail })
                });
                feedback.textContent = response.message + " Student: " + response.student_email + ".";
                feedback.className = "feedback-banner success";
                input.value = "";
            } catch (error) {
                feedback.textContent = error.message || "Could not assign this video to the student.";
                feedback.className = "feedback-banner warning";
            } finally {
                assignStudentButton.disabled = false;
                assignStudentButton.textContent = "Assign Student";
            }
        });

        assignCourseButton.addEventListener("click", async function () {
            setBulkButtonBusy(assignCourseButton, "Assigning...");
            try {
                const response = await window.ThinkNoteApp.apiRequest(
                    "/videos/" + video.id + "/assign/course-registered",
                    { method: "POST" }
                );
                feedback.textContent =
                    "Assigned to " + response.assigned_count + " new student" +
                    (response.assigned_count === 1 ? "" : "s") +
                    " in " + response.course_name + ". " +
                    response.already_assigned_count + " already had access.";
                feedback.className = "feedback-banner success";
            } catch (error) {
                feedback.textContent = error.message || "Could not assign this video to registered course students.";
                feedback.className = "feedback-banner warning";
            } finally {
                restoreBulkButton(assignCourseButton);
            }
        });

        assignAllButton.addEventListener("click", async function () {
            setBulkButtonBusy(assignAllButton, "Assigning...");
            try {
                const response = await window.ThinkNoteApp.apiRequest(
                    "/videos/" + video.id + "/assign/all-students",
                    { method: "POST" }
                );
                feedback.textContent =
                    "Assigned to " + response.assigned_count + " new active student" +
                    (response.assigned_count === 1 ? "" : "s") +
                    ". " + response.already_assigned_count + " already had access.";
                feedback.className = "feedback-banner success";
            } catch (error) {
                feedback.textContent = error.message || "Could not assign this video to all active students.";
                feedback.className = "feedback-banner warning";
            } finally {
                restoreBulkButton(assignAllButton);
            }
        });

        card.appendChild(panel);
        button.textContent = "Hide Assign";
        input.focus();
    }

    function renderVideos(videoItems, activeRole, onDeleteVideo) {
        const container = document.getElementById("video-list");
        const count = document.getElementById("video-results-count");
        const sessionRole = window.ThinkNoteApp.getCurrentRole();
        const canAssignVideos = sessionRole === "teacher" || sessionRole === "admin";
        const canDeleteVideos = sessionRole === "teacher";

        container.innerHTML = "";

        if (!videoItems.length) {
            container.innerHTML = "<article class='empty-state'>No videos matched the selected filters.</article>";
            count.textContent = "0 videos matched your search.";
            count.className = "feedback-banner warning";
            return;
        }

        function accessLabel(role) {
            if (role === "student") {
                return "Student Visible";
            }
            if (role === "admin") {
                return "Admin View";
            }
            return "Teacher Owned";
        }

        videoItems.forEach(function (video) {
            const card = document.createElement("article");
            const resultPage = window.ThinkNoteApp.getResultPage(window.ThinkNoteApp.getCurrentRole());
            card.className = "video-card";
            card.innerHTML =
                "<div class='video-card-header'>" +
                    "<div>" +
                        "<span class='eyebrow'>" + video.course_name + "</span>" +
                        "<h3>" + video.title + "</h3>" +
                        "<p>Uploaded by " + video.owner_name + " | " + (video.module_week || "No module") + "</p>" +
                    "</div>" +
                    "<span class='status-pill " + statusTone(video.status) + "'>" + statusLabel(video.status) + "</span>" +
                "</div>" +
                "<div class='chip-row'>" +
                    "<span class='role-badge " + (activeRole === "student" ? "student" : "teacher") + "'>" + accessLabel(activeRole) + "</span>" +
                    chipsForVideo(video).map(function (chip) { return "<span class='chip'>" + chip + "</span>"; }).join("") +
                "</div>" +
                "<p>" + (video.description || "No description provided for this lecture video.") + "</p>" +
                "<div class='row-between'>" +
                    "<strong>Status: " + statusLabel(video.status) + "</strong>" +
                    "<div class='chip-row'>" +
                        "<button class='btn-secondary' type='button' data-watch-video>Watch Video</button>" +
                        (canAssignVideos ? "<button class='btn-secondary' type='button' data-assign-video>Assign</button>" : "") +
                        "<a class='btn-ghost' href='" + resultPage + "?video=" + video.id + "'>" + (video.status === "completed" ? "View Result" : "Open Result Page") + "</a>" +
                        (canDeleteVideos ? "<button class='btn-danger' type='button' data-delete-video>Delete</button>" : "") +
                    "</div>" +
                "</div>";
            card.querySelector("[data-watch-video]").addEventListener("click", function (event) {
                loadVideoPlayer(video, card, event.currentTarget);
            });
            if (canAssignVideos) {
                card.querySelector("[data-assign-video]").addEventListener("click", function (event) {
                    toggleAssignmentPanel(video, card, event.currentTarget);
                });
            }
            if (canDeleteVideos) {
                card.querySelector("[data-delete-video]").addEventListener("click", async function (event) {
                    const button = event.currentTarget;
                    const confirmed = await confirmLectureDeletion(video);
                    if (!confirmed) {
                        return;
                    }

                    button.disabled = true;
                    button.textContent = "Deleting...";
                    count.textContent = 'Deleting "' + video.title + '" and its learning materials...';
                    count.className = "feedback-banner info";
                    try {
                        const response = await window.ThinkNoteApp.apiRequest("/videos/" + video.id, {
                            method: "DELETE"
                        });
                        await onDeleteVideo();
                        count.textContent = '"' + video.title + '" was deleted successfully.';
                        count.className = response.cleanup_warnings && response.cleanup_warnings.length
                            ? "feedback-banner warning"
                            : "feedback-banner success";
                    } catch (error) {
                        count.textContent = error.message ||
                            "The lecture could not be deleted. Please refresh the page and try again.";
                        count.className = "feedback-banner warning";
                        button.disabled = false;
                        button.textContent = "Delete";
                    }
                });
            }
            container.appendChild(card);
        });

        count.textContent = videoItems.length + " video" + (videoItems.length === 1 ? "" : "s") + " loaded.";
        count.className = "feedback-banner info";
    }

    function groupVideosByCourse(videos) {
        return videos.reduce(function (courses, video) {
            const courseName = video.course_name || "Untitled Course";
            if (!courses[courseName]) {
                courses[courseName] = [];
            }
            courses[courseName].push(video);
            return courses;
        }, {});
    }

    function getCourseNames(courses) {
        return Object.keys(courses).sort(function (first, second) {
            return first.localeCompare(second);
        });
    }

    function getVideoOrderValue(video) {
        const moduleText = String(video.module_week || "");
        const match = moduleText.match(/\d+/);
        if (match) {
            return Number(match[0]);
        }
        return Number.MAX_SAFE_INTEGER;
    }

    function sortCourseVideos(videos) {
        return videos.slice().sort(function (first, second) {
            const orderDifference = getVideoOrderValue(first) - getVideoOrderValue(second);
            if (orderDifference !== 0) {
                return orderDifference;
            }
            return String(first.created_at || "").localeCompare(String(second.created_at || ""));
        });
    }

    function lectureLabel(index) {
        return "Lecture " + String(index + 1).padStart(2, "0");
    }

    function renderStudentCourseCards(courseNames, courses, selectedCourse, onSelect) {
        const list = document.getElementById("student-course-list");
        const selector = document.getElementById("student-course-selector");

        list.innerHTML = "";
        selector.innerHTML = "";

        if (!courseNames.length) {
            selector.innerHTML = "<option>No available courses</option>";
            list.innerHTML =
                "<article class='student-course-empty'>" +
                    "<strong>No available courses yet</strong>" +
                    "<span>Approved courses and directly assigned videos will appear here.</span>" +
                "</article>";
            return;
        }

        courseNames.forEach(function (courseName) {
            const videos = sortCourseVideos(courses[courseName]);
            const completedCount = videos.filter(function (video) { return video.status === "completed"; }).length;

            const option = document.createElement("option");
            option.value = courseName;
            option.textContent = courseName;
            selector.appendChild(option);

            const button = document.createElement("button");
            button.className = "student-course-card" + (courseName === selectedCourse ? " active" : "");
            button.type = "button";
            button.innerHTML =
                "<span>Course</span>" +
                "<strong>" + courseName + "</strong>" +
                "<small>" + videos.length + " video" + (videos.length === 1 ? "" : "s") + " | " + completedCount + " ready</small>";
            button.addEventListener("click", function () {
                onSelect(courseName);
            });

            list.appendChild(button);
        });

        selector.value = selectedCourse;
    }

    function renderStudentCourseVideos(courseName, videos) {
        const title = document.getElementById("student-course-title");
        const activeName = document.getElementById("student-active-course-name");
        const copy = document.getElementById("student-active-course-copy");
        const total = document.getElementById("student-course-video-count");
        const count = document.getElementById("video-results-count");
        const container = document.getElementById("video-list");
        const resultPage = window.ThinkNoteApp.getResultPage("student");

        title.textContent = courseName || "Available course videos";
        activeName.textContent = courseName || "No course selected";
        total.textContent = String(videos.length);
        copy.textContent = videos.length
            ? "Videos and AI summaries available from course approval or direct teacher assignment."
            : "No videos are available in this course yet.";

        container.innerHTML = "";

        if (!videos.length) {
            count.textContent = "No videos matched this course and filter.";
            container.innerHTML = "<article class='student-course-empty'>No videos matched this course.</article>";
            return;
        }

        count.textContent = videos.length + " video" + (videos.length === 1 ? "" : "s") + " available in " + courseName + ".";

        sortCourseVideos(videos).forEach(function (video, index) {
            const courseQuery = encodeURIComponent(courseName || video.course_name || "");
            const resultUrl = resultPage + "?course=" + courseQuery + "&video=" + video.id;
            const card = document.createElement("article");
            card.className = "student-course-video-card";
            card.innerHTML =
                "<div class='student-course-video-main'>" +
                    "<div class='student-course-video-title-row'>" +
                        "<strong>" + lectureLabel(index) + "</strong>" +
                        "<h3>" + video.title + "</h3>" +
                    "</div>" +
                    "<span>" + lectureLabel(index) + (video.module_week ? " | " + video.module_week : "") + "</span>" +
                    "<p>" + (video.description || "Open the video workspace to watch the lecture and read the generated summary.") + "</p>" +
                "</div>" +
                "<div class='student-course-video-meta'>" +
                    "<span class='status-pill " + statusTone(video.status) + "'>" + statusLabel(video.status) + "</span>" +
                    "<small>" + formatInstructorName(video.owner_name) + "</small>" +
                "</div>" +
                "<div class='student-course-video-actions'>" +
                    "<button class='student-course-watch' type='button' data-watch-video>Preview</button>" +
                    "<a class='student-course-open' href='" + resultUrl + "'>" +
                        (video.status === "completed" ? "Open Summary" : "Open Workspace") +
                    "</a>" +
                "</div>";

            card.querySelector("[data-watch-video]").addEventListener("click", function (event) {
                loadVideoPlayer(video, card, event.currentTarget);
            });

            container.appendChild(card);
        });
    }

    function initStudentCoursesPage() {
        const search = document.getElementById("search");
        const statusFilter = document.getElementById("status-filter");
        const selector = document.getElementById("student-course-selector");
        const count = document.getElementById("video-results-count");
        const initialParams = new URLSearchParams(window.location.search);
        const teacherIdFilter = Number(initialParams.get("teacher_id") || initialParams.get("teacher") || 0);
        let allVideos = [];
        let selectedCourse = "";

        function filteredVideos() {
            const keyword = search.value.trim().toLowerCase();
            const status = statusFilter.value;

            return allVideos.filter(function (video) {
                const searchable = [
                    video.title,
                    video.course_name,
                    video.description,
                    video.module_week,
                    video.owner_name
                ].join(" ").toLowerCase();

                const matchesTeacher = !teacherIdFilter || Number(video.owner_id) === teacherIdFilter;
                const matchesKeyword = !keyword || searchable.indexOf(keyword) !== -1;
                const matchesStatus = status === "all" ||
                    (status === "processing" ? video.status === "processing" || video.status === "uploaded" : false) ||
                    (status === "review" ? video.status !== "completed" && video.status !== "processing" && video.status !== "uploaded" : video.status === status);

                return matchesTeacher && matchesKeyword && matchesStatus;
            });
        }

        function selectCourse(courseName) {
            selectedCourse = courseName;
            const url = new URL(window.location.href);
            if (selectedCourse) {
                url.searchParams.set("course", selectedCourse);
            }
            window.history.replaceState({}, "", url);
            render();
        }

        function render() {
            const courses = groupVideosByCourse(filteredVideos());
            const courseNames = getCourseNames(courses);
            const params = new URLSearchParams(window.location.search);
            const courseFromUrl = params.get("course");

            if (!selectedCourse || !courses[selectedCourse]) {
                selectedCourse = courseFromUrl && courses[courseFromUrl] ? courseFromUrl : (courseNames[0] || "");
            }

            renderStudentCourseCards(courseNames, courses, selectedCourse, selectCourse);
            renderStudentCourseVideos(selectedCourse, selectedCourse ? courses[selectedCourse] || [] : []);
        }

        async function loadCourses() {
            try {
                allVideos = await window.ThinkNoteApp.apiRequest("/videos");
                if (!allVideos.length) {
                    count.textContent = "No course videos are visible yet.";
                }
                render();
            } catch (error) {
                count.textContent = error.message || "Could not load available courses from backend.";
                document.getElementById("student-course-list").innerHTML =
                    "<article class='student-course-empty'>Could not load courses.</article>";
                document.getElementById("video-list").innerHTML =
                    "<article class='student-course-empty'>Backend connection failed.</article>";
            }
        }

        search.addEventListener("input", render);
        statusFilter.addEventListener("change", render);
        selector.addEventListener("change", function () {
            selectCourse(selector.value);
        });

        loadCourses();
    }

    function statusText(status) {
        status = String(status || "").trim().toLowerCase();

        if (status === "accepted") {
            return "Accepted";
        }
        if (status === "pending") {
            return "Pending Approval";
        }
        if (status === "rejected") {
            return "Rejected";
        }
        return "Not Requested";
    }

    function courseVideosUrl(course) {
        const query = new URLSearchParams();
        query.set("course", course.course_name || "");
        query.set("teacher_id", String(course.teacher_id));
        return "student-videos.html?" + query.toString();
    }

    function renderCourses(courses, onRegister) {
        const panel = document.getElementById("course-registration-panel");
        const list = document.getElementById("course-list");
        const feedback = document.getElementById("course-registration-feedback");

        if (!panel || !list || !feedback) {
            return;
        }

        panel.classList.remove("is-hidden");
        list.innerHTML = "";

        if (!courses.length) {
            feedback.textContent = "No published courses are available yet.";
            feedback.className = "feedback-banner warning";
            return;
        }

        feedback.textContent = courses.length + " course" + (courses.length === 1 ? "" : "s") + " available in the catalog.";
        feedback.className = "feedback-banner info";

        courses.forEach(function (course) {
            const card = document.createElement("article");
            card.className = "video-card";

            const assignedCount = Number(course.assigned_videos_count || 0);
            const hasAssignedVideos = assignedCount > 0;
            const canRequest = course.registration_status === "none" || course.registration_status === "rejected";

            const body = document.createElement("div");
            body.className = "row-between";
            body.innerHTML =
                "<div>" +
                    "<span class='eyebrow'>Course</span>" +
                    "<h3>" + course.course_name + "</h3>" +
                    "<p>Teacher: " + course.teacher_name + "</p>" +
                "</div>" +
                "<div class='chip-row'>" +
                    "<span class='chip'>" + course.published_videos_count + " lecture" + (course.published_videos_count === 1 ? "" : "s") + "</span>" +
                    "<span class='chip'>" + course.completed_videos_count + " ready</span>" +
                    (hasAssignedVideos ? "<span class='chip assigned'>" + assignedCount + " assigned</span>" : "") +
                "</div>";

            const footer = document.createElement("div");
            footer.className = "row-between";
            footer.innerHTML =
                "<strong>" +
                    (
                        course.registered
                            ? "Course access enabled"
                            : hasAssignedVideos
                                ? assignedCount + " assigned video" + (assignedCount === 1 ? "" : "s") + " available"
                                : course.registration_status === "pending"
                                    ? "Waiting for course approval"
                                    : "Request access to open this course"
                    ) +
                "</strong>";

            const actions = document.createElement("div");
            actions.className = "course-card-actions";

            if (course.registered) {
                const openLink = document.createElement("a");
                openLink.className = "btn";
                openLink.href = courseVideosUrl(course);
                openLink.textContent = "Open Lectures";
                actions.appendChild(openLink);
            } else {
                if (hasAssignedVideos) {
                    const assignedLink = document.createElement("a");
                    assignedLink.className = "btn";
                    assignedLink.href = courseVideosUrl(course);
                    assignedLink.textContent = "Open Assigned Videos";
                    actions.appendChild(assignedLink);
                }

                if (canRequest) {
                    const button = document.createElement("button");
                    button.className = hasAssignedVideos ? "btn-secondary" : "btn";
                    button.type = "button";
                    button.textContent = "Request Course";
                    button.addEventListener("click", function () {
                        onRegister(course, button);
                    });
                    actions.appendChild(button);
                } else {
                    const statusBadge = document.createElement("span");
                    statusBadge.className = "decision-locked " + course.registration_status;
                    statusBadge.textContent = statusText(course.registration_status);
                    actions.appendChild(statusBadge);
                }
            }

            footer.appendChild(actions);

            card.appendChild(body);
            card.appendChild(footer);
            list.appendChild(card);
        });
    }

    function renderStudentRequests(requests, onDecision) {
        const panel = document.getElementById("student-request-panel");
        const list = document.getElementById("student-request-list");
        const feedback = document.getElementById("student-request-feedback");

        if (!panel || !list || !feedback) {
            return;
        }

        panel.classList.remove("is-hidden");
        list.innerHTML = "";

        if (!requests.length) {
            feedback.textContent = "No student registration requests yet.";
            feedback.className = "feedback-banner info";
            return;
        }

        const pendingCount = requests.filter(function (request) {
            return String(request.status || "").trim().toLowerCase() === "pending";
        }).length;
        feedback.textContent = pendingCount
            ? pendingCount + " pending request" + (pendingCount === 1 ? "" : "s") + " need your decision."
            : "No pending requests need your decision.";
        feedback.className = pendingCount ? "feedback-banner warning" : "feedback-banner info";

        requests.forEach(function (request) {
            const requestStatus = String(request.status || "none").trim().toLowerCase();
            const canDecide = requestStatus === "pending";
            const statusClass = requestStatus === "accepted" ? "success" : requestStatus === "rejected" ? "danger" : "warning";
            const card = document.createElement("article");
            card.className = "video-card student-request-card" + (canDecide ? "" : " is-locked");

            card.innerHTML =
                "<div class='video-card-header'>" +
                    "<div>" +
                        "<span class='eyebrow'>Course Request</span>" +
                        "<h3>" + request.student_name + "</h3>" +
                        "<p>" + request.student_email + "</p>" +
                        (request.course_name ? "<p><strong>Course:</strong> " + request.course_name + "</p>" : "") +
                    "</div>" +
                    "<span class='status-pill " + statusClass + "'>" + statusText(requestStatus) + "</span>" +
                "</div>" +
                "<div class='row-between'>" +
                    "<strong>Requested: " + request.created_at + "</strong>" +
                    (
                        canDecide
                            ? "<div class='chip-row'>" +
                                "<button class='btn' type='button' data-decision='accept'>Accept</button>" +
                                "<button class='btn-ghost' type='button' data-decision='reject'>Reject</button>" +
                            "</div>"
                            : "<span class='decision-locked " + requestStatus + "' aria-disabled='true'>" + statusText(requestStatus) + "</span>"
                    ) +
                "</div>";

            card.querySelectorAll("[data-decision]").forEach(function (button) {
                button.addEventListener("click", function () {
                    onDecision(request.id, button.dataset.decision, button);
                });
            });

            list.appendChild(card);
        });
    }

    function scrollToCourseRequestsIfRequested() {
        if (window.location.hash !== "#student-request-panel") {
            return;
        }

        const panel = document.getElementById("student-request-panel");
        if (!panel || panel.classList.contains("is-hidden")) {
            return;
        }

        window.requestAnimationFrame(function () {
            panel.scrollIntoView({ block: "start" });
        });
    }

    function isCourseRequestsOnlyView() {
        const params = new URLSearchParams(window.location.search);
        return params.get("view") === "requests";
    }

    function applyCourseRequestsOnlyView() {
        if (!isCourseRequestsOnlyView()) {
            return;
        }

        const libraryPanel = document.getElementById("video-library-panel");
        const resultsCount = document.getElementById("video-results-count");
        const videoList = document.getElementById("video-list");
        const topbar = document.querySelector(".topbar");
        const topbarEyebrow = topbar ? topbar.querySelector(".eyebrow") : null;
        const topbarTitle = topbar ? topbar.querySelector("h2") : null;
        const topbarActions = topbar ? topbar.querySelector(".topbar-actions") : null;

        if (libraryPanel) {
            libraryPanel.classList.add("is-hidden");
        }
        if (resultsCount) {
            resultsCount.classList.add("is-hidden");
        }
        if (videoList) {
            videoList.classList.add("is-hidden");
        }
        if (topbarEyebrow) {
            topbarEyebrow.textContent = "Course Requests";
        }
        if (topbarTitle) {
            topbarTitle.textContent = "Review student course access requests";
        }
        if (topbarActions) {
            topbarActions.classList.add("is-hidden");
        }
    }

    function initVideos() {
        const page = document.body.dataset.page;
        if (page !== "videos" && page !== "teacher-videos" && page !== "student-videos" && page !== "student-courses" && page !== "course-requests") {
            return;
        }

        if (page === "student-videos") {
            initStudentCoursesPage();
            return;
        }

        const search = document.getElementById("search");
        const roleView = document.getElementById("role-view");
        const statusFilter = document.getElementById("status-filter");
        const applyButton = document.getElementById("apply-filters");
        const courseFeedback = document.getElementById("course-registration-feedback");
        const requestFeedback = document.getElementById("student-request-feedback");
        const requestsOnlyView = page === "course-requests" || isCourseRequestsOnlyView();

        applyCourseRequestsOnlyView();

        if (roleView) {
            roleView.value = "current";
        }

        async function applyFilters() {
            const sessionRole = window.ThinkNoteApp.getCurrentRole();
            const activeRole = roleView.value === "current" ? sessionRole : roleView.value;
            const keyword = search.value.trim();
            const status = statusFilter.value;

            try {
                const query = new URLSearchParams();
                if (keyword) {
                    query.set("search", keyword);
                }
                if (status !== "all") {
                    query.set("status_filter", status === "review" ? "review" : status);
                }
                if (sessionRole === "teacher" && window.ThinkNoteApp.getActiveWorkspaceId()) {
                    query.set("workspace_id", window.ThinkNoteApp.getActiveWorkspaceId());
                }

                const suffix = query.toString() ? "?" + query.toString() : "";
                const videos = await window.ThinkNoteApp.apiRequest("/videos" + suffix);
                renderVideos(videos, activeRole, applyFilters);
            } catch (error) {
                const count = document.getElementById("video-results-count");
                count.textContent = error.message || "Could not load videos .";
                count.className = "feedback-banner warning";
            }
        }

        if (page === "student-courses") {
            async function loadCourses() {
                try {
                    const courses = await window.ThinkNoteApp.apiRequest("/users/courses");
                    renderCourses(courses, async function (course, button) {
                        button.disabled = true;
                        button.textContent = "Requesting...";

                        try {
                            await window.ThinkNoteApp.apiRequest(
                                "/users/courses/" + course.teacher_id + "/register?course_name=" + encodeURIComponent(course.course_name),
                                { method: "POST" }
                            );
                            courseFeedback.textContent = "Request sent. Your teacher must accept before this course appears in Lectures.";
                            courseFeedback.className = "feedback-banner success";
                            await loadCourses();
                        } catch (error) {
                            button.disabled = false;
                            button.textContent = "Request Course";
                            courseFeedback.textContent = error.message || "Could not request course access.";
                            courseFeedback.className = "feedback-banner warning";
                        }
                    });
                } catch (error) {
                    const panel = document.getElementById("course-registration-panel");
                    if (panel) {
                        panel.classList.remove("is-hidden");
                    }
                    courseFeedback.textContent = error.message || "Could not load courses.";
                    courseFeedback.className = "feedback-banner warning";
                }
            }

            loadCourses();
            return;
        }

        async function loadStudentRequests() {
            if (window.ThinkNoteApp.getCurrentRole() !== "teacher") {
                return;
            }

            try {
                const requests = await window.ThinkNoteApp.apiRequest("/users/teacher/course-requests");
                renderStudentRequests(requests, async function (requestId, decision, button) {
                    button.disabled = true;
                    button.textContent = decision === "accept" ? "Accepting..." : "Rejecting...";

                    try {
                        await window.ThinkNoteApp.apiRequest("/users/teacher/course-requests/" + requestId + "/" + decision, {
                            method: "POST"
                        });
                        requestFeedback.textContent = "Course access request updated.";
                        requestFeedback.className = "feedback-banner success";
                        await loadStudentRequests();
                    } catch (error) {
                        requestFeedback.textContent = error.message || "Could not update request.";
                        requestFeedback.className = "feedback-banner warning";
                        await loadStudentRequests();
                    }
                });
                scrollToCourseRequestsIfRequested();
            } catch (error) {
                const panel = document.getElementById("student-request-panel");
                if (panel) {
                    panel.classList.remove("is-hidden");
                }
                requestFeedback.textContent = error.message || "Could not load course access requests.";
                requestFeedback.className = "feedback-banner warning";
                scrollToCourseRequestsIfRequested();
            }
        }

        if (requestsOnlyView) {
            loadStudentRequests();
            return;
        }

        applyButton.addEventListener("click", applyFilters);
        search.addEventListener("input", applyFilters);
        statusFilter.addEventListener("change", applyFilters);
        roleView.addEventListener("change", applyFilters);

        if (requestFeedback) {
            loadStudentRequests();
        }
        if (!requestsOnlyView) {
            applyFilters();
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        initVideos();
    });
})();

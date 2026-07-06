(function () {
    const STORAGE_KEY = "thinknote_session";
    const ACCESS_NOTICE_KEY = "thinknote_access_notice";
    const SIDEBAR_COLLAPSED_KEY = "thinknote_sidebar_collapsed";
    const SIDEBAR_HIDDEN_KEY = "thinknote_sidebar_hidden";
    const ACTIVE_WORKSPACE_KEY = "thinknote_active_workspace_id";
    const API_BASE_URL = "http://127.0.0.1:8000";

    const pageAccess = {
        login: ["public"],
        signup: ["public"],
        dashboard: ["admin", "teacher", "student"],
        "teacher-dashboard": ["teacher"],
        "student-dashboard": ["student"],
        analytics: ["admin"],
        upload: ["teacher"],
        videos: ["admin", "teacher", "student"],
        "teacher-videos": ["teacher"],
        "course-requests": ["teacher"],
        settings: ["admin", "teacher", "student"],
        "student-courses": ["student"],
        "student-videos": ["student"],
        results: ["admin", "teacher", "student"],
        "teacher-results": ["admin", "teacher"],
        "student-results": ["student"]
    };

    const roleConfig = {
        admin: {
            label: "Admin",
            dashboardTitle: "Product Overview",
            dashboardCopy: "See how ThinkNote AI is being used across videos, summaries, and learners.",
            dashboardHeroTitle: "ThinkNote AI turns lecture videos into clear study resources.",
            dashboardHeroDescription: "Review product activity, published content, and learning material from one readable dashboard.",
            dashboardChip: "Product Admin",
            uploadTitle: "Upload Oversight",
            uploadCopy: "Admins can inspect upload configuration, but lecture submission is reserved for teachers.",
            videosTitle: "Institution Video Catalog",
            videosCopy: "Browse every lecture record across departments, teachers, and statuses.",
            resultsTitle: "Review Generated Outputs",
            resultsCopy: "Inspect transcripts, captions, summaries, and evaluation data across all users.",
            analyticsTitle: "Platform Monitoring",
            analyticsCopy: "Observe usage trends, content growth, and summary quality metrics."
        },
        teacher: {
            label: "Teacher",
            dashboardTitle: "Teacher Home",
            dashboardCopy: "Upload lectures, review summaries, and publish study-ready material.",
            dashboardHeroTitle: "Upload a lecture and turn it into notes students can actually use.",
            dashboardHeroDescription: "ThinkNote AI keeps the video, transcript, and summary connected so your class material is easier to share.",
            dashboardChip: "Teaching Workspace",
            uploadTitle: "Lecture Upload",
            uploadCopy: "Prepare metadata, upload the video, and monitor every AI stage.",
            videosTitle: "My Lecture Library",
            videosCopy: "Manage your uploads and inspect processing progress or published summaries.",
            resultsTitle: "Summary Results",
            resultsCopy: "Review transcript, fusion output, summary blocks, and evaluation scores.",
            analyticsTitle: "Course Analytics Preview",
            analyticsCopy: "Teachers can review summary performance and learning activity trends."
        },
        student: {
            label: "Student",
            dashboardTitle: "Student Home",
            dashboardCopy: "Open lectures, search important moments, and revise from clear notes.",
            dashboardHeroTitle: "Study from lecture videos without losing the main points.",
            dashboardHeroDescription: "ThinkNote AI brings the video, transcript, captions, and summary into one focused learning view.",
            dashboardChip: "Study Workspace",
            uploadTitle: "Upload Restricted",
            uploadCopy: "Students can inspect the workflow design, but only teachers can submit lecture videos.",
            videosTitle: "Learning Video Catalog",
            videosCopy: "Browse lectures assigned to your student account and search processed educational content.",
            resultsTitle: "Summary Results",
            resultsCopy: "Read processed transcripts, captions, and structured summaries for revision.",
            analyticsTitle: "Learning Analytics Preview",
            analyticsCopy: "Students see a simplified analytics perspective focused on accessible learning content."
        }
    };

    const roleRoutes = {
        admin: {
            dashboard: "dashboard.html",
            videos: "videos.html",
            results: "teacher-results.html"
        },
        teacher: {
            dashboard: "teacher-dashboard.html",
            videos: "teacher-videos.html",
            results: "teacher-results.html"
        },
        student: {
            dashboard: "student-dashboard.html",
            videos: "student-videos.html",
            results: "student-results.html"
        }
    };

    const sidebarConfig = {
        admin: {
            subtitle: "Administrator",
            groups: [
                {
                    label: "Navigation",
                    links: [
                        { href: "dashboard.html", title: "Home", icon: "home" },
                        { href: "dashboard.html", title: "Dashboard", icon: "dashboard" },
                        { href: "analytics.html", title: "Analytics", icon: "analytics" },
                        { href: "videos.html", title: "Projects", icon: "projects" },
                        { href: "teacher-results.html", title: "Team", icon: "team" },
                        { href: "settings.html", title: "Settings", icon: "settings" }
                    ]
                }
            ]
        },
        teacher: {
            subtitle: "Teacher Workspace",
            groups: [
                {
                    label: "Navigation",
                    links: [
                        { href: "teacher-dashboard.html", title: "Home", icon: "home" },
                        { href: "teacher-results.html", title: "Analytics", icon: "analytics" },
                        { href: "teacher-videos.html", title: "Videos", icon: "projects" },
                        { href: "upload.html", title: "Upload", icon: "upload" },
                        { href: "course-requests.html", title: "Course Requests", icon: "requests" },
                        { href: "settings.html", title: "Settings", icon: "settings" }
                    ]
                }
            ]
        },
        student: {
            subtitle: "Student Workspace",
            groups: [
                {
                    label: "Navigation",
                    links: [
                        { href: "student-dashboard.html", title: "Home", icon: "home" },
                        { href: "student-videos.html", title: "Lectures", icon: "projects" },
                        { href: "student-courses.html", title: "Courses", icon: "team" },
                        { href: "settings.html", title: "Settings", icon: "settings" }
                    ]
                }
            ]
        }
    };

    function normalizeRole(role) {
        return roleConfig[role] ? role : "teacher";
    }

    function getSession() {
        try {
            const raw = window.localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (error) {
            return null;
        }
    }

    function saveSession(session) {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    }

    function clearSession() {
        window.localStorage.removeItem(STORAGE_KEY);
    }

    function getPageNameFromHref(href) {
        if (!href || href.charAt(0) === "#") {
            return "";
        }

        const filename = href.split("?")[0].split("#")[0].split("/").pop();
        if (!filename || filename === ".") {
            return "";
        }

        return filename.replace(".html", "");
    }

    function canAccessPage(role, pageName) {
        const allowedRoles = pageAccess[pageName];
        if (!allowedRoles) {
            return true;
        }

        if (allowedRoles.indexOf("public") !== -1) {
            return true;
        }

        return allowedRoles.indexOf(normalizeRole(role)) !== -1;
    }

    function isDashboardPage(pageName) {
        return pageName === "dashboard" || pageName === "teacher-dashboard" || pageName === "student-dashboard";
    }

    function roleAccessMessage(role, pageName) {
        if (pageName === "upload") {
            return "Upload is available only for teacher accounts.";
        }
        if (pageName === "analytics") {
            return "Analytics is available only for admin accounts.";
        }
        if (pageName && pageName.indexOf("teacher-") === 0) {
            return "Teacher pages are available only for teacher accounts.";
        }
        if (pageName && pageName.indexOf("student-") === 0) {
            return "Student pages are available only for student accounts.";
        }

        return "Your account role cannot open that page.";
    }

    function getDashboardPage(role) {
        return roleRoutes[normalizeRole(role)].dashboard;
    }

    function getVideosPage(role) {
        return roleRoutes[normalizeRole(role)].videos;
    }

    function getResultPage(role) {
        return roleRoutes[normalizeRole(role)].results;
    }

    function getCanonicalPage(role, pageName) {
        if (pageName === "dashboard") {
            return getDashboardPage(role);
        }
        if (pageName === "videos") {
            return getVideosPage(role);
        }
        if (pageName === "results") {
            return getResultPage(role);
        }
        return "";
    }

    function redirectToPage(page) {
        const query = window.location.search || "";
        window.location.replace(page + query);
    }

    function ensureSession() {
        const page = document.body.dataset.page;
        if (page === "login" || page === "signup") {
            return null;
        }

        const session = getSession();
        if (!session || !session.user) {
            window.location.href = "login.html";
            return null;
        }

        const role = normalizeRole(session.user.role);
        const canonicalPage = getCanonicalPage(role, page);
        if (canonicalPage && getPageNameFromHref(canonicalPage) !== page) {
            redirectToPage(canonicalPage);
            return null;
        }

        if (!canAccessPage(role, page)) {
            window.sessionStorage.setItem(ACCESS_NOTICE_KEY, roleAccessMessage(role, page));
            redirectToPage(getDashboardPage(role));
            return null;
        }

        return session;
    }

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }

    function setRoleBadge(role) {
        document.querySelectorAll("[data-role-badge]").forEach(function (badge) {
            badge.textContent = roleConfig[role].label;
            badge.classList.remove("admin", "teacher", "student");
            badge.classList.add(role);
        });
    }

    function sidebarIcon(name) {
        const icons = {
            home: "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M3 10.5 12 3l9 7.5v9a1.5 1.5 0 0 1-1.5 1.5H15v-6H9v6H4.5A1.5 1.5 0 0 1 3 19.5v-9Z'/></svg>",
            dashboard: "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M4 4h7v7H4V4Zm9 0h7v4h-7V4ZM4 13h7v7H4v-7Zm9-3h7v10h-7V10Z'/></svg>",
            analytics: "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M4 19h16v2H4v-2Zm2-2V9h3v8H6Zm5 0V4h3v13h-3Zm5 0v-6h3v6h-3Z'/></svg>",
            projects: "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M4 5.5A2.5 2.5 0 0 1 6.5 3h3.2l2 2H18a2 2 0 0 1 2 2v1H4V5.5ZM4 10h16l-1.2 8.4A3 3 0 0 1 15.8 21H8.2a3 3 0 0 1-3-2.6L4 10Z'/></svg>",
            upload: "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M11 16V7.8l-3.1 3.1-1.4-1.4L12 4l5.5 5.5-1.4 1.4L13 7.8V16h-2Zm-6 4v-5h2v3h10v-3h2v5H5Z'/></svg>",
            requests: "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M8 3h8l1 2h3v16H4V5h3l1-2Zm1.2 4h5.6l-.5-1h-4.6l-.5 1ZM7 10h10v2H7v-2Zm0 4h7v2H7v-2Z'/></svg>",
            settings: "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M19.4 13.5c.1-.5.1-1 .1-1.5s0-1-.1-1.5l2-1.5-2-3.5-2.4 1a8 8 0 0 0-2.6-1.5L14 2h-4l-.4 3a8 8 0 0 0-2.6 1.5l-2.4-1-2 3.5 2 1.5A9 9 0 0 0 4.5 12c0 .5 0 1 .1 1.5l-2 1.5 2 3.5 2.4-1a8 8 0 0 0 2.6 1.5l.4 3h4l.4-3a8 8 0 0 0 2.6-1.5l2.4 1 2-3.5-2-1.5ZM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5Z'/></svg>",
            team: "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M8 11a4 4 0 1 1 0-8 4 4 0 0 1 0 8Zm8.5 1a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7ZM2 20a6 6 0 0 1 12 0v1H2v-1Zm11.5 1v-1a7.5 7.5 0 0 0-1.3-4.2A5.2 5.2 0 0 1 22 18.3V21h-8.5Z'/></svg>"
        };
        return icons[name] || icons.dashboard;
    }

    function renderSidebar(role) {
        const sidebar = document.querySelector(".sidebar");
        if (!sidebar) {
            return;
        }

        const config = sidebarConfig[normalizeRole(role)];
        const session = getSession();
        const user = session && session.user ? session.user : { full_name: "ThinkNote User", email: roleConfig[normalizeRole(role)].label };
        const initials = String(user.full_name || "TN").split(" ").map(function (part) {
            return part.charAt(0);
        }).join("").slice(0, 2).toUpperCase();
        const currentPage = document.body.dataset.page || "";
        const currentHash = window.location.hash || "";
        let activeAssigned = false;
        const groups = config.groups.map(function (group) {
            const links = group.links.map(function (link) {
                const pageName = getPageNameFromHref(link.href);
                const linkHash = link.href.indexOf("#") !== -1 ? link.href.slice(link.href.indexOf("#")) : "";
                const isActive = !activeAssigned && pageName === currentPage && (
                    currentHash ? linkHash === currentHash : !linkHash
                );
                if (isActive) {
                    activeAssigned = true;
                }
                const active = isActive ? " active" : "";
                return (
                    "<li><a class='nav-link" + active + "' href='" + link.href + "' title='" + link.title + "'>" +
                        "<span class='nav-icon'>" + sidebarIcon(link.icon) + "</span>" +
                        "<span class='nav-text'>" + link.title + "</span>" +
                    "</a></li>"
                );
            }).join("");

            return (
                "<div class='nav-group'>" +
                    "<div class='nav-label'>" + group.label + "</div>" +
                    "<ul class='nav-list'>" + links + "</ul>" +
                "</div>"
            );
        }).join("");

        sidebar.innerHTML =
            "<div class='sidebar-top'>" +
                "<div class='brand-mark'>TN</div>" +
                "<div class='brand-copy'>" +
                    "<h1>ThinkNote AI</h1>" +
                    "<p>" + config.subtitle + "</p>" +
                "</div>" +
                "<button class='sidebar-collapse' type='button' data-sidebar-collapse aria-label='Hide sidebar'>Hide</button>" +
                "<button class='sidebar-close' type='button' data-sidebar-close aria-label='Close menu'>Close</button>" +
            "</div>" +
            "<nav>" +
                groups +
            "</nav>";
    }

    function getActiveWorkspaceId() {
        return window.localStorage.getItem(ACTIVE_WORKSPACE_KEY) || "";
    }

    function setActiveWorkspaceId(value) {
        if (value) {
            window.localStorage.setItem(ACTIVE_WORKSPACE_KEY, String(value));
        } else {
            window.localStorage.removeItem(ACTIVE_WORKSPACE_KEY);
        }
    }

    function requestWorkspaceName() {
        return new Promise(function (resolve) {
            const backdrop = document.createElement("div");
            backdrop.className = "workspace-dialog-backdrop";
            backdrop.innerHTML =
                "<section class='workspace-dialog' role='dialog' aria-modal='true' aria-labelledby='workspace-dialog-title' aria-describedby='workspace-dialog-description'>" +
                    "<div class='workspace-dialog-icon' aria-hidden='true'>+</div>" +
                    "<div class='workspace-dialog-heading'>" +
                        "<span class='eyebrow'>New Course</span>" +
                        "<h2 id='workspace-dialog-title'>Create a course workspace</h2>" +
                        "<p id='workspace-dialog-description'>Organize lectures, summaries, and student access under one course.</p>" +
                    "</div>" +
                    "<form class='workspace-dialog-form' data-workspace-form novalidate>" +
                        "<label for='workspace-dialog-name'>Course workspace name</label>" +
                        "<input id='workspace-dialog-name' name='workspace-name' type='text' maxlength='120' autocomplete='off' placeholder='e.g., CSC401 Artificial Intelligence' aria-describedby='workspace-dialog-hint workspace-dialog-error'>" +
                        "<div class='workspace-dialog-field-meta'>" +
                            "<span id='workspace-dialog-hint'>Use a clear course code or subject name.</span>" +
                            "<span class='workspace-dialog-error' id='workspace-dialog-error' role='alert'></span>" +
                        "</div>" +
                        "<div class='workspace-dialog-actions'>" +
                            "<button class='btn-ghost' type='button' data-workspace-cancel>Cancel</button>" +
                            "<button class='btn' type='submit' data-workspace-confirm>Create Workspace</button>" +
                        "</div>" +
                    "</form>" +
                "</section>";

            const form = backdrop.querySelector("[data-workspace-form]");
            const input = backdrop.querySelector("#workspace-dialog-name");
            const errorText = backdrop.querySelector("#workspace-dialog-error");
            const cancelButton = backdrop.querySelector("[data-workspace-cancel]");
            let settled = false;

            function closeDialog(value) {
                if (settled) {
                    return;
                }
                settled = true;
                document.removeEventListener("keydown", handleKeydown);
                backdrop.remove();
                resolve(value);
            }

            function handleKeydown(event) {
                if (event.key === "Escape") {
                    closeDialog(null);
                }
            }

            form.addEventListener("submit", function (event) {
                event.preventDefault();
                const name = input.value.trim();
                if (name.length < 2) {
                    input.classList.add("has-error");
                    input.setAttribute("aria-invalid", "true");
                    errorText.textContent = "Enter at least 2 characters.";
                    input.focus();
                    return;
                }
                closeDialog(name);
            });
            input.addEventListener("input", function () {
                input.classList.remove("has-error");
                input.removeAttribute("aria-invalid");
                errorText.textContent = "";
            });
            cancelButton.addEventListener("click", function () {
                closeDialog(null);
            });
            backdrop.addEventListener("click", function (event) {
                if (event.target === backdrop) {
                    closeDialog(null);
                }
            });
            document.addEventListener("keydown", handleKeydown);
            document.body.appendChild(backdrop);
            input.focus();
        });
    }

    async function syncTeacherWorkspaces(role) {
        if (normalizeRole(role) !== "teacher") {
            return;
        }

        const select = document.querySelector("[data-workspace-select]");
        const addButton = document.querySelector("[data-workspace-add]");
        if (!select || !addButton) {
            return;
        }

        try {
            const workspaces = await apiRequest("/users/workspaces");
            select.innerHTML = "";
            if (!workspaces.length) {
                const option = document.createElement("option");
                option.value = "";
                option.textContent = "No course yet";
                select.appendChild(option);
            } else {
                workspaces.forEach(function (workspace) {
                    const option = document.createElement("option");
                    option.value = String(workspace.id);
                    option.textContent = workspace.name;
                    select.appendChild(option);
                });
                const activeId = getActiveWorkspaceId();
                const hasActive = workspaces.some(function (workspace) {
                    return String(workspace.id) === activeId;
                });
                select.value = hasActive ? activeId : String(workspaces[0].id);
                setActiveWorkspaceId(select.value);
            }

            if (select.dataset.workspaceWired !== "true") {
                select.dataset.workspaceWired = "true";
                select.addEventListener("change", function () {
                    setActiveWorkspaceId(select.value);
                    window.location.href = getDashboardPage(role);
                });
            }

            if (addButton.dataset.workspaceWired !== "true") {
                addButton.dataset.workspaceWired = "true";
                addButton.addEventListener("click", async function () {
                    const name = await requestWorkspaceName();
                    if (!name) {
                        return;
                    }
                    addButton.disabled = true;
                    try {
                        const workspace = await apiRequest("/users/workspaces", {
                            method: "POST",
                            body: JSON.stringify({ name: name })
                        });
                        setActiveWorkspaceId(workspace.id);
                        window.location.href = getDashboardPage(role);
                    } catch (error) {
                        addButton.textContent = error.message || "Could not create course";
                        window.setTimeout(function () {
                            addButton.textContent = "Add Course";
                        }, 3000);
                    } finally {
                        addButton.disabled = false;
                    }
                });
            }
        } catch (error) {
            select.innerHTML = "<option>Could not load courses</option>";
        }
    }

    function ensureSidebarToggle() {
        if (document.body.dataset.page === "login" || document.body.dataset.page === "signup") {
            return;
        }

        if (!document.querySelector(".sidebar")) {
            return;
        }

        let toggle = document.querySelector("[data-sidebar-toggle]");
        if (!toggle) {
            toggle = document.createElement("button");
            toggle.className = "sidebar-toggle";
            toggle.type = "button";
            toggle.setAttribute("data-sidebar-toggle", "true");
            toggle.setAttribute("aria-controls", "app-sidebar");
            toggle.setAttribute("aria-expanded", "false");
            toggle.innerHTML = "<span></span><span></span><span></span><strong>Menu</strong>";
            document.body.appendChild(toggle);
        }

        let overlay = document.querySelector("[data-sidebar-overlay]");
        if (!overlay) {
            overlay = document.createElement("button");
            overlay.className = "sidebar-overlay";
            overlay.type = "button";
            overlay.setAttribute("data-sidebar-overlay", "true");
            overlay.setAttribute("aria-label", "Close menu");
            document.body.appendChild(overlay);
        }

        const sidebar = document.querySelector(".sidebar");
        sidebar.id = "app-sidebar";
        document.body.classList.remove("sidebar-collapsed", "sidebar-hidden");
        window.localStorage.removeItem(SIDEBAR_COLLAPSED_KEY);
        window.localStorage.removeItem(SIDEBAR_HIDDEN_KEY);

        function setOpen(open) {
            document.body.classList.toggle("sidebar-open", open);
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        }

        if (toggle.dataset.sidebarWired !== "true") {
            toggle.dataset.sidebarWired = "true";
            toggle.addEventListener("click", function () {
                setOpen(!document.body.classList.contains("sidebar-open"));
            });
        }

        if (overlay.dataset.sidebarWired !== "true") {
            overlay.dataset.sidebarWired = "true";
            overlay.addEventListener("click", function () {
                setOpen(false);
            });
        }

        sidebar.querySelectorAll("a[href]").forEach(function (link) {
            if (link.dataset.sidebarCloseWired === "true") {
                return;
            }

            link.dataset.sidebarCloseWired = "true";
            link.addEventListener("click", function () {
                setOpen(false);
            });
        });

        sidebar.querySelectorAll("[data-sidebar-close]").forEach(function (button) {
            if (button.dataset.sidebarCloseWired === "true") {
                return;
            }

            button.dataset.sidebarCloseWired = "true";
            button.addEventListener("click", function () {
                setOpen(false);
            });
        });

        sidebar.querySelectorAll("[data-sidebar-collapse]").forEach(function (button) {
            if (button.dataset.sidebarCollapseWired === "true") {
                return;
            }

            button.dataset.sidebarCollapseWired = "true";
            button.addEventListener("click", function () {
                if (window.matchMedia("(max-width: 900px)").matches) {
                    setOpen(false);
                }

                document.body.classList.remove("sidebar-collapsed", "sidebar-hidden");
            });
        });

        if (document.body.dataset.sidebarEscapeWired !== "true") {
            document.body.dataset.sidebarEscapeWired = "true";
            document.addEventListener("keydown", function (event) {
                if (event.key === "Escape") {
                    setOpen(false);
                }
            });
        }
    }

    function attachLogout() {
        document.querySelectorAll("[data-action='logout']").forEach(function (link) {
            if (link.dataset.logoutWired === "true") {
                return;
            }

            link.dataset.logoutWired = "true";
            link.addEventListener("click", function (event) {
                event.preventDefault();
                clearSession();
                window.location.href = "login.html";
            });
        });
    }

    function applyRoleNavigation(role) {
        document.querySelectorAll("a[href]").forEach(function (link) {
            const href = link.getAttribute("href");
            const pageName = getPageNameFromHref(href);
            const queryIndex = href.indexOf("?");
            const hashIndex = href.indexOf("#");
            const suffixIndex = queryIndex === -1 ? hashIndex : hashIndex === -1 ? queryIndex : Math.min(queryIndex, hashIndex);
            const suffix = suffixIndex !== -1 ? href.slice(suffixIndex) : "";

            if (pageName === "dashboard") {
                link.setAttribute("href", getDashboardPage(role) + suffix);
            } else if (pageName === "videos") {
                link.setAttribute("href", getVideosPage(role) + suffix);
            } else if (pageName === "results") {
                link.setAttribute("href", getResultPage(role) + suffix);
            }
        });

        document.querySelectorAll("a[href]").forEach(function (link) {
            const href = link.getAttribute("href");
            const pageName = getPageNameFromHref(href);
            const visibleTarget = link.closest("li") || link;
            if (!pageName || canAccessPage(role, pageName)) {
                visibleTarget.classList.remove("is-hidden");
                return;
            }

            visibleTarget.classList.add("is-hidden");
        });
    }

    function activateCurrentNav() {
        const page = window.location.pathname.split("/").pop() || "dashboard.html";
        const currentHash = window.location.hash || "";
        let activeAssigned = false;
        document.querySelectorAll(".nav-link").forEach(function (link) {
            const href = link.getAttribute("href");
            const hrefPage = href.split("?")[0].split("#")[0];
            const hrefHash = href.indexOf("#") !== -1 ? href.slice(href.indexOf("#")) : "";
            const isActive = !activeAssigned && hrefPage === page && (
                currentHash ? hrefHash === currentHash : !hrefHash
            );
            if (isActive) {
                activeAssigned = true;
            }
            link.classList.toggle("active", isActive);
        });
    }

    function syncRoleText() {
        const session = getSession();
        const role = normalizeRole(session && session.user ? session.user.role : "teacher");
        const config = roleConfig[role];

        document.body.dataset.role = role;
        renderSidebar(role);
        ensureSidebarToggle();
        setRoleBadge(role);
        attachLogout();
        syncTeacherWorkspaces(role);
        applyRoleNavigation(role);
        activateCurrentNav();

        setText("dashboard-role-title", config.dashboardTitle);
        setText("dashboard-role-copy", config.dashboardCopy);
        setText("dashboard-role-chip", config.dashboardChip);
        setText("dashboard-hero-title", config.dashboardHeroTitle);
        setText("dashboard-hero-description", config.dashboardHeroDescription);

        setText("upload-role-title", config.uploadTitle);
        setText("upload-role-copy", config.uploadCopy);
        setText("videos-role-title", config.videosTitle);
        setText("videos-role-copy", config.videosCopy);
        setText("results-role-title", config.resultsTitle);
        setText("results-role-copy", config.resultsCopy);
        setText("analytics-role-title", config.analyticsTitle);
        setText("analytics-role-copy", config.analyticsCopy);

        const accessNotice = window.sessionStorage.getItem(ACCESS_NOTICE_KEY);
        if (accessNotice && isDashboardPage(document.body.dataset.page)) {
            document.body.dataset.accessNotice = "true";
            setText("dashboard-hero-title", "Access restricted for this role.");
            setText("dashboard-hero-description", accessNotice);
            window.sessionStorage.removeItem(ACCESS_NOTICE_KEY);
        }
    }

    async function apiRequest(path, options) {
        const session = getSession();
        const requestOptions = Object.assign(
            {
                headers: {
                    "Content-Type": "application/json"
                }
            },
            options || {}
        );

        requestOptions.headers = requestOptions.headers || {};

        if (session && session.token) {
            requestOptions.headers.Authorization = "Bearer " + session.token;
        }

        if (requestOptions.body instanceof FormData) {
            delete requestOptions.headers["Content-Type"];
        }

        const response = await window.fetch(API_BASE_URL + path, requestOptions);
        let payload = null;

        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }

        if (!response.ok) {
            let message = "Request failed.";
            if (payload && Array.isArray(payload.detail) && payload.detail.length) {
                message = payload.detail.map(function (item) {
                    return item.msg || "Validation failed.";
                }).join(" ");
            } else if (payload && payload.detail) {
                message = payload.detail;
            }
            throw new Error(message);
        }

        return payload;
    }

    function getRoleConfig() {
        const session = getSession();
        return roleConfig[normalizeRole(session && session.user ? session.user.role : "teacher")];
    }

    function getCurrentRole() {
        const session = getSession();
        return normalizeRole(session && session.user ? session.user.role : "teacher");
    }

    let mathJaxPromise = null;

    function ensureMathJax() {
        if (window.MathJax && window.MathJax.typesetPromise) {
            return Promise.resolve(window.MathJax);
        }

        if (mathJaxPromise) {
            return mathJaxPromise;
        }

        window.MathJax = {
            tex: {
                inlineMath: [["\\(", "\\)"]],
                displayMath: [["\\[", "\\]"]],
                processEscapes: true
            },
            options: {
                skipHtmlTags: ["script", "noscript", "style", "textarea", "pre"]
            },
            startup: {
                typeset: false
            }
        };

        mathJaxPromise = new Promise(function (resolve, reject) {
            const script = document.createElement("script");
            script.src = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js";
            script.async = true;
            script.onload = function () {
                resolve(window.MathJax);
            };
            script.onerror = function () {
                reject(new Error("MathJax could not be loaded."));
            };
            document.head.appendChild(script);
        });

        return mathJaxPromise;
    }

    function renderMath(root) {
        return ensureMathJax()
            .then(function (mathJax) {
                if (!mathJax || !mathJax.typesetPromise) {
                    return null;
                }
                if (mathJax.typesetClear) {
                    mathJax.typesetClear(root ? [root] : undefined);
                }
                return mathJax.typesetPromise(root ? [root] : undefined);
            })
            .catch(function () {
                return null;
            });
    }

    window.ThinkNoteApp = {
        API_BASE_URL: API_BASE_URL,
        STORAGE_KEY: STORAGE_KEY,
        roleConfig: roleConfig,
        pageAccess: pageAccess,
        getDashboardPage: getDashboardPage,
        getVideosPage: getVideosPage,
        getResultPage: getResultPage,
        getSession: getSession,
        saveSession: saveSession,
        clearSession: clearSession,
        getActiveWorkspaceId: getActiveWorkspaceId,
        setActiveWorkspaceId: setActiveWorkspaceId,
        ensureSession: ensureSession,
        getRoleConfig: getRoleConfig,
        getCurrentRole: getCurrentRole,
        syncRoleText: syncRoleText,
        setText: setText,
        apiRequest: apiRequest,
        renderMath: renderMath
    };

    document.addEventListener("DOMContentLoaded", function () {
        ensureSession();
        syncRoleText();
    });

    window.addEventListener("hashchange", function () {
        activateCurrentNav();
    });
})();

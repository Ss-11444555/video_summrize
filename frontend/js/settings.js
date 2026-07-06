(function () {
    function byId(id) {
        return document.getElementById(id);
    }

    function setFeedback(element, message, tone) {
        if (!element) {
            return;
        }
        element.textContent = message;
        element.className = "feedback-banner " + (tone || "info");
    }

    function getSession() {
        return window.ThinkNoteApp.getSession();
    }

    function saveSessionUser(user) {
        const session = getSession();
        if (!session) {
            return;
        }
        session.user = user;
        window.ThinkNoteApp.saveSession(session);
    }

    function showSettingsMenu() {
        byId("settings-menu").classList.remove("is-hidden");
        ["settings-profile-panel", "settings-delete-panel", "settings-workspace-panel"].forEach(function (id) {
            const panel = byId(id);
            if (panel) {
                panel.classList.add("is-hidden");
            }
        });
    }

    function showSettingsPanel(view) {
        byId("settings-menu").classList.add("is-hidden");
        ["settings-profile-panel", "settings-delete-panel", "settings-workspace-panel"].forEach(function (id) {
            const panel = byId(id);
            if (panel) {
                panel.classList.add("is-hidden");
            }
        });

        const target = byId("settings-" + view + "-panel");
        if (target) {
            target.classList.remove("is-hidden");
        }
    }

    function initSettings() {
        if (document.body.dataset.page !== "settings") {
            return;
        }

        const session = getSession();
        const user = session && session.user ? session.user : null;
        if (!user) {
            window.location.href = "login.html";
            return;
        }

        const isTeacher = user.role === "teacher";
        document.querySelectorAll("[data-teacher-only]").forEach(function (element) {
            element.classList.toggle("is-hidden", !isTeacher);
        });
        if (!isTeacher) {
            document.querySelectorAll("[data-teacher-only], [data-teacher-only-panel]").forEach(function (element) {
                element.remove();
            });
        }

        const fullName = byId("settings-full-name");
        const email = byId("settings-email");
        if (fullName) {
            fullName.value = user.full_name || "";
        }
        if (email) {
            email.value = user.email || "";
        }

        document.querySelectorAll("[data-settings-view]").forEach(function (button) {
            button.addEventListener("click", function () {
                showSettingsPanel(button.dataset.settingsView);
            });
        });

        document.querySelectorAll("[data-settings-back]").forEach(function (button) {
            button.addEventListener("click", showSettingsMenu);
        });

        const profileForm = byId("settings-profile-form");
        if (profileForm) {
            profileForm.addEventListener("submit", async function (event) {
                event.preventDefault();
                const feedback = byId("settings-profile-feedback");
                const submit = profileForm.querySelector("button[type='submit']");
                const payload = {
                    full_name: fullName.value.trim(),
                    email: email.value.trim(),
                    password: byId("settings-password").value
                };

                submit.disabled = true;
                setFeedback(feedback, "Updating information...", "info");
                try {
                    const updatedUser = await window.ThinkNoteApp.apiRequest("/users/me", {
                        method: "PUT",
                        body: JSON.stringify(payload)
                    });
                    saveSessionUser(updatedUser);
                    byId("settings-password").value = "";
                    setFeedback(feedback, "Information updated successfully.", "success");
                    window.setTimeout(showSettingsMenu, 700);
                } catch (error) {
                    setFeedback(feedback, error.message || "Could not update information.", "warning");
                } finally {
                    submit.disabled = false;
                }
            });
        }

        const deleteForm = byId("settings-delete-form");
        if (deleteForm) {
            deleteForm.addEventListener("submit", async function (event) {
                event.preventDefault();
                const feedback = byId("settings-delete-feedback");
                const submit = deleteForm.querySelector("button[type='submit']");
                const password = byId("settings-delete-password").value;

                submit.disabled = true;
                setFeedback(feedback, "Verifying password...", "warning");
                try {
                    await window.ThinkNoteApp.apiRequest("/users/me", {
                        method: "DELETE",
                        body: JSON.stringify({ password: password })
                    });
                    window.ThinkNoteApp.clearSession();
                    window.location.href = "login.html";
                } catch (error) {
                    setFeedback(feedback, error.message || "Could not delete account.", "warning");
                    submit.disabled = false;
                }
            });
        }
    }

    document.addEventListener("DOMContentLoaded", initSettings);
})();

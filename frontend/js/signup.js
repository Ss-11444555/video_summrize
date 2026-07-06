(function () {
    function setFeedback(text, tone) {
        const el = document.getElementById("signup-feedback");
        if (!el) return;
        el.textContent = text;
        el.className = "feedback-banner " + tone;
    }

    async function signupWithBackend(payload) {
        return await window.ThinkNoteApp.apiRequest("/auth/signup", {
            method: "POST",
            body: JSON.stringify(payload)
        });
    }

    function isValidEmail(email) {
        return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);
    }

    function isStrongEnoughPassword(password) {
        return password.length >= 8 && /[A-Za-z]/.test(password) && /\d/.test(password);
    }

    function initSignup() {
        if (document.body.dataset.page !== "signup") {
            return;
        }

        const form = document.getElementById("signup-form");
        const fullNameInput = document.getElementById("full_name");
        const emailInput = document.getElementById("email");
        const passwordInput = document.getElementById("password");
        const confirmPasswordInput = document.getElementById("confirm_password");
        const roleInput = document.getElementById("role");
        const workspaceNameInput = document.getElementById("workspace_name");
        const workspaceNameField = document.getElementById("workspace-name-field");

        function syncWorkspaceField() {
            const isTeacher = roleInput.value === "teacher";
            workspaceNameField.classList.toggle("is-hidden", !isTeacher);
            workspaceNameInput.required = isTeacher;
        }

        roleInput.addEventListener("change", syncWorkspaceField);
        syncWorkspaceField();

        form.addEventListener("submit", async function (event) {
            event.preventDefault();

            const full_name = (fullNameInput.value || "").trim();
            const email = (emailInput.value || "").trim().toLowerCase();
            const password = passwordInput.value || "";
            const confirmPassword = confirmPasswordInput.value || "";
            const role = roleInput.value;
            const workspace_name = (workspaceNameInput.value || "").trim();

            if (!full_name || !email || !password) {
                setFeedback("Please fill all fields.", "warning");
                return;
            }

            if (full_name.length < 2) {
                setFeedback("Enter your full name.", "warning");
                return;
            }

            if (!isValidEmail(email)) {
                setFeedback("Enter a valid email address.", "warning");
                return;
            }

            if (!isStrongEnoughPassword(password)) {
                setFeedback("Password must be at least 8 characters and include one letter and one number.", "warning");
                return;
            }

            if (password !== confirmPassword) {
                setFeedback("Passwords do not match.", "warning");
                return;
            }

            if (role !== "teacher" && role !== "student") {
                setFeedback("Invalid role selected.", "warning");
                return;
            }

            if (role === "teacher" && workspace_name.length < 2) {
                setFeedback("Enter the first course workspace name.", "warning");
                return;
            }

            window.ThinkNoteApp.clearSession();
            setFeedback("Creating your account...", "info");
            form.querySelector("button[type='submit']").disabled = true;

            try {
                await signupWithBackend({
                    full_name: full_name,
                    email: email,
                    password: password,
                    role: role,
                    workspace_name: role === "teacher" ? workspace_name : null
                });

                window.ThinkNoteApp.clearSession();
                setFeedback("Account created successfully. Redirecting to login...", "success");
                window.setTimeout(function () {
                    window.location.replace("login.html");
                }, 500);
            } catch (error) {
                setFeedback(error.message || "Signup failed.", "warning");
            } finally {
                form.querySelector("button[type='submit']").disabled = false;
            }
        });
    }

    document.addEventListener("DOMContentLoaded", initSignup);
})();


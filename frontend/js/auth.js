(function () {
    function setFeedback(text, tone) {
        const feedback = document.getElementById("login-feedback");
        feedback.textContent = text;
        feedback.className = "feedback-banner " + tone;
    }

    async function signIn(credentials) {
        const response = await window.ThinkNoteApp.apiRequest("/auth/login", {
            method: "POST",
            body: JSON.stringify({
                email: credentials.email,
                password: credentials.password
            })
        });

        window.ThinkNoteApp.saveSession({
            token: response.access_token,
            user: response.user
        });
    }

    function initLogin() {
        if (document.body.dataset.page !== "login") {
            return;
        }

        const form = document.getElementById("login-form");
        const emailInput = document.getElementById("email");
        const passwordInput = document.getElementById("password");

        form.addEventListener("submit", async function (event) {
            event.preventDefault();

            const email = emailInput.value.trim();
            const password = passwordInput.value.trim();

            if (!email || !password) {
                setFeedback("Enter both email and password before continuing.", "warning");
                return;
            }

            setFeedback("Signing in...", "info");

            try {
                await signIn({ email: email, password: password });
                const session = window.ThinkNoteApp.getSession();

                if (!session || !session.user || !session.user.role) {
                    setFeedback("Sign in succeeded, but the account role could not be found.", "warning");
                    return;
                }

                setFeedback("Login successful. Redirecting to dashboard...", "success");
                window.setTimeout(function () {
                    window.location.href = window.ThinkNoteApp.getDashboardPage(session.user.role);
                }, 500);
            } catch (error) {
                setFeedback(error.message || "Could not sign in. Check your account details and try again.", "warning");
            }
        });
    }

    document.addEventListener("DOMContentLoaded", initLogin);
})();

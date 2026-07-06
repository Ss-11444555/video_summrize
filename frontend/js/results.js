(function () {
    function byId(id) {
        return document.getElementById(id);
    }

    function setText(id, value) {
        const element = byId(id);
        if (element) {
            element.textContent = value;
        }
    }

    function paragraph(text) {
        const p = document.createElement("p");
        p.textContent = text;
        return p;
    }

    function asList(value) {
        if (!value) {
            return [];
        }
        return Array.isArray(value) ? value : [value];
    }

    function renderMath(root) {
        if (window.ThinkNoteApp && window.ThinkNoteApp.renderMath) {
            window.ThinkNoteApp.renderMath(root || document.body);
        }
    }

    function mathText(equation) {
        const value = String(equation || "").trim();
        if (!value) {
            return "";
        }
        if (value.indexOf("\\(") !== -1 || value.indexOf("\\[") !== -1) {
            return value;
        }
        return "\\[" + value + "\\]";
    }

    function equationSourceLabel(source) {
        const value = String(source || "").trim();
        if (value === "transcript_llm_fallback") {
            return "Inferred from transcript near this slide timestamp";
        }
        if (value === "visual_extractor") {
            return "Detected from visual equation extraction";
        }
        if (value === "fallback_failed") {
            return "Transcript fallback attempted but failed";
        }
        return "";
    }

    function formatTimestamp(seconds) {
        const total = Number(seconds || 0);
        const minutes = Math.floor(total / 60);
        const remainingSeconds = Math.floor(total % 60);
        return String(minutes).padStart(2, "0") + ":" + String(remainingSeconds).padStart(2, "0");
    }

    function formatPlayerTime(seconds) {
        const total = Number(seconds || 0);
        const hours = Math.floor(total / 3600);
        const minutes = Math.floor((total % 3600) / 60);
        const remainingSeconds = Math.floor(total % 60);
        return String(hours).padStart(2, "0") + ":" +
            String(minutes).padStart(2, "0") + ":" +
            String(remainingSeconds).padStart(2, "0") + ".00";
    }

    function shortText(text, maxLength) {
        const value = String(text || "").trim();
        if (value.length <= maxLength) {
            return value;
        }
        return value.slice(0, maxLength - 1).trim() + "...";
    }

    function conceptSearchText(concept, result) {
        return [
            String(concept || "").replace(/^#/, "").trim(),
            result && result.course_name ? result.course_name : "",
            "simple explanation examples"
        ].filter(Boolean).join(" ");
    }

    function externalConceptUrl(kind, concept, result) {
        const query = conceptSearchText(concept, result);
        const encoded = encodeURIComponent(query);
        if (kind === "google") {
            return "https://www.google.com/search?q=" + encoded;
        }
        if (kind === "youtube") {
            return "https://www.youtube.com/results?search_query=" + encoded;
        }
        if (kind === "khan") {
            return "https://www.khanacademy.org/search?page_search_query=" + encoded;
        }
        if (kind === "wikipedia") {
            return "https://en.wikipedia.org/w/index.php?search=" + encoded;
        }
        return "https://www.google.com/search?q=" + encoded;
    }

    function closeConceptMenus(exceptMenu) {
        document.querySelectorAll(".student-concept-menu").forEach(function (menu) {
            if (menu !== exceptMenu) {
                menu.setAttribute("hidden", "");
            }
        });
        document.querySelectorAll(".student-concept-chip").forEach(function (button) {
            const controls = button.getAttribute("aria-controls");
            const menu = controls ? byId(controls) : null;
            button.setAttribute("aria-expanded", String(menu && !menu.hasAttribute("hidden")));
        });
    }

    function openExternalConcept(kind, concept, result) {
        window.open(externalConceptUrl(kind, concept, result), "_blank", "noopener");
    }

    function askAiAboutConcept(concept) {
        switchStudentTab("chat");
        handleStudentChat("Explain " + concept + " from this video in simple words.");
    }

    function createConceptTag(concept, result, index) {
        const wrapper = document.createElement("span");
        wrapper.className = "student-concept-tag";

        const button = document.createElement("button");
        button.type = "button";
        button.className = "student-concept-chip";
        button.textContent = "#" + String(concept || "").split(" ").slice(0, 4).join(" ");

        const menuId = "student-concept-menu-" + String(index);
        const menu = document.createElement("div");
        menu.className = "student-concept-menu";
        menu.id = menuId;
        menu.setAttribute("hidden", "");
        button.setAttribute("aria-expanded", "false");
        button.setAttribute("aria-controls", menuId);

        [
            ["google", "Search Google"],
            ["youtube", "Watch on YouTube"],
            ["khan", "Open Khan Academy"],
            ["wikipedia", "Open Wikipedia"],
            ["ai", "Ask AI"]
        ].forEach(function (item) {
            const action = item[0];
            const label = item[1];
            const actionButton = document.createElement("button");
            actionButton.type = "button";
            actionButton.textContent = label;
            actionButton.addEventListener("click", function (event) {
                event.stopPropagation();
                closeConceptMenus();
                if (action === "ai") {
                    askAiAboutConcept(concept);
                } else {
                    openExternalConcept(action, concept, result);
                }
            });
            menu.appendChild(actionButton);
        });

        button.addEventListener("click", function (event) {
            event.stopPropagation();
            const isHidden = menu.hasAttribute("hidden");
            closeConceptMenus(menu);
            if (isHidden) {
                menu.removeAttribute("hidden");
            } else {
                menu.setAttribute("hidden", "");
            }
            button.setAttribute("aria-expanded", String(isHidden));
        });

        wrapper.appendChild(button);
        wrapper.appendChild(menu);
        return wrapper;
    }

    function appendLabeledText(container, label, text, className) {
        if (!text) {
            return;
        }
        const block = document.createElement("div");
        block.className = className || "student-moment-detail";
        const strong = document.createElement("strong");
        strong.textContent = label;
        const p = document.createElement("p");
        p.textContent = text;
        block.appendChild(strong);
        block.appendChild(p);
        container.appendChild(block);
    }

    function isUsableEquation(value) {
        const text = String(value || "").trim();
        if (!text || text.length > 220) {
            return false;
        }

        const slashCount = (text.match(/\\/g) || []).length;
        const braceCount = (text.match(/[{}]/g) || []).length;
        return slashCount <= 18 && braceCount <= 28;
    }

    function appendEquationEvidence(container, equations, source, notes) {
        const values = asList(equations).map(function (equation) {
            return String(equation || "").trim();
        }).filter(Boolean);
        if (!values.length) {
            return;
        }

        const usable = values.filter(isUsableEquation);
        const block = document.createElement("div");
        block.className = "student-moment-detail student-equation-evidence";

        const strong = document.createElement("strong");
        strong.textContent = "Equations";
        block.appendChild(strong);

        const sourceLabel = equationSourceLabel(source);
        if (sourceLabel) {
            const sourceText = document.createElement("p");
            sourceText.className = "student-equation-source";
            sourceText.textContent = sourceLabel;
            if (notes && source === "transcript_llm_fallback") {
                sourceText.title = String(notes);
            }
            block.appendChild(sourceText);
        }

        if (!usable.length) {
            const p = document.createElement("p");
            p.textContent = "Equation OCR returned noisy LaTeX, so it is not shown here.";
            block.appendChild(p);
        } else {
            usable.slice(0, 4).forEach(function (equation) {
                const formula = document.createElement("div");
                formula.className = "student-equation-render";
                formula.textContent = mathText(equation);
                block.appendChild(formula);
            });
        }

        container.appendChild(block);
    }

    function appendFrameEvidence(container, item, label) {
        const visualType = item.visual_type ? String(item.visual_type).replace(/_/g, " ") : "";
        const evidenceParts = [
            visualType ? "Visual type: " + visualType : "",
            item.ocr_text ? "Detected text: " + shortText(item.ocr_text, 220) : "",
            item.caption_text ? "Frame caption: " + shortText(item.caption_text, 260) : ""
        ].filter(Boolean);

        appendLabeledText(
            container,
            label,
            evidenceParts.join(" | ") || "No frame evidence stored.",
            "student-moment-detail student-moment-evidence"
        );
        appendEquationEvidence(container, item.equations, item.equation_source, item.equation_fallback_notes);
    }

    const chatStopWords = new Set([
        "about", "after", "again", "also", "and", "are", "can", "could", "does", "for", "from",
        "give", "go", "how", "into", "jump", "lecture", "me", "move", "part", "please", "show",
        "take", "tell", "that", "the", "there", "this", "time", "to", "video", "what", "when",
        "where", "why", "with", "you"
    ]);

    function normalizeSearchText(value) {
        return String(value || "").toLowerCase().replace(/[^a-z0-9\s]+/g, " ").replace(/\s+/g, " ").trim();
    }

    function stemToken(token) {
        return token.replace(/(ing|ed|es|s)$/g, "");
    }

    function keywords(value) {
        return normalizeSearchText(value).split(" ").map(stemToken).filter(function (token) {
            return token.length > 2 && !chatStopWords.has(token);
        });
    }

    function uniqueList(values) {
        return values.filter(function (value, index) {
            return value && values.indexOf(value) === index;
        });
    }

    function isNavigationQuestion(message) {
        const text = normalizeSearchText(message);
        return /\b(go|jump|move|take|seek|find|show|where)\b/.test(text) ||
            text.indexOf("which part") !== -1 ||
            text.indexOf("what time") !== -1;
    }

    function extractNavigationTarget(message) {
        return normalizeSearchText(message)
            .replace(/\b(can|could|please|you|me|the|video|lecture)\b/g, " ")
            .replace(/\b(go|jump|move|take|seek|find|show)\b/g, " ")
            .replace(/\b(to|where|is|are|does|do|part|time|explain|about)\b/g, " ")
            .replace(/\s+/g, " ")
            .trim();
    }

    function buildStudyMoments(result) {
        const captions = asList(result.captions).filter(Boolean);
        const segments = asList(result.transcript_segments).filter(Boolean);
        const moments = [];

        captions.forEach(function (caption) {
            const transcriptText = caption.transcript_text || "";
            moments.push({
                timestamp: Number(caption.timestamp_seconds || caption.transcript_start_seconds || 0),
                title: "Caption at " + formatTimestamp(caption.timestamp_seconds),
                caption: caption.caption_text || "",
                transcript: transcriptText,
                text: [caption.caption_text, transcriptText].filter(Boolean).join(" ")
            });
        });

        segments.forEach(function (segment) {
            moments.push({
                timestamp: Number(segment.start_seconds || 0),
                title: "Transcript at " + formatTimestamp(segment.start_seconds),
                caption: "",
                transcript: segment.text || "",
                text: segment.text || ""
            });
        });

        return moments.filter(function (moment) {
            return moment.text.trim();
        });
    }

    function scoreMoment(moment, queryText, queryTokens) {
        const normalizedMoment = normalizeSearchText(moment.text);
        const normalizedQuery = normalizeSearchText(queryText);
        let score = 0;

        if (normalizedQuery && normalizedMoment.indexOf(normalizedQuery) !== -1) {
            score += 18;
        }

        queryTokens.forEach(function (token) {
            const tokenPattern = new RegExp("\\b" + token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
            if (tokenPattern.test(normalizedMoment)) {
                score += 4;
            } else if (normalizedMoment.indexOf(token) !== -1) {
                score += 2;
            }
        });

        if (moment.caption && score > 0) {
            score += 1;
        }
        return score;
    }

    function findBestStudyMoment(result, message) {
        const target = extractNavigationTarget(message) || message;
        const queryTokens = uniqueList(keywords(target));
        const moments = buildStudyMoments(result);

        if (!queryTokens.length || !moments.length) {
            return null;
        }

        const ranked = moments.map(function (moment) {
            return {
                moment: moment,
                score: scoreMoment(moment, target, queryTokens)
            };
        }).filter(function (item) {
            return item.score > 0;
        }).sort(function (first, second) {
            return second.score - first.score;
        });

        return ranked.length ? ranked[0].moment : null;
    }

    function switchStudentTab(tabName) {
        document.querySelectorAll("[data-study-tab]").forEach(function (item) {
            item.classList.toggle("active", item.dataset.studyTab === tabName);
        });
        document.querySelectorAll("[data-study-panel]").forEach(function (panel) {
            panel.classList.toggle("active", panel.dataset.studyPanel === tabName);
        });
        const activeButton = document.querySelector("[data-study-tab='" + tabName + "']");
        setText("student-panel-title", activeButton ? activeButton.textContent.trim() : "Chat");
    }

    function seekStudentVideo(seconds) {
        const video = byId("student-result-video");
        const targetSeconds = Math.max(Number(seconds || 0), 0);
        if (!video) {
            return;
        }

        video.currentTime = targetSeconds;
        setText("student-current-time", formatPlayerTime(targetSeconds));
        const progress = byId("student-progress");
        if (progress && video.duration) {
            progress.value = String(Math.floor((targetSeconds / video.duration) * 1000));
        }
    }

    function renderVideoTranscript(result) {
        const transcriptList = byId("student-video-transcript-list");
        if (!transcriptList) {
            return;
        }

        transcriptList.innerHTML = "";
        const segments = asList(result.transcript_segments).filter(Boolean);
        if (segments.length) {
            segments.forEach(function (segment) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "student-transcript-segment";
                button.innerHTML =
                    "<span>" + formatTimestamp(segment.start_seconds) + "</span><p></p>";
                button.querySelector("p").textContent = segment.text || "";
                button.addEventListener("click", function () {
                    seekStudentVideo(segment.start_seconds || 0);
                });
                transcriptList.appendChild(button);
            });
            return;
        }

        const fallback = document.createElement("p");
        fallback.className = "student-transcript-fallback";
        fallback.textContent = result.cleaned_transcript || result.transcript || "Transcript is not available yet.";
        transcriptList.appendChild(fallback);
    }

    function renderMainTranscript(result) {
        const transcript = byId("student-transcript-text");
        if (!transcript) {
            return;
        }

        transcript.innerHTML = "";
        transcript.classList.add("student-transcript-reader");
        const segments = asList(result.transcript_segments).filter(Boolean);
        if (!segments.length) {
            const fallback = document.createElement("p");
            fallback.className = "student-transcript-fallback";
            fallback.textContent = result.cleaned_transcript || result.transcript || "Transcript not available yet.";
            transcript.appendChild(fallback);
            return;
        }

        const firstStart = Number(segments[0].start_seconds || 0);
        const lastSegment = segments[segments.length - 1];
        const lastEnd = Number(lastSegment.end_seconds || lastSegment.start_seconds || firstStart);

        const header = document.createElement("div");
        header.className = "student-transcript-summary";
        header.innerHTML =
            "<div><strong>Timed Transcript</strong><span>" +
            segments.length + " segments from " + formatTimestamp(firstStart) + " to " + formatTimestamp(lastEnd) +
            "</span></div>";
        transcript.appendChild(header);

        const list = document.createElement("div");
        list.className = "student-transcript-reader-list";
        segments.forEach(function (segment, index) {
            const segmentButton = document.createElement("button");
            segmentButton.type = "button";
            segmentButton.className = "student-transcript-reader-segment";
            segmentButton.setAttribute("aria-label", "Jump to transcript segment at " + formatTimestamp(segment.start_seconds));

            const time = document.createElement("span");
            time.className = "student-transcript-reader-time";
            time.textContent = formatTimestamp(segment.start_seconds);

            const body = document.createElement("p");
            body.textContent = segment.text || "";

            const indexBadge = document.createElement("small");
            indexBadge.textContent = String(index + 1).padStart(2, "0");

            segmentButton.appendChild(time);
            segmentButton.appendChild(body);
            segmentButton.appendChild(indexBadge);
            segmentButton.addEventListener("click", function () {
                seekStudentVideo(segment.start_seconds || 0);
            });
            list.appendChild(segmentButton);
        });

        transcript.appendChild(list);
    }

    function setQualityNote(value) {
        const note = byId("student-quality-note");
        if (!note) {
            return;
        }
        if (String(value).startsWith("message:")) {
            note.textContent = String(value).slice(8);
            return;
        }
        if (value === "auto") {
            note.textContent = "Auto uses the uploaded video stream.";
        } else {
            note.textContent = String(value) + "p stream selected.";
        }
    }

    function getQualityLabel(value) {
        return value === "auto" ? "Auto" : String(value) + "p";
    }

    function getActiveTranscriptSegment(result, currentTime) {
        const segments = asList(result && result.transcript_segments).filter(Boolean);
        if (!segments.length) {
            return null;
        }

        return segments.find(function (segment) {
            const start = Number(segment.start_seconds || 0);
            const end = Number(segment.end_seconds || start);
            return currentTime >= start && currentTime < end;
        }) || null;
    }

    function updateVideoCaption() {
        const caption = byId("student-video-caption");
        const video = byId("student-result-video");
        const result = window.ThinkNoteStudentResult;
        if (!caption || !video || !result) {
            return;
        }

        if (caption.dataset.enabled === "false") {
            caption.textContent = "";
            caption.classList.remove("is-visible");
            return;
        }

        const segment = getActiveTranscriptSegment(result, video.currentTime || 0);
        const text = segment && segment.text ? segment.text.trim() : "";
        caption.textContent = text;
        caption.classList.toggle("is-visible", Boolean(text));
    }

    function createChatMessage(role, text, moment) {
        const card = document.createElement("div");
        card.className = "student-chat-card student-chat-card-" + role;

        const label = document.createElement("strong");
        label.textContent = role === "user" ? "You" : "Study agent";
        const body = document.createElement("p");
        body.textContent = text;

        card.appendChild(label);
        card.appendChild(body);

        if (moment) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "student-chat-jump";
            button.textContent = "Jump to " + formatTimestamp(moment.timestamp);
            button.addEventListener("click", function () {
                seekStudentVideo(moment.timestamp);
            });
            card.appendChild(button);
        }

        return card;
    }

    function appendChatMessage(role, text, moment) {
        const list = byId("student-chat-list");
        if (!list) {
            return;
        }
        list.appendChild(createChatMessage(role, text, moment));
        list.scrollTop = list.scrollHeight;
        renderMath(list);
    }

    async function handleStudentChat(message) {
        const result = window.ThinkNoteStudentResult;
        if (!result) {
            appendChatMessage("agent", "Open a processed video first, then ask about that video.");
            return;
        }

        const trimmedMessage = String(message || "").trim();
        if (!trimmedMessage) {
            return;
        }

        appendChatMessage("user", trimmedMessage);

        try {
            const response = await window.ThinkNoteApp.apiRequest("/results/" + result.video_id + "/chat", {
                method: "POST",
                body: JSON.stringify({ message: trimmedMessage })
            });
            const timestamp = response.timestamp_seconds;
            const moment = timestamp !== null && timestamp !== undefined
                ? { timestamp: Number(timestamp) }
                : null;
            if (response.should_seek && moment) {
                seekStudentVideo(moment.timestamp);
            }
            appendChatMessage("agent", response.answer || "I could not answer from this video.", moment);
        } catch (error) {
            const bestMoment = findBestStudyMoment(result, trimmedMessage);
            if (bestMoment) {
                appendChatMessage(
                    "agent",
                    "The LLM chat endpoint is not available, so I used local video search. " +
                    (bestMoment.transcript || bestMoment.caption).slice(0, 260),
                    bestMoment
                );
            } else {
                appendChatMessage("agent", error.message || "The video chat agent is not available right now.");
            }
        }
    }

    function renderStudyChat(result) {
        const list = byId("student-chat-list");
        if (!list) {
            return;
        }

        list.innerHTML = "";
        const title = result.title || "this video";
        appendChatMessage(
            "agent",
            "Ask me about " + title + ". I can answer from this video's summary, transcript, and picture captions, or jump to a matching moment."
        );

        const summary = result.structured_summary || {};
        const concepts = asList(summary.key_concepts).filter(Boolean);
        const suggestions = [
            "What is the main idea?",
            concepts.length ? "Go to " + concepts[0] : "Go to the first important concept",
            "Find the part I should revise"
        ];
        const suggestionRow = document.createElement("div");
        suggestionRow.className = "student-chat-suggestions";
        suggestions.forEach(function (suggestion) {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = suggestion;
            button.addEventListener("click", function () {
                handleStudentChat(suggestion);
            });
            suggestionRow.appendChild(button);
        });
        list.appendChild(suggestionRow);
    }

    function renderPlainBlock(id, text) {
        const element = byId(id);
        if (!element) {
            return;
        }
        element.innerHTML = "";
        element.appendChild(paragraph(text));
    }

    function renderList(id, values, emptyText) {
        const element = byId(id);
        if (!element) {
            return;
        }

        const items = asList(values).filter(Boolean);
        element.innerHTML = "";

        if (!items.length) {
            element.innerHTML = "<li>" + emptyText + "</li>";
            return;
        }

        items.forEach(function (item) {
            const li = document.createElement("li");
            li.textContent = item;
            element.appendChild(li);
        });
    }

    function renderStructuredSummary(summaryData) {
        const summaryList = byId("result-summary-list");
        if (!summaryList) {
            return;
        }

        summaryList.innerHTML = "";

        if (!summaryData || typeof summaryData !== "object") {
            summaryList.innerHTML = "<li>No structured summary is available yet.</li>";
            return;
        }

        [
            ["main_topic", "Main Topic"],
            ["key_concepts", "Key Concepts"],
            ["important_points", "Important Points"],
            ["examples", "Examples"],
            ["revision_notes", "Revision Notes"]
        ].forEach(function (pair) {
            const key = pair[0];
            const label = pair[1];
            const value = summaryData[key];
            if (!value) {
                return;
            }

            const li = document.createElement("li");
            const renderedValue = Array.isArray(value) ? value.join(", ") : value;
            li.innerHTML = "<strong>" + label + ":</strong> " + renderedValue;
            summaryList.appendChild(li);
        });
    }

    function getRougeInterpretation(value) {
        const percentage = Math.round(Math.max(0, Math.min(1, Number(value) || 0)) * 100);

        if (percentage >= 75) {
            return { percentage: percentage, label: "Excellent", tone: "excellent" };
        }
        if (percentage >= 50) {
            return { percentage: percentage, label: "Good", tone: "good" };
        }
        if (percentage >= 25) {
            return { percentage: percentage, label: "Moderate", tone: "moderate" };
        }
        return { percentage: percentage, label: "Low", tone: "low" };
    }

    function renderEvaluation(result) {
        const rougeList = byId("result-rouge-list");
        const scoreChips = byId("result-score-chips");

        if (scoreChips) {
            scoreChips.innerHTML = '<span class="status-pill success">Backend Result</span>';
        }

        if (!rougeList) {
            return;
        }

        rougeList.innerHTML = "";
        if (!result.evaluation) {
            rougeList.innerHTML = "<div class='split-stat'><div><strong>ROUGE</strong><p>Evaluation is not available yet.</p></div><span>N/A</span></div>";
            return;
        }

        const metrics = [
            { label: "ROUGE-1", description: "Matching individual words", value: result.evaluation.rouge_1 },
            { label: "ROUGE-2", description: "Matching two-word phrases", value: result.evaluation.rouge_2 },
            { label: "ROUGE-L", description: "Matching word order and sentence structure", value: result.evaluation.rouge_l }
        ].filter(function (item) {
            return item.value !== null && item.value !== undefined;
        });

        if (!metrics.length) {
            rougeList.innerHTML = "<div class='split-stat'><div><strong>ROUGE</strong><p>Evaluation scores are not available yet.</p></div><span>N/A</span></div>";
            return;
        }

        const interpretations = metrics.map(function (item) {
            return getRougeInterpretation(item.value);
        });
        const averagePercentage = Math.round(
            interpretations.reduce(function (total, item) {
                return total + item.percentage;
            }, 0) / interpretations.length
        );
        const overall = getRougeInterpretation(averagePercentage / 100);
        const overallCard = document.createElement("div");
        overallCard.className = "rouge-overall rouge-tone-" + overall.tone;
        overallCard.innerHTML =
            "<span class='eyebrow'>Overall Text Similarity</span>" +
            "<div class='rouge-overall-heading'><strong>" + averagePercentage + "%</strong>" +
            "<span class='rouge-quality-label'>" + overall.label + "</span></div>" +
            "<p>The AI summary has <strong>" + overall.label.toLowerCase() +
            " wording similarity</strong> to the teacher reference summary.</p>";
        rougeList.appendChild(overallCard);

        metrics.forEach(function (item, index) {
            const interpretation = interpretations[index];
            const wrapper = document.createElement("div");
            wrapper.className = "rouge-metric rouge-tone-" + interpretation.tone;
            wrapper.innerHTML =
                "<div class='rouge-metric-heading'><div><strong>" + item.label + "</strong><p>" +
                item.description + "</p></div><div class='rouge-metric-score'><strong>" +
                interpretation.percentage + "%</strong><span>" + interpretation.label + "</span></div></div>" +
                "<div class='rouge-progress' aria-label='" + item.label + " " + interpretation.percentage +
                " percent'><span style='width: " + interpretation.percentage + "%;'></span></div>";
            rougeList.appendChild(wrapper);

            if (scoreChips) {
                const chip = document.createElement("span");
                chip.className = "chip";
                chip.textContent = item.label + " " + interpretation.percentage + "%";
                scoreChips.appendChild(chip);
            }
        });

        const note = document.createElement("p");
        note.className = "rouge-explanation";
        note.innerHTML =
            "<strong>How to read this:</strong> Higher percentages mean more wording overlaps with the teacher reference. " +
            "ROUGE does not fully measure meaning, so a low score can still occur when the AI explains the same ideas using different words.";
        rougeList.appendChild(note);
    }

    function renderStudentStudy(result) {
        const summary = result.structured_summary || {};
        setText("result-main-topic", summary.main_topic || result.course_name || "Lecture summary");
        renderPlainBlock("result-student-summary", result.summary_text || "Summary is not available yet.");
        renderList("result-key-concepts", summary.key_concepts, "No key concepts are available yet.");
        renderList("result-important-points", summary.important_points, "No important points are available yet.");
        renderList("result-examples", summary.examples, "No examples are available yet.");
        renderList("result-revision-notes", summary.revision_notes, "No revision notes are available yet.");
    }

    function clearAndFill(element, emptyText, values, renderItem) {
        if (!element) {
            return;
        }

        element.innerHTML = "";
        const items = asList(values).filter(Boolean);
        if (!items.length) {
            const empty = document.createElement("div");
            empty.className = "student-chat-card";
            empty.textContent = emptyText;
            element.appendChild(empty);
            return;
        }

        items.forEach(function (item, index) {
            element.appendChild(renderItem(item, index));
        });
    }

    function renderStudentSlideSummaries(result) {
        const slideSummaries = asList(result.slide_summaries).filter(Boolean);

        clearAndFill(
            byId("student-slide-summary-list"),
            "No slide summaries are available yet.",
            slideSummaries,
            function (slide) {
                const item = document.createElement("div");
                item.className = "student-moment student-slide-summary";

                const time = document.createElement("strong");
                time.className = "student-moment-time";
                time.textContent = formatTimestamp(slide.start_seconds) + " - " + formatTimestamp(slide.end_seconds);
                time.appendChild(document.createElement("span"));

                const card = document.createElement("div");
                card.className = "student-moment-card student-slide-summary-card";

                const heading = document.createElement("h3");
                heading.textContent = slide.topic || "Slide " + String(slide.frame_index || "");
                card.appendChild(heading);

                appendLabeledText(
                    card,
                    "Slide summary",
                    slide.summary_text || "No summary generated for this slide interval."
                );

                const keyPoints = asList(slide.key_points).filter(Boolean);
                appendLabeledText(
                    card,
                    "Key points",
                    keyPoints.length ? keyPoints.join(" | ") : "No key points generated for this slide interval."
                );

                appendEquationEvidence(
                    card,
                    slide.equations,
                    slide.equation_source,
                    slide.equation_fallback_notes
                );
                appendLabeledText(
                    card,
                    "Transcript in this slide range",
                    shortText(slide.transcript_text || slide.transcript_excerpt || "No transcript found for this slide range.", 520),
                    "student-moment-detail student-moment-transcript"
                );

                item.appendChild(time);
                item.appendChild(card);
                return item;
            }
        );
    }

    function shortNodeText(text, maxLength) {
        return shortText(String(text || "").replace(/\s+/g, " "), maxLength);
    }

    function createMindMapChip(text, className) {
        const chip = document.createElement("span");
        chip.className = className || "student-mindmap-chip";
        chip.textContent = shortNodeText(text, 72);
        return chip;
    }

    function createMindMapNode(label, detail, options) {
        const config = options || {};
        const node = config.timestamp !== undefined && config.timestamp !== null
            ? document.createElement("button")
            : document.createElement("div");
        node.className = "student-mindmap-node " + (config.className || "");
        if (node.tagName === "BUTTON") {
            node.type = "button";
            node.addEventListener("click", function () {
                seekStudentVideo(config.timestamp);
            });
        }

        const title = document.createElement("strong");
        title.textContent = shortNodeText(label, config.titleLength || 82);
        node.appendChild(title);

        if (detail) {
            const p = document.createElement("p");
            p.textContent = shortNodeText(detail, config.detailLength || 140);
            node.appendChild(p);
        }

        if (config.meta) {
            const meta = document.createElement("span");
            meta.className = "student-mindmap-meta";
            meta.textContent = config.meta;
            node.appendChild(meta);
        }

        return node;
    }

    function buildMindMapBranches(summary, result) {
        const detailedNotes = asList(summary.detailed_topic_notes).filter(Boolean);
        const concepts = asList(summary.key_concepts).filter(Boolean);
        const importantPoints = asList(summary.important_points).filter(Boolean);
        const examples = asList(summary.examples).filter(Boolean);
        const definitions = asList(summary.definitions_and_terms).filter(Boolean);
        const visuals = asList(summary.visual_and_equation_notes).filter(Boolean);

        let branches = detailedNotes.slice(0, 4).map(function (note) {
            const details = asList(note.important_details).filter(Boolean).slice(0, 2);
            const examplesOrVisuals = asList(note.examples_or_visuals).filter(Boolean).slice(0, 1);
            return {
                title: note.topic_title || "Topic",
                detail: note.explanation || note.student_takeaway || "",
                chips: details.concat(examplesOrVisuals),
                takeaway: note.student_takeaway || ""
            };
        });

        if (!branches.length) {
            branches = concepts.slice(0, 4).map(function (concept, index) {
                return {
                    title: concept,
                    detail: importantPoints[index] || examples[index] || "",
                    chips: [definitions[index], visuals[index]].filter(Boolean),
                    takeaway: ""
                };
            });
        }

        if (!branches.length && result.summary_text) {
            branches = [{
                title: summary.main_topic || result.title || "Lecture topic",
                detail: result.summary_text,
                chips: importantPoints.slice(0, 3),
                takeaway: summary.final_understanding || ""
            }];
        }

        return branches;
    }

    function renderMindMap(result) {
        const container = byId("student-mindmap-list");
        if (!container) {
            return;
        }

        const summary = result.structured_summary || {};
        const branches = buildMindMapBranches(summary, result);
        const slideSummaries = asList(result.slide_summaries).filter(Boolean).slice(0, 5);

        container.innerHTML = "";
        if (!branches.length) {
            const empty = document.createElement("div");
            empty.className = "student-chat-card";
            empty.textContent = "No mindmap points are available yet.";
            container.appendChild(empty);
            return;
        }

        const map = document.createElement("div");
        map.className = "student-mindmap-canvas";

        const header = document.createElement("div");
        header.className = "student-mindmap-header";
        header.innerHTML = "<strong>Concept Map</strong><span>Main idea, connected concepts, and video moments</span>";
        map.appendChild(header);

        const center = createMindMapNode(
            summary.main_topic || result.title || "Lecture",
            result.summary_text || summary.final_understanding || "",
            { className: "student-mindmap-center", meta: "Main topic" }
        );
        map.appendChild(center);

        const branchGrid = document.createElement("div");
        branchGrid.className = "student-mindmap-branches";
        branches.forEach(function (branch, index) {
            const branchCard = document.createElement("section");
            branchCard.className = "student-mindmap-branch";
            branchCard.appendChild(
                createMindMapNode(
                    branch.title,
                    branch.detail,
                    {
                        className: "student-mindmap-topic",
                        meta: "Concept " + String(index + 1),
                        titleLength: 78,
                        detailLength: 150
                    }
                )
            );

            const chipList = document.createElement("div");
            chipList.className = "student-mindmap-chip-list";
            asList(branch.chips).filter(Boolean).slice(0, 3).forEach(function (chip, chipIndex) {
                const point = document.createElement("div");
                point.className = "student-mindmap-point";
                const number = document.createElement("span");
                number.textContent = String(chipIndex + 1);
                const text = document.createElement("p");
                text.textContent = shortNodeText(chip, 105);
                point.appendChild(number);
                point.appendChild(text);
                chipList.appendChild(point);
            });
            if (branch.takeaway) {
                chipList.appendChild(createMindMapChip(branch.takeaway, "student-mindmap-chip student-mindmap-takeaway"));
            }
            if (chipList.children.length) {
                branchCard.appendChild(chipList);
            }
            branchGrid.appendChild(branchCard);
        });
        map.appendChild(branchGrid);

        if (slideSummaries.length) {
            const timeline = document.createElement("section");
            timeline.className = "student-mindmap-timeline";
            const heading = document.createElement("strong");
            heading.textContent = "Video Path";
            timeline.appendChild(heading);
            slideSummaries.forEach(function (slide) {
                timeline.appendChild(
                    createMindMapNode(
                        slide.topic || "Slide " + String(slide.frame_index || ""),
                        slide.summary_text,
                        {
                            className: "student-mindmap-slide",
                            timestamp: Number(slide.start_seconds || 0),
                            meta: formatTimestamp(slide.start_seconds),
                            titleLength: 70,
                            detailLength: 105
                        }
                    )
                );
            });
            map.appendChild(timeline);
        }

        container.appendChild(map);
    }

    function renderStudentSummaryWorkspace(result) {
        if (document.body.dataset.page !== "student-results") {
            return;
        }

        window.ThinkNoteStudentResult = result;

        const summary = result.structured_summary || {};
        const concepts = asList(summary.key_concepts).filter(Boolean);
        const importantPoints = asList(summary.important_points).filter(Boolean);
        const examples = asList(summary.examples).filter(Boolean);
        const revisionNotes = asList(summary.revision_notes).filter(Boolean);
        const captions = asList(result.captions).filter(Boolean);
        const backToCourse = document.getElementById("student-back-to-course");
        const selectedCourse = courseFromQuery() || result.course_name || "";

        setText("student-panel-title", "Summary");
        setText("student-video-title", result.title);
        setText("result-course-name", result.course_name);
        setText("student-result-context-label", selectedCourse ? "Course" : "Tools");
        if (backToCourse) {
            backToCourse.href = "student-videos.html" + (selectedCourse ? "?course=" + encodeURIComponent(selectedCourse) : "");
        }

        const overview = byId("student-summary-overview");
        if (overview) {
            overview.textContent = result.summary_text || "Summary is not available yet.";
        }

        const tags = byId("student-summary-tags");
        if (tags) {
            tags.innerHTML = "";
            const tagValues = concepts.concat(importantPoints).slice(0, 5);
            (tagValues.length ? tagValues : [result.course_name || "Lecture"]).forEach(function (tag, index) {
                tags.appendChild(createConceptTag(tag, result, index));
            });
        }

        renderStudentSlideSummaries(result);

        renderMainTranscript(result);
        renderVideoTranscript(result);

        renderMindMap(result);

        renderStudyChat(result);

        updateStudentVideo(result.video_id);
    }

    function buildStudentVideoUrl(videoId, quality) {
        const session = window.ThinkNoteApp.getSession();
        if (!session || !session.token || !videoId) {
            return "";
        }

        const selectedQuality = String(quality || "auto").toLowerCase();
        let url = window.ThinkNoteApp.API_BASE_URL +
            "/videos/" + videoId + "/stream?access_token=" + encodeURIComponent(session.token);
        if (selectedQuality !== "auto") {
            url += "&quality=" + encodeURIComponent(selectedQuality);
        }
        return url;
    }

    function updateStudentVideo(videoId) {
        const video = byId("student-result-video");
        if (!video || !videoId) {
            return;
        }

        const qualitySelect = byId("student-quality-select");
        const selectedQuality = qualitySelect ? String(qualitySelect.value || "auto").toLowerCase() : "auto";
        const videoUrl = buildStudentVideoUrl(videoId, selectedQuality);
        if (!videoUrl) {
            return;
        }

        if (qualitySelect) {
            qualitySelect.dataset.activeQuality = selectedQuality;
            qualitySelect.disabled = false;
        }
        video.src = videoUrl;
        video.load();
        setText("student-current-time", "00:00:00.00");
        setText("student-duration-time", "00:00:00.00");
        setText("student-video-caption", "");
        const caption = byId("student-video-caption");
        if (caption) {
            caption.classList.remove("is-visible");
        }
        const progress = byId("student-progress");
        if (progress) {
            progress.value = "0";
        }
    }

    function changeStudentVideoQuality(quality) {
        const video = byId("student-result-video");
        const result = window.ThinkNoteStudentResult;
        if (!video || !result) {
            return;
        }

        const nextUrl = buildStudentVideoUrl(result.video_id, quality);
        if (!nextUrl || video.src === nextUrl) {
            return;
        }

        const currentTime = video.currentTime || 0;
        const wasPlaying = !video.paused;
        const qualitySelect = byId("student-quality-select");
        const previousUrl = video.src;
        const previousQuality = qualitySelect ? qualitySelect.dataset.activeQuality || "auto" : "auto";
        const selectedQuality = String(quality || "auto").toLowerCase();
        const probe = document.createElement("video");

        if (selectedQuality === previousQuality) {
            return;
        }

        if (qualitySelect) {
            qualitySelect.disabled = true;
        }
        setQualityNote(selectedQuality === "auto" ? "auto" : "message:Preparing " + selectedQuality + "p stream...");

        probe.preload = "metadata";
        probe.src = nextUrl;
        probe.addEventListener("loadedmetadata", function restorePlayback() {
            video.addEventListener("loadedmetadata", function syncReplacement() {
                video.removeEventListener("loadedmetadata", syncReplacement);
                video.currentTime = Math.min(currentTime, video.duration || currentTime);
                setText("student-duration-time", formatPlayerTime(video.duration));
                if (wasPlaying) {
                    video.play();
                }
            });
            video.src = nextUrl;
            video.load();
            if (qualitySelect) {
                qualitySelect.disabled = false;
                qualitySelect.dataset.activeQuality = selectedQuality;
            }
            setQualityNote(selectedQuality);
        });
        probe.addEventListener("error", function () {
            if (qualitySelect) {
                qualitySelect.disabled = false;
                qualitySelect.value = previousQuality;
            }
            if (video.src !== previousUrl) {
                video.src = previousUrl;
            }
            setQualityNote(
                "message:" +
                getQualityLabel(selectedQuality) +
                " is not ready. Still using " +
                getQualityLabel(previousQuality) +
                "."
            );
        });
        probe.load();
    }

    function initStudentSummaryControls() {
        if (document.body.dataset.page !== "student-results") {
            return;
        }
        if (document.body.dataset.conceptMenuWired !== "true") {
            document.body.dataset.conceptMenuWired = "true";
            document.addEventListener("click", function () {
                closeConceptMenus();
            });
        }

        document.querySelectorAll("[data-study-tab]").forEach(function (button) {
            button.addEventListener("click", function () {
                switchStudentTab(button.dataset.studyTab);
            });
        });

        const video = byId("student-result-video");
        const playToggle = byId("student-play-toggle");
        const playOverlay = byId("student-play-overlay");
        const progress = byId("student-progress");
        const muteToggle = byId("student-mute-toggle");
        const fullscreenToggle = byId("student-fullscreen-toggle");
        const settingsToggle = byId("student-settings-toggle");
        const playerSettings = byId("student-player-settings");
        const downloadButton = byId("student-download-summary");
        const shareButton = byId("student-share-summary");
        const chatForm = byId("student-chat-form");
        const chatInput = byId("student-chat-input");
        const speedSelect = byId("student-speed-select");
        const qualitySelect = byId("student-quality-select");
        const captionToggle = byId("student-caption-toggle");
        const transcriptToggle = byId("student-transcript-toggle");
        const videoTranscript = byId("student-video-transcript");
        const videoCaption = byId("student-video-caption");

        function syncPlayLabel() {
            const label = video && !video.paused ? "Pause" : "Play";
            if (playToggle) {
                playToggle.textContent = label;
            }
            if (playOverlay) {
                playOverlay.textContent = label;
                playOverlay.classList.toggle("is-hidden", video && !video.paused);
            }
        }

        function syncMuteLabel() {
            if (muteToggle && video) {
                muteToggle.textContent = video.muted || video.volume === 0 ? "Mute" : "Vol";
            }
        }

        function syncCaptionToggle() {
            if (!captionToggle || !videoCaption) {
                return;
            }
            const isEnabled = videoCaption.dataset.enabled !== "false";
            captionToggle.textContent = isEnabled ? "Captions On" : "Captions Off";
            captionToggle.setAttribute("aria-pressed", String(isEnabled));
        }

        function getFullscreenElement() {
            return document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement;
        }

        function syncFullscreenLabel() {
            if (!fullscreenToggle) {
                return;
            }
            const isFullscreen = Boolean(getFullscreenElement());
            fullscreenToggle.textContent = isFullscreen ? "Exit" : "Full";
            fullscreenToggle.setAttribute("aria-label", isFullscreen ? "Exit fullscreen" : "Open fullscreen");
        }

        function toggleFullscreen() {
            const shell = video ? video.closest(".student-video-shell") : null;
            if (!shell) {
                return;
            }

            if (getFullscreenElement()) {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                } else if (document.msExitFullscreen) {
                    document.msExitFullscreen();
                }
                return;
            }

            if (shell.requestFullscreen) {
                shell.requestFullscreen();
            } else if (shell.webkitRequestFullscreen) {
                shell.webkitRequestFullscreen();
            } else if (shell.msRequestFullscreen) {
                shell.msRequestFullscreen();
            }
        }

        function closePlayerSettings() {
            if (playerSettings && settingsToggle) {
                playerSettings.setAttribute("hidden", "");
                settingsToggle.setAttribute("aria-expanded", "false");
            }
        }

        function togglePlayback() {
            if (!video) {
                return;
            }
            if (video.paused) {
                video.play();
            } else {
                video.pause();
            }
        }

        if (playToggle) {
            playToggle.addEventListener("click", togglePlayback);
        }
        if (playOverlay) {
            playOverlay.addEventListener("click", togglePlayback);
        }
        if (muteToggle && video) {
            muteToggle.addEventListener("click", function () {
                video.muted = !video.muted;
                syncMuteLabel();
            });
            syncMuteLabel();
        }
        if (fullscreenToggle) {
            fullscreenToggle.addEventListener("click", toggleFullscreen);
            document.addEventListener("fullscreenchange", syncFullscreenLabel);
            document.addEventListener("webkitfullscreenchange", syncFullscreenLabel);
            document.addEventListener("MSFullscreenChange", syncFullscreenLabel);
            syncFullscreenLabel();
        }
        if (settingsToggle && playerSettings) {
            settingsToggle.addEventListener("click", function (event) {
                event.stopPropagation();
                const isHidden = playerSettings.hasAttribute("hidden");
                if (isHidden) {
                    playerSettings.removeAttribute("hidden");
                } else {
                    playerSettings.setAttribute("hidden", "");
                }
                settingsToggle.setAttribute("aria-expanded", String(isHidden));
            });
            playerSettings.addEventListener("click", function (event) {
                event.stopPropagation();
            });
            document.addEventListener("click", closePlayerSettings);
        }
        if (video) {
            video.addEventListener("loadedmetadata", function () {
                setText("student-duration-time", formatPlayerTime(video.duration));
                updateVideoCaption();
                syncPlayLabel();
                syncMuteLabel();
            });
            video.addEventListener("timeupdate", function () {
                setText("student-current-time", formatPlayerTime(video.currentTime));
                updateVideoCaption();
                if (progress && video.duration) {
                    progress.value = String(Math.floor((video.currentTime / video.duration) * 1000));
                }
            });
            video.addEventListener("seeked", updateVideoCaption);
            video.addEventListener("play", syncPlayLabel);
            video.addEventListener("pause", syncPlayLabel);
            video.addEventListener("volumechange", syncMuteLabel);
        }
        if (progress) {
            progress.addEventListener("input", function () {
                if (video && video.duration) {
                    video.currentTime = (Number(progress.value) / 1000) * video.duration;
                }
            });
        }
        if (speedSelect) {
            speedSelect.addEventListener("change", function () {
                if (video) {
                    video.playbackRate = Number(speedSelect.value || 1);
                }
            });
        }
        if (qualitySelect) {
            qualitySelect.addEventListener("change", function () {
                setQualityNote(qualitySelect.value);
                changeStudentVideoQuality(qualitySelect.value);
            });
            setQualityNote(qualitySelect.value);
        }
        if (captionToggle && videoCaption) {
            if (!videoCaption.dataset.enabled) {
                videoCaption.dataset.enabled = "true";
            }
            captionToggle.addEventListener("click", function () {
                const isEnabled = videoCaption.dataset.enabled !== "false";
                videoCaption.dataset.enabled = isEnabled ? "false" : "true";
                syncCaptionToggle();
                updateVideoCaption();
            });
            syncCaptionToggle();
        }
        if (transcriptToggle && videoTranscript) {
            transcriptToggle.addEventListener("click", function () {
                const isHidden = videoTranscript.hasAttribute("hidden");
                if (isHidden) {
                    videoTranscript.removeAttribute("hidden");
                } else {
                    videoTranscript.setAttribute("hidden", "");
                }
                transcriptToggle.setAttribute("aria-expanded", String(isHidden));
            });
        }
        if (downloadButton) {
            downloadButton.addEventListener("click", function () {
                const result = window.ThinkNoteStudentResult;
                if (!result) {
                    return;
                }
                const summary = result.summary_text || "Summary is not available yet.";
                const blob = new Blob(
                    [result.title + "\n" + result.course_name + "\n\n" + summary],
                    { type: "text/plain" }
                );
                const link = document.createElement("a");
                link.href = URL.createObjectURL(blob);
                link.download = String(result.title || "lecture-summary").replace(/[^a-z0-9_-]+/gi, "_") + ".txt";
                link.click();
                URL.revokeObjectURL(link.href);
            });
        }
        if (shareButton) {
            shareButton.addEventListener("click", function () {
                const result = window.ThinkNoteStudentResult;
                const shareData = {
                    title: result ? result.title : document.title,
                    text: result ? result.summary_text || result.title : document.title,
                    url: window.location.href
                };
                if (navigator.share) {
                    navigator.share(shareData);
                } else if (navigator.clipboard) {
                    navigator.clipboard.writeText(window.location.href);
                }
            });
        }
        if (chatForm && chatInput) {
            chatForm.addEventListener("submit", function (event) {
                event.preventDefault();
                const message = chatInput.value.trim();
                chatInput.value = "";
                switchStudentTab("chat");
                handleStudentChat(message);
            });
        }
    }

    function renderResultData(result) {
        setText("result-lecture-title", result.title);
        setText("result-course-name", result.course_name);
        setText("result-lecture-description", result.summary_text || "Result details loaded from the backend pipeline.");

        renderPlainBlock("result-transcript", result.cleaned_transcript || result.transcript || "Transcript not available yet.");
        renderPlainBlock("result-fusion", result.redundancy_removed_text || result.fused_text || "Fused multimodal text not available yet.");

        renderStructuredSummary(result.structured_summary);
        renderStudentStudy(result);
        renderStudentSummaryWorkspace(result);
        renderEvaluation(result);
        renderMath(
            document.body.dataset.page === "student-results"
                ? document.querySelector(".student-summary-app")
                : document.querySelector(".content-shell")
        );
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

    function normalizeText(value) {
        return String(value || "").trim().toLowerCase();
    }

    function courseFromQuery() {
        const params = new URLSearchParams(window.location.search);
        return params.get("course") || "";
    }

    async function loadVideoList(selector) {
        let videoPath = "/videos";
        if (window.ThinkNoteApp.getCurrentRole() === "teacher" && window.ThinkNoteApp.getActiveWorkspaceId()) {
            videoPath += "?workspace_id=" + encodeURIComponent(window.ThinkNoteApp.getActiveWorkspaceId());
        }
        const videos = await window.ThinkNoteApp.apiRequest(videoPath);
        const selectedCourse = courseFromQuery();
        const visibleVideos = selectedCourse
            ? videos.filter(function (video) { return normalizeText(video.course_name) === normalizeText(selectedCourse); })
            : videos;
        const sortedVideos = sortCourseVideos(visibleVideos);
        selector.innerHTML = "";

        sortedVideos.forEach(function (video, index) {
            const option = document.createElement("option");
            option.value = String(video.id);
            option.textContent = selectedCourse
                ? lectureLabel(index) + " - " + video.title
                : (video.course_name || "Course") + " | " + lectureLabel(index) + " - " + video.title;
            selector.appendChild(option);
        });

        return sortedVideos;
    }

    function getSelectedVideoId(videos) {
        const params = new URLSearchParams(window.location.search);
        const fromQuery = params.get("video");
        if (fromQuery && videos.some(function (video) { return String(video.id) === fromQuery; })) {
            return fromQuery;
        }

        return videos.length ? String(videos[0].id) : null;
    }

    async function initResults() {
        const page = document.body.dataset.page;
        if (page === "results") {
            window.location.replace(window.ThinkNoteApp.getResultPage(window.ThinkNoteApp.getCurrentRole()) + window.location.search);
            return;
        }

        if (page !== "teacher-results" && page !== "student-results") {
            return;
        }

        const selector = byId("result-video-selector");

        try {
            const videos = await loadVideoList(selector);
            if (!videos.length) {
                setText("result-lecture-title", "No accessible videos found.");
                setText("result-lecture-description", page === "student-results" ? "Register to a teacher first, then open assigned lecture results." : "Upload and process a lecture first.");
                return;
            }

            const currentVideoId = getSelectedVideoId(videos);
            selector.value = currentVideoId;

            async function fetchAndRender(videoId) {
                try {
                    const result = await window.ThinkNoteApp.apiRequest("/results/" + videoId);
                    renderResultData(result);
                    const url = new URL(window.location.href);
                    if (!url.searchParams.get("course") && result.course_name) {
                        url.searchParams.set("course", result.course_name);
                    }
                    url.searchParams.set("video", videoId);
                    window.history.replaceState({}, "", url);
                } catch (error) {
                    setText("result-lecture-title", "Result not ready yet");
                    setText("result-lecture-description", error.message || "The backend result is not available yet.");
                }
            }

            await fetchAndRender(currentVideoId);

            selector.addEventListener("change", function () {
                fetchAndRender(selector.value);
            });
        } catch (error) {
            setText("result-lecture-title", "Backend connection failed");
            setText("result-lecture-description", error.message || "Could not load result data from FastAPI.");
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        initStudentSummaryControls();
        initResults();
    });
})();

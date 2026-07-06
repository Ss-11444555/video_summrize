(function () {
    function renderMetrics(metrics) {
        const container = document.getElementById("analytics-metrics");
        container.innerHTML = "";

        metrics.forEach(function (metric) {
            const card = document.createElement("article");
            card.className = "metric-card";
            card.innerHTML = "<span>" + metric.label + "</span><strong>" + metric.value + "</strong><p>" + metric.copy + "</p>";
            container.appendChild(card);
        });
    }

    function renderUsageChart(values) {
        const chart = document.getElementById("usage-chart");
        chart.innerHTML = "";

        values.forEach(function (item) {
            const column = document.createElement("div");
            column.className = "chart-column";
            column.innerHTML =
                "<span class='chart-column-value'>" + item.value + "</span>" +
                "<div class='chart-column-bar' style='height: " + Math.max(item.value * 6, 28) + "px;'></div>" +
                "<span class='chart-column-label'>" + item.label + "</span>";
            chart.appendChild(column);
        });
    }

    function renderBarList(targetId, items, formatValue) {
        const target = document.getElementById(targetId);
        target.innerHTML = "";

        items.forEach(function (item) {
            const value = formatValue ? formatValue(item) : item.value + "%";
            const width = item.value;
            const row = document.createElement("div");
            row.className = "bar-item";
            row.innerHTML =
                "<div class='row-between'><strong>" + item.label + "</strong><span>" + value + "</span></div>" +
                "<div class='bar-track'><span class='bar-fill' style='width: " + width + "%;'></span></div>";
            target.appendChild(row);
        });
    }

    function renderBottlenecks(items) {
        const container = document.getElementById("analytics-bottlenecks");
        container.innerHTML = "";

        items.forEach(function (item) {
            const row = document.createElement("div");
            row.className = "split-stat";
            row.innerHTML = "<div><strong>" + item.label + "</strong><p>" + item.copy + "</p></div><span>" + item.value + "</span>";
            container.appendChild(row);
        });
    }

    async function initAnalytics() {
        if (document.body.dataset.page !== "analytics") {
            return;
        }

        try {
            const overview = await window.ThinkNoteApp.apiRequest("/analytics/overview");
            const videos = await window.ThinkNoteApp.apiRequest("/videos");

            const completedVideos = videos.filter(function (video) { return video.status === "completed"; }).length;
            const processingVideos = videos.filter(function (video) { return video.status === "processing" || video.status === "uploaded"; }).length;
            const publishedVideos = videos.filter(function (video) { return video.is_published; }).length;
            const failedVideos = videos.filter(function (video) { return video.status === "failed"; }).length;

            renderMetrics([
                { label: "Registered Users", value: String(overview.total_users || 0), copy: "Loaded from the backend analytics endpoint." },
                { label: "Total Videos", value: String(overview.total_videos || 0), copy: "Current lecture videos stored in the system." },
                { label: "Completed Videos", value: String(overview.completed_videos || 0), copy: "Videos that finished the AI pipeline." },
                { label: "Published Videos", value: String(overview.published_videos || 0), copy: "Videos currently visible to student accounts." }
            ]);

            renderUsageChart([
                { label: "All", value: overview.total_videos || 0 },
                { label: "Done", value: completedVideos },
                { label: "Proc", value: processingVideos },
                { label: "Pub", value: publishedVideos },
                { label: "Fail", value: failedVideos },
                { label: "R1", value: Math.round((overview.average_rouge_1 || 0) * 100) },
                { label: "RL", value: Math.round((overview.average_rouge_l || 0) * 100) }
            ]);

            renderBarList("role-distribution-list", [
                { label: "Completed Videos", value: overview.total_videos ? Math.round((completedVideos / overview.total_videos) * 100) : 0 },
                { label: "Published Videos", value: overview.total_videos ? Math.round((publishedVideos / overview.total_videos) * 100) : 0 },
                { label: "Processing Videos", value: overview.total_videos ? Math.round((processingVideos / overview.total_videos) * 100) : 0 }
            ]);

            renderBottlenecks([
                { label: "Processing Queue", copy: "Videos still moving through the backend pipeline", value: String(processingVideos) },
                { label: "Failed Videos", copy: "Video runs that ended with a backend processing error", value: String(failedVideos) },
                { label: "Published Content", copy: "Videos already released to students", value: String(publishedVideos) }
            ]);

            renderBarList("analytics-quality-list", [
                { label: "ROUGE-1 Average", value: Math.round((overview.average_rouge_1 || 0) * 100), display: (overview.average_rouge_1 || 0).toFixed(2) },
                { label: "ROUGE-2 Average", value: Math.round((overview.average_rouge_2 || 0) * 100), display: (overview.average_rouge_2 || 0).toFixed(2) },
                { label: "ROUGE-L Average", value: Math.round((overview.average_rouge_l || 0) * 100), display: (overview.average_rouge_l || 0).toFixed(2) }
            ], function (item) {
                return item.display;
            });
        } catch (error) {
            renderMetrics([
                { label: "Analytics Unavailable", value: "--", copy: error.message || "Only admin accounts can load backend analytics." }
            ]);
            document.getElementById("usage-chart").innerHTML = "<div class='empty-state'>Analytics could not be loaded from the backend.</div>";
            document.getElementById("role-distribution-list").innerHTML = "<div class='empty-state'>No analytics data available.</div>";
            document.getElementById("analytics-bottlenecks").innerHTML = "<div class='empty-state'>No analytics data available.</div>";
            document.getElementById("analytics-quality-list").innerHTML = "<div class='empty-state'>No analytics data available.</div>";
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        initAnalytics();
    });
})();

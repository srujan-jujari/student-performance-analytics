(() => {
    "use strict";

    const dataElement = document.getElementById("dashboard-data");
    if (!dataElement) {
        return;
    }

    const dashboardData = JSON.parse(dataElement.textContent);
    const riskLabels = ["High", "Medium", "Low"];
    const riskColors = ["#fb7185", "#fbbf24", "#34d399"];
    const riskCanvas = document.getElementById("risk-chart");
    const subjectCanvas = document.getElementById("subject-chart");

    if (window.Chart && riskCanvas) {
        const existingChart = Chart.getChart(riskCanvas);
        if (existingChart) {
            existingChart.destroy();
        }
        new Chart(riskCanvas, {
            type: "doughnut",
            data: {
                labels: riskLabels,
                datasets: [{
                    data: riskLabels.map((label) => dashboardData.riskCounts[label] || 0),
                    backgroundColor: riskColors,
                    borderWidth: 2,
                    borderColor: "#222222",
                    hoverOffset: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { color: "#a3a3a3", padding: 18, usePointStyle: true }
                    },
                    tooltip: {
                        backgroundColor: "#171717",
                        borderColor: "#484848",
                        borderWidth: 1,
                        titleColor: "#fafafa",
                        bodyColor: "#d4d4d4",
                        padding: 11
                    }
                }
            }
        });
    }

    if (window.Chart && subjectCanvas) {
        const existingChart = Chart.getChart(subjectCanvas);
        if (existingChart) {
            existingChart.destroy();
        }
        const subjects = dashboardData.subjectSummary || [];
        new Chart(subjectCanvas, {
            type: "bar",
            data: {
                labels: subjects.map((subject) => subject.subject),
                datasets: [{
                    label: "Average percentage",
                    data: subjects.map((subject) => subject.average_percentage),
                    backgroundColor: "rgba(245, 158, 11, 0.82)",
                    hoverBackgroundColor: "#f97316",
                    borderColor: "#f59e0b",
                    borderWidth: 1,
                    borderRadius: 5,
                    maxBarThickness: 42
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: {
                            display: true,
                            text: "Average percentage",
                            color: "#a3a3a3",
                            font: { size: 10 }
                        },
                        ticks: { color: "#a3a3a3", font: { size: 9 } },
                        grid: { color: "rgba(255, 255, 255, 0.07)" },
                        border: { color: "#383838" }
                    },
                    x: {
                        ticks: { autoSkip: false, color: "#a3a3a3", font: { size: 9 } },
                        grid: { display: false },
                        border: { color: "#383838" }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: "#171717",
                        borderColor: "#484848",
                        borderWidth: 1,
                        titleColor: "#fafafa",
                        bodyColor: "#d4d4d4",
                        callbacks: {
                            label: (context) => ` ${context.parsed.y.toFixed(1)}%`
                        }
                    }
                }
            }
        });
    }

    const table = document.getElementById("student-table");
    const searchInput = document.getElementById("student-search");
    const subjectFilter = document.getElementById("subject-filter");
    const riskFilter = document.getElementById("risk-filter");
    const resultCount = document.getElementById("student-result-count");
    const noMatchesRow = document.getElementById("no-students-match");

    if (table && searchInput && subjectFilter && riskFilter) {
        const studentRows = Array.from(table.tBodies[0].rows)
            .filter((row) => row.id !== "no-students-match");
        const initialCount = studentRows.length;

        const applyFilters = () => {
            const query = searchInput.value.trim().toLocaleLowerCase();
            const selectedSubject = subjectFilter.value;
            const selectedRisk = riskFilter.value;
            let visibleCount = 0;

            studentRows.forEach((row) => {
                const studentId = row.cells[0].textContent.toLocaleLowerCase();
                const studentName = row.cells[1].textContent.toLocaleLowerCase();
                const matchesSearch = !query
                    || studentId.includes(query)
                    || studentName.includes(query);
                const matchesSubject = !selectedSubject
                    || row.cells[2].textContent === selectedSubject;
                const matchesRisk = !selectedRisk
                    || row.cells[6].textContent === selectedRisk;
                const isVisible = matchesSearch && matchesSubject && matchesRisk;

                row.hidden = !isVisible;
                if (isVisible) {
                    visibleCount += 1;
                }
            });

            noMatchesRow.hidden = visibleCount !== 0 || studentRows.length === 0;
            resultCount.textContent = `Showing ${visibleCount} of ${initialCount} students`;
        };

        searchInput.addEventListener("input", applyFilters);
        subjectFilter.addEventListener("change", applyFilters);
        riskFilter.addEventListener("change", applyFilters);
    }

    const storageForms = document.querySelectorAll(".cloud-storage-form");
    const sourceCsv = dashboardData.sourceCsv;

    storageForms.forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (form.dataset.submitting === "true") {
                return;
            }

            form.dataset.submitting = "true";
            const action = form.dataset.storageAction;
            const status = document.getElementById(`${action}-storage-status`);
            const submitButton = form.querySelector("button[type='submit']");
            const label = submitButton.querySelector(".button-label");
            const loading = submitButton.querySelector(".button-loading");
            const formData = new FormData(form);
            formData.set("source_csv", sourceCsv);
            submitButton.disabled = true;
            label.hidden = true;
            loading.hidden = false;
            status.textContent = "Sending your file securely…";
            status.className = "storage-status storage-status-pending";

            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: formData,
                    credentials: "same-origin",
                    headers: { Accept: "application/json" }
                });
                const result = await response.json();
                if (!response.ok || !result.success) {
                    throw new Error(result.message || "Upload failed. Please try again.");
                }

                status.textContent = result.message;
                status.className = "storage-status storage-status-success";
                label.textContent = "Uploaded successfully";
            } catch (error) {
                status.textContent = error instanceof Error
                    ? error.message
                    : "Upload could not be completed. Check your connection and try again.";
                status.className = "storage-status storage-status-error";
                submitButton.disabled = false;
                label.textContent = action === "source"
                    ? "Upload Source CSV"
                    : "Upload Analytics Report";
            } finally {
                form.dataset.submitting = "false";
                label.hidden = false;
                loading.hidden = true;
            }
        });
    });

    const downloadButton = document.getElementById("download-csv");
    if (downloadButton) {
        downloadButton.addEventListener("click", () => {
            const visibleRows = table
                ? Array.from(table.tBodies[0].rows)
                    .filter((row) => row.id !== "no-students-match" && !row.hidden)
                : [];
            const visibleIndexes = new Set(
                visibleRows.map((row) => Number(row.dataset.recordIndex))
            );
            const records = (dashboardData.students || []).filter((student, index) =>
                visibleIndexes.has(index)
            );
            const columns = [
                "student_id",
                "name",
                "subject",
                "marks",
                "max_marks",
                "attendance",
                "percentage",
                "risk_level"
            ];
            const escapeCell = (value, column) => {
                let text = String(value ?? "");
                if (
                    ["student_id", "name", "subject", "risk_level"].includes(column)
                    && /^[\s\u0000-\u001f]*[=+\-@]/.test(text)
                ) {
                    text = `'${text}`;
                }
                return `"${text.replaceAll('"', '""')}"`;
            };
            const csv = [
                columns.map((column) => escapeCell(column, column)).join(","),
                ...records.map((record) =>
                    columns.map((column) => escapeCell(record[column], column)).join(",")
                )
            ].join("\r\n");
            const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = "student-performance-analysis.csv";
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
        });
    }
})();

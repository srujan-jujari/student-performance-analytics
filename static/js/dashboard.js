(() => {
    "use strict";

    const dataElement = document.getElementById("dashboard-data");
    if (!dataElement) {
        return;
    }

    const dashboardData = JSON.parse(dataElement.textContent);
    const riskLabels = ["High", "Medium", "Low"];
    const riskColors = ["#dc3545", "#ffc107", "#198754"];
    const riskCanvas = document.getElementById("risk-chart");
    const subjectCanvas = document.getElementById("subject-chart");

    if (window.Chart && riskCanvas) {
        new Chart(riskCanvas, {
            type: "doughnut",
            data: {
                labels: riskLabels,
                datasets: [{
                    data: riskLabels.map((label) => dashboardData.riskCounts[label] || 0),
                    backgroundColor: riskColors,
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom" }
                }
            }
        });
    }

    if (window.Chart && subjectCanvas) {
        const subjects = dashboardData.subjectSummary || [];
        new Chart(subjectCanvas, {
            type: "bar",
            data: {
                labels: subjects.map((subject) => subject.subject),
                datasets: [{
                    label: "Average percentage",
                    data: subjects.map((subject) => subject.average_percentage),
                    backgroundColor: "#0d6efd",
                    borderRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: { display: true, text: "Average percentage" }
                    },
                    x: {
                        ticks: { autoSkip: false }
                    }
                },
                plugins: {
                    legend: { display: false }
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
        form.addEventListener("submit", (event) => {
            if (form.dataset.submitting === "true") {
                event.preventDefault();
                return;
            }

            const sourceInput = document.createElement("input");
            sourceInput.type = "hidden";
            sourceInput.name = "source_csv";
            sourceInput.value = sourceCsv;
            form.appendChild(sourceInput);

            form.dataset.submitting = "true";
            const submitButton = event.submitter;
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = "Storing...";
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

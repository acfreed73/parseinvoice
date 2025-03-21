document.addEventListener("DOMContentLoaded", () => {
    loadUnprocessedFiles();
    fetchProcessedFiles();
    setupDragAndDrop();
});

function setupDragAndDrop() {
    let dropArea = document.getElementById("drop-area");
    if (!dropArea) return;

    dropArea.addEventListener("dragover", (event) => {
        event.preventDefault();
        dropArea.classList.add("dragover");
    });

    dropArea.addEventListener("dragleave", () => {
        dropArea.classList.remove("dragover");
    });

    dropArea.addEventListener("drop", async (event) => {
        event.preventDefault();
        dropArea.classList.remove("dragover");

        let files = event.dataTransfer.files;
        if (files.length === 0) return;

        await uploadFile(files[0]);
    });
}

async function uploadFile(file) {
    let formData = new FormData();
    formData.append("file", file);

    try {
        let response = await fetch("/files/upload/", {
            method: "POST",
            body: formData
        });

        let result = await response.json();
        alert(result.message);

        let row = document.createElement("tr");
        row.innerHTML = `
            <td>${file.name}</td>
            <td>${result.status === "success" ? "✅ Processed" : "❌ Failed"}</td>
        `;

        if (result.status === "success") {
            document.getElementById("file-list").appendChild(row);
        } else {
            document.getElementById("unprocessed-list").appendChild(row);
        }

        fetchProcessedFiles();
        loadUnprocessedFiles();
    } catch (error) {
        console.error("Upload failed:", error);
    }
}



async function loadUnprocessedFiles() {
    try {
        let response = await fetch("/files/uploaded_files/");
        let result = await response.json();

        let unprocessedList = document.getElementById("unprocessed-list");
        if (!unprocessedList) return;
        unprocessedList.innerHTML = "";

        if (!result.files || result.files.length === 0) {
            unprocessedList.innerHTML = "<tr><td colspan='2'>No unprocessed files</td></tr>";
            return;
        }

        result.files.forEach(file => {
            if (!file.unprocessed) return;

            let row = document.createElement("tr");
            row.innerHTML = `
                <td>${file.filename}</td>
                <td>
                    <input type="checkbox" id="pdftotext-${file.filename}" onchange="toggleTemplateDropdown('${file.filename}')"> Use pdftotext
                    <select id="template-select-${file.filename}" style="display:none;">
                        <option value="">-- Select Template --</option>
                        ${rawTemplates.map(tpl => `<option value="${tpl}">${tpl}</option>`).join("")}
                    </select>
                </td>
                <td>
                    <button class="btn btn-warning" onclick="retryProcessing('${file.filename}')">
                        <i class="fa fa-sync"></i> Retry
                    </button>
                    <button class="btn btn-danger" onclick="deleteFile('${file.filename}')">
                        <i class="fa fa-trash"></i> Delete
                    </button>
                </td>
            `;

            unprocessedList.appendChild(row);
        });
    } catch (error) {
        console.error("Failed to load unprocessed files:", error);
    }
}

async function fetchProcessedFiles() {
    try {
        let response = await fetch("/files/uploaded_files/");
        let data = await response.json();

        let fileList = document.getElementById("file-list");
        let unprocessedList = document.getElementById("unprocessed-list");
        let downloadButtons = document.getElementById("download-buttons"); // ✅ Get the download buttons div
        if (!fileList || !unprocessedList || !downloadButtons) return;

        fileList.innerHTML = "";
        unprocessedList.innerHTML = "";

        let hasProcessedFiles = false; // ✅ Track if there are processed files

        if (!data.files || data.files.length === 0) {
            fileList.innerHTML = "<tr><td colspan='3'>No processed files</td></tr>";
            downloadButtons.style.display = "none"; // ✅ Hide download buttons if no files exist
            return;
        }

        data.files.forEach(file => {
            let row = document.createElement("tr");
            row.id = `row-${file.filename}`;

            let filenameCell = document.createElement("td");
            filenameCell.textContent = file.filename;

            let statusCell = document.createElement("td");
            let actionCell = document.createElement("td");

            if (file.unprocessed) {
                statusCell.innerHTML = "❌ Unprocessed";
                actionCell.innerHTML = `
                    <button class="btn btn-warning" onclick="retryProcessing('${file.filename}')">
                        <i class="fa fa-sync"></i> Retry
                    </button>
                    <button class="btn btn-danger" onclick="deleteFile('${file.filename}')">
                        <i class="fa fa-trash"></i> Delete
                    </button>
                `;
                row.appendChild(filenameCell);
                row.appendChild(statusCell);
                row.appendChild(actionCell);
                unprocessedList.appendChild(row);
            } else if (file.processed) {
                hasProcessedFiles = true; // ✅ We found a processed file
                statusCell.innerHTML = "✅ Processed";
                actionCell.innerHTML = `
                    <button class="btn btn-danger" onclick="deleteFile('${file.filename}')">
                        <i class="fa fa-trash"></i> Delete
                    </button>
                `;
                row.appendChild(filenameCell);
                row.appendChild(statusCell);
                row.appendChild(actionCell);
                fileList.appendChild(row);
            }
        });

        // ✅ Show or Hide Download Buttons Based on Processed Files
        downloadButtons.style.display = hasProcessedFiles ? "block" : "none";
    } catch (error) {
        console.error("Error loading processed files:", error);
    }
}

// Call the function after processing
document.addEventListener("DOMContentLoaded", fetchProcessedFiles);


async function retryProcessing(filename) {
    if (!confirm(`Reprocess ${filename}?`)) return;

    const usePdftotext = document.getElementById(`pdftotext-${filename}`)?.checked || false;
    const template = document.getElementById(`template-select-${filename}`)?.value || "";

    const url = new URL(`/processing/process/${filename}`, window.location.origin);
    url.searchParams.set("pdftotext", usePdftotext);
    if (usePdftotext && template) {
        url.searchParams.set("template", template);
    }

    try {
        const response = await fetch(url.toString(), { method: "POST" });
        const result = await response.json();
        alert(result.message);
        fetchProcessedFiles();
        loadUnprocessedFiles();
    } catch (err) {
        console.error("Error reprocessing:", err);
        alert("Failed to reprocess the file.");
    }
}

async function deleteFile(filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;

    try {
        let response = await fetch(`/files/delete/${filename}`, { method: "DELETE" });
        let data = await response.json();

        alert(data.message);

        let row = document.getElementById(`row-${filename}`);
        if (row) {
            row.remove();
        }

        fetchProcessedFiles();
        loadUnprocessedFiles();
    } catch (error) {
        console.error("Error deleting file:", error);
    }
}
async function reprocessFile(filename) {
    if (!confirm(`Reprocess ${filename}?`)) return;

    const checkbox = document.querySelector(`.pdftotext-toggle[data-filename="${filename}"]`);
    const usePdftotext = checkbox?.checked ? "true" : "false";

    try {
        let response = await fetch(`/processing/process/${filename}?pdftotext=${usePdftotext}`, {
            method: "POST"
        });

        let result = await response.json();
        alert(result.message);

        if (result.message.includes("Successfully")) {
            fetchProcessedFiles();
            loadUnprocessedFiles();
        }
    } catch (error) {
        console.error("Error reprocessing file:", error);
    }
}
async function resetAll() {
    if (!confirm("Are you sure you want to reset everything? This will delete all files and data!")) return;

    try {
        let response = await fetch("/files/reset/", { method: "POST" });
        let data = await response.json();

        alert(data.message);
        location.reload();
    } catch (error) {
        console.error("Error resetting system:", error);
    }
}
async function downloadCSV() {
    window.location.href = "/downloads/download/csv/";  // ✅ Fixed API path
}

async function downloadJSON() {
    window.location.href = "/downloads/download/json/";  // ✅ Fixed API path
}
async function downloadXLS() {
    window.location.href = "/downloads/download/xls/";  // ✅ Fixed API path
}
function toggleTemplateDropdown(filename) {
    const checkbox = document.getElementById(`pdftotext-${filename}`);
    const dropdown = document.getElementById(`template-select-${filename}`);
    dropdown.style.display = checkbox.checked ? "inline" : "none";
}

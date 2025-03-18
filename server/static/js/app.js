document.addEventListener("DOMContentLoaded", () => {
    let dropArea = document.getElementById("drop-area");

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

        let formData = new FormData();
        formData.append("file", files[0]); // Only handling one file for now

        try {
            let response = await fetch("/upload/", {
                method: "POST",
                body: formData,
            });

            let result = await response.json();
            alert(result.message);
            location.reload();
        } catch (error) {
            console.error("Upload failed:", error);
        }
    });
});
async function retryProcessing(filename) {
    if (!confirm(`Retry processing ${filename}?`)) return;

    try {
        let response = await fetch(`/process/${filename}`, { method: "POST" });
        let result = await response.json();
        alert(result.message);

        if (result.message.includes("Successfully")) {
            loadFileList();  // Refresh processed files ✅
            loadUnprocessedFiles();  // Refresh unprocessed list ❌
        }
    } catch (error) {
        console.error("Error retrying processing:", error);
    }
}

async function loadUnprocessedFiles() {
    try {
        let response = await fetch("/uploaded_files/");
        let result = await response.json();

        let unprocessedList = document.getElementById("unprocessed-list");
        unprocessedList.innerHTML = ""; // Clear previous entries

        result.files.forEach(file => {
            if (!file.unprocessed) return; // Only show unprocessed files

            let row = document.createElement("tr");
            row.innerHTML = `
                <td>${file.filename}</td>
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


// Call the function to populate the unprocessed section
document.addEventListener("DOMContentLoaded", loadUnprocessedFiles);

async function uploadFile() {
    let fileInput = document.getElementById('fileUpload');
    let file = fileInput.files[0];
    if (!file) return;

    let formData = new FormData();
    formData.append("file", file);

    try {
        let response = await fetch("/upload/", { method: "POST", body: formData });
        let result = await response.json();

        alert(result.message);

        if (result.processed) {
            fetchProcessedFiles(); // Refresh processed list
        } else {
            loadUnprocessedFiles(); // Refresh unprocessed list
        }
    } catch (error) {
        console.error("Upload error:", error);
    }
}

function resetAll() {
    fetch("/reset/", { method: "POST" }).then(() => location.reload());
}

async function deleteFile(filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;

    try {
        let response = await fetch(`/delete/${filename}`, { method: "DELETE" });
        let data = await response.json();

        alert(data.message);

        // Find the row and remove it safely
        let row = document.getElementById(`row-${filename}`);
        if (row) {
            row.remove();
        } else {
            console.warn(`Row for ${filename} not found in DOM.`);
        }

        // Refresh the UI
        fetchProcessedFiles();  // Refresh processed list
        loadUnprocessedFiles(); // Refresh unprocessed list
    } catch (error) {
        console.error("Error deleting file:", error);
    }
}


async function reprocessFile(filename) {
    if (!confirm(`Reprocess ${filename}?`)) return;

    try {
        let response = await fetch(`/process/${filename}`, { method: "POST" });
        let result = await response.json();
        alert(result.message);

        if (result.message.includes("Successfully")) {
            loadFileList();  // Refresh processed list
            loadUnprocessedFiles();  // Refresh unprocessed list
        }
    } catch (error) {
        console.error("Error reprocessing file:", error);
    }
}
async function fetchProcessedFiles() {
    const response = await fetch("/uploaded_files/");
    const data = await response.json();

    const fileList = document.getElementById("file-list");
    const unprocessedList = document.getElementById("unprocessed-list");

    fileList.innerHTML = "";  // Clear processed list
    unprocessedList.innerHTML = "";  // Clear unprocessed list

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
}


// Call the function after processing
document.addEventListener("DOMContentLoaded", fetchProcessedFiles);

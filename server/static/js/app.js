document.addEventListener("DOMContentLoaded", () => {
    let dropArea = document.getElementById("drop-area");
    let fileInput = document.getElementById("fileUpload");

    // Drag & Drop Events
    dropArea.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropArea.style.backgroundColor = "#e3f2fd";
    });

    dropArea.addEventListener("dragleave", () => {
        dropArea.style.backgroundColor = "#f8f9fa";
    });

    dropArea.addEventListener("drop", (e) => {
        e.preventDefault();
        dropArea.style.backgroundColor = "#f8f9fa";

        let files = e.dataTransfer.files;
        uploadFile(files[0]); // Upload only the first file for now
    });

    dropArea.addEventListener("click", () => {
        fileInput.click();
    });

    fileInput.addEventListener("change", () => {
        uploadFile(fileInput.files[0]);
    });
});

function uploadFile(file) {
    if (!file) return;

    let formData = new FormData();
    formData.append("file", file);

    fetch("/upload/", {
        method: "POST",
        body: formData
    }).then(() => location.reload());
}

function resetAll() {
    fetch("/reset/", { method: "POST" }).then(() => location.reload());
}

function deleteFile(filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;

    fetch(`/delete/${filename}`, { method: "DELETE" })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            document.getElementById(`row-${filename}`).remove();
        })
        .catch(error => console.error("Error deleting file:", error));
}

function reprocessFile(filename) {
    fetch(`/process/${filename}`, { method: "POST" })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            location.reload();
        })
        .catch(error => console.error("Error reprocessing file:", error));
}
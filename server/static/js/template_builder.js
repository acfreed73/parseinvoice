let annotations = []; // ✅ Global annotations array
let pdfDoc = null;
let pageNum = 1;
const scale = 1.5; // ✅ Adjust zoom scale
const canvas = document.getElementById("pdfCanvas");
const ctx = canvas.getContext("2d");

document.addEventListener("DOMContentLoaded", () => {
    let extractedText = document.getElementById("extractedText");
    let annotationType = document.getElementById("annotationType");
    let addAnnotationBtn = document.getElementById("addAnnotation");
    let saveTemplateBtn = document.getElementById("saveTemplate");
    let selectedTextInput = document.getElementById("selectedText");
    let annotationsList = document.getElementById("annotationsList");
    let fileInput = document.getElementById("uploadPDF");
    let dropArea = document.getElementById("uploadPDFArea");

    addAnnotationBtn.disabled = true;
    saveTemplateBtn.disabled = true;

    extractedText.addEventListener("mouseup", () => {
        let selectedText = window.getSelection().toString().trim();
        if (selectedText) {
            selectedTextInput.value = selectedText;
            addAnnotationBtn.disabled = false;
        }
    });

    addAnnotationBtn.addEventListener("click", () => {
        let selectedText = selectedTextInput.value.trim();
        let type = annotationType.value;

        if (!selectedText || !type) {
            alert("Select text and choose an annotation type!");
            return;
        }

        if (annotations.some(a => a.text === selectedText && a.type === type)) {
            alert("This annotation already exists!");
            return;
        }

        let annotation = { text: selectedText, type };
        annotations.push(annotation);

        let listItem = document.createElement("li");
        listItem.textContent = `${selectedText} (${type})`;

        let removeBtn = document.createElement("button");
        removeBtn.textContent = "❌";
        removeBtn.style.marginLeft = "10px";
        removeBtn.onclick = () => removeAnnotation(annotation, listItem);

        listItem.appendChild(removeBtn);
        annotationsList.appendChild(listItem);

        saveTemplateBtn.disabled = annotations.length === 0;
    });

    saveTemplateBtn.addEventListener("click", async () => {
        let pdfName = document.getElementById("pdfName").value.trim();
        if (!pdfName || annotations.length === 0) {
            alert("Provide a PDF name and at least one annotation!");
            return;
        }

        let payload = { pdf_name: pdfName, annotations };

        try {
            let response = await fetch("/templates/save/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            let result = await response.json();
            alert(result.message);

            // ✅ Clear UI Elements After Saving
            document.getElementById("pdfName").value = "";
            document.getElementById("extractedText").value = "";
            document.getElementById("selectedText").value = "";
            annotationsList.innerHTML = "";
            annotations = [];  // Clear annotation array
            saveTemplateBtn.disabled = true;

            // ✅ Hide Upload Area (If Needed)
            document.getElementById("uploadPDFArea").style.display = "block";
        } catch (error) {
            console.error("Error saving template:", error);
            alert("Failed to save template.");
        }
    });


    async function uploadPDF(file) {
        if (!file) {
            alert("Please select a PDF file!");
            return;
        }

        let formData = new FormData();
        formData.append("file", file);

        try {
            let response = await fetch("/templates/extract/", {
                method: "POST",
                body: formData
            });

            let result = await response.json();

            if (response.status === 400) {
                alert("The PDF requires OCR before extraction. Please process the PDF with OCR and try again.");
                return;
            }

            if (result.text) {
                extractedText.value = result.text;
                alert(`Text extracted from ${result.filename} successfully!`);
                renderPDF(URL.createObjectURL(file)); // ✅ Show PDF preview
            } else {
                alert("Failed to extract text from the PDF.");
            }
        } catch (error) {
            console.error("Error extracting text:", error);
            alert("Failed to upload and extract text.");
        }
    }

    fileInput.addEventListener("change", (event) => {
        let file = event.target.files[0];
        if (file) {
            uploadPDF(file);
        }
    });

    dropArea.addEventListener("dragover", (event) => {
        event.preventDefault();
        dropArea.classList.add("dragover");
    });

    dropArea.addEventListener("dragleave", () => {
        dropArea.classList.remove("dragover");
    });

    dropArea.addEventListener("drop", (event) => {
        event.preventDefault();
        dropArea.classList.remove("dragover");

        let files = event.dataTransfer.files;
        if (files.length > 0) {
            uploadPDF(files[0]);
        }
    });

    function removeAnnotation(annotation, listItem) {
        annotations = annotations.filter(a => !(a.text === annotation.text && a.type === annotation.type));
        listItem.remove();
        saveTemplateBtn.disabled = annotations.length === 0;
    }
});

// ✅ **PDF.js: Render the PDF in the Canvas**
async function renderPDF(pdfURL) {
    const loadingTask = pdfjsLib.getDocument(pdfURL);
    pdfDoc = await loadingTask.promise;
    renderPage(pageNum);
}

async function renderPage(num) {
    const page = await pdfDoc.getPage(num);
    const viewport = page.getViewport({ scale });
    canvas.width = viewport.width;
    canvas.height = viewport.height;

    const renderContext = {
        canvasContext: ctx,
        viewport: viewport
    };
    page.render(renderContext);
}

function nextPage() {
    if (pageNum < pdfDoc.numPages) {
        pageNum++;
        renderPage(pageNum);
    }
}

function prevPage() {
    if (pageNum > 1) {
        pageNum--;
        renderPage(pageNum);
    }
}
window.openTooltipModal = function (type) {
    let tooltipText = {
        "annotationType": "Annotations define what to extract from the invoice. Examples:\n- Issuer: The company name\n- Keywords: Words used to identify this invoice\n- Fields: Extracted values like date, amount, and invoice number.",
        "keywords": "Keywords help match the invoice format. If the keywords don't appear, the template won't be used.",
        "fields": "Fields define the data to extract. Required fields are:\n- invoice_number\n- date\n- amount\n- issuer."
    };

    document.getElementById("tooltipText").innerText = tooltipText[type] || "No information available.";
    document.getElementById("tooltipModal").style.display = "block";
};

// Close Modal
window.closeTooltipModal = function () {
    document.getElementById("tooltipModal").style.display = "none";
};

// Close when clicking outside of modal
window.onclick = function (event) {
    let modal = document.getElementById("tooltipModal");
    if (event.target === modal) {
        modal.style.display = "none";
    }
};


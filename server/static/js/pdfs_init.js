// ✅ Load pdf.js dynamically
const script = document.createElement("script");
script.src = "/static/pdfjs/pdf.js"; // Ensure this path is correct
script.onload = () => {
    console.log("PDF.js loaded");
    initPDFJS();
};
document.head.appendChild(script);

// ✅ Initialize pdf.js Worker
function initPDFJS() {
    if (typeof pdfjsLib === "undefined") {
        console.error("pdfjsLib is not loaded!");
        return;
    }
    pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/pdfjs/pdf.worker.js";
    console.log("PDF.js Worker initialized");
}

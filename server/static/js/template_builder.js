let annotations = [];

document.addEventListener("DOMContentLoaded", () => {
    console.log("Template Builder Loaded");

    let templateFileInput = document.getElementById("templateFile");
    let loadTemplateBtn = document.getElementById("loadTemplateBtn");

    let uploadedFileName = "";

    let saveTemplateBtn = document.getElementById("saveTemplateBtn"); // Ensure the ID is correct

    if (saveTemplateBtn) {
        saveTemplateBtn.addEventListener("click", saveTemplate);
    } else {
        console.error("Save button not found!");
    }

    templateFileInput.addEventListener("change", async function () {
        let file = this.files[0];
        if (!file) return;

        let formData = new FormData();
        formData.append("file", file);

        try {
            let response = await fetch("/templates/upload_template/", {
                method: "POST",
                body: formData,
            });

            let result = await response.json();
            if (result.filename) {
                uploadedFileName = result.filename;
                console.log("Uploaded File:", uploadedFileName);
                alert("Template uploaded! Click 'Load Template' to view it.");
            } else {
                console.error("Upload response did not contain a filename:", result);
            }
        } catch (error) {
            console.error("Template upload failed:", error);
        }
    });

    loadTemplateBtn.addEventListener("click", function () {
        if (!uploadedFileName) {
            alert("Please upload a template first!");
            return;
        }
        console.log("Loading PDF from:", `/static/templates/${uploadedFileName}`);
        loadPDF(`/static/templates/${uploadedFileName}`);
    });

});

// ✅ Function to Load and Render the PDF
async function loadPDF(pdfUrl) {
    console.log("Loading PDF:", pdfUrl);

    const pdfCanvasContainer = document.getElementById("pdfAnnotator");
    pdfCanvasContainer.innerHTML = ""; // Clear previous content

    const loadingTask = pdfjsLib.getDocument(pdfUrl);
    const pdf = await loadingTask.promise;
    const page = await pdf.getPage(1);

    const containerWidth = pdfCanvasContainer.clientWidth;
    const scale = containerWidth / 780;

    const viewport = page.getViewport({ scale });

    const container = document.createElement("div");
    container.style.position = "relative";
    container.style.width = "100%";
    container.style.maxWidth = `${viewport.width}px`;
    container.style.height = `${viewport.height}px`;
    container.style.overflow = "hidden";
    container.style.margin = "0 auto";
    pdfCanvasContainer.appendChild(container);

    const pdfCanvas = document.createElement("canvas");
    pdfCanvas.width = viewport.width;
    pdfCanvas.height = viewport.height;
    pdfCanvas.id = "pdfCanvas";
    pdfCanvas.style.position = "absolute";
    pdfCanvas.style.top = "0";
    pdfCanvas.style.left = "0";
    pdfCanvas.style.zIndex = "1";

    container.appendChild(pdfCanvas);

    const ctx = pdfCanvas.getContext("2d");
    const renderContext = { canvasContext: ctx, viewport };
    await page.render(renderContext).promise;

    console.log("✅ PDF successfully rendered on canvas:", pdfCanvas);

    const fabricCanvasElement = document.createElement("canvas");
    fabricCanvasElement.width = viewport.width;
    fabricCanvasElement.height = viewport.height;
    fabricCanvasElement.id = "fabricCanvas";
    fabricCanvasElement.style.position = "absolute";
    fabricCanvasElement.style.top = "0";
    fabricCanvasElement.style.left = "0";
    fabricCanvasElement.style.zIndex = "2";

    container.appendChild(fabricCanvasElement);

    setTimeout(() => initializeFabric(fabricCanvasElement), 500);
}
function initializeFabric(canvasElement) {
    const fabricCanvas = new fabric.Canvas(canvasElement, {
        selection: true, // Enable selection
    });

    let isDrawing = false;
    let startX, startY;
    let activeRect = null;
    let activeText = null;

    // Start drawing a rectangle or selecting an existing one
    fabricCanvas.on("mouse:down", (event) => {
        const pointer = fabricCanvas.getPointer(event.e);
        const targetObject = fabricCanvas.findTarget(event.e, true);

        // If clicking on an existing annotation, select it instead of drawing
        if (targetObject) {
            fabricCanvas.setActiveObject(targetObject);
            return;
        }

        isDrawing = true;
        startX = pointer.x;
        startY = pointer.y;

        activeRect = new fabric.Rect({
            left: startX,
            top: startY,
            width: 0,
            height: 0,
            fill: "rgba(255, 0, 0, 0.3)",
            stroke: "red",
            strokeWidth: 2,
            selectable: true,
            hasControls: true,
        });

        fabricCanvas.add(activeRect);
    });

    // Adjust rectangle size while dragging
    fabricCanvas.on("mouse:move", (event) => {
        if (!isDrawing) return;

        const pointer = fabricCanvas.getPointer(event.e);
        const width = pointer.x - startX;
        const height = pointer.y - startY;

        activeRect.set({ width, height });
        fabricCanvas.renderAll();
    });

    // Stop drawing and prompt for annotation details
    fabricCanvas.on("mouse:up", async () => {
        if (!isDrawing) return;
        isDrawing = false;

        if (!activeRect || activeRect.width < 5 || activeRect.height < 5) {
            fabricCanvas.remove(activeRect);
            return;
        }

        const fieldName = prompt("Enter a name for this annotation (e.g., 'Invoice Number', 'Total')");
        if (!fieldName) {
            fabricCanvas.remove(activeRect);
            return;
        }

        const annotationType = prompt("Type: issuer, field, or keyword?");
        if (!["issuer", "field", "keyword"].includes(annotationType)) {
            alert("Invalid type. Must be 'issuer', 'field', or 'keyword'.");
            fabricCanvas.remove(activeRect);
            return;
        }

        annotations.push({
            field: fieldName,
            type: annotationType,
            x: activeRect.left,
            y: activeRect.top,
            width: activeRect.width,
            height: activeRect.height,
        });

        activeRect.set({
            name: fieldName,
            hasControls: true,
            lockMovementX: true,
            lockMovementY: true,
        });

        activeText = new fabric.Text(fieldName, {
            left: activeRect.left + 5,
            top: activeRect.top - 20,
            fontSize: 14,
            fill: "red",
            selectable: false,
        });

        fabricCanvas.add(activeText);
        fabricCanvas.renderAll();

        activeRect = null;
    });

    // 📌 Click to select an annotation instead of creating new ones
    fabricCanvas.on("object:selected", (event) => {
        const selectedObject = event.target;
        if (!selectedObject) return;

        console.log(`Selected annotation: ${selectedObject.name}`);
    });

    // 📌 Allow deleting selected annotation with the "Delete" key
    document.addEventListener("keydown", (event) => {
        if (event.key === "Delete") {
            const selectedObject = fabricCanvas.getActiveObject();
            if (selectedObject) {
                fabricCanvas.remove(selectedObject);

                // Remove from annotations list
                annotations = annotations.filter((ann) => ann.field !== selectedObject.name);

                fabricCanvas.discardActiveObject();
                fabricCanvas.renderAll();
            }
        }
    });

    console.log("✅ Fabric.js initialized with selection and delete functionality");
}
async function saveTemplate() {
    console.log("Saving template...");

    let pdfFileInput = document.getElementById("templateFile");
    if (!pdfFileInput.files.length) {
        alert("No template selected!");
        return;
    }

    let pdfName = pdfFileInput.files[0].name;
    if (!annotations.length) {
        alert("No annotations made!");
        return;
    }

    // ✅ Ensure JSON structure matches the backend model
    let payload = {
        pdf_name: pdfName,
        annotations: annotations.map((ann) => ({
            field: ann.field,
            type: ann.type,
            x: Math.round(ann.x), // Ensure values are properly formatted
            y: Math.round(ann.y),
            width: Math.round(ann.width),
            height: Math.round(ann.height),
        })),
    };

    console.log("Payload being sent:", JSON.stringify(payload, null, 2)); // Debugging

    try {
        let response = await fetch("/templates/save/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        let result = await response.json();

        if (response.ok) {
            alert("Template saved successfully!");
        } else {
            alert(`Error saving template: ${result.message || "Unknown error"}`);
        }
    } catch (error) {
        console.error("Error saving template:", error);
        alert("Failed to save template. Check the console for details.");
    }
}

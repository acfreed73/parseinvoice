let annotations = []; // ✅ Global annotations array

document.addEventListener("DOMContentLoaded", () => {
    let extractedText = document.getElementById("extractedText");
    let annotationType = document.getElementById("annotationType");
    let addAnnotationBtn = document.getElementById("addAnnotation");
    let saveTemplateBtn = document.getElementById("saveTemplate");

    // ✅ Capture selected text from extracted text area
    extractedText.addEventListener("mouseup", () => {
        let selectedText = window.getSelection().toString().trim();
        document.getElementById("selectedText").value = selectedText;
    });

    // ✅ Add selected text as an annotation
    addAnnotationBtn.addEventListener("click", () => {
        let selectedText = document.getElementById("selectedText").value;
        let type = annotationType.value;

        if (!selectedText || !type) {
            alert("Select text and choose a type!");
            return;
        }

        let annotation = { text: selectedText, type };
        annotations.push(annotation); // ✅ Add to global array

        let listItem = document.createElement("li");
        listItem.textContent = `${selectedText} (${type})`;

        // ✅ Add remove button for each annotation
        let removeBtn = document.createElement("button");
        removeBtn.textContent = "❌";
        removeBtn.style.marginLeft = "10px";
        removeBtn.onclick = () => {
            annotations = annotations.filter(a => !(a.text === annotation.text && a.type === annotation.type));
            listItem.remove();
        };

        listItem.appendChild(removeBtn);
        document.getElementById("annotationsList").appendChild(listItem);
    });

    // ✅ Save annotations to YAML template
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
        } catch (error) {
            console.error("Error saving template:", error);
            alert("Failed to save template.");
        }
    });
});

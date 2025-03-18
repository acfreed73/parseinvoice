import React, { useState, useRef, useEffect } from "react";
import { pdfjs, Document, Page } from "react-pdf";
import "react-pdf/dist/esm/Page/TextLayer.css";
import "react-pdf/dist/esm/Page/AnnotationLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.js`;

const PdfAnnotator = ({ pdfUrl, onSave }) => {
    const [numPages, setNumPages] = useState(null);
    const [annotations, setAnnotations] = useState([]);
    const [selectedField, setSelectedField] = useState("");
    const [currentPage, setCurrentPage] = useState(1);
    const canvasRef = useRef(null);
    const [isDrawing, setIsDrawing] = useState(false);
    const [startPos, setStartPos] = useState(null);

    const handleMouseDown = (e) => {
        setIsDrawing(true);
        const rect = canvasRef.current.getBoundingClientRect();
        setStartPos({
            x: e.clientX - rect.left,
            y: e.clientY - rect.top,
        });
    };

    const handleMouseUp = (e) => {
        if (!isDrawing) return;
        setIsDrawing(false);
        const rect = canvasRef.current.getBoundingClientRect();
        const endPos = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top,
        };

        if (startPos) {
            const newAnnotation = {
                field: selectedField || `Field_${annotations.length + 1}`,
                page: currentPage,
                x: startPos.x,
                y: startPos.y,
                width: endPos.x - startPos.x,
                height: endPos.y - startPos.y,
            };

            setAnnotations([...annotations, newAnnotation]);
        }
    };

    const saveAnnotations = () => {
        onSave(annotations);
    };

    return (
        <div>
            <h3>Annotate PDF</h3>
            <input
                type="text"
                placeholder="Field Name"
                value={selectedField}
                onChange={(e) => setSelectedField(e.target.value)}
            />
            <Document file={pdfUrl} onLoadSuccess={({ numPages }) => setNumPages(numPages)}>
                <Page pageNumber={currentPage} width={600} />
                <canvas
                    ref={canvasRef}
                    className="annotation-layer"
                    onMouseDown={handleMouseDown}
                    onMouseUp={handleMouseUp}
                />
            </Document>
            <button onClick={saveAnnotations}>Save Template</button>
        </div>
    );
};

export default PdfAnnotator;

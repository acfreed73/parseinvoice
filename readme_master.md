# **ParseInvoice & Invoice2Data Deployment**

This project consists of two services:
1. **`parseinvoice`** – A FastAPI-based invoice processing server.
2. **`invoice2data`** – A background service for invoice data extraction.

Both services are containerized and can be deployed via **Docker Compose**.

---

## **📌 Prerequisites**
Before you begin, ensure you have the following installed:
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

---

## **🚀 Deployment Guide**

### **1️⃣ Clone the Repository**
```bash
git clone https://github.com/yourusername/parseinvoice.git
cd parseinvoice
```

### **2️⃣ Build and Start the Services**
```bash
docker-compose up -d --build
```
This will:
- Build and start the **`parseinvoice`** API server.
- Build and start the **`invoice2data`** service.

---

## **🔧 Configuration**
The services use the following **directory structure**:
```
parseinvoice/
│— data/
│   ├── pdfs/           # Store uploaded invoices
│   ├── templates/      # Custom invoice2data templates
│   └── output/         # Extracted JSON & CSV data
│— server/             # FastAPI application
│— Dockerfile.parseinvoice
│— Dockerfile.invoice2text
│— docker-compose.yml
│— requirements-server.txt
│— requirements-invoice2text.txt
│— README.md           # You're here
```

---

## **💼 Access the API**
Once running, the **`parseinvoice`** API will be available at:
- **FastAPI Docs:** [`http://localhost:8000/docs`](http://localhost:8000/docs)
- **Raw API Endpoint:** [`http://localhost:8000`](http://localhost:8000)

### **🛠 Available Endpoints**
| Method | Endpoint           | Description |
|--------|-------------------|-------------|
| `GET`  | `/`               | UI listing uploaded PDFs |
| `POST` | `/upload/`        | Upload a new invoice PDF |
| `POST` | `/process/`       | Process all invoices |
| `POST` | `/process/{file}` | Process a specific invoice |
| `GET`  | `/download/json/` | Download extracted data (JSON) |
| `GET`  | `/download/csv/`  | Download extracted data (CSV) |
| `POST` | `/reset/`         | Reset all invoices & database |
| `DELETE` | `/delete/{file}` | Delete a specific invoice |

---

## **💾 Persistent Data**
All uploaded files and processed data are **stored in `./data/`**:
- **PDFs go to** `data/pdfs/`
- **Extracted JSON/CSV files go to** `data/output/`
- **Templates go to** `data/templates/`

These are **mounted as volumes** in `docker-compose.yml` so that data persists across container restarts.

---

## **🚦 Stopping the Services**
To **stop** both services:
```bash
docker-compose down
```

To **restart**:
```bash
docker-compose up -d
```

---

## **🚀 Rebuilding & Updating**
If you update the source code, rebuild the containers with:
```bash
docker-compose up -d --build
```

---

## **🐛 Debugging**
Check logs for **parseinvoice**:
```bash
docker logs parseinvoice -f
```
Check logs for **invoice2data**:
```bash
docker logs invoice2data -f
```

Check running containers:
```bash
docker ps
```

Remove all stopped containers:
```bash
docker system prune -f
```

---

## **🗝️ Notes**
- **SQLITE3 is included** inside the containers for lightweight database storage.
- **Poppler & Invoice2Data** are installed for invoice text extraction.
- **Docker volumes** persist data, so you don’t lose invoices between restarts.

---

## **📌 Next Steps**
👉 **Deploy this to a private GitHub repository**  
👉 **Set up auto-builds in Docker Hub or GitHub Actions**  
👉 **Expand template support for more invoice formats**  

---

💡 **Questions? Contributions? Open an issue!** 🚀

---

### **🎯 TL;DR**
```bash
git clone https://github.com/yourusername/parseinvoice.git
cd parseinvoice
docker-compose up -d --build
```
👉 Upload invoices  
👉 Extract data  
👉 Download JSON/CSV  
👉 Fully automated! 🚀


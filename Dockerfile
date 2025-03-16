# Use the official Python image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Install required dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    python3-tk \
    nano \
    && rm -rf /var/lib/apt/lists/*

# Copy the project files into the container
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir .

# Create a symbolic link for invoice2data
RUN ln -s /usr/local/bin/invoice2data /usr/bin/invoice2data
ENV PATH="/usr/local/bin:${PATH}"

# Expose a port if needed (optional)
EXPOSE 80

# Run invoice2data when the container launches
ENTRYPOINT ["invoice2data"]

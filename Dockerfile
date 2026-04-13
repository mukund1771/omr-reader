FROM python:3.11-slim

# System libraries required by opencv-python-headless
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY geometry.py generate_sample_sheet.py scan_mark_sheet.py synthetic_scan_test.py ./

# Create runtime directories (overridden by volume mounts in docker-compose)
RUN mkdir -p output test_results scans

# Default: generate the answer sheet PDF + layout JSON into /app/output/
CMD ["python", "generate_sample_sheet.py"]

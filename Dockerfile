# ── What is a Dockerfile? ────────────────────────────────────────────
# It tells Docker: "here is exactly how to package my app"
# So the app runs the same way everywhere — your laptop, any server
# ─────────────────────────────────────────────────────────────────────

# Start with Python 3.11 (slim = smaller file size)
FROM python:3.11-slim

# Set the working folder inside the container
WORKDIR /app

# Copy requirements first (Docker caches this layer — faster rebuilds)
COPY requirements.txt .

# Install all Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code
COPY . .

# Create the ChromaDB folder (needs to exist before app starts)
RUN mkdir -p knowledge_base/chroma_db

# Streamlit runs on port 8501
EXPOSE 8501

# Start the app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

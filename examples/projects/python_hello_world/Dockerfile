# An official lightweight Python image, pinned by its multi-platform digest
FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534

# Set the working directory inside the container
WORKDIR /app

# Copy requirements first to leverage Docker's caching
COPY requirements.txt .

# Install pandas and its dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Command to run your script
CMD ["python", "main.py"]
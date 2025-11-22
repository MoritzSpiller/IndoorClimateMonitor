# Use a lightweight Python image compatible with Raspberry Pi (ARM)
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 5000 (Flask's default)
EXPOSE 5000

# Run the application
CMD ["python", "server.py"]
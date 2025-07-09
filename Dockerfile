# Use an official Python runtime as base image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy all project files to the working directory
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port (only needed if webhook server used)
EXPOSE 8080

# Command to run your app
CMD ["python", "main.py"]

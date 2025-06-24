# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that might be needed (e.g., for mysql-connector-python or other libraries)
# Example: RUN apt-get update && apt-get install -y default-libmysqlclient-dev gcc && rm -rf /var/lib/apt/lists/*
# For now, we'll assume mysql-connector-python wheels don't need extra system libs,
# but if there are build issues, this is the place to add them.

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Ensure the upload folder exists (if it's not created dynamically)
# RUN mkdir -p /app/static/media
# The UPLOAD_FOLDER in config.py is 'static/media', which should be relative to the app's root.
# If it's created by the app, this line might not be needed.
# For now, we assume the app or Flask handles its creation if needed.

# Expose the port the app runs on
# We'll use 8080 as per the default in config.py and common practice
EXPOSE 8080

# Define the command to run the application
# This will execute main.py which in turn starts the bot and the Flask admin panel
CMD ["python", "main.py"]

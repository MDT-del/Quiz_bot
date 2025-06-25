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

# Copy Gunicorn config file
COPY gunicorn.conf.py /app/gunicorn.conf.py

# Expose the port the app runs on (Gunicorn will listen on this port as defined in gunicorn.conf.py or CMD)
EXPOSE 8080

# Define the command to run the application using Gunicorn with the config file
# Gunicorn will look for an 'application' object in a module named 'wsgi' (wsgi.py)
# Settings like bind, workers, timeout are now primarily managed in gunicorn.conf.py
CMD ["gunicorn", "-c", "./gunicorn.conf.py", "wsgi:application"]

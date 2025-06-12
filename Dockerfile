# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies, including PHP and Composer
RUN apt-get update && apt-get install -y \
    unzip \
    git \
    curl \
    php \
    php-curl \
    php-mbstring \
    php-xml \
    && rm -rf /var/lib/apt/lists/*

# Install Composer (PHP package manager)
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Copy dependency files first to leverage Docker cache
COPY requirements.txt composer.json ./

# Install Python and PHP dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN composer install --no-dev --optimize-autoloader

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# The command to run when the container starts
# Gunicorn is a production-ready server for Python/WSGI applications
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "admin_panel:app"]

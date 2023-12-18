# Use an official Python runtime as a parent image
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir boto3 redis pillow requests numpy

# Copy the current directory contents into the container at /app
COPY app /app

# Specify the command to run on container start
CMD ["python3", "canvas_updater.py"]

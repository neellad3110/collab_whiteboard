# Step 1: Use an official Python runtime as a parent image
FROM python:3

# Step 2: Set environment variables for non-interactive installation
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Step 3: Set the working directory in the container
WORKDIR /app
COPY . /app

# Step 4: Copy the requirements.txt file into the container at /app
COPY requirements.txt /app/

# Step 5: Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Step 6: Copy the entire application (including static and templates) into the container
COPY . /app/

# Step 7: Expose port for Flask (default Flask port is 5000)
EXPOSE 5000

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
# CMD ["python", "app.py"]
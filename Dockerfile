# using a slim python image to keep things light
FROM python:3.11-slim

WORKDIR /app

# need some basic tools for building dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# copy and install the python libraries first to use docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy the rest of the project
COPY . .

# make sure the data folder exists for the sqlite database
RUN mkdir -p data

EXPOSE 8000

# start the fastapi server on port 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

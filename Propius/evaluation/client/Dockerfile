FROM python:3.9

# Set working directory
WORKDIR /

# Create necessary directories
RUN mkdir -p evaluation/job propius

# Copy required files
COPY ./evaluation/job/channels evaluation/job/channels
COPY ./evaluation/requirements_peripheral.txt evaluation/requirements_peripheral.txt
COPY ./propius propius
COPY ./evaluation/commons.py evaluation/commons.py

# Upgrade pip and install dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r evaluation/requirements_peripheral.txt

# Ensure NumPy compatibility
RUN pip install "numpy<2"

# Set entrypoint
ENTRYPOINT ["/evaluation/client/entrypoint.sh"]
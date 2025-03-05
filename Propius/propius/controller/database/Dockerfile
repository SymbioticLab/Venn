# Use the official Ubuntu image as the base image
FROM ubuntu:20.04

# Update and install necessary packages
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    lsb-release

# Add the Redis GPG key to /usr/share/keyrings
RUN curl -fsSL https://packages.redis.io/gpg | gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg

# Set proper permissions for the GPG key
RUN chmod 644 /usr/share/keyrings/redis-archive-keyring.gpg

# Add Redis repository to sources.list.d
RUN echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/redis.list

# Update again to refresh package lists with the new repository
RUN apt-get update

# Install Redis server
RUN apt-get install -y redis-stack-server

COPY ./propius/controller/database/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh 

# Start the Redis server when the container starts
ENTRYPOINT ["/entrypoint.sh"]
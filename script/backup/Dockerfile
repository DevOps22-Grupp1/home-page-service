FROM mongo
WORKDIR /opt/backup/
# Create app directory
WORKDIR /usr/src/configs

# Install app dependencies
COPY dump.sh .
RUN chmod +x dump.sh
COPY restore.sh .
RUN chmod +x restore.sh
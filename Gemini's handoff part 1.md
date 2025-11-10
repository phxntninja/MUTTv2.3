MUTT (Moog/Monitoring Universal-Translation-Toolkit) Project Overview

This document provides a complete overview of the MUTT project, its architecture, configuration, and components. It is intended to be used by a developer or AI assistant to understand the system and continue development.

1. Project Objective

MUTT (Moog/Monitoring Universal-Translation-Toolkit) is a middleware solution built in Python. Its primary purpose is to decouple the SolarWinds monitoring platform from the Moogsoft AIOps platform.

It achieves this by:

Receiving alerts from SolarWinds via a simple webhook (the "Alerter Service").

Normalizing the incoming alert data into a standardized format.

Deduplicating alerts in-memory to reduce noise.

Buffering all alerts in a robust Redis queue.

Forwarding the buffered alerts reliably to the Moogsoft API (the "Moog Forwarder Service").

This architecture prevents alert loss during Moogsoft maintenance, provides a "poison pill" queue for bad alerts, and makes the entire pipeline more resilient and easier to monitor.

2. System Architecture

The data flow is a simple, resilient pipeline:

SolarWinds (or any source) sends an HTTP POST (webhook) to the Alerter Service.

Alerter Service (services/alerter_service.py):

Validates and normalizes the JSON payload.

Performs in-memory deduplication based on a time window.

Pushes the normalized alert string onto the alert_queue in Redis.

Redis:

alert_queue: The main buffer for alerts waiting for Moogsoft.

dlq (Dead Letter Queue): Stores "poison pill" alerts that fail processing.

processing_list: A temporary list for alerts the Forwarder is actively processing.

Moog Forwarder Service (moog_forwarder_service.py):

Pops an alert from alert_queue and places it in processing_list.

Attempts to POST the alert to the Moogsoft API.

On success, removes the alert from processing_list.

On failure, moves the alert to the dlq and removes it from processing_list.

Moogsoft API:

Receives the normalized alert.

Web UI Service (web_ui_service.py):

A simple Flask app that reads Redis queue depths (alert_queue, dlq).

Exposes a /metrics endpoint for Prometheus monitoring.

3. Handoff File Index

This project is documented across the following files:

MUTT_Project_Overview.md (This file): High-level goals, architecture, and configuration.

MUTT_Alerter_Service.md: Contains the complete source code for services/alerter_service.py.

MUTT_Moog_Forwarder_Service.md: Contains the complete source code for moog_forwarder_service.py.

MUTT_Web_UI_Service.md: Contains the complete source code for web_ui_service.py.

4. Configuration (config.ini)

This file contains non-sensitive configuration for all services.

#
# MUTT Project Configuration File
#
# This file contains non-sensitive settings for all services.
#

[Redis]
# Hostname for the Redis server
Host = redis
# Port for the Redis server
Port = 6379
# Database number to use
DB = 0
# Main queue for alerts pending processing
AlertQueue = alert_queue
# Dead-letter queue for alerts that fail processing (poison pills)
DLQ = dlq
# List for alerts actively being processed by the forwarder
ProcessingList = processing_list
# Prefix for in-memory deduplication keys
DedupKeyPrefix = dedup_
# Deduplication window in seconds (e.g., 300 = 5 minutes)
DedupSeconds = 300

[AlerterService]
# Host for the alerter webhook listener
Host = 0.0.0.0
# Port for the alerter webhook listener
Port = 8080
# Max JSON payload size (in bytes)
MaxContentLength = 16777216
# Log file path
LogFile = /var/log/mutt/alerter.log
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LogLevel = INFO
# Length of alert preview in logs
MessagePreviewLength = 200

[MoogForwarderService]
# API endpoint for Moogsoft
MoogApiUrl = [https://api.moogsoft.ai/v1/alerts](https://api.moogsoft.ai/v1/alerts)
# Connection timeout for Moogsoft API (in seconds)
ConnectTimeout = 5
# Read timeout for Moogsoft API (in seconds)
ReadTimeout = 10
# Number of worker threads to run
WorkerThreads = 5
# Log file path
LogFile = /var/log/mutt/forwarder.log
# Log level
LogLevel = INFO
# Length of alert preview in logs
MessagePreviewLength = 200

[WebUIService]
# Host for the monitoring web UI
Host = 0.0.0.0
# Port for the monitoring web UI
Port = 8081
# Log file path
LogFile = /var/log/mutt/webui.log
# Log level
LogLevel = INFO


5. Secrets (secrets.ini)

This file contains sensitive credentials. It should never be checked into source control.

#
# MUTT Project Secrets File
#
# This file contains sensitive credentials and API keys.
# DO NOT commit this file to source control.
#

[Redis]
# Password for Redis (if any). Leave blank for no password.
Password =

[MoogForwarderService]
# API Key for the Moogsoft API
MoogApiKey = YOUR_MOOGSOFT_API_KEY_HERE


6. Dependencies (requirements.txt)

This file lists all required Python libraries.

# Python Dependencies for MUTT Project

# Redis client
redis

# Web server for Alerter and WebUI services
Flask
gunicorn

# HTTP client for Moog Forwarder
requests

# Prometheus client for monitoring
prometheus-client


7. Deployment (docker-compose.yml)

This file defines the services for deployment using Docker Compose.

#
# Docker Compose file for MUTT Project
#
version: '3.7'

services:
  
  redis:
    image: redis:6-alpine
    container_name: mutt-redis
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped
    # Uncomment the command line if you set a password in secrets.ini
    # command: redis-server --requirepass YOUR_REDIS_PASSWORD_HERE

  alerter_service:
    build:
      context: ./alerter_service
      dockerfile: Dockerfile
    container_name: mutt-alerter
    ports:
      - "8080:8080"
    volumes:
      - ./config/config.ini:/app/config/config.ini:ro
      - ./config/secrets.ini:/app/config/secrets.ini:ro
      - mutt_logs:/var/log/mutt
    depends_on:
      - redis
    restart: unless-stopped

  moog_forwarder_service:
    build:
      context: ./moog_forwarder_service
      dockerfile: Dockerfile
    container_name: mutt-forwarder
    volumes:
      - ./config/config.ini:/app/config/config.ini:ro
      - ./config/secrets.ini:/app/config/secrets.ini:ro
      - mutt_logs:/var/log/mutt
    depends_on:
      - redis
    restart: unless-stopped

  web_ui_service:
    build:
      context: ./web_ui_service
      dockerfile: Dockerfile
    container_name: mutt-webui
    ports:
      - "8888:8081" # Expose UI on host port 8888
    volumes:
      - ./config/config.ini:/app/config/config.ini:ro
      - ./config/secrets.ini:/app/config/secrets.ini:ro
      - mutt_logs:/var/log/mutt
    depends_on:
      - redis
    restart: unless-stopped

volumes:
  redis_data:
  mutt_logs:

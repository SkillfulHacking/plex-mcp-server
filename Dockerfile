FROM python:3.11-slim
WORKDIR /app
# Install system git only if you clone at build time; omit if you COPY the repo
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy your forked repo into the image
COPY . /app

# Install deps
RUN python -m pip install -U pip && pip install --no-cache-dir -r requirements.txt

# Defaults; override with env or compose
ENV PLEX_URL=http://127.0.0.1:32400
ENV PLEX_TOKEN=changeme

# Start the MCP server over SSE
CMD ["python","plex_mcp_server.py","--transport","sse","--host","0.0.0.0","--port","3001"]

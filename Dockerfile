# Long-running API (keeps the in-memory HITL gate between requests). `docker build -t taxsetu-api . && docker run -p 8000:8000 -e HITL_SIGNING_SECRET=... taxsetu-api`
FROM python:3.12-slim
WORKDIR /app
COPY packages packages
COPY apps apps
RUN pip install --no-cache-dir fastapi "pydantic>=2" uvicorn \
    -e packages/deterministic-tax-engine -e packages/mcp-servers -e packages/agents -e apps/api-gateway \
 && useradd -m app
USER app
ENV PORT=8000
EXPOSE 8000
CMD uvicorn --factory taxsetu_api.main:create_app --host 0.0.0.0 --port $PORT

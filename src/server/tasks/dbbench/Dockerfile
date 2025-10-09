FROM python:3.10

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ./src/server/tasks/dbbench/requirements.txt /app/src/server/tasks/dbbench/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    python -m pip install \
      agentrl-worker \
      -r ./src/server/tasks/dbbench/requirements.txt

COPY ./src/server/tasks/dbbench /app/src/server/tasks/dbbench
COPY ./configs/tasks/dbbench.yaml /app/configs/tasks/dbbench.yaml
COPY ./data/dbbench /app/data/dbbench

COPY --chmod=0755 ./extra/worker-entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh", "-c", "configs/tasks/dbbench.yaml"]

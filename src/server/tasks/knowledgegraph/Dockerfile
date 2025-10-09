FROM python:3.10

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ./src/server/tasks/knowledgegraph/requirements.txt /app/src/server/tasks/knowledgegraph/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    python -m pip install \
      agentrl-worker \
      -r ./src/server/tasks/knowledgegraph/requirements.txt

COPY ./src/server/tasks/knowledgegraph /app/src/server/tasks/knowledgegraph
COPY ./configs/tasks/kg.yaml /app/configs/tasks/kg.yaml
COPY ./data/knowledgegraph /app/data/knowledgegraph

COPY --chmod=0755 ./extra/worker-entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh", "-c", "configs/tasks/kg.yaml"]

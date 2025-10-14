FROM --platform=$BUILDPLATFORM alpine:3.22.0 AS data-downloader

RUN apk add --no-cache curl unzip

ENV DATA_DIR=/data

WORKDIR $DATA_DIR

RUN curl -L -o json_2.1.1_json.zip https://github.com/alfworld/alfworld/releases/download/0.2.2/json_2.1.1_json.zip && \
    unzip json_2.1.1_json.zip -d $DATA_DIR && \
    rm json_2.1.1_json.zip

RUN curl -L -o json_2.1.1_pddl.zip https://github.com/alfworld/alfworld/releases/download/0.2.2/json_2.1.1_pddl.zip && \
    unzip json_2.1.1_pddl.zip -d $DATA_DIR && \
    rm json_2.1.1_pddl.zip

RUN curl -L -o json_2.1.1_tw-pddl.zip https://github.com/alfworld/alfworld/releases/download/0.2.2/json_2.1.1_tw-pddl.zip && \
    unzip json_2.1.1_tw-pddl.zip -d $DATA_DIR && \
    rm json_2.1.1_tw-pddl.zip

FROM python:3.9-bookworm AS worker

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y build-essential cmake libgl1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ADD https://github.com/alfworld/alfworld.git#a5d3476e65e3effc2ac9b7f2493979ba6794e2a6 /usr/src/alfworld
RUN --mount=type=cache,target=/root/.cache/pip \
    sed -i '/numpy/d' /usr/src/alfworld/requirements.txt && \
    sed -i '/torch/d' /usr/src/alfworld/requirements.txt && \
    sed -i '/transformers/d' /usr/src/alfworld/requirements.txt && \
    echo "blis<=1.2.0" >> /usr/src/alfworld/requirements.txt && \
    echo "jsonlines" >> /usr/src/alfworld/requirements.txt && \
    echo "numpy<2.0" >> /usr/src/alfworld/requirements.txt && \
    echo "torch<2.0" >> /usr/src/alfworld/requirements.txt && \
    echo "torchvision<0.15" >> /usr/src/alfworld/requirements.txt && \
    echo "transformers<4.48.0" >> /usr/src/alfworld/requirements.txt && \
    echo "Werkzeug<3.0" >> /usr/src/alfworld/requirements.txt && \
    python -m pip install --upgrade pip && \
    python -m pip install \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      agentrl-worker \
      -r /usr/src/alfworld/requirements.txt \
      /usr/src/alfworld

ENV ALFWORLD_DATA=/app/data/alfworld
COPY --from=data-downloader /data /app/data/alfworld

COPY ./src/server/tasks/alfworld /app/src/server/tasks/alfworld
COPY ./configs/tasks/alfworld.yaml /app/configs/tasks/alfworld.yaml
COPY ./data/alfworld /app/data/alfworld

COPY --chmod=0755 ./extra/worker-entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh", "-c", "configs/tasks/alfworld.yaml"]

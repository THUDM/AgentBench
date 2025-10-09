FROM --platform=$BUILDPLATFORM python:slim AS data-downloader

ENV PYTHONUNBUFFERED=1

WORKDIR /data

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install \
      --index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple \
      --upgrade pip && \
    python -m pip install \
      --index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple \
      gdown

RUN gdown https://drive.google.com/uc?id=1A2whVgOO0euk5O13n2iYDM0bQRkkRduB
RUN gdown https://drive.google.com/uc?id=1s2j6NgHljiZzQNL3veZaAiyW_qDEgBNi
RUN gdown https://drive.google.com/uc?id=14Kb5SPBk_jfdLZ_CDBNitW98QLDlKR5O

FROM python:3.9-bullseye AS worker

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TQDM_DISABLE=1

WORKDIR /app

ADD https://github.com/princeton-nlp/WebShop.git#64fa2a5c15c7daa698b9ac93f5bb5437b634c9bd /usr/src/webshop
# change the following line based on which method is available
# COPY --from=data-downloader /data /app/src/server/tasks/webshop/data
COPY --from=longinyu/agentbench-webshop:latest /root/webshop/data /usr/src/webshop/data

RUN apt-get update && \
    apt-get install -y git openjdk-11-jdk-headless && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY ./src/server/tasks/webshop/requirements.txt /app/src/server/tasks/webshop/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    python -m pip install \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      -r /app/src/server/tasks/webshop/requirements.txt \
      agentrl-worker && \
    python -m spacy download en_core_web_sm && \
    python -m spacy download en_core_web_lg

ENV PYTHONPATH="/usr/src/webshop"

COPY ./src/server/tasks/webshop/webshop.patch /tmp/webshop.patch
RUN cd /usr/src/webshop && \
    git apply --check /tmp/webshop.patch && \
    git apply /tmp/webshop.patch && \
    rm /tmp/webshop.patch && \
    cd /usr/src/webshop/search_engine && \
    mkdir -p resources indexes && \
    python convert_product_file_format.py && \
    bash run_indexing.sh

COPY ./src/server/tasks/webshop /app/src/server/tasks/webshop
COPY ./configs/tasks/webshop.yaml /app/configs/tasks/webshop.yaml

COPY --chmod=0755 ./extra/worker-entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh", "-c", "configs/tasks/webshop.yaml"]

#!/bin/bash

SOURCE_NAMES=("leixy20/alfworld:v1.0" "docker.io/foreverpiano/card_game:v3" "mkw18/lateralthinkingpuzzle:latest" "capco707/mind2web-dev:v0" "zhc7/webshop:0.7.0")
TARGET_NAMES=("localhost/task:alfworld" "localhost/task:card_game" "localhost/task:ltp" "localhost/task:mind2web" "localhost/task:webshop")
TEMP_DOCKERFILE_NAME=".dockerfile-cache/.dockerfile"
TEMP_DOCKERFILE_DIRNAME=$(dirname $TEMP_DOCKERFILE_NAME)
mkdir -p $TEMP_DOCKERFILE_DIRNAME
cp "requirements.txt" $TEMP_DOCKERFILE_DIRNAME

for ((i=0; i<${#SOURCE_NAMES[@]}; i++)); do
    # print in cyan
    echo ""
    echo -e "\033[36mBUIDING:  ${SOURCE_NAMES[i]}  ==>  ${TARGET_NAMES[i]}\033[0m"
    echo ""
    echo "FROM ${SOURCE_NAMES[i]}" > $TEMP_DOCKERFILE_NAME
    echo "COPY requirements.txt /root/.tmpdir/" >> $TEMP_DOCKERFILE_NAME
    echo "RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && pip install -r /root/.tmpdir/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple" >> $TEMP_DOCKERFILE_NAME
    docker build -t ${TARGET_NAMES[i]} -f $TEMP_DOCKERFILE_NAME $TEMP_DOCKERFILE_DIRNAME
done

rm -rf $TEMP_DOCKERFILE_DIRNAME
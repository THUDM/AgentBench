#!/bin/bash

function evaluate_directly() {
    echo "Evaluating Directly, Parameters: $*"
    python eval.py $*
}

function evaluate_in_docker() {
    DOCKER_IMAGE=$1
    shift
    echo "Evaluating in docker $DOCKER_IMAGE, Parameters: $*"
    docker run -it --rm --network host -v $(pwd):/root/workspace -w /root/workspace $DOCKER_IMAGE \
        bash -c "
            umask 0
            [ -f /root/.setup.sh ] && bash /root/.setup.sh
            python eval.py $*
        "
}

function get_min() {
  if [ "$1" -lt "$2" ]; then
    echo "$1"
  else
    echo "$2"
  fi
}

function check_and_append_suffix() {
  local dir="$1"
  local count=1
  local new_dir="${dir}"

  while [[ -d "${new_dir}" ]]; do
    new_dir="${dir}-$(printf '%04d' "${count}")"
    count=$((count + 1))
  done
  echo "${new_dir}"
}
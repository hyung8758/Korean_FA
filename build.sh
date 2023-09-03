#!/bin/bash
# this script build a korean_fa docker image 
#
# Hyungwon Yang
# 23.09.03


IMAGE_NAME=koreanfa
DOCKER_PATH=./docker/dockerfile
SOURCE_PATH=. # only if you are in Korean_FA directory.

# please adjust parameters based on your OS setting.
USE_BUILDX=false # true if use buildx
USE_SUDO=false # true if needs to use sudo
USE_CACHE=false # false if you want to rebuild it from the beginning.

option=""
docker_cmd=

# sudo user.
if $USE_SUDO; then
    docker_cmd+="sudo "; fi
# use buildx?
if $USE_BUILDX; then
    docker_cmd+="docker buildx build "
else
    docker_cmd+="docker build "; fi
# use chahe?
if ! $USE_CACHE; then
    docker_cmd+="--no-cache "; fi
# add option if exists.
docker_cmd+=$option" "
# add image name, dockerfile path, and path directory.
docker_cmd+="-t $IMAGE_NAME -f $DOCKER_PATH $SOURCE_PATH"
# build an image.
echo "build command: $docker_cmd"
$docker_cmd
#!/bin/bash
# this script build a korean_fa docker image 
#
# Hyungwon Yang
# 23.09.03


IMAGE_NAME=korean_fa_app
DOCKER_PATH=./docker/dockerfile
SOURCE_PATH=. # only if you are in Korean_FA directory.

# please adjust parameters based on your OS setting.
USE_BUILDX=false # true if use buildx
USE_SUDO=false # true if needs to use sudo
USE_CACHE=true # false if you want to rebuild it from the beginning.

option=
sudo_cmd=

if $USE_SUDO; then
    sudo_cmd=sudo; fi
if ! $USE_CACHE; then
    option+="--no-cache"; fi

if $USE_BUILDX; then
    # buildx
    $sudo_cmd docker buildx build  $option -t $IMAGE_NAME -f $DOCKER_PATH $SOURCE_PATH
else
    # default build command
    $sudo_cmd docker build $option -t $IMAGE_NAME $DOCKER_PATH $SOURCE_PATH
fi
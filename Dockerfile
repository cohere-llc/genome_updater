FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    build-essential \
    parallel \
    wget \
    curl \
    python3 \
    python3-pip \
    bc \
    locales \
    lftp \
    gawk

# Configure wget for passive FTP mode
RUN echo "passive_ftp = on" >> /etc/wgetrc && \
    echo "timeout = 120" >> /etc/wgetrc && \
    echo "tries = 5" >> /etc/wgetrc && \
    echo "prefer-family = IPv4" >> /etc/wgetrc

# Configure curl for passive FTP mode
RUN echo "--ftp-pasv" >> ~/.curlrc && \
    echo "--retry 5" >> ~/.curlrc && \
    echo "--retry-delay 2" >> ~/.curlrc && \
    echo "--connect-timeout 120" >> ~/.curlrc

RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

COPY . /genome_updater

WORKDIR /genome_updater

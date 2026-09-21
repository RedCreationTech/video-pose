# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}

ARG DEBIAN_FRONTEND=noninteractive
ARG VIDEO_POSE_EXTRAS=api,db,video,yolo,gstreamer-native

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:${PATH} \
    XDG_CACHE_HOME=/var/cache/video-pose \
    YOLO_CONFIG_DIR=/var/cache/video-pose/ultralytics

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        gir1.2-gstreamer-1.0 \
        gir1.2-gst-plugins-base-1.0 \
        gstreamer1.0-libav \
        gstreamer1.0-plugins-bad \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-ugly \
        gstreamer1.0-tools \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        python3 \
        python3-gi \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv --system-site-packages /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade \
        pip setuptools wheel

WORKDIR /opt/video-pose

COPY pyproject.toml README.org alembic.ini ./
COPY src ./src
COPY migrations ./migrations
COPY deploy/edge/entrypoint.sh /usr/local/bin/video-pose-entrypoint

RUN /opt/venv/bin/pip install --no-cache-dir \
        ".[${VIDEO_POSE_EXTRAS}]" \
    && chmod 0755 /usr/local/bin/video-pose-entrypoint \
    && useradd --system --uid 10001 --create-home \
        --home-dir /var/cache/video-pose video-pose \
    && mkdir -p \
        /var/lib/video-pose/audit \
        /var/lib/video-pose/evidence \
        /var/cache/video-pose/ultralytics \
    && chown -R video-pose:video-pose \
        /var/lib/video-pose \
        /var/cache/video-pose

USER 10001:10001

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/video-pose-entrypoint"]

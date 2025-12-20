FROM debian:bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        findutils \
        git \
        iproute2 \
        net-tools \
        procps \
        util-linux \
        python3 \
        python3-pip \
        python3-venv \
        build-essential \
        autoconf \
        automake \
        libtool \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN chmod +x /app/sh/vps-audit.sh

CMD ["bash"]

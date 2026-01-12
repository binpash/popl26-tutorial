FROM ubuntu:latest

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
        bsdextrautils \
        attr \
        mergerfs \
        python3 \
        python3-pip \
        python3-venv \
        build-essential \
        autoconf \
        automake \
        libtool \
        nano \
        vim \
        emacs
        
COPY requirements.txt /app/requirements.txt
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:/app/bin:$PATH"
ENV LC_ALL=C
ENV IFS=" \t\n"
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

CMD ["bash"]

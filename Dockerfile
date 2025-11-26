# Build a virtualenv using the appropriate Debian release:
FROM debian:12

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Singapore \
    VIRTUAL_ENV=/venv \
    PATH="/venv/bin:$PATH" \
    PYTHONPATH="/experiment"

# Install base packages and create the virtualenv.
RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        python3-venv \
        gcc \
        libpython3-dev \
        git \
        apt-transport-https \
        ca-certificates \
        gnupg \
        curl \
        wget2 \
        clang-format && \
    python3 -m venv /venv

# Configure Google Cloud SDK repository via keyring.
RUN install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
        gpg --dearmor -o /etc/apt/keyrings/google-cloud-sdk.gpg && \
    chmod 0644 /etc/apt/keyrings/google-cloud-sdk.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/google-cloud-sdk.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
        > /etc/apt/sources.list.d/google-cloud-sdk.list

# Install Docker CLI (talking to host daemon) and Google Cloud CLI.
RUN install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install --no-install-recommends --yes \
        google-cloud-cli \
        docker-ce-cli \
        docker-buildx-plugin \
        docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /experiment

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY . .

# ENTRYPOINT ["python3", "./report/docker_run.py"]

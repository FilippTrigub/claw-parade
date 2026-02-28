# ── extra builders ────────────────────────────────────────────────────
FROM golang:1.25-alpine AS go-builder
RUN apk add --no-cache git

# wacli
WORKDIR /build/wacli
RUN git clone https://github.com/steipete/wacli.git . && \
    go build -o wacli ./cmd/wacli

# camsnap (RTSP/ONVIF camera snapshots)
WORKDIR /build/camsnap
RUN git clone https://github.com/steipete/camsnap.git . && \
    go build -o camsnap ./cmd/camsnap

# obsidian-cli (notesmd-cli — interact with Obsidian vaults)
WORKDIR /build/obsidian-cli
RUN git clone https://github.com/yakitrak/notesmd-cli.git . && \
    go build -o obsidian-cli .

# ── extend upstream image (build with: make build-base first) ─────────
FROM alpine/openclaw:latest

USER root

# Go runtime
ARG GO_VERSION=1.23.5
RUN curl -fsSL https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz -o /tmp/go.tar.gz && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && \
    rm /tmp/go.tar.gz

# apt packages: jq, tmux, ffmpeg, gh
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        | tee /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends jq tmux ffmpeg gh ripgrep && \
    rm -rf /var/lib/apt/lists/*

# Go-built binaries
COPY --from=go-builder /build/wacli/wacli         /usr/local/bin/wacli
COPY --from=go-builder /build/camsnap/camsnap      /usr/local/bin/camsnap
COPY --from=go-builder /build/obsidian-cli/obsidian-cli /usr/local/bin/obsidian-cli
RUN chmod +x /usr/local/bin/wacli /usr/local/bin/camsnap /usr/local/bin/obsidian-cli

USER root

# npm global packages
RUN npm install -g clawhub

USER node

# git identity + credential helper — uses GH_TOKEN at runtime via gh
RUN git config --global user.name "FilippTrigub" && \
    git config --global user.email "filipp.trigub@gmail.com" && \
    git config --global credential.https://github.com.helper '!gh auth git-credential' && \
    git config --global init.defaultBranch main

# uv (Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

USER root

# Install dependencies for Homebrew (needs root)
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential \
        procps \
        file \
        git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Homebrew (for skill installations)
# Install to /home/node/.linuxbrew so the node user owns it
RUN mkdir -p /home/node/.linuxbrew && \
    chown -R node:node /home/node/.linuxbrew

USER node
ENV HOMEBREW_PREFIX="/home/node/.linuxbrew"
RUN git clone https://github.com/Homebrew/brew ${HOMEBREW_PREFIX}/Homebrew && \
    mkdir -p ${HOMEBREW_PREFIX}/bin && \
    ln -s ${HOMEBREW_PREFIX}/Homebrew/bin/brew ${HOMEBREW_PREFIX}/bin/brew

USER root
RUN echo 'eval "$(/home/node/.linuxbrew/bin/brew shellenv)"' >> /etc/profile.d/brew.sh && \
    chmod 755 /etc/profile.d/brew.sh

# Install gogcli (Google OAuth CLI for Gmail skills)
RUN curl -fsSL https://github.com/steipete/gogcli/releases/download/v0.11.0/gogcli_0.11.0_linux_amd64.tar.gz | \
    tar xz -C /usr/local/bin gog && \
    chmod +x /usr/local/bin/gog

ENV GOPATH="/home/node/go"
ENV GOBIN="/home/node/go/bin"
RUN mkdir -p ${GOPATH}/bin ${GOBIN}

# Set up pnpm global bin directory
ENV PNPM_HOME="/home/node/.local/share/pnpm"
ENV PATH="${PNPM_HOME}:${PATH}"
RUN mkdir -p ${PNPM_HOME} && \
    pnpm config set global-bin-dir ${PNPM_HOME} && \
    pnpm config set global-dir /home/node/.local/share/pnpm/global

# Add Homebrew to PATH for the node user
ENV PATH="/home/node/.linuxbrew/bin:/usr/local/go/bin:${GOBIN}:/home/node/.local/bin:${PATH}"

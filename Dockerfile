FROM ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake swig python3 python3-dev python3-pip git \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/sa-pcb
COPY . .
RUN if [ -d .git ]; then git submodule update --init --recursive; fi

RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release || true
RUN cmake --build build -j"$(nproc)" || true

FROM ubuntu:24.04 AS runner

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip \
    libboost-program-options1.83.0 libboost-system1.83.0 libboost-filesystem1.83.0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/sa-pcb
COPY --from=builder /opt/sa-pcb /opt/sa-pcb
RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["python3", "src/py_utils/multistart.py", "--help"]

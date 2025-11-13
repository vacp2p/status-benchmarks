FROM debian:12-slim

RUN apt-get update && apt-get install -y curl wget python3 python3-pip python3-venv openssh-server iputils-ping net-tools screen parallel \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /run/sshd /root/.ssh && chmod 0755 /run/sshd && chmod 700 /root/.ssh

RUN pip3 install --break-system-packages --upgrade pip
RUN pip3 install --break-system-packages requests websocket-client kubernetes

RUN wget https://github.com/<your_github_handle>.keys -O /root/.ssh/authorized_keys \
    && chmod 600 /root/.ssh/authorized_keys

CMD ["/bin/sleep", "infinity"]

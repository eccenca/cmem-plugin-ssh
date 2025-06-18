FROM debian:bullseye

RUN apt-get update && apt-get install -y openssh-server sudo && rm -rf /var/lib/apt/lists/*

RUN useradd -m testuser && echo 'testuser:testpassword' | chpasswd && echo 'testuser ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

RUN mkdir /var/run/sshd && \
    mkdir -p /home/testuser/.ssh && \
    chmod 700 /home/testuser/.ssh

COPY authorized_keys /home/testuser/.ssh/authorized_keys

RUN chown -R testuser:testuser /home/testuser/.ssh && \
    chmod 600 /home/testuser/.ssh/authorized_keys && \
    sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    echo "PermitRootLogin no" >> /etc/ssh/sshd_config && \
    echo "AllowUsers testuser" >> /etc/ssh/sshd_config

RUN mkdir /restricted && \
    chmod 700 /restricted && \
    chown root:root /restricted

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
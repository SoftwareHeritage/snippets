FROM structurizr/lite

ARG UID
ARG GID

RUN groupadd -g $GID structurizr && useradd -d /usr/local/structurizr -g $GID -u $UID structurizr

USER structurizr

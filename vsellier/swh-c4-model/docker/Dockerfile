FROM structurizr/lite

ARG UID
ARG GID

RUN if [ "$GID" -ne 1000 ]; then groupadd -g $GID structurizr; fi
RUN if [ "$UID" -ne 1000 ]; then useradd -d /usr/local/structurizr -g $GID -u $UID structurizr; fi

USER $UID

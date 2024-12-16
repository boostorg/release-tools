FROM ubuntu:noble
LABEL maintainer="samuel.d.darwin@gmail.com"

WORKDIR /root
RUN mkdir -p /tmp/build
COPY requirements.txt /tmp/build/requirements.txt
COPY Gemfile /tmp/build/Gemfile
ARG GH_CLI_VERSION=2.63.2
ARG RCLONE_VERSION=1.68.2
ARG DOXYGEN_VERSION=1_12_0

RUN set -xe \
    && apt-get update \
    && DEBIAN_FRONTEND="noninteractive" apt-get install -y tzdata \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y locales \
    && apt-get install -y \
        apt-transport-https \
        bison \
        ca-certificates \
        clang \
        cmake \
        curl \
        default-jre-headless \
        docbook \
        docbook-xml \
        docbook-xsl \
        docutils-common \
        docutils-doc \
        dos2unix \
        flex \
        ghostscript \
        git \
        graphviz \
        jq \
        libsaxonhe-java \
        openssh-client \
        openssl libssl-dev \
        p7zip-full  \
        python-is-python3 \
        python3-pip \
        python3-venv \
        rsync \
        ruby \
        software-properties-common \
        sshpass \
        sudo \
        texlive \
        texlive-latex-extra \
        unzip \
        vim \
        wget \
        xsltproc \
    && sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG=en_US.UTF-8 \
    && python3 -m venv /opt/venvboostdocs \
    && export PATH=/opt/venvboostdocs/bin:$PATH \
    && mkdir /tmp/aws_cli_install && cd /tmp/aws_cli_install && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && unzip awscliv2.zip && ./aws/install && cd /root && rm -rf /tmp/aws_cli_install \
    && mkdir /tmp/rclone_install && cd /tmp/rclone_install && wget https://downloads.rclone.org/v${RCLONE_VERSION}/rclone-v${RCLONE_VERSION}-linux-amd64.deb && dpkg -i rclone-v${RCLONE_VERSION}-linux-amd64.deb && cd /root && rm -rf /tmp/rclone_install \
    && curl -s -S --retry 10 -L -o gh_${GH_CLI_VERSION}_linux_amd64.deb https://github.com/cli/cli/releases/download/v${GH_CLI_VERSION}/gh_${GH_CLI_VERSION}_linux_amd64.deb \
    && dpkg -i gh_${GH_CLI_VERSION}_linux_amd64.deb \
    && git clone -b "Release_${DOXYGEN_VERSION}" --depth 1 https://github.com/doxygen/doxygen.git \
    && cd doxygen \
    && cmake -H. -Bbuild -DCMAKE_BUILD_TYPE=Release \
    && cd build \
    && make install \
    && cd && rm -rf doxygen* \
    && curl -s -S --retry 10 -L -o saxonhe.zip https://sourceforge.net/projects/saxon/files/Saxon-HE/9.9/SaxonHE9-9-1-4J.zip/download \
    && unzip saxonhe.zip \
    && rm /usr/share/java/Saxon-HE.jar \
    && cp saxon9he.jar /usr/share/java/Saxon-HE.jar \
    && rm -r * \
    && mkdir -p build && cd build \
    && gem install bundler \
    && pip3 install -r /tmp/build/requirements.txt \
    && bundle install --gemfile=/tmp/build/Gemfile \
    && curl -s -S --retry 10 -L -o rapidxml.zip http://sourceforge.net/projects/rapidxml/files/latest/download \
    && unzip -n -d rapidxml rapidxml.zip \
    && curl -s -S --retry 10 -L -o docbook-xml.zip http://www.docbook.org/xml/4.5/docbook-xml-4.5.zip \
    && unzip -n -d docbook-xml docbook-xml.zip \
    && curl -s -S --retry 10 -L -o docbook-xsl.zip https://sourceforge.net/projects/docbook/files/docbook-xsl/1.79.1/docbook-xsl-1.79.1.zip/download \
    && unzip -n -d docbook-xsl docbook-xsl.zip \
    && chmod -R 777 /opt/venvboostdocs \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean -y

ENV PATH /opt/venvboostdocs/bin:$PATH
ENV NODE_VERSION=18.18.1
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
ENV NVM_DIR=/root/.nvm
RUN . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION}
RUN . "$NVM_DIR/nvm.sh" && nvm use v${NODE_VERSION}
RUN . "$NVM_DIR/nvm.sh" && nvm alias default v${NODE_VERSION}
ENV PATH="/root/.nvm/versions/node/v${NODE_VERSION}/bin/:${PATH}"
RUN node --version
RUN npm --version
RUN npm install -g gulp-cli@2.3.0
RUN npm install -g @mermaid-js/mermaid-cli@10.5.1
# For other CI jobs:
RUN groupadd -g 150 jenkins
RUN useradd jenkins -u 150 -g 150 -m -s /bin/bash
RUN echo "ALL ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/all
ENV LC_ALL en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8

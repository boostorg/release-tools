FROM ubuntu:focal
LABEL maintainer="samuel.d.darwin@gmail.com"

WORKDIR /root

RUN apt-get update \
    && DEBIAN_FRONTEND="noninteractive" apt-get install -y tzdata \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y locales \
    && apt-get install -y \
        p7zip-full  \
        curl \
        rsync \
        docutils-common \
        docutils-doc \
        docbook \
        docbook-xml \
        docbook-xsl \
        xsltproc \
        openssh-client \
        git \
        graphviz \
        texlive \
        sshpass \
        ghostscript \
        unzip \
        wget \
        python3-pip \
        ruby \
        python3-docutils \
        libsaxonhe-java \
        cmake \
        bison \
        flex \
        texlive-latex-extra \
        default-jre-headless \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        vim \
        python \
    && sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG=en_US.UTF-8 \
    && curl -s -S --retry 10 -L -o gh_2.16.1_linux_amd64.deb https://github.com/cli/cli/releases/download/v2.16.1/gh_2.16.1_linux_amd64.deb \
    && dpkg -i gh_2.16.1_linux_amd64.deb \
    && git clone -b 'Release_1_9_5' --depth 1 https://github.com/doxygen/doxygen.git \
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
    && mkdir build && cd build \
    && curl -s -S --retry 10 -L -o rapidxml.zip http://sourceforge.net/projects/rapidxml/files/latest/download \
    && unzip -n -d rapidxml rapidxml.zip \
    && pip3 install --user Jinja2==3.1.2 \
    && pip3 install --user MarkupSafe==2.1.1 \
    && pip3 install --user Sphinx==5.2.1 \
    && pip3 install --user git+https://github.com/pfultz2/sphinx-boost@8ad7d424c6b613864976546d801439c34a27e3f6 \
    && pip3 install --user myst-parser==0.18.1 \
    && curl -s -S --retry 10 -L -o docbook-xml.zip http://www.docbook.org/xml/4.5/docbook-xml-4.5.zip \
    && unzip -n -d docbook-xml docbook-xml.zip \
    && curl -s -S --retry 10 -L -o docbook-xsl.zip https://sourceforge.net/projects/docbook/files/docbook-xsl/1.79.1/docbook-xsl-1.79.1.zip/download \
    && unzip -n -d docbook-xsl docbook-xsl.zip \
    && gem install asciidoctor --version 2.0.17 \
    && asciidoctor --version \
    && gem install rouge --version 4.0.0 \
    && gem install pygments.rb --version 2.3.0 \
    && pip3 install --user Pygments==2.13.0 \
    && pip3 install --user https://github.com/bfgroup/jam_pygments/archive/master.zip \
    && pip3 install --user future==0.18.2 \
    && pip3 install --user six==1.14.0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean -y
ENV LC_ALL en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8

# To maintain consistency between the Dockerfile and the build_docs scripts, in the next future revision of the Dockerfile
# install, track, and upgrade these gems also.
# gem install public_suffix --version 4.0.7
# gem install css_parser --version 1.12.0

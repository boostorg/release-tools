FROM ubuntu:bionic
LABEL maintainer="samuel.d.darwin@gmail.com"

WORKDIR /root

RUN apt-get update \
 && DEBIAN_FRONTEND="noninteractive" apt-get -y install tzdata \
 && apt-get install -y \
        p7zip-full  \
        curl \
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
        python-pip \
        ruby \
        python-docutils \
        libsaxonhe-java \
        cmake \
        bison \
        flex \
        texlive-latex-extra \
        default-jre-headless \
        python3 \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
    && apt-key adv --keyserver keyserver.ubuntu.com --recv-key C99B11DEB97541F0 \
    && apt-add-repository https://cli.github.com/packages \
    && apt-get update \
    && apt-get install -y gh \
    && git clone -b 'Release_1_8_15' --depth 1 https://github.com/doxygen/doxygen.git \
    && cd doxygen \
    && cmake -H. -Bbuild -DCMAKE_BUILD_TYPE=Release \
    && cd build \
    && make install \
    && cd && rm -rf doxygen* \
    && wget -O saxonhe.zip https://sourceforge.net/projects/saxon/files/Saxon-HE/9.9/SaxonHE9-9-1-4J.zip/download \
    && unzip saxonhe.zip \
    && rm /usr/share/java/Saxon-HE.jar \
    && cp saxon9he.jar /usr/share/java/Saxon-HE.jar \
    && rm -r * \
    && mkdir build && cd build \
    && wget -O rapidxml.zip http://sourceforge.net/projects/rapidxml/files/latest/download \
    && unzip -n -d rapidxml rapidxml.zip \
    && pip install --user Jinja2==2.11.2 \
    && pip install --user MarkupSafe==1.1.1 \
    && pip install --user docutils==0.12 \
    && echo "Sphinx==1.5.6" > constraints.txt \
    && pip install --user Sphinx==1.5.6 \
    && pip install --user sphinx-boost==0.0.3 \
    && pip install --user -c /root/build/constraints.txt git+https://github.com/rtfd/recommonmark@50be4978d7d91d0b8a69643c63450c8cd92d1212 \ 
    && wget -O docbook-xml.zip http://www.docbook.org/xml/4.5/docbook-xml-4.5.zip \
    && unzip -n -d docbook-xml docbook-xml.zip \
    && wget -O docbook-xsl.zip https://sourceforge.net/projects/docbook/files/docbook-xsl/1.79.1/docbook-xsl-1.79.1.zip/download \
    && unzip -n -d docbook-xsl docbook-xsl.zip \
    && gem install asciidoctor --version 2.0.16 \
    && asciidoctor --version \
    && gem install rouge --version 3.26.1 \
    && gem install pygments.rb --version 1.2.1 \
    && pip install --user Pygments==2.1 \
    && pip install --user https://github.com/bfgroup/jam_pygments/archive/master.zip \
    && pip install --user future==0.18.2 \
    && pip install --user six==1.15.0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean -y


Earlier notes:  

In the Dockerfile, docbook is being installed twice. As apt packages:

```
        docbook \
        docbook-xml \
        docbook-xsl \
```

and zip files:
```
    && curl -s -S --retry 10 -L -o docbook-xml.zip http://www.docbook.org/xml/4.5/docbook-xml-4.5.zip \
    && unzip -n -d docbook-xml docbook-xml.zip \
    && curl -s -S --retry 10 -L -o docbook-xsl.zip https://sourceforge.net/projects/docbook/files/docbook-xsl/1.79.1/docbook-xsl-1.79.1.zip/download \
    && unzip -n -d docbook-xsl docbook-xsl.zip
```

There are boostbook warnings if DOCBOOK_XSL_DIR and DOCBOOK_DTD_DIR aren't specified. build_docs is setting those variables, pointing to the unzipped location.  
The main release script does not set those variables. It is using the default. Which might be the apt packages.  
Versions are approximately the same currently between packages and downloads.  

---

2023 note. Focal had pinned these gems to support Ruby 2.5

```
    && gem install public_suffix --version 4.0.7 \
    && gem install css_parser --version 1.12.0 \
```

In Jammy, it may be unnecessary. But, continuing to track these gems.

```
    && gem install public_suffix --version 5.0.3 \
    && gem install css_parser --version 1.16.0 \
```

In the near future they can return to being unpinned.  


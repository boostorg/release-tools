
2024-12-10

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

Versions are approximately the same currently between packages and downloads.

When release-tools executes, /root/build/site-config.jam points to the copies in /root/build so the apt packages are ignored.

When build_docs scripts run, there are boostbook warnings if DOCBOOK_XSL_DIR and DOCBOOK_DTD_DIR aren't specified. build_docs is setting those variables, pointing to the unzipped location in BOOST_ROOT/build.

So in both cases, the zip files are used instead of the apt packages. At the moment this seems acceptable, without a reason to modify it.

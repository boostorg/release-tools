#!/usr/bin/env python

# Copyright Raffi Enficiaud 2020

# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)


'''
Create GitHub releases and upload files

This script creates a GitHub release and adds release files to it.

1. The releases of a particular repository are listed.
1. If the release from its tag name does not exist already, it is created
1. The files are then uploaded to this release.

It is possible to re-upload existing files.


@author: Raffi Enficiaud

.. note::

    Currently, a release description is not re-edited when a release already exists.

'''


import base64
import urllib.request
import urllib.parse
from urllib.request import Request
from urllib.error import HTTPError
from http import HTTPStatus
import os
import ssl
import json
import platform
import sys
import traceback
import logging

logger = logging.getLogger(__file__)

logging.basicConfig(level=logging.DEBUG)


class HTTPAuthHeader(urllib.request.BaseHandler):
    """A class that adds the authorization token"""

    def __init__(self,
                 token=None,
                 username=None,
                 password=None):
        if token is None and (username is None or password is None):
            raise RuntimeError("'token' or 'username/password' should be provided")
        if token is not None and (username is not None or password is not None):
            raise RuntimeError("'token' and 'username/password' authentications are mutually exclusive")
        if token is not None:
            self.token = token
        else:
            self.username = username
            self.password = password

    def http_request(self, request):
        if hasattr(self, 'token'):
            request.add_header('Authorization', 'token %s' % self.token)
        else:
            base64_creds = base64.b64encode(b'%s:%s' % (self.username.encode(), self.password.encode())).decode()
            request.add_header('Authorization', 'Basic %s' % base64_creds)
        return request

    https_request = http_request


def get_create_default_SSL_context():
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.check_hostname = True
    ssl_context.load_default_certs()

    if platform.system().lower() == 'darwin':
        # we load an autoritative CA bundle from the certifi package
        # see the content of the file "/Applications/Python 3.7/Install Certificates.command"
        # that pulls the CA of certifi into the python CA.
        import certifi
        ssl_context.load_verify_locations(
            cafile=os.path.relpath(certifi.where()),
            capath=None,
            cadata=None)

    return ssl_context


class GitHubReleaseHelper:

    def __init__(self, token, org, repo):
        self.token = token
        self.org = org
        self.repo = repo
        self.opener = urllib.request.build_opener(
            HTTPAuthHeader(token=self.token),
            urllib.request.HTTPSHandler(context=get_create_default_SSL_context()))
        self.opener.addheaders += [  # ('Accept', 'application/json'),
            ('Accept', 'application/vnd.github.v3+json')]

    def _get_api_url(self, release_id=None, assets=False, asset_id=None):
        """Returns the URL of the release API endpoint

        :param release_id: if provided, will return the URL of the indicated release (through its ID)
        :param assets: if `True`, returns the URL for assets management
        """
        # A GET lists the releases, a POST creates one
        path = "repos/%s/%s/releases" % (self.org, self.repo)

        if asset_id:
            path += "/assets/%s" % asset_id
        else:
            if release_id is not None:
                path += "/%s" % release_id

            if assets:
                path += "/assets"

        return urllib.parse.urlunparse(
            ('https',
             "api.github.com",
             path,
             "",
             "",
             ""))

    @staticmethod
    def _get_next(response):

        _link = response.getheader('Link')
        if _link:
            _link = _link.split(',')

            for _l in _link:
                if 'rel="next"' in _l:
                    return _l.split(';')[0].strip()

        return None

    def get_paginated_result(self, url, ok_code=HTTPStatus.OK):
        out = []
        ret = self.opener.open(
            url,
            timeout=30)

        if ret.getcode() != ok_code:
            raise RuntimeError("Communication failed with error code '%s'" % ret.getcode())

        out += json.loads(ret.read())

        _next = self._get_next(ret)
        while _next:
            ret = self.opener.open(
                _next,
                timeout=30)
            if ret.getcode() != ok_code:
                raise RuntimeError("Communication failed with error code '%s'" % ret.getcode())

            out += json.loads(ret.read())
            _next = self._get_next(ret)

        return out

    def list_releases(self):
        """Returns the lists of releases

        .. note:: handles GitHub pagination
        """
        return self.get_paginated_result(self._get_api_url())

    def list_assets(self, release_id):
        return self.get_paginated_result(self._get_api_url(release_id=release_id, assets=True))

    def create_release(self,
                       tag_name,
                       release_name=None,
                       description=None):
        """Creates a new GitHub release

        This method will fail if the release exists already

        :param tag_name: tag of the repository from which the release is being made. If the tag does not
          exist already, the current `master` branch will be used to create a tag instead.
        :param release_name: name of this release. If not provided, defaults to `tag_name`
        :param description: description of the release
        """

        data = {
            "tag_name": tag_name,
            "target_commitish": "master",
            "draft": False,
            "prerelease": False
        }

        if description:
            data['body'] = description

        if release_name:
            data['name'] = release_name

        ret = self.opener.open(
            self._get_api_url(),
            timeout=30,
            data=json.dumps(data).encode())

        if ret.getcode() == HTTPStatus.CREATED:
            return json.loads(ret.read())
        raise RuntimeError("Communication failed with error code '%s'" % ret.getcode())

    def upload_files(self,
                     release_id,
                     files,
                     url_upload=None,
                     replace_files=False):

        if url_upload is None:
            release = self.get_release(release_id=release_id)
            url_upload = release["upload_url"]
            url_upload = url_upload.replace("{?name,label}", "")

        parsed = urllib.parse.urlparse(url_upload)

        all_assets = self.list_assets(release_id)

        all_assets = {_['name']: _ for _ in all_assets}
        logger.debug("Existing assets: '%s'", ','.join(all_assets.keys()))

        for filename in files:

            # name of the asset: we should this to be the same as the name of the file
            name = os.path.basename(filename)

            if name in all_assets:
                if replace_files:
                    logger.warning("Deleting asset '%s' as it exists and should be replaced", name)

                    req = Request(self._get_api_url(asset_id=all_assets[name]['id']), method='DELETE')

                    try:
                        ret = self.opener.open(
                            req,
                            timeout=60)
                        if ret.getcode() == HTTPStatus.NO_CONTENT:
                            logger.info("Asset '%s' deleted", name)
                        else:
                            logger.warning("Unexpected response code '%s' for asset deletion '%s'", ret.getcode(), name)

                    except HTTPError as e:
                        logger.error("Error while deleting asset '%s': '%s': '%s'", name, e, e.file.read())
                        # continue on error?
                        continue
                else:
                    logger.info("Ignoring file '%s' as asset '%s' already exists", filename, name)
                    continue

            url_upload = urllib.parse.urlunparse(
                (parsed.scheme,
                 parsed.netloc,
                 parsed.path,
                 "",
                 urllib.parse.urlencode({'name': name,
                                         # label if provided will be the name of the link shown under the assets
                                         #'label': os.path.basename(filename)
                                         }),
                 ""))

            filesize = os.path.getsize(filename)
            with open(filename, 'rb') as f:
                try:
                    logger.info("Uploading asset '%s' file '%s' of size '%s'", name, filename, filesize)
                    headers = {'Content-length': str(filesize),
                               "Content-Type": "application/octet-stream"}  # this is needed for streaming
                    req = Request(url_upload, data=f, headers=headers)
                    ret = self.opener.open(
                        req,
                        timeout=60)
                    if ret.getcode() == HTTPStatus.CREATED:
                        logger.info("Asset '%s' file '%s' of size '%s' uploaded successfully", name, filename, filesize)
                    else:
                        logger.warning("Unexpected response code '%s' during upload of asset '%s' file '%s'", ret.getcode(), name, filename)
                except Exception as e:
                    logger.error("Error while uploading asset '%s' and file '%s': '%s'", name, filename, e)
                    # continue to next file

    def get_release(self, release_id):
        ret = self.opener.open(
            self._get_api_url(release_id),
            timeout=30)

        if ret.getcode() == HTTPStatus.OK:
            return json.loads(ret.read())
        raise RuntimeError("Communication failed with error code '%s'" % ret.getcode())


def upload_to_github(
        github_object: GitHubReleaseHelper,
        release_tag,
        release_name,
        files,
        replace_existing=True,
        description=None):

    all_releases = github_object.list_releases()
    logger.debug("current releases")
    for release in all_releases:
        logger.debug("ID: %s, name '%s' tag '%s'", release["id"], release["name"], release["tag_name"])

    for release in all_releases:
        if release["tag_name"] == release_tag:
            release_id = release["id"]
            logger.debug("Tag %s found with release ID %s", release_tag, release_id)
            break
    else:
        release_id = None

    if release_id is None:
        logger.debug("Creating new release from tag %s", release_tag)
        release = github_object.create_release(
            tag_name=release_tag,
            release_name=release_name,
            description=description)

        release_id = release["id"]

    logger.debug("Uploading files to release %s", release_tag)
    github_object.upload_files(
        release_id=release_id,
        files=files,
        replace_files=replace_existing)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Command line tool creating Github releases.')

    parser.add_argument('--github-token', metavar='token', type=str,
                        help='GitHub user access token. The corresponding user should have write access to the repository.')
    parser.add_argument('--github-organization', metavar='organization', type=str,
                        help='GitHub organization. The revision should be for this repository in this organization.')
    parser.add_argument('--github-repository', metavar='repository', type=str,
                        help='GitHub repository. The revision should be for this repository in this organization.')

    parser.add_argument('--release-tag', metavar='tag', type=str,
                        help='Tag which the release is being made from')
    parser.add_argument('--release-name', metavar='desc', type=str,
                        help='Name of the release')
    parser.add_argument('--release-description', metavar='desc', type=str,
                        help='Description of the release')
    parser.add_argument('--files', nargs='+',
                        help='List of files to be uploaded to this release')
    parser.add_argument('--replace-existing', action='store_true',
                        help='Indicates if any existing file should be replaced')

    args = parser.parse_args()

    github_object = GitHubReleaseHelper(
        token=args.github_token,
        org=args.github_organization,
        repo=args.github_repository)

    release_name = None
    if args.release_name:
        release_name = args.release_name.strip()

    description = None
    if args.release_description:
        description = args.release_description.strip()

    try:
        upload_to_github(
            github_object=github_object,
            release_tag=args.release_tag.strip().lower(),
            release_name=release_name,
            description=description,
            files=args.files,
            replace_existing=args.replace_existing)

    except Exception as e:
        print("Exception during execution", e)
        traceback.print_exc()
        sys.exit(1)

    sys.exit(0)

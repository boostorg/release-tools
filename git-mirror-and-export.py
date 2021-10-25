#!/usr/bin/python
#

from __future__ import print_function

import requests

import json
import sys
import os
import os.path
import errno
import subprocess
import re
import shutil

# For urllib
from future.standard_library import install_aliases
install_aliases()
from urllib.parse import urlparse, urljoin

# For iteritems
from future.utils import iteritems

# Check python version
if sys.version_info[0] == 2 :
    pythonversion="2"
else:
    pythonversion="3"

# Update or create the github mirror.
def mirror_boostorg(root_dir):
    mirror_dir = os.path.join(root_dir, 'mirror')
    print("Updating mirror at %s" % mirror_dir)
    url = 'https://api.github.com/orgs/boostorg/repos'

    while (url) :
        r = requests.get(url)
        if (not r.ok):
            raise Exception("Error getting: " + url)

        for repo in json.loads(r.text or r.content):
            print("Downloading " + repo['name'])
            url = repo['clone_url']
            # Not using os.path.join because url path is absolute.
            path = mirror_dir + urlparse(url).path
            mkdir_p(os.path.join(path, os.pardir))

            # TODO: Check that path is actually a git repo?
            if os.path.isdir(path):
                subprocess.check_call(["git", "--git-dir=" + path, "fetch"])
            else:
                subprocess.check_call(["git", "clone", "--mirror", url, path])

        url = r.links['next']['url'] if 'next' in r.links else False

# Export the full tree from the mirror
def mirror_export(root_dir, dst_dir, branch = 'master', eol = 'lf'):
    git_flags = "-c core.autocrlf=false -c core.eol="+ eol
    boost_module_dir = os.path.join(root_dir, 'mirror/boostorg/boost.git')

    os.mkdir(dst_dir)
    export_single_repo(boost_module_dir, dst_dir, branch, eol)
    module_settings = get_submodule_settings(dst_dir)
    hashes = get_submodule_hashes(boost_module_dir, branch,
            [ module_settings[x]['path'] for x in module_settings ])

    # Export child submodules
    for name, module in iteritems(module_settings):
        print("Exporting submodule " + name)
        if module['path'] not in hashes:
            raise Exception('No hash for module ' + name)
        export_single_repo(
                urljoin(boost_module_dir + '/', module['url']),
                os.path.join(dst_dir, module['path']),
                hashes[module['path']], eol)

# Export from a single git repo
def export_single_repo(git_dir, dst_dir, ref, eol):
    ps = subprocess.Popen(
            ["git", "-c", "core.autocrlf=false", "-c", "core.eol=" + eol,
                "--git-dir=" + git_dir, "archive", ref],
            stdout=subprocess.PIPE)
    subprocess.check_call(['tar', '-x', '-C', dst_dir], stdin=ps.stdout)

# Load the submodule settings from an exported repo.
def get_submodule_settings(dst_dir):
    module_settings = {}
    for line in subprocess.Popen(
            [ 'git', 'config', '-f', dst_dir + "/.gitmodules", "-l" ],
            stdout=subprocess.PIPE).stdout:
        if pythonversion=="3":
            line=line.decode(encoding="utf-8")
        result = re.match('submodule\.([^.]*)\.([^.]*)=(.*)', line)
        if result.group(1) not in module_settings:
            module_settings[result.group(1)] = { 'name': result.group(1) }
        module_settings[result.group(1)][result.group(2)] = result.group(3)
    return module_settings

# Load the submodule hashes from the given paths
def get_submodule_hashes(boost_module_dir, branch, paths):
    hashes = {}
    for line in subprocess.Popen(
            [ 'git', '--git-dir=' + boost_module_dir, 'ls-tree', branch ] + paths,
            stdout=subprocess.PIPE).stdout:
        if pythonversion=="3":
            line=line.decode(encoding="utf-8")
        result = re.match('160000 commit ([0-9a-zA-Z]+)\t(.*)', line)
        hashes[result.group(2)] = result.group(1)
    return hashes

# Equivalent to mkdir -p
# From http://stackoverflow.com/a/600612/2434
def mkdir_p(path):
    path = os.path.realpath(path)
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

############################################################################### 

def export_boost(root_dir, branch, eol):
    dir = os.path.join(root_dir, branch + '-' + eol)
    print("Exporting to %s" % dir)
    if os.path.isdir(dir):
        shutil.rmtree(dir)
    mirror_export(root_dir, dir, branch, eol)

if len(sys.argv) > 1:
	root=sys.argv[1]
else:
	root=os.path.dirname(sys.argv[0])

print("Update mirror")
print()
mirror_boostorg(root)

print("Export master-crlf")
print()
export_boost(root, 'master', 'crlf')

print("Export master-lf")
print()
export_boost(root, 'master', 'lf')

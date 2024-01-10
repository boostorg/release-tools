#!/usr/bin/python
#

# 	Prepare a boost checkout for release
# 	1) Copy all the files at the root level to the dest folder ($DEST)
# 	2) Copy all the "special" folders to the dest folder ($DEST)
# 	3) copy all the files from $SOURCE/libs to $DEST/libs
# 	4a) For each subproject, copy everything except "include" into $DEST/libs
# 	4b) For each subproject, copy the contents of the "includes" folder into $DEST/boost
#
# 	Usage: %0 source dest

from __future__ import print_function

import os
import sys
import shutil
import stat
import six
import datetime
import fnmatch
import re

ignored_files_pattern = shutil.ignore_patterns(
    "[.]*",
    "[.]gitattributes",
    "[.]gitignore",
    "[.]gitmodules",
    "[.]travis[.]yml",
    "appveyor[.]yml",
    "circle[.]yml",
)


def should_ignore_file(src, name):
    return len(ignored_files_pattern(src, [name])) > 0


source_file_patterns = [
    "*.jam",
    "Jamfile.v2",
    "Jamfile",
    "Jamfile.jam",
    "jamfile.jam",
    "jamfile.v2",
    "jamfile",
    "build.jam",
    "Jamroot",
    "*.cpp",
    "*.hpp",
    "*.ipp",
    "*.cxx",
    "*.hxx",
    "*.c",
    "*.h",
    "*.asm",
    "*.S",
    "CMakeLists.txt",
    "*.cmake",
    "Makefile",
    "*.py",
    "*.sh",
    "*.bash",
    "*.zsh",
    "*.ksh",
    "*.csh",
    "*.bat",
    "*.pl",
    "INSTALL",
    "LICENSE*",
    "COPYING*",
    "COPYRIGHT*",
    "LICENCE*",
    "UNLICENSE*",
]


def is_image_file(file_path):
    return any(
        file_path.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg"]
    )


def is_html_content_file(file_path):
    return (
        any(
            file_path.endswith(ext)
            for ext in [
                ".html",
                ".htm",
                ".css",
                ".js",
                ".txt",
                "README.md",
                ".pdf",
                "readme",
                ".md",
            ]
        )
        and os.path.split(file_path)[1] != "CMakeLists.txt"
    )


# Determine if file should be included in a source release
def is_source_file(f):
    return any(
        fnmatch.fnmatch(os.path.split(f)[1], pattern)
        for pattern in source_file_patterns
    )


DocFiles = ["INSTALL", "LICENSE*", "COPYING*", "COPYRIGHT*", "LICENCE*", "UNLICENSE*"]


# Determine if file should be included in a documentation release
def is_doc_file(f):
    return (
        is_html_content_file(f)
        or is_image_file(f)
        or any(fnmatch.fnmatch(os.path.split(f)[1], pattern) for pattern in DocFiles)
    )


# http://stackoverflow.com/questions/1868714/how-do-i-copy-an-entire-directory-of-files-into-an-existing-directory-using-pyth
def merge_dir_tree(src, dst, symlinks=False):
    if not os.path.exists(dst):
        os.makedirs(dst)
        shutil.copystat(src, dst)
    lst = os.listdir(src)
    excl = ignored_files_pattern(src, lst)
    lst = [x for x in lst if x not in excl]
    for item in lst:
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if symlinks and os.path.islink(s):
            if os.path.lexists(d):
                os.remove(d)
            os.symlink(os.readlink(s), d)
            try:
                st = os.lstat(s)
                mode = stat.S_IMODE(st.st_mode)
                os.lchmod(d, mode)
            except:
                pass  # lchmod not available
        elif os.path.isdir(s):
            merge_dir_tree(s, d, symlinks)
        else:
            if os.path.exists(d):
                print("## Overwriting file %s with %s" % (d, s))
            shutil.copy2(s, d)


# Merge dd into '{s}/{d}' if it exists
def merge_dir_tree_if_exists(s, d, dd):
    if os.path.exists(os.path.join(s, dd)):
        merge_dir_tree(os.path.join(s, dd), os.path.join(d, dd), symlinks=False)


# Copy a file is it belongs to this release variant
def copy_distro_file(s, d, f, include_source, include_docs):
    is_full_dist = include_source and include_docs
    if (
        os.path.isfile(os.path.join(s, f))
        and not should_ignore_file(s, f)
        and (
            is_full_dist or (include_source and is_source_file(f)) or (include_docs and is_doc_file(f))
        )
    ):
        shutil.copy2(os.path.join(s, f), os.path.join(d, f))


# Copy file s to directory d if it's a source file
def copy_abs_source_file(s, d):
    if os.path.isfile(s) and is_source_file(s):
        shutil.copy2(s, d)


# Copy file s to directory d if it's a documentation file
def copy_abs_doc_file(s, d):
    if os.path.isfile(s) and is_doc_file(s):
        shutil.copy2(s, d)


# Copy file s to directory d if it belongs to the distribution
def copy_distro_dir(s, d, dd, include_source, include_docs):
    if os.path.isdir(os.path.join(s, dd)) and not should_ignore_file(s, dd):
        full_dist = include_source and include_docs
        if full_dist:
            if os.path.isdir(os.path.join(s, dd)) and not should_ignore_file(s, dd):
                shutil.copytree(
                    os.path.join(s, dd),
                    os.path.join(d, dd),
                    symlinks=False,
                    ignore=ignored_files_pattern,
                )
        elif not include_docs:
            shutil.copytree(
                os.path.join(s, dd),
                os.path.join(d, dd),
                symlinks=False,
                ignore=ignored_files_pattern,
                copy_function=copy_abs_source_file,
            )
        elif not include_source:
            shutil.copytree(
                os.path.join(s, dd),
                os.path.join(d, dd),
                symlinks=False,
                ignore=ignored_files_pattern,
                copy_function=copy_abs_doc_file,
            )


# Copy an include directory
def copy_distro_include_dir(src, dst, include_source, include_docs):
    for item in os.listdir(src):
        if should_ignore_file(src, item):
            continue
        if item == "pending":
            continue
        if item == "detail":
            continue
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            merge_dir_tree(s, d, symlinks=False)
        else:
            if not include_docs and not is_doc_file(item):
                continue
            if not include_source and not is_source_file(item):
                continue
            if os.path.exists(d):
                print("## Overwriting file %s with %s" % (d, s))
            copy_distro_file(src, dst, item, include_source, include_docs)


# Copy a subproject according to the distribution rules
def copy_distro_subproject(src, dst, headers, p, include_source, include_docs):
    # First, everything except the "include" directory
    source_project_dir = os.path.join(src, p)
    dest_project_dir = os.path.join(dst, p)
    # print "CopySubProject %p" % p
    os.makedirs(dest_project_dir)
    for item in os.listdir(source_project_dir):
        if item == "antora":
            continue
        if os.path.isfile(os.path.join(source_project_dir, item)):
            copy_distro_file(
                source_project_dir, dest_project_dir, item, include_source, include_docs
            )
        elif item != "include":
            copy_distro_dir(
                source_project_dir, dest_project_dir, item, include_source, include_docs
            )

    # Now the includes
    source_project_dir = os.path.join(src, "%s/include/boost" % p)
    if os.path.exists(source_project_dir):
        copy_distro_include_dir(
            source_project_dir, headers, include_source, include_docs
        )
        merge_dir_tree_if_exists(source_project_dir, headers, "detail")
        merge_dir_tree_if_exists(source_project_dir, headers, "pending")


def copy_distro_nested_project(src, dst, headers, p, include_source, include_docs):
    # First, everything except the "include" directory
    source_nested_dir = os.path.join(src, p[1])
    dest_nested_dir = os.path.join(dst, p[1])
    os.makedirs(dest_nested_dir)
    for item in os.listdir(source_nested_dir):
        if os.path.isfile(os.path.join(source_nested_dir, item)):
            copy_distro_file(
                source_nested_dir, dest_nested_dir, item, include_source, include_docs
            )
        elif item != "include":
            copy_distro_dir(
                source_nested_dir, dest_nested_dir, item, include_source, include_docs
            )
    source_nested_dir = os.path.join(src, "%s/include/boost" % (p[1]))
    copy_distro_include_dir(source_nested_dir, headers, include_source, include_docs)


# Remove any empty subdirectories that might have been left after
# recursively skipping files
def remove_empty_subdirs(path):
    subdirs = [
        os.path.join(path, d)
        for d in os.listdir(path)
        if os.path.isdir(os.path.join(path, d))
    ]
    for subdir in subdirs:
        remove_empty_subdirs(subdir)
        try:
            os.rmdir(subdir)
        except OSError:
            pass


def main(
    src_root, dest_root, include_source=True, include_docs=True, cmake_distro=False
):
    if not os.path.isabs(src_root):
        src_root = os.path.abspath(src_root)
    print("Source = %s" % src_root)

    if not os.path.isabs(dest_root):
        dest_root = os.path.abspath(dest_root)
    print("Dest   = %s" % dest_root)

    if not os.path.exists(src_root):
        print("## Error: %s does not exist" % src_root)
        exit(1)

    if os.path.exists(dest_root):
        print(
            "The destination directory already exists. Renaming it, so that a new one can be generated.\n"
        )
        timestamp1 = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        os.rename(dest_root, dest_root + "_bck_" + timestamp1)

    if not os.path.exists(dest_root):
        print("Creating destination directory %s" % dest_root)
        os.makedirs(dest_root)

    # Step 1: Copy all the files at the root level to the dest folder
    for f in os.listdir(src_root):
        if f != "CMakeLists.txt" or cmake_distro:
            copy_distro_file(src_root, dest_root, f, include_source, include_docs)

    # Step 2: Copy all the "special" root folders to the dest folder
    special_root_folders = ["tools"]
    if include_docs:
        special_root_folders += ["doc", "more", "status"]
    if cmake_distro:
        special_root_folders += ["libs"]
    for d in special_root_folders:
        copy_distro_dir(src_root, dest_root, d, include_source, include_docs)

    # Step 3: copy all the files from $SOURCE/libs/* to $DEST/libs/*
    libs_dir_name = "libs"
    dest_libs_dir = os.path.join(dest_root, libs_dir_name)
    if not os.path.exists(dest_libs_dir):
        os.makedirs(dest_libs_dir)
    source_libs_dir = os.path.join(src_root, libs_dir_name)
    for f in os.listdir(source_libs_dir):
        copy_distro_file(
            source_libs_dir, dest_libs_dir, f, include_source, include_docs
        )

    # Step 4: For each subproject, copy everything except "include" into $DEST/libs
    # 4a) Aggregate subprojects to copy
    boost_subprojects = set()
    for f in os.listdir(source_libs_dir):
        if os.path.isdir(os.path.join(source_libs_dir, f)):
            if os.path.isfile(
                os.path.join(source_libs_dir, f, "meta", "libraries.json")
            ):
                boost_subprojects.add(f)
            elif os.path.isdir(os.path.join(source_libs_dir, f, "include")):
                boost_subprojects.add(f)
            elif f == "headers":
                boost_subprojects.add(f)
            elif os.path.isfile(os.path.join(source_libs_dir, f, "sublibs")):
                for s in os.listdir(os.path.join(source_libs_dir, f)):
                    if os.path.isdir(os.path.join(source_libs_dir, f, s)):
                        if os.path.isfile(
                            os.path.join(
                                source_libs_dir, f, s, "meta", "libraries.json"
                            )
                        ):
                            boost_subprojects.add((f, s))
                        elif os.path.isdir(
                            os.path.join(source_libs_dir, f, s, "include")
                        ):
                            boost_subprojects.add((f, s))

    if not cmake_distro:
        # Step 4b) Copy each subproject
        # copy the contents of the "includes" folder into $DEST/boost
        # copy the contents of the other folders into $DEST/libs
        headers_dir_name = "boost"
        dest_headers = os.path.join(dest_root, headers_dir_name)
        os.makedirs(dest_headers)
        for p in boost_subprojects:
            if isinstance(p, six.string_types):
                copy_distro_subproject(
                    source_libs_dir,
                    dest_libs_dir,
                    dest_headers,
                    p,
                    include_source,
                    include_docs,
                )
            else:
                nested_source_dir = os.path.join(src_root, "libs", p[0])
                nested_dest_dir = os.path.join(dest_root, "libs", p[0])
                nested_dest_headers_dir = os.path.join(dest_root, "boost")
                if not os.path.exists(nested_dest_dir):
                    os.makedirs(nested_dest_dir)
                if not os.path.exists(nested_dest_headers_dir):
                    os.makedirs(nested_dest_headers_dir)
                for f in os.listdir(nested_source_dir):
                    copy_distro_file(
                        nested_source_dir,
                        nested_dest_dir,
                        f,
                        include_source,
                        include_docs,
                    )
                copy_distro_nested_project(
                    nested_source_dir,
                    nested_dest_dir,
                    nested_dest_headers_dir,
                    p,
                    include_source,
                    include_docs,
                )
    else:
        # Step 4b) Clean tests dir from cmake distro
        def clean_test_dir(test_dir):
            if not os.path.exists(test_dir) or not os.path.exists(test_dir):
                return
            for base_path in os.listdir(test_dir):
                abs_path = os.path.join(test_dir, base_path)
                if os.path.isdir(abs_path):
                    clean_test_dir(abs_path)
                elif base_path == "CMakeLists.txt" or base_path.endswith(".cmake"):
                    with open(abs_path, "w") as fw:
                        fw.write("# Placeholder \n")
                else:
                    os.remove(abs_path)

        for p in boost_subprojects:
            if isinstance(p, six.string_types):
                clean_test_dir(os.path.join(dest_root, "libs", p, "test"))
            else:
                clean_test_dir(os.path.join(dest_root, "libs", p[0], "docs"))
                clean_test_dir(os.path.join(dest_root, "libs", p[0], p[1], "docs"))

    # Step 5: Copy any source files referred linked in the docs
    if not include_source and include_docs:
        href_pattern = re.compile(r'href=["\'](.*?)["\']')
        # Iterate html files
        for root, dirs, files in os.walk(dest_root):
            for file in files:
                filepath = os.path.join(root, file)
                if filepath.endswith(".html") or filepath.endswith(".htm"):
                    # extract href contents
                    with open(filepath, "r") as f:
                        dir = os.path.dirname(filepath)
                        try:
                            contents = f.read()
                            hrefs = href_pattern.findall(contents)
                            for href in hrefs:
                                if href.startswith("http:") or href.startswith(
                                    "https:"
                                ):
                                    continue
                                p = href.rfind("#")
                                if p != -1:
                                    href = href[:p]
                                if href == "" or is_doc_file(href):
                                    continue
                                dest = os.path.normpath(os.path.join(dir, href))
                                if not dest.startswith(dest_root):
                                    continue
                                if os.path.exists(dest):
                                    continue
                                src = os.path.join(
                                    src_root, os.path.relpath(dest, dest_root)
                                )
                                if not src.startswith(src_root):
                                    continue
                                if not os.path.exists(src):
                                    continue
                                destdir = os.path.dirname(dest)
                                if not os.path.exists(destdir):
                                    os.makedirs(destdir)
                                shutil.copy2(src, dest)
                        except UnicodeDecodeError:
                            pass

    # Step 6: remove any empty subdirs
    if not (include_source and include_docs):
        remove_empty_subdirs(dest_root)


if __name__ == "__main__":
    include_source = True
    include_docs = True
    cmake_distro = False
    if "--source" in sys.argv[3:]:
        include_source = True
    if "--no-source" in sys.argv[3:]:
        include_source = False
    if "--docs" in sys.argv[3:]:
        include_docs = True
    if "--no-docs" in sys.argv[3:]:
        include_docs = False
    if "--cmake" in sys.argv[3:]:
        cmake_distro = True
    if "--no-cmake" in sys.argv[3:]:
        cmake_distro = False
    main(
        sys.argv[1],
        sys.argv[2],
        include_source,
        include_docs,
        cmake_distro,
    )

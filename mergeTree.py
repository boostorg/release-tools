#!/usr/bin/python

import os, sys
import shutil

def mergetree(src, dst, symlinks=False, ignore=None):
	from shutil import copy2, copystat, Error
	import os

	names = os.listdir(src)
	if ignore is not None:
		ignored_names = ignore(src, names)
	else:
		ignored_names = set()

	try:
		os.makedirs(dst)
	except OSError, exc:
		# XXX - this is pretty ugly
		if "file already exists" in exc[1]:	 # Windows
			pass
		elif "File exists" in exc[1]:		 # Linux
			pass
		else:
			raise

	errors = []
	for name in names:
		if name in ignored_names:
			continue
		srcname = os.path.join(src, name)
		dstname = os.path.join(dst, name)
		try:
			if symlinks and os.path.islink(srcname):
				linkto = os.readlink(srcname)
				os.symlink(linkto, dstname)
			elif os.path.isdir(srcname):
				mergetree(srcname, dstname, symlinks, ignore)
			else:
				copy2(srcname, dstname)
			# XXX What about devices, sockets etc.?
		except (IOError, os.error), why:
			errors.append((srcname, dstname, str(why)))
		# catch the Error from the recursive mergetree so that we can
		# continue with other files
		except Error, err:
			errors.extend(err.args[0])
	try:
		copystat(src, dst)
	except WindowsError:
		# can't copy file access times on Windows
		pass
	except OSError, why:
		errors.extend((src, dst, str(why)))
	if errors:
		raise Error, errors

if len(sys.argv) == 3:
	mergetree ( sys.argv[1], sys.argv[2] )
else:
	print "Usage %s <source> <dest>" % sys.argv[0]

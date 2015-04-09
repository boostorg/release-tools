#!/usr/bin/python
#

#	Prepare a boost checkout for release
#	1) Copy all the files at the root level to the dest folder ($DEST)
#	2) Copy all the "special" folders to the dest folder ($DEST)
#	3) copy all the files from $SOURCE/libs to $DEST/libs
#	4a) For each subproject, copy everything except "include" into $DEST/libs
#	4b) For each subproject, copy the contents of the "includes" folder into $DEST/boost
#
#	Usage: %0 source dest

import os, sys
import shutil

## from <http://stackoverflow.com/questions/1868714/how-do-i-copy-an-entire-directory-of-files-into-an-existing-directory-using-pyth>
def mergetree(src, dst, symlinks = False, ignore = None):
	if not os.path.exists(dst):
		os.makedirs(dst)
		shutil.copystat(src, dst)
	lst = os.listdir(src)
	if ignore:
		excl = ignore(src, lst)
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
				pass # lchmod not available
		elif os.path.isdir(s):
			mergetree(s, d, symlinks, ignore)
		else:
			if os.path.exists(d):
				print "## Overwriting file %s with %s" % (d, s)
			shutil.copy2(s, d)
      

def CopyFile (s, d, file):
	shutil.copy2(os.path.join(s,file), os.path.join(d,file))	

def CopyDir (s, d, dir):
	shutil.copytree(os.path.join(s,dir), os.path.join(d,dir), symlinks=False, ignore=shutil.ignore_patterns('\.*'))		

def MergeIf(s, d, dir):
# 	if dir == 'detail':
# 		print "MergeIf %s -> %s" % (os.path.join(s, dir), os.path.join(d, dir))
	if os.path.exists(os.path.join(s, dir)):
		mergetree(os.path.join(s, dir), os.path.join(d, dir), symlinks=False, ignore=shutil.ignore_patterns('\.*'))

def CopyInclude(src, dst):
	for item in os.listdir(src):
		if item[0] == '.':
			continue
		if item == 'pending':
			continue
		if item == 'detail':
			continue
		s = os.path.join(src, item)
		d = os.path.join(dst, item)
		if os.path.isdir(s):
			mergetree(s, d, symlinks=False, ignore=shutil.ignore_patterns('\.*'))
		else:
			if os.path.exists(d):
				print "## Overwriting file %s with %s" % (d, s)
			shutil.copy2(s, d)
	

def CopySubProject(src, dst, headers, p):
#	First, everything except the "include" directory
	Source = os.path.join(src,p)
	Dest   = os.path.join(dst,p)
#	print "CopySubProject %p" % p
	os.makedirs(Dest)
	items  = [ f for f in os.listdir(Source) if f[0] != '.' ]
	for item in items:
		if os.path.isfile(os.path.join(Source, item)):
			CopyFile(Source, Dest, item)
		elif item != "include":
			CopyDir(Source, Dest, item)
			
#	shutil.copytree(Source, Dest, symlinks=False, ignore=shutil.ignore_patterns('\.*', "include"))	

# Now the includes
	Source = os.path.join(src, "%s/include/boost" % p)
	CopyInclude(Source, headers)
# 	mergetree(Source, Dest, symlinks=False, ignore=shutil.ignore_patterns('\.*', 'detail', 'pending'))
	MergeIf(Source, headers, 'detail')
	MergeIf(Source, headers, 'pending')
	

def CopyNestedProject(src, dst, headers, p):
#	First, everything except the "include" directory
	Source = os.path.join(src,p)
	Dest   = os.path.join(dst,p)
	os.makedirs(Dest)
	items  = [ f for f in os.listdir(Source) if f[0] != '.' ]
	for item in items:
		if os.path.isfile(os.path.join(Source, item)):
			CopyFile(Source, Dest, item)
		elif item != "include":
			CopyDir(Source, Dest, item)			
# 	shutil.copytree(Source, Dest, symlinks=False, ignore=shutil.ignore_patterns('\.*', "include"))	

 	Source = os.path.join(src, "%s/include/boost/numeric" % p)
#  	Dest = os.path.join(headers, p)
# 	print "Installing headers from %s to %s" % (Source, headers)
	CopyInclude(Source, headers)
# # 	mergetree(Source, Dest, symlinks=False, ignore=shutil.ignore_patterns('\.*', 'detail', 'pending'))
# 	MergeIf(Source, headers, 'detail')
# 	MergeIf(Source, headers, 'pending')
	return

BoostHeaders = "boost"
BoostLibs = "libs"

BoostSpecialFolders = [ "doc", "more", "status", "tools" ]
BoostSubProjects = [
	"accumulators", "align", "algorithm", "any", "array", "asio", "assert", "assign", "atomic", 
	"bimap", "bind", 
	"chrono", "circular_buffer", "compatibility", "concept_check", "config", "container", "context", "conversion", "core", "coroutine", "crc",
	"date_time", "detail", "disjoint_sets", "dynamic_bitset", 
	"endian", "exception",
	"filesystem", "flyweight", "foreach", "format", "function", "function_types", "functional", "fusion",
	"geometry", "gil", "graph", "graph_parallel",
	"heap",
	"icl", "integer", "interprocess", "intrusive", "io", "iostreams", "iterator",
	"lambda", "lexical_cast", "local_function", "locale", "lockfree", "log", "logic",
	"math", "move", "mpi", "mpl", "msm", "multi_array", "multi_index", "multiprecision", 
#	"numeric",
	"optional",
	"parameter", "phoenix", "polygon", "pool", "predef", "preprocessor", "program_options", "property_map", "property_tree", "proto", "ptr_container", "python",
	"random", "range", "ratio", "rational", "regex",
	"scope_exit", "serialization", "signals", "signals2", "smart_ptr", "sort", "spirit", "statechart", "static_assert", "system",
	"test", "thread", "throw_exception", "timer", "tokenizer", "tr1", "tti", "tuple", "type_index", "type_erasure", "type_traits", "typeof",
	"units", "unordered", "utility", "uuid",
	"variant",
	"wave", "winapi",
	"xpressive"
]

NumericLibs = [ "conversion", "interval", "odeint", "ublas" ]

SourceRoot = sys.argv[1]
DestRoot   = sys.argv[2]

print "Source = %s" % SourceRoot
print "Dest   = %s" % DestRoot

if not os.path.exists(SourceRoot):
	print "## Error: %s does not exist" % SourceRoot
	exit(1)

if not os.path.exists(DestRoot):
	print "Creating destination directory %s" % DestRoot
	os.makedirs(DestRoot)

DestHeaders = os.path.join(DestRoot, BoostHeaders)
DestLibs    = os.path.join(DestRoot, BoostLibs)
os.makedirs(DestHeaders)
os.makedirs(DestLibs)

## Step 1
files = [ f for f in os.listdir(SourceRoot) if os.path.isfile(os.path.join(SourceRoot,f)) and f[0] != '.' ]
for f in files:
	CopyFile(SourceRoot, DestRoot, f)

## Step 2
for d in BoostSpecialFolders:
	CopyDir(SourceRoot, DestRoot, d)

## Step 3
SourceLibs = os.path.join(SourceRoot, BoostLibs)
files = [ f for f in os.listdir(SourceLibs) if os.path.isfile(os.path.join(SourceLibs,f)) and f[0] != '.' ]
for f in files:
	CopyFile(SourceLibs, DestLibs, f)

for p in BoostSubProjects:
	CopySubProject(SourceLibs, DestLibs, DestHeaders, p)
 
# ## Step 4
NumericSource  = os.path.join(SourceRoot, "libs/numeric")
NumericDest    = os.path.join(DestRoot,   "libs/numeric")
NumericHeaders = os.path.join(DestRoot,   "boost/numeric")
os.makedirs(NumericDest)
os.makedirs(NumericHeaders)
files = [ f for f in os.listdir(NumericSource) if os.path.isfile(os.path.join(NumericSource,f)) and f[0] != '.' ]
for f in files:
	CopyFile(NumericSource, NumericDest, f)
for p in NumericLibs:
	CopyNestedProject (NumericSource, NumericDest, NumericHeaders, p)



Refer to the README.md in the docker/ folder.

Upgrade process:

PIP

Remove version constraints:
```
sed -i 's/[=<>!~].*//' requirements.txt
```

After docker build, it will output the versions, copy them back into requirements.txt

GEMS

It would be possible to remove version constraints from the Gemfile
```
sed -i -E "s/^([[:space:]]*gem '[^']+').*/\1/" Gemfile
```

After the docker build, adjust the file again.  
However what we will try it to copy the output of Gemfile.lock back to Gemfile.lock, and leave versions unspecified in Gemfile.a  
To upgrade, remove the contents from Gemfile.lock. Or run "bundle update". Need to experiment.  

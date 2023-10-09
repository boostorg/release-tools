## Testing release-tools

It is possible to run or test release-tools locally in the same way that CI executes the scripts.  

Observe these files and consider any recent updates. The contents of the files are the main instructions.  

https://github.com/boostorg/boost/blob/develop/.circleci/config.yml  
https://github.com/boostorg/boost/blob/master/.circleci/config.yml  

```
docker run -it cppalliance/boost_superproject_build:20.04-v2 bash
```

Inside the container  

```
cd ${HOME}
export CIRCLECI=true
export CIRCLE_BRANCH=develop
export CIRCLE_WORKING_DIRECTORY=~/project
git clone -b develop https://github.com/boostorg/boost project
wget "https://raw.githubusercontent.com/boostorg/release-tools/develop/ci_boost_common.py" -P ${HOME}
wget "https://raw.githubusercontent.com/boostorg/release-tools/develop/ci_boost_release.py" -P ${HOME}
python3 ${HOME}/ci_boost_release.py checkout_post
python3 ${HOME}/ci_boost_release.py test_pre
python3 ${HOME}/ci_boost_release.py test_override
```



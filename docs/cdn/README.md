
## CDN

The infrastructure to distribute boost downloads includes:  
- brorigin1.cpp.al (aws ec2 instance)
- brorigin2.cpp.al (aws ec2 instance)
- ALB (aws application load balancer with dns name brorigin.cpp.al)
- Fastly CDN

## brorigin servers  

On each of the brorigin servers /var/spool/cron/crontabs/root   

```
# m h  dom mon dow   command
0 3 * * * /root/scripts/s3-all.sh
0,15,30,45 0-2,4-23 * * * /root/scripts/s3-snapshots.sh
* * * * * ${HOME}/scripts/s3-file-sync.py > /tmp/s3-file-sync-output.txt 2>&1
```

Refer to the scripts in this directory.  

## Fastly Configuration

Domains:  
archives.boost.io   
archives.boost.org   
boost.global.ssl.fastly.net   
boostorg.global.ssl.fastly.net   

Origins:  

brorigins.cpp.al : 443   

Fallback TTL (sec): 3600 

VCL Snippets:  

Segmented Caching:  

```
# my custom enabled Segmented Caching code
if (req.url.ext ~ "(?i)(7z|bz2|gz|gzip|iso|json|rar|tar|tgz|ts|zip)$") {
   set req.enable_segmented_caching = true;
}
```

Set TTLs:  

```
# download archives
if (req.url.ext ~ "(?i)(7z|bz2|gz|gzip|iso|json|rar|tar|tgz|ts|zip)$") {
  set beresp.ttl = 2592000s;
  return (deliver);
}

# index pages
if (req.url ~ "/$") {
  set beresp.ttl = 300s;
  return (deliver);
}
```


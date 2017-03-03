#!/bin/bash

# checkMD5:  output MD5 sum of file(s), in a consistent manner across platforms

md5_func()
{
    # Mac OS/X 
    value=`md5 -q $1`
    echo "$value $1"
}

md5sum_func()
{
    # Linux
    md5sum $1
}


M5list="md5sum md5"
M5util=
M5func=
for util in $M5list ; do
    M5util=`type -P $util`
    if [ -n "$M5util" ] ; then
        M5func=${util}_func
    fi
done

if [ -z "$M5func" ] ; then
    echo "Error: could not find an MD5 utility in your \$PATH" >&2
    echo "       (looked for: $M5list)"
    exit 1
fi

for file in $@ ; do
    $M5func $file
done

#!/bin/bash

Errors=`egrep "Error|File|Traceback" $1`
if [ -n "$Errors" ] ; then
    echo "$Errors"
    exit 1
fi
exit 0

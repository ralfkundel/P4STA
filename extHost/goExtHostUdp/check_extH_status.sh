#!/bin/bash
declare file="receiver_finished.log"
declare regex="\s+True\s+"
declare file_content=$( cat "${file}" )
if [[ " $file_content " =~ $regex ]] # please preserve the space before and after the file content
    then
        echo "1" # if True is in "receiver_finished.log receiver is finished
    else
        echo "0"
fi
exit


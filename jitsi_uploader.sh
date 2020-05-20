#!/bin/bash

CONFIG_FILE_PATH="/etc/jitsi/uploader"

# pull jitsi uploader environment var overrides if it exists
[ -e  "$CONFIG_FILE_PATH" ] && . "$CONFIG_FILE_PATH"

#make this backed by a decent sized disk
[ -z "$FAILED_UPLOAD_DIR" ] && FAILED_UPLOAD_DIR="/tmp/failed"

#assume supporting binaries are in /usr/bin
BIN_PATH="/usr/bin"

UPLOAD_DIR=$1

if [ -z "$UPLOAD_DIR" ]; then
    echo "No upload directory provided, failing..."
    exit 1
fi

if [ ! -d "$UPLOAD_DIR" ]; then
    echo "No such directory $UPLOAD_DIR, failing..."
    exit 2
fi

METADATA_JSON="$UPLOAD_DIR/metadata.json"

if [[ ! -e "$METADATA_JSON" ]]; then
  echo "No file found $METADATA_JSON, failing."
  exit 3
fi

#only read token from metadata if token is not already defined
[[ -z "$TOKEN" ]] && TOKEN=$(cat $METADATA_JSON | jq -r ".upload_credentials.token")
[[ "$TOKEN" == "null" ]] && TOKEN=""
[[ -z "$UPLOAD_TYPE" ]] && UPLOAD_TYPE=$(cat $METADATA_JSON | jq -r ".upload_credentials.service_name")
[[ "$UPLOAD_TYPE" == "null" ]] && UPLOAD_TYPE=""
URL=$(cat $METADATA_JSON | jq -r ".meeting_url")
[[ "$URL" == "null" ]] && URL=""
URL_NAME="${URL##*/}"

if [[ -z "$UPLOAD_TYPE" ]]; then

  if [[ -f $BIN_PATH/jitsi-recording-service.sh ]] && [[ -x $BIN_PATH/jitsi-recording-service.sh ]]; then
    $BIN_PATH/jitsi-recording-service.sh $UPLOAD_DIR
    exit $?
  fi

  echo "No upload type found, skipping upload..."
  exit 4
fi


if [[ -z "$TOKEN" ]]; then
  echo "No upload credentials found, skipping upload..."
  exit 5
fi

case "$UPLOAD_TYPE" in
"dropbox")
    UPLOAD_FUNC="dropbox_upload"
    ;;
*)
    echo "Unknown upload type $UPLOAD_TYPE, skipping upload..."
    exit 6
    ;;
esac

#db uploader function
# $1 - current path to source file
# $2 - full path of destination
function dropbox_upload {
    echo "Upload method: dropbox"
    UPLOAD_BIN="$BIN_PATH/dropbox_uploader.sh"
    export OAUTH_ACCESS_TOKEN=$TOKEN
    $UPLOAD_BIN -b upload "$1" "$2"
    return $?
}

#processes direct with uploads
# $1 - path to directory for upload
function process_upload_dir {
    #final return defaults to success
    FRET=0;
    for i in $1/*; do
      b=$(basename "$i")
      if [[ "$b" == "metadata.json" ]]; then
        #skip, metadata
        echo "skipping metadata"
      else
        UPLOAD_FLAG=0
        echo "Upload Candidate $b"
        EXT="${b##*.}"
        MTIME=$(stat -c %Y "$i")
        FDATE=$(date --date="@$MTIME" '+%F %H-%M')
        if [[ "$EXT" == "pdf" ]]; then
          FINAL_UPLOAD_PATH="/Transcripts/$URL_NAME on $FDATE.pdf"
          UPLOAD_FLAG=1
        elif [[ "$EXT" == "mp4" ]]; then
          FINAL_UPLOAD_PATH="/Recordings/$URL_NAME on $FDATE.mp4"
          UPLOAD_FLAG=1
        else
          #skip this one, not a known type
          echo "Unknown extension $EXT, skipping $b"
        fi

        if [[ $UPLOAD_FLAG == 1 ]]; then
          echo "Uploading file $i to path $FINAL_UPLOAD_PATH"
          $UPLOAD_FUNC "$i" "$FINAL_UPLOAD_PATH"
          URET=$?
          #assign the final return value if non-zero return was found on upload
          if [[ $FRET == 0 ]] && [[ $URET != 0 ]]; then
            FRET=$URET
          fi
        fi
      fi
    done;
    return $FRET;
}

#now that everything is in order, run the uploader tool on the directory
echo $(date) "START Uploader tool received path \"$UPLOAD_DIR\""
echo $(date) $(ls -l $UPLOAD_DIR 2>&1)

process_upload_dir $UPLOAD_DIR

MRET=$?

if [ $MRET -eq 0 ]; then
    echo $(date) "END SUCCESS Cleaning remaining upload files in \"$UPLOAD_DIR\""
    #remove the files from the directory
    rm $UPLOAD_DIR/*
    rmdir $UPLOAD_DIR
else
    FAILED_UPLOAD_PATH="$FAILED_UPLOAD_DIR/$(basename $UPLOAD_DIR)"
    echo $(date) "END FAILURE Moving remaining upload files in \"$UPLOAD_DIR\" to \"$FAILED_UPLOAD_DIR\""
    #move the whle upload dir to failed processing
    mkdir -p $FAILED_UPLOAD_PATH
    mv $UPLOAD_DIR/* $FAILED_UPLOAD_PATH
fi

# exit based on return of upload processing
exit $MRET

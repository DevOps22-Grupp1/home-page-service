#!/bin/bash

echo ******************************************************
echo Starting-BACKUP
echo ******************************************************
# NOW="$(date +"%F")-$(date +"%T")"
NOW=$(date + %H)
FILE="$DB_NAME-$NOW"

# mongodump --uri=mongodb://$MONGODB_URI:$MONGOD_USER@$MONGOD_HOST:$MONGOD_PORT/$DB_NAME  --out=/mongodump/db/$FILE
mongodump --uri=$MONGODB_URI$DB_USERNAME:$DB_PASSWORD@$MONGOD_HOST:$MONGOD_PORT --out=/mongodump/db/$FILE
sleep 30 | echo End-BACKUP FOR $FILE
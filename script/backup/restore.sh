#!/bin/bash

echo ******************************************************
echo Starting-BACKUP
echo ******************************************************
NOW="$(date +"%F")-$(date +"%T")"

FILE="$DB_NAME"

# mongorestore --uri=$MONGODB_URI$DB_USERNAME:$DB_PASSWORD@$MONGOD_HOST:$MONGOD_PORT --out=/mongodump/db/$FILE
mongorestore --uri=$MONGODB_URI$DB_USERNAME:$DB_PASSWORD@$MONGOD_HOST:$MONGOD_PORT --verbose /mongodump/db/$FILE

sleep 30 | echo End-BACKUP

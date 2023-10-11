#!/bin/bash

echo "****************************************************"
echo "Starting-BACKUP"
echo "****************************************************"

EXTEND=$(ls -1 /mongodump/db/ | wc -l)
FILE="${DB_NAME}_${EXTEND}"

mongodump --uri="$MONGODB_URI$DB_USERNAME:$DB_PASSWORD@$MONGOD_HOST:$MONGOD_PORT" --out="/mongodump/db/$FILE"
sleep 30
echo "End-BACKUP FOR $FILE"
import pymongo
import os
from pymongo import MongoClient
# Anslut till MongoDB

db_username = os.environ.get("DB_USERNAME")
db_password = os.environ.get("DB_PASSWORD")
host = os.environ.get("DB_HOST")
db_port = os.environ.get("DB_PORT")
client = MongoClient(host, int(db_port),
                     username=db_username, password=db_password)

db = client["mydatabase"]  # Byt ut "mydatabase" mot namnet på din databas

# Skapa en samling (collection) om den inte redan finns
# Byt ut "mycollection" mot namnet på din samling
collection = db["mycollection"]

# Data att lägga till i samlingen
data_to_insert = [
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": 25},
    {"name": "Charlie", "age": 35},
    # Lägg till fler dokument efter behov
]

# Lägg till data i samlingen
inserted_ids = collection.insert_many(data_to_insert)

# Skriv ut de insatta dokumentens IDs
for _id in inserted_ids.inserted_ids:
    print(f"Inserted document with ID: {_id}")

# Stäng anslutningen till MongoDB
client.close()

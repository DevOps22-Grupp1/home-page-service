db.createUser({
  user: "bpalmer",
  pwd: "password",
  roles: [
    {
      role: "readWrite",
      db: "testdb",
    },
  ],
});
db.createCollection("users");
db.users.insertOne({
  id: 1,
  name: "Max Svensson",
  email: "me@gmail.com"
});
db.users.insertOne({
  id: 2,
  name: "Jarl Svensson",
  email: "js@gmail.com"
});
db.users.insertOne({
  id: 3,
  name: "Harisha Svensson",
  email: "hs@gmail.com",
});
db.users.insertOne({
  id: 4,
  name: "Dennis Svensson",
  email: "ds@gmail.com",
});
db.users.insertOne({
  id: 5,
  name: "Simon Svensson",
  email: "ss@gmail.com",
});
db.users.insertOne({
  id: 6,
  name: "Zoreh Svensson",
  email: "zs@gmail.com",
});

db.createCollection("orders");
db.orders.insertOne({
  order: "Samsung Galaxy S10",
  price: 999.99,
  user_id: 2,
});
db.orders.insertOne({
  order: "LG G8 ThinQ",
  price: 1499.99,
  user_id: 6,
});
db.orders.insertOne({
  order: "MSI GS65 Stealth Thin",
  price: 499.99,
  user_id: 5,
});
db.orders.insertOne({
  order: "Bowers & Wilkins PX7",
  price: 799.99,
  user_id: 4,
});
db.orders.insertOne({
  order: "Apple AirPods Pro",
  price: 699.99,
  user_id: 3,
});
db.orders.insertOne({
  order: "Air Jordan 1 Retro High OG",
  price: 2099.99,
  user_id: 1,
});

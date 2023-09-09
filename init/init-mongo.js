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
  name: "Bill Palmer",
  email: "bpalmer@gmail.com"
});
db.users.insertOne({
  name: "Lilly Smith",
  email: "lsmith@gmail.com"
});
db.createCollection("orders");
db.orders.insertOne({
  order: "Pizza",
  price: 10.99,
});

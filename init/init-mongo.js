db.createUser({
  user: "sudo_admin",
  pwd: "password",
  roles: [
    {
      role: "readWrite",
      db: "testdb",
    },
  ],
});

db.createCollection("users");
db.users.insertMany([{
  id: 1,
  name: "Max Svensson",
  email: "me@gmail.com"
},
{
  id: 2,
  name: "Jarl Svensson",
  email: "js@gmail.com"
},
{
  id: 3,
  name: "Harisha Svensson",
  email: "hs@gmail.com",
},
{
  id: 4,
  name: "Dennis Svensson",
  email: "ds@gmail.com",
},
{
  id: 5,
  name: "Simon Svensson",
  email: "ss@gmail.com",
},
{
  id: 6,
  name: "Zoreh Svensson",
  email: "zs@gmail.com",
}
]);

db.createCollection("orders");
db.orders.insertMany([
  {
  order: "Samsung Galaxy S10",
  price: 999.99,
  user_email: "me@gmail.com",

  order: "LG G8 ThinQ",
  price: 1499.99,
  user_email: "js@gmail.com",
},
{
  order: "MSI GS65 Stealth Thin",
  price: 499.99,
  user_email: "hs@gmail.com",
},
{
  order: "Bowers & Wilkins PX7",
  price: 799.99,
  user_email: "ds@gmail.com",
},
{
  order: "Apple AirPods Pro",
  price: 699.99,
  user_email: "ss@gmail.com",
},
{
  order: "Air Jordan 1 Retro High OG",
  price: 2099.99,
  user_email: "zs@gmail.com",
}
]);

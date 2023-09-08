const express = require('express');

const app = express();

app.get('/', async(req, res) => {
  let rep = await fetch("http://localhost:5002");
  console.log(rep.body);
  res.body()
});

app.listen(3000, () => console.log('Example app is listening on port 3000.'));


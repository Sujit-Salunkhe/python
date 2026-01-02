from fastapi import FastAPI
from enum import Enum
app = FastAPI()

@app.get('/hello/{name}')
async def say_hello(name: str):
    return {"message": f"Hello, {name}!"}

@app.get('/')
async def read_root():
    return {"message": "Welcome to the FastAPI application!"}

class aviable_menus(str, Enum):
    indian = "indian"
    italian = "italian"
    japanese = "japanese"
    mexican = "mexican"

food_items = {
  "indian": ["masala dosa", "butter chicken", "biryani"],
  "italian": ["pizza", "pasta carbonara", "gelato", "risotto"],
  "japanese": ["sushi", "ramen", "tempura"],
  "mexican": ["tacos", "guacamole", "enchiladas"]
}



@app.get('/items/{menu}')
async def read_item(menu: aviable_menus):
    return food_items.get(menu)
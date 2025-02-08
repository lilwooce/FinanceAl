from flask import Flask
from routes import app
from config import engine, Base

# 🔹 Initialize the database
Base.metadata.create_all(engine)

if __name__ == "__main__":
    app.run(debug=True)

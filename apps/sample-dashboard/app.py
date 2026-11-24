"""Fake sample dashboard for testing the sandbox deployment path."""
from flask import Flask, render_template

from data.client import get_orders

app = Flask(__name__)


@app.get("/")
def index():
    rows = get_orders()
    return render_template("index.html", rows=rows, total=sum(row["orders"] for row in rows))

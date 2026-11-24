"""Stub data client for the clean sample app. It makes no connection."""


def get_orders():
    return [
        {"region": "North", "orders": 12},
        {"region": "South", "orders": 9},
    ]

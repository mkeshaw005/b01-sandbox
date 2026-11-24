"""Sample dashboard with no credentials, used for the B00b D11 runs. Not a real app."""
from data.client import get_orders


def index():
    rows = get_orders()
    return {"orders": len(rows)}
# B01 acceptance test 20261124020412

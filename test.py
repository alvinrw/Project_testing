import time
from binance.client import Client

API_KEY = "bzkjaJ12OGvoGYHV77Q4CHdS4o9fUwTCwepFXZ2JSFn0xlabYZ5pULxeRqalyQcE"
API_SECRET = "wjqRV1v3KUNAF3HAQawWSUhOmnX8gadDc9bC2moNa8fftS8vWD2OgH4KC8t3kjWw"

client = Client(API_KEY, API_SECRET, testnet=True)

# Sync time between local and Binance server to avoid Timestamp ahead error
server_time = client.get_server_time()['serverTime']
system_time = int(time.time() * 1000)
client.timestamp_offset = server_time - system_time

# Cek saldo USDT virtual
balance = client.get_asset_balance(asset='USDT')
print("Saldo USDT Testnet:", balance)
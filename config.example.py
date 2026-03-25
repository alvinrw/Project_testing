# config.py
# File untuk menset semua pengaturan kunci bot

API_KEY = "your_api_key_here"
API_SECRET = "your_api_secret_here"

# Gunakan Testnet agar tidak memakai uang sungguhan saat testing
USE_TESTNET = True

# Pengaturan Telegram
TELEGRAM_BOT_TOKEN = "your_telegram_bot_token_here"
TELEGRAM_CHAT_ID = "your_telegram_chat_id_here"

# Pengaturan Trading
QUOTE_ASSET = "USDT"         # Hanya trade koin yang berpasangan dengan USDT
TRADE_AMOUNT_USDT = 50.0     # Modal per trade (Beli 50 USDT per transaksi)
STARTING_BALANCE = 10000.0   # Modal Awal (Untuk menghitung nilai PnL Profit/Loss di Telegram)
MAX_OPEN_POSITIONS = 2       # Batas maksimal buka koin bersamaan (isi 0 atau False untuk Unlimited)
STOP_LOSS_PERCENT = 1.5      # Cut Loss Otomatis jika turun 1.5%
TAKE_PROFIT_PERCENT = 3.0    # Take Profit Otomatis jika naik 3.0%

# Pengaturan Strategi (Golden Trifecta)
EMA_LENGTH = 200
RSI_LENGTH = 14
RSI_OVERSOLD_THRESHOLD = 30
RSI_OVERBOUGHT_THRESHOLD = 70

# Pengaturan Worker (Multiprocessing/Threading)
NUM_WORKERS = 1            # Jumlah pekerja yang mengecek koin secara bersamaan
KLINE_INTERVAL = "15m"       # Timeframe Candlestick: 15 menit (bisa diganti "1h" atau "5m")
KLINE_LIMIT = 250            # Butuh setidaknya 200 candle untuk hitung EMA 200

# Pengaturan State Internal (Bot Telegram Interaktif)
BOT_ACTIVE = False           # Ganti ke True jika ingin bot otomatis jalan saat script dijalankan (tanpa tunggu /run)
SKIPPED_SIGNALS = []         # Menyimpan sinyal koin bagus yang terlewat karena slot posisi penuh

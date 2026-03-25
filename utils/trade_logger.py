import os
import csv
from datetime import datetime

LOGS_DIR = "logs"
TRADE_CSV = os.path.join(LOGS_DIR, "trades.csv")

def ensure_logs_dir_exists():
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)
        
def init_trade_logger():
    ensure_logs_dir_exists()
    
    # Buat file dan tulis header jika belum ada
    if not os.path.exists(TRADE_CSV):
        with open(TRADE_CSV, mode="w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Symbol", "Action", "Price", "Amount USDT", "Strategy", "Note"])

def log_trade(symbol: str, action: str, price: float, amount_usdt: float, strategy: str = "Golden Trifecta", note: str = ""):
    """
    Merekam rekap setiap kali bot selesai Buy (Buka posisi) atau Sell (Take profit).
    """
    ensure_logs_dir_exists()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(TRADE_CSV, mode="a", newline='') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, symbol, action, f"{price:.4f}", f"{amount_usdt:.2f}", strategy, note])

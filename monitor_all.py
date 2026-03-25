import time
import os
# For newer python-binance versions, we should use ThreadedWebsocketManager
from binance import ThreadedWebsocketManager

API_KEY = "bzkjaJ12OGvoGYHV77Q4CHdS4o9fUwTCwepFXZ2JSFn0xlabYZ5pULxeRqalyQcE"
API_SECRET = "wjqRV1v3KUNAF3HAQawWSUhOmnX8gadDc9bC2moNa8fftS8vWD2OgH4KC8t3kjWw"


def process_message(msg):
    """
    Fungsi ini dipanggil setiap kali Binance mengirimkan update data (setiap detik!).
    """
    # msg adalah list dari semua koin. Kita filter yang USDT saja.
    updates = []
    
    for item in msg:
        symbol = item['s'] # Nama pasangan koin, misal BTCUSDT
        if symbol.endswith('USDT'):
            price_change_percent = float(item['P']) # Persentase perubahan 24 jam
            last_price = float(item['c'])          # Harga terakhir
            volume = float(item['q'])              # Volume dalam USDT
            
            updates.append({
                'symbol': symbol,
                'price': last_price,
                'change': price_change_percent,
                'volume': volume
            })
            
    # Kita urutkan berdasarkan koin yang naik paling tinggi (Gainers Tertinggi)
    updates.sort(key=lambda x: x['change'], reverse=True)
    
    # Supaya tidak spam terminal, kita bersihkan layar setiap 2 detik dan print ulang Top 5
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("="*50)
    print("  LIVE MONITOR: TOP 5 KOIN USDT NAIK TERTINGGI  ")
    print("="*50)
    for i in range(5):
        if i < len(updates):
            coin = updates[i]
            print(f"{i+1}. {coin['symbol']:<10} | Harga: {coin['price']:>10.4f} | Naik: +{coin['change']:.2f}% | Vol: ${coin['volume']:,.0f}")
            
    print("\n" + "="*50)
    print("  LIVE MONITOR: TOP 5 KOIN USDT TURUN TERDALAM  ")
    print("="*50)
    # 5 Terbawah
    for i in range(1, 6):
        if i <= len(updates):
            coin = updates[-i]
            print(f"{i}. {coin['symbol']:<10} | Harga: {coin['price']:>10.4f} | Turun: {coin['change']:.2f}% | Vol: ${coin['volume']:,.0f}")
            
    print("\nTekan Ctrl+C untuk berhenti...")

def main():
    print("Menghubungkan ke server Binance (Mainnet)...")
    
    # Kita menggunakan Testnet karena Mainnet Binance ('api.binance.com') kadang di-intercept ISP (SSL Error)
    twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=API_SECRET, testnet=True)
    
    # Mulai manager websocket
    twm.start()
    
    # Subscribe ke "All Market Tickers" (semua koin sekaligus!)
    # Binance akan push data ke fungsi process_message secara otomatis.
    print("Berhasil terhubung! Menunggu aliran data pertama... (Sekitar 1-2 detik)")
    twm.start_ticker_socket(callback=process_message)
    
    try:
        # Biarkan bot berjalan terus (blocking) 
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nBot Dihentikan!")
        twm.stop()

if __name__ == "__main__":
    main()

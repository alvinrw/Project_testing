import sys
import io
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Force UTF-8 on Windows Console so Emojis don't crash
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from binance.client import Client
from binance.exceptions import BinanceAPIException

# Custom Modules
import config
from core.data_fetcher import get_historical_klines_df
from core.strategy import calculate_golden_trifecta
from core.executer import open_buy_position
from utils.telegram_notifier import send_telegram_message, start_telegram_polling, set_binance_client, auto_check_closed_trades
from utils.trade_logger import init_trade_logger

def get_current_active_symbols(client: Client):
    """
    Menghitung posisi aktif berdasarkan koin yang Punya Nilai Signifikan (> 2 USDT).
    Mengabaikan koin 'debu' (dust) sisa testnet agar tidak memenuhi kuota posisi.
    """
    try:
        acc = client.get_account()
        # Ambil semua harga sekaligus (biar cepat & nggak kena ban)
        all_tickers = {t['symbol']: float(t['price']) for t in client.get_symbol_ticker()}
        
        active_symbols = set()
        for a in acc['balances']:
            asset = a['asset']
            if asset == 'USDT': continue
            
            qty = float(a['free']) + float(a['locked'])
            if qty <= 0: continue
            
            sym = f"{asset}USDT"
            price = all_tickers.get(sym, 0)
            
            # Jika nilai koin > 2 USDT, baru kita anggap "Posisi Aktif"
            if (qty * price) > 2.0:
                active_symbols.add(sym)
                
        return active_symbols
    except Exception as e:
        print(f"[API ERROR] Gagal cek saldo wallet: {e}")
        return set()

def get_all_usdt_pairs(client: Client):
    """
    Mengambil daftar semua koin yang berakhiran USDT dan berstatus TRADING.
    """
    try:
        info = client.get_exchange_info()
        symbols = [s['symbol'] for s in info['symbols'] if s['quoteAsset'] == config.QUOTE_ASSET and s['status'] == 'TRADING']
        return symbols
    except Exception as e:
        print(f"[API ERROR] Gagal mendownload Exchange Info: {e}")
        return []

def worker_task(client: Client, symbol: str):
    """
    Fungsi utama yang dilakukan oleh masing-masing 'Worker' untuk menganalisa SATU koin.
    """
    # 1. Unduh Data Lilin Historis (Klines)
    df = get_historical_klines_df(client, symbol)
    if df is None or df.empty:
        return (symbol, 'ERROR', 'Gagal Fetch Data')
        
    current_price = df.iloc[-1]['close']
    
    # 2. Kaluklasi Indikator (EMA, RSI, MACD)
    decision = calculate_golden_trifecta(df, rsi_len=config.RSI_LENGTH, ema_len=config.EMA_LENGTH)
    
    signal = decision['signal']
    reason = decision['reason']
    
    # 3. Eksekusi Jual / Beli
    if signal == 'BUY':
        return (symbol, 'BUY_READY', reason, current_price)
        
    return (symbol, signal, reason, current_price)

def main():
    print("="*50)
    print(" 🚀 STARTING SCALABLE BINANCE BOT (TESTNET) 🚀  ")
    print("="*50)
    
    # Inisialisasi file CSV
    init_trade_logger()
    
    # 1. Inisialisasi Binance Client
    print("[1/3] Menghubungkan ke API Binance...")
    client = Client(config.API_KEY, config.API_SECRET, testnet=config.USE_TESTNET)
    
    # Berikan akses klien API ke modul Telegram agar bisa mengecek status posisi LIVE
    set_binance_client(client)
    
    # Sinkronisasi Waktu Server
    try:
        server_time = client.get_server_time()['serverTime']
        client.timestamp_offset = server_time - int(time.time() * 1000)
        print("✅ Terhubung Spesifik: Time Offset Synced.")
    except Exception as e:
        print(f"❌ Gagal Sync Waktu: {e}")
        return
        
    # Kirim Pesan Telegram awal
    send_telegram_message("🤖 <b>Bot Scalable Mulai Berjalan! Mode: RUNNING 24/7</b>\nMencari sinyal: <i>Golden Trifecta</i>")
    
    # 2. Ambil Semua Koin USDT
    print("[2/3] Mengunduh daftar koin USDT aktif...")
    symbols = get_all_usdt_pairs(client)
    print(f"✅ Ditemukan {len(symbols)} pasangan {config.QUOTE_ASSET} yang bisa ditrading-kan.")
    
    if not symbols:
        print("❌ Tidak ada koin yang ditemukan.")
        return

    # Mulai pendengar Telegram di latar belakang
    start_telegram_polling()

    # Loop utama 24 Jam
    cycle = 1
    print(f"[3/3] Memulai sistem multi-worker ({config.NUM_WORKERS} Threads)...\n")
    
    while True:
        try:
            # Pengecekan status Toggle Bot dari perintah Telegram (/run, /stop)
            if not config.BOT_ACTIVE:
                # Jangan spam layar saat tidur, cukup tunggu
                time.sleep(5)
                continue
                
            print(f"--- TANDA MULAI SIKLUS #{cycle} ---")
            start_time = time.time()
            
            max_pos = config.MAX_OPEN_POSITIONS
            active_symbols = get_current_active_symbols(client)
            current_pos = len(active_symbols) if max_pos else 0
            
            if max_pos:
                print(f"--- LIMIT POSISI AKTIF: {current_pos}/{max_pos} Terisi ---")
                
            # Mengecek apakah ada posisi yang baru saja tertutup otomatis di market
            auto_check_closed_trades(client)
            
            # 3. Kirimkan semua koin (400+) ke sistem pekerja pool (ThreadPoolExecutor) menggunakan Batch Processing
            # Agar cepat, kita lempar puluhan pekerjaan ini secara otomatis agar berjalan paralel
            with ThreadPoolExecutor(max_workers=config.NUM_WORKERS) as executor:
                # Daftarkan semua pekerjaan
                futures = {executor.submit(worker_task, client, sym): sym for sym in symbols}
                
                # Tunggu dan proses hasilnya satu per satu yang sudah selesai
                for future in as_completed(futures):
                    symbol = futures[future]
                    try:
                        sym, signal, reason, current_price = future.result()
                        # Jika sudah pegang koin ini, jangan beli lagi sampe laku!
                        if sym in active_symbols and signal == 'BUY_READY':
                            print(f"🔄 [HOLD] {sym} sudah ada di dompet, skip Beli.")
                            continue
                            
                        # Jika ada sinyal BUY dicetak
                        if signal == 'BUY_READY':
                             print(f"🔥 [BUY SIGNAL] {sym}: {reason}")
                             if max_pos and current_pos >= max_pos:
                                 print(f"🔒 [SKIPPED] Beli {sym} dibatalkan karena batas posisi ({max_pos}) penuh.")
                                 # Catat ke memori agar bisa dilihat dari fitur /bagus Telegram
                                 config.SKIPPED_SIGNALS.append(f"💎 <b>{sym}</b> (Harga: <code>{current_price}</code>)\n   └ <i>{reason}</i>")
                                 if len(config.SKIPPED_SIGNALS) > 50:
                                     config.SKIPPED_SIGNALS.pop(0) # hapus riwayat terlama
                             else:
                                 # Buka posisi
                                 success = open_buy_position(client, sym, current_price, reason)
                                 if success:
                                     active_symbols.add(sym)
                                     current_pos += 1
                    except Exception as exc:
                        print(f"⚠️ [WORKER ERROR] Gagal memproses {symbol}: {exc}")
                        
            elapsed = time.time() - start_time
            print(f"--- SIKLUS #{cycle} SELESAI ({elapsed:.2f} detik) ---")
            
            # Jeda sebelum siklus berikutnya agar tidak terkena limit rate Binance terlalu parah
            # Binance mengizinkan sekitar 1200 request/menit, kita tunggu 30 detik untuk aman.
            print("⏳ Menunggu 30 detik sebelum pemindaian ulang...\n")
            time.sleep(30)
            
            cycle += 1
            # (Opsional) Refresh list koin sesekali bisa ditambahkan di sini
            
        except KeyboardInterrupt:
            print("\n🛑 Dihentikan Otomatis oleh Sistem/User (Ctrl+C).")
            send_telegram_message("🔴 <b>Bot Dihentikan</b> - User mematikan sistem.")
            break
        except Exception as massive_err:
            print(f"FATAL ERROR LUBANG: {massive_err}")
            time.sleep(10)

if __name__ == "__main__":
    main()

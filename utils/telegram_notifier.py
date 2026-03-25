import telebot
import config
from threading import Thread
from utils.telegram_state import save_chat_id, get_chat_id

# Inisialisasi Bot Telegram
bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN)
binance_client = None

def set_binance_client(client):
    global binance_client
    binance_client = client

def send_telegram_message(message: str):
    """
    Mengirim pesan ke Telegram. Coba gunakan Chat ID dari file agar tidak lupa setelah Ctrl+C.
    """
    chat_id = get_chat_id() or config.TELEGRAM_CHAT_ID
    if chat_id == "ISI_CHAT_ID_DI_SINI_NANTI" or not chat_id:
        print(f"[LOCAL NOTIFICATION] {message}\n")
        return
        
    try:
        bot.send_message(chat_id, message, parse_mode="HTML")
    except Exception as e:
        print(f"[TELEGRAM ERROR] Gagal mengirim pengumuman: {e}")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = str(message.chat.id)
    save_chat_id(chat_id)
    config.TELEGRAM_CHAT_ID = chat_id
    bot.reply_to(message, f"👋 <b>Halo Bos!</b>\n\nID Chat kamu: <code>{chat_id}</code> tersimpan permanen. Mulai sekarang Notif akan masuk.\n\n"
                          f"<b>⚙️ Daftar Perintah Kontrol Sistem:</b>\n"
                          f"/run - Mengaktifkan radar pemantau 24/7\n"
                          f"/stop - Mengistirahatkan radar\n"
                          f"/status - Mengecek posisi koin-koin yang masuk keranjang\n"
                          f"/done - Mengecek hasil akhir (Profit/Rugi) trade yang sudah tertutup\n"
                          f"/log - Mengecek riwayat pembelian terakhir bot (Log CSV)\n"
                          f"/bagus - Melihat potesi koin incaran terbaik yang di-skip mesin", parse_mode="HTML")

@bot.message_handler(commands=['run'])
def cmd_run(message):
    config.BOT_ACTIVE = True
    bot.reply_to(message, "🟢 <b>Mesin V12 Trading DIAKTIFKAN!</b>\nMesin mulai memindai 400+ koin pada background...", parse_mode="HTML")

@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    config.BOT_ACTIVE = False
    bot.reply_to(message, "🔴 <b>Bot Trading DIHENTIKAN!</b>\nMesin di-pause menunggu perintah /run berikutnya.", parse_mode="HTML")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    status_text = "🟢 AKTIF (Berburu Sinyal)" if config.BOT_ACTIVE else "🔴 TIDUR (Jeda Istirahat)"
    
    active_info = "<i>Tidak ada posisi yang bergantung di Market saat ini.</i>"
    current_pos_count = 0
    pnl_text = ""
    
    if binance_client:
        try:
            # Kalkulasi PnL / Equity
            acc = binance_client.get_account()
            free_usdt = float(next((a['free'] for a in acc['balances'] if a['asset'] == 'USDT'), 0))
            locked_usdt = float(next((a['locked'] for a in acc['balances'] if a['asset'] == 'USDT'), 0))
            total_usdt = free_usdt + locked_usdt
            
            orders = binance_client.get_open_orders()
            sell_orders = [o for o in orders if o['side'] == 'SELL' and o['symbol'].endswith('USDT')]
            symbols = list(set([o['symbol'] for o in sell_orders]))
            current_pos_count = len(symbols)
            
            open_assets_value = 0.0
            
            if current_pos_count > 0:
                active_info = "<b>Daftar Posisi Aktif Saat Ini:</b>\n"
                for sym in symbols:
                    sym_orders = [o for o in sell_orders if o['symbol'] == sym]
                    tp = next((o['price'] for o in sym_orders if o['type'] == 'LIMIT_MAKER'), "N/A")
                    sl = next((o['stopPrice'] for o in sym_orders if o['type'] == 'STOP_LOSS_LIMIT'), "N/A")
                    
                    # Cek harga market saat ini untuk koin tersebut
                    ticker = binance_client.get_symbol_ticker(symbol=sym)
                    current_price = float(ticker['price'])
                    
                    # Cari harga Beli (Entry Price) dari riwayat lokal kita
                    entry_price = "N/A"
                    import os
                    from utils.trade_logger import TRADE_CSV
                    if os.path.exists(TRADE_CSV):
                        with open(TRADE_CSV, "r", encoding="utf-8") as f:
                            for line in reversed(f.readlines()):
                                cols = line.strip().split(',')
                                if len(cols) >= 4 and cols[1] == sym and cols[2].upper() == "BUY":
                                    entry_price = cols[3]
                                    break
                    
                    # Hitung valuasi koin yang di-hold
                    base_asset = sym.replace('USDT', '')
                    asset_bal = float(next((a['free'] for a in acc['balances'] if a['asset'] == base_asset), 0))
                    asset_bal += float(next((a['locked'] for a in acc['balances'] if a['asset'] == base_asset), 0))
                    open_assets_value += (asset_bal * current_price)
                    
                    active_info += f"▻ <b>{sym}</b>\n   🏷️ Masuk (Beli): <code>{entry_price}</code> | 🔄 Skrg: <code>{current_price}</code>\n   🎯 TP: {tp} | 🛡️ SL: {sl}\n"
                    
            # Total kekayaan (Saldo nganggur + Nilai aset berjalan)
            total_equity = total_usdt + open_assets_value
            pnl = total_equity - config.STARTING_BALANCE
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            
            pnl_text = (f"💰 <b>Modal Awal:</b> {config.STARTING_BALANCE:,.2f} USDT\n"
                        f"💵 <b>Estimasi Saldo Total:</b> {total_equity:,.2f} USDT\n"
                        f"📈 <b>P/L (Profit/Loss):</b> {pnl_emoji} {pnl:,.2f} USDT\n"
                        f"💸 <b>Sisa USDT Nganggur:</b> {total_usdt:,.2f} USDT\n\n")

        except Exception as e:
            active_info = f"⚠️ <i>Gagal menyedot database Binance: {e}</i>"

    bot.reply_to(message, f"📊 <b>Laporan Status 24/7:</b>\n\n"
                          f"Sistem: {status_text}\n"
                          f"Batas Koleksi Posisi: {current_pos_count} / {config.MAX_OPEN_POSITIONS}\n\n"
                          f"{pnl_text}"
                          f"{active_info}\n\n"
                          f"Sinyal /bagus Tersimpan: {len(config.SKIPPED_SIGNALS)} koin", parse_mode="HTML")

@bot.message_handler(commands=['log', 'logs'])
def cmd_log(message):
    import os
    from utils.trade_logger import TRADE_CSV
    
    if not os.path.exists(TRADE_CSV):
        bot.reply_to(message, "📜 Belum ada catatan log transaksi sama sekali.")
        return
        
    try:
        with open(TRADE_CSV, mode="r", encoding="utf-8") as f:
            lines = f.readlines()
            
        if len(lines) <= 1:
            bot.reply_to(message, "📜 Log masih kosong (Hanya ada baris judul).")
            return
            
        recent_logs = lines[-7:] # Ambil maksimal 7 baris terakhir
        
        reply_msg = "📜 <b>Riwayat Transaksi Terakhir (Log CSV):</b>\n\n"
        for line in reversed(recent_logs):
            cols = line.strip().split(',')
            if len(cols) >= 5:
                waktu = cols[0]
                koin = cols[1]
                aksi = cols[2]
                harga = cols[3]
                modal = cols[4]
                
                emoji = "✅" if aksi.upper() == "BUY" else "💰"
                reply_msg += f"{emoji} <b>{aksi} {koin}</b>\n   🕒 {waktu}\n   💲 Harga eksekusi: <code>{harga}</code> USDT\n   💳 Modal dialokasikan: {modal} USDT\n\n"
                
        bot.reply_to(message, reply_msg, parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Gagal membaca file log: {e}")

@bot.message_handler(commands=['bagus', 'aslinya_bagus'])
def cmd_bagus(message):
    if not config.SKIPPED_SIGNALS:
        bot.reply_to(message, "🤷‍♂️ Keranjang log masih kosong. Belum ada sinyal koin cakep siang ini.")
    else:
        text = "\n\n".join(config.SKIPPED_SIGNALS[-8:])
        bot.reply_to(message, f"⭐ <b>8 Sinyal Terbaik Terakhir (Terpaksa Diabaikan Karena Slot Habis):</b>\n\n{text}", parse_mode="HTML")

@bot.message_handler(commands=['done', 'history'])
def cmd_done(message):
    import os
    from utils.trade_logger import TRADE_CSV
    
    if not binance_client:
        bot.reply_to(message, "⚠️ API Binance belum terhubung sepenuhnya.")
        return

    if not os.path.exists(TRADE_CSV):
        bot.reply_to(message, "📜 Belum ada catatan log transaksi secara lokal.")
        return
        
    bot.reply_to(message, "🔍 Sedang menyedot data history tertutup dari Binance... Mohon tunggu sebentar.")
    
    try:
        # 1. Ambil history BUY kita
        buy_history = []
        with open(TRADE_CSV, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in reversed(lines):
                cols = line.strip().split(',')
                if len(cols) >= 7 and cols[2].upper() == "BUY":
                    buy_history.append({
                        'time': cols[0],
                        'symbol': cols[1],
                        'entry_price': float(cols[3]),
                        'budget': float(cols[4]),
                        'note': cols[6]
                    })
                if len(buy_history) >= 15: # Ambil 15 histori koin terakhir
                    break
        
        if not buy_history:
            bot.send_message(message.chat.id, "Belum ada transaksi Beli.")
            return

        # 2. Cek open orders untuk mengetahui koin yang statusnya MASIH AKTIF (Belum Done)
        open_orders = binance_client.get_open_orders()
        active_symbols = set([o['symbol'] for o in open_orders if o['side'] == 'SELL' and o['symbol'].endswith('USDT')])
        
        reply_msg = "🏁 <b>HISTORI TRADE SELESAI (/Done):</b>\n\n"
        closed_count = 0
        
        # 3. Proses hanya koin yang sudah di-BUY tapi sudah TIDAK ADA di open_orders (Artinya sudah TP / SL)
        for trade in buy_history:
            sym = trade['symbol']
            
            # Jika masih aktif (nggantung), abaikan
            if sym in active_symbols:
                continue
                
            # Jika sudah tidak aktif, cari riwayat SELL terakhir di akun untuk koin ini
            my_trades = binance_client.get_my_trades(symbol=sym, limit=10)
            sell_trades = [t for t in my_trades if not t['isBuyer']] # isBuyer = False (Artinya SELL)
            
            if not sell_trades:
                continue # Belum kejual sama sekali (Mungkin SL dicancel manual dll)
                
            last_sell = sell_trades[-1]
            sell_price = float(last_sell['price'])
            sell_qty = float(last_sell['qty'])
            usd_received = sell_price * sell_qty
            usd_spent = trade['budget']
            
            pnl = usd_received - usd_spent
            pnl_pct = (pnl / usd_spent) * 100
            
            icon = "🟢" if pnl > 0 else "🔴"
            status_text = "PROFIT (TP)" if pnl > 0 else "LOSS (SL)"
            
            reply_msg += (
                f"{icon} <b>{sym}</b> ({status_text})\n"
                f"   🔸 Harga Beli: <code>{trade['entry_price']}</code>\n"
                f"   🔹 Terjual di: <code>{sell_price}</code>\n"
                f"   📋 Setup: <i>{trade['note']}</i>\n"
                f"   💰 P/L: <b>{pnl:+.2f} USDT ({pnl_pct:+.2f}%)</b>\n\n"
            )
            closed_count += 1
            
            if closed_count >= 5: # Batasi tampilkan 5 terakhir biar Telegram nggak kepanjangan
                break
                
        if closed_count == 0:
            bot.send_message(message.chat.id, "Semua trade kamu masih <i>menggantung (floating)</i> di market. Belum ada yang selesai atau kena TP/SL.", parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, reply_msg, parse_mode="HTML")

    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Gagal mengekstrak history dari Binance: {e}")

def run_telegram_bot_thread():
    print("[TELEGRAM] Interaktif Bot telah on air! (Silakan Ketik /start di HP Anda)")
    bot.infinity_polling()

def start_telegram_polling():
    t = Thread(target=run_telegram_bot_thread, daemon=True)
    t.start()

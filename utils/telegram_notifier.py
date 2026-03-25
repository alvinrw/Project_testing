import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
import os
import csv
from threading import Thread
from utils.telegram_state import save_chat_id, get_chat_id
from utils.trade_logger import TRADE_CSV, log_trade

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
                          f"/bagus - Melihat potesi koin incaran terbaik yang di-skip mesin\n"
                          f"/reset - NUCLEAR RESET: Jual semua koin ke USDT & hapus history", parse_mode="HTML")

@bot.message_handler(commands=['reset', 'clear'])
def cmd_reset(message):
    chat_id = message.chat.id
    if not binance_client:
        bot.reply_to(message, "⚠️ API Belum Siap")
        return

    bot.reply_to(message, "☢️ <b>NUCLEAR RESET DIMULAI...</b>\nSedang membersihkan semua posisi dan order. Mohon tunggu.", parse_mode="HTML")
    
    try:
        # 1. Batalkan SEMUA Open Orders di akun (Try-Except per koin biar gak mandek)
        open_orders = binance_client.get_open_orders()
        cancel_count = 0
        for o in open_orders:
            try:
                binance_client.cancel_order(symbol=o['symbol'], orderId=o['orderId'])
                cancel_count += 1
            except Exception: pass
            
        # 2. Ambil semua aset yang punya saldo > 0 dan bukan USDT
        acc = binance_client.get_account()
        balances = [b for b in acc['balances'] if float(b['free']) + float(b['locked']) > 0.0001 and b['asset'] != 'USDT']
        
        sold_count = 0
        for b in balances:
            asset = b['asset']
            symbol = f"{asset}USDT"
            qty = float(b['free']) + float(b['locked'])
            
            try:
                info = binance_client.get_symbol_info(symbol)
                if not info: 
                    print(f"Skipping {symbol}: Symbol info not found")
                    continue
                
                from binance.helpers import round_step_size
                lot_f = next((f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
                if not lot_f: continue
                
                step = float(lot_f['stepSize'])
                final_qty = round_step_size(qty, step)
                
                if final_qty > 0:
                    try:
                        binance_client.create_order(symbol=symbol, side='SELL', type='MARKET', quantity=final_qty)
                        sold_count += 1
                        time.sleep(0.1) # Kasih nafas dikit biar gak kena ban
                    except Exception as e_sell:
                        print(f"Gagal jual {symbol}: {e_sell}")
            except Exception as e_info:
                print(f"Gagal dapat info {symbol}: {e_info}")

        # ... (rest of cleanup) ...
        # Update Threshold di Status (Baris 240 an)
        # (I will do this in another chunk or same)

        # 3. Bersihkan file LOG dan Notifikasi
        import os
        from utils.trade_logger import TRADE_CSV
        if os.path.exists(TRADE_CSV):
            with open(TRADE_CSV, "w", newline='') as f:
                import csv
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Symbol", "Action", "Price", "Amount USDT", "Strategy", "Note"])
        
        notified_file = os.path.join("logs", "notified_closed.txt")
        if os.path.exists(notified_file):
            with open(notified_file, "w") as f: f.write("")
            
        config.SKIPPED_SIGNALS = []
        
        # 4. Ambil Saldo Baru & Reset Modal Awal
        new_acc = binance_client.get_account()
        free_usdt = float(next((a['free'] for a in new_acc['balances'] if a['asset'] == 'USDT'), 0))
        locked_usdt = float(next((a['locked'] for a in new_acc['balances'] if a['asset'] == 'USDT'), 0))
        new_balance = free_usdt + locked_usdt
        config.STARTING_BALANCE = new_balance
        
        # 5. Update Permanen di File config.py
        try:
            config_path = os.path.join(os.getcwd(), "config.py")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                with open(config_path, "w", encoding="utf-8") as f:
                    for line in lines:
                        if "STARTING_BALANCE =" in line:
                            f.write(f"STARTING_BALANCE = {new_balance:.2f}   # Auto-reset via /reset\n")
                        else:
                            f.write(line)
        except Exception as e_file:
            print(f"Gagal update file config.py: {e_file}")

        bot.send_message(chat_id, f"✅ <b>NUCLEAR RESET BERHASIL!</b>\n\n- {cancel_count} Order dibatalkan.\n- {sold_count} Koin disapu bersih ke USDT.\n- History & Log dikosongkan.\n- Modal Awal di-reset permanen ke: <b>{new_balance:,.2f} USDT</b>.\n- P/L kamu sekarang murni <b>0%</b>.\n\nSekarang bot kamu bersih total dari nol! 🚀", parse_mode="HTML")

    except Exception as e:
        bot.send_message(chat_id, f"❌ Terjadi kesalahan fatal saat Reset: {e}")

@bot.message_handler(commands=['run'])
def cmd_run(message):
    config.BOT_ACTIVE = True
    bot.reply_to(message, "🟢 <b>Mesin V12 Trading DIAKTIFKAN!</b>\nMesin mulai memindai 400+ koin pada background...", parse_mode="HTML")

@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    config.BOT_ACTIVE = False
    bot.reply_to(message, "🔴 <b>Bot Trading DIHENTIKAN!</b>\nMesin di-pause menunggu perintah /run berikutnya.")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    # set_binance_client() # This line is not needed here, client is set globally
    status_text = "🟢 AKTIF (Berburu Sinyal)" if config.BOT_ACTIVE else "🔴 TIDUR (Jeda Istirahat)" # Reverted to BOT_ACTIVE as RUN_STATUS is not defined
    
    # Inisialisasi variabel default biar nggak Error "referenced before assignment"
    total_usdt = 0
    total_equity = 0
    realized_pnl = 0
    unrealized_pnl = 0
    open_assets_value = 0
    active_info = "<i>Tidak ada posisi yang bergantung di Market saat ini.</i>"
    current_pos_count = 0
    pnl_text = ""
    markup = InlineKeyboardMarkup()
    
    if binance_client:
        try:
            # 1. Hitung Realized P/L
            if os.path.exists(TRADE_CSV):
                buys = {}
                with open(TRADE_CSV, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    next(reader) 
                    for row in reader:
                        if len(row) < 7: continue
                        sym, action, price, amount = row[1], row[2], float(row[3]), float(row[4])
                        if action == "BUY":
                            buys[sym] = amount
                        elif action == "SELL":
                            note = row[6]
                            if "PNL:" in note:
                                try:
                                    pnl_val = float(note.split("PNL:")[1].split("USDT")[0].strip())
                                    realized_pnl += pnl_val
                                except: pass

            # 2. Ambil data Wallet
            acc = binance_client.get_account()
            free_usdt = float(next((a['free'] for a in acc['balances'] if a['asset'] == 'USDT'), 0))
            locked_usdt = float(next((a['locked'] for a in acc['balances'] if a['asset'] == 'USDT'), 0))
            total_usdt = free_usdt + locked_usdt
            
            orders = binance_client.get_open_orders()
            sell_orders = [o for o in orders if o['side'] == 'SELL' and o['symbol'].endswith('USDT')]
            symbols = list(set([o['symbol'] for o in sell_orders]))
            current_pos_count = len(symbols)
            
            open_assets_value = 0.0
            
            # 3. Hitung Floating (Unrealized) P/L posisi yang sedang jalan
            unrealized_pnl = 0
            open_assets_value = 0
            active_info = "<b>Daftar Posisi Aktif Saat Ini:</b>\n"
            
            # Baca Log untuk cari harga beli terakhir (Entry Price)
            buy_prices = {}
            if os.path.exists(TRADE_CSV):
                 with open(TRADE_CSV, "r", encoding="utf-8") as f:
                    rows = list(csv.reader(f))
                    for row in reversed(rows):
                        if len(row) >= 4 and row[2] == "BUY":
                            if row[1] not in buy_prices: 
                                buy_prices[row[1]] = float(row[3])

            for b in acc['balances']:
                asset = b['asset']
                if asset == 'USDT': continue
                
                qty = float(b['free']) + float(b['locked'])
                if qty > 0.0001:
                    sym = f"{asset}USDT"
                    try:
                        ticker = binance_client.get_symbol_ticker(symbol=sym)
                        curr_price = float(ticker['price'])
                        asset_val = qty * curr_price
                        open_assets_value += asset_val
                        
                        # Cari Entry Price
                        entry = buy_prices.get(sym)
                        if not entry:
                             try:
                                my_trades = binance_client.get_my_trades(symbol=sym, limit=5)
                                buy_trades = [t for t in my_trades if t['isBuyer']]
                                if buy_trades: entry = float(buy_trades[-1]['price'])
                             except: pass
                        
                        ur_pnl_str = ""
                        if entry:
                            ur_pnl_val = (curr_price - entry) * qty
                            ur_pnl_pct = ((curr_price - entry) / entry) * 100
                            unrealized_pnl += ur_pnl_val
                            icon = "🟢" if ur_pnl_val > 0 else "🔴"
                            ur_pnl_str = f"| 🚀 P/L: {icon} {ur_pnl_val:+.2f} ({ur_pnl_pct:+.2f}%)"
                            
                        # Hanya munculkan di list jika nilainya > 5.0 USDT (abaikan debu)
                        if asset_val > 5.0:
                            active_info += f"▻ <b>{sym}</b>\n   🏷️ Harga: <code>{curr_price}</code> {ur_pnl_str}\n"
                            markup.add(InlineKeyboardButton(f"❌ Jual Manual {sym}", callback_data=f"close_{sym}"))
                            current_pos_count += 1
                    except: pass

            if current_pos_count == 0:
                active_info = "<i>Tidak ada posisi aktif saat ini.</i>"

            total_session_pnl = realized_pnl + unrealized_pnl
            pnl_icon = "🟢" if total_session_pnl >= 0 else "🔴"
            
            pnl_text = (f"📈 <b>Profit Sesi Ini:</b> {pnl_icon} <b>{total_session_pnl:+.2f} USDT</b>\n"
                        f"   └ <i>(Realized: {realized_pnl:+.2f} | Floating: {unrealized_pnl:+.2f})</i>\n\n")

            total_equity = total_usdt + open_assets_value

        except Exception as e:
            active_info = f"⚠️ <i>Gagal menyedot database Binance: {e}</i>"

    bot.reply_to(message, f"📊 <b>Laporan Status 24/7:</b>\n\n"
                           f"Sistem: {status_text}\n"
                           f"Batas Koleksi Posisi: {current_pos_count} / {config.MAX_OPEN_POSITIONS}\n\n"
                           f"{pnl_text}"
                           f"💵 <b>Estimasi Saldo Total:</b> {total_equity:,.2f} USDT\n"
                           f"💸 <b>Sisa USDT Nganggur:</b> {total_usdt:,.2f} USDT\n\n"
                           f"{active_info}\n\n"
                           f"Sinyal /bagus Tersimpan: {len(config.SKIPPED_SIGNALS)} koin\n\n"
                           f"💡 <i>Ketik /done untuk melihat riwayat Win/Loss trade yang sudah selesai.</i>", 
                           parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("close_"))
def callback_close_coin(call):
    symbol = call.data.replace("close_", "")
    chat_id = call.message.chat.id
    
    if not binance_client:
        bot.answer_callback_query(call.id, "⚠️ API Belum Siap")
        return
        
    bot.answer_callback_query(call.id, f"⌛ Menutup {symbol}...")
    
    try:
        # 1. Batalkan semua order gantung (TP/SL) untuk koin ini
        orders = binance_client.get_open_orders(symbol=symbol)
        for o in orders:
            binance_client.cancel_order(symbol=symbol, orderId=o['orderId'])
            
        # 2. Ambil semua saldo koin tersebut
        acc = binance_client.get_account()
        base_asset = symbol.replace('USDT', '')
        asset_bal = float(next((a['free'] for a in acc['balances'] if a['asset'] == base_asset), 0))
        
        if asset_bal <= 0:
            bot.send_message(chat_id, f"🤷‍♂️ Tidak ada saldo <b>{symbol}</b> untuk dijual.", parse_mode="HTML")
            return
            
        # 3. Jual di Market Price
        ticker = binance_client.get_symbol_ticker(symbol=symbol)
        sell_price = float(ticker['price'])
        
        # Penanganan Lot Size Filter (Copy logic dari executer)
        info = binance_client.get_symbol_info(symbol)
        lot_filter = next((f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
        from binance.helpers import round_step_size
        if lot_filter:
            step_size = float(lot_filter['stepSize'])
            quantity = round_step_size(asset_bal, step_size)
        else:
            quantity = asset_bal

        binance_client.create_order(
            symbol=symbol,
            side='SELL',
            type='MARKET',
            quantity=quantity
        )
        
        log_trade(symbol, "SELL", sell_price, 0, "Manual Close", f"Closed via Telegram Button (PNL: {pnl:+.2f} USDT)")
        
        bot.send_message(chat_id, f"💰 <b>{symbol} BERHASIL DITUTUP MANUAL!</b>\nLaku di harga market: <code>{sell_price}</code>\nProfit/Loss: <b>{pnl:+.2f} USDT</b>", parse_mode="HTML")
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Gagal menutup {symbol}: {e}")

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

        reply_msg = "🏁 <b>HISTORI TRADE SELESAI (/Done):</b>\n\n"
        closed_count = 0
        
        # 3. Proses hanya koin yang sudah di-BUY dan transaksi paling akhirnya adalah SELL
        for trade in buy_history:
            sym = trade['symbol']
            
            my_trades = binance_client.get_my_trades(symbol=sym, limit=5)
            if not my_trades: continue
            
            last_trade = my_trades[-1]
            if last_trade['isBuyer']: # Terakhir masih BUY, artinya belum dijual (Masih Floating)
                continue
                
            # Sudah terjual!
            sell_price = float(last_trade['price'])
            sell_qty = float(last_trade['qty'])
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
            
            if closed_count >= 10: # Tampilkan lebih banyak history (10 terakhir) di /done
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

def auto_check_closed_trades(client):
    import os
    from utils.trade_logger import TRADE_CSV
    
    notified_file = os.path.join("logs", "notified_closed.txt")
    if not os.path.exists(os.path.dirname(notified_file)):
        os.makedirs(os.path.dirname(notified_file), exist_ok=True)
    if not os.path.exists(notified_file):
        with open(notified_file, "w", encoding="utf-8") as f:
            f.write("")
            
    if not os.path.exists(TRADE_CSV):
        return
        
    try:
        # Load already notified trades
        with open(notified_file, "r", encoding="utf-8") as f:
            notified = set([line.strip() for line in f.readlines()])
            
        # Read recent BUYs
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
                if len(buy_history) >= 20: break
                
        # Process closures
        for trade in buy_history:
            sym = trade['symbol']
            trade_id = f"{sym}_{trade['time']}"
            
            if trade_id in notified:
                continue # Sudah dinotifikasi
                
            # Baru selesai? Cek transaksi pamungkas si koin
            my_trades = client.get_my_trades(symbol=sym, limit=5)
            if not my_trades: continue
            
            last_trade = my_trades[-1]
            if last_trade['isBuyer']: # Terakhir msh Buy -> blm TP/SL
                continue
                
            sell_price = float(last_trade['price'])
            qty = float(last_trade['qty'])
            usd_received = sell_price * qty
            usd_spent = trade['budget']
            pnl = usd_received - usd_spent
            pnl_pct = (pnl / usd_spent) * 100
            
            icon = "🟢" if pnl > 0 else "🔴"
            status_text = "MENCAPAI TP (PROFIT)" if pnl > 0 else "MENYENTUH SL (LOSS)"
            
            msg = (
                f"🔔 <b>TRADE OTOMATIS TERTUTUP</b>\n\n"
                f"{icon} <b>{sym}</b> ({status_text})\n"
                f"   🔸 Harga Beli: <code>{trade['entry_price']}</code>\n"
                f"   🔹 Terjual di: <code>{sell_price}</code>\n"
                f"   💰 P/L Bersih: <b>{pnl:+.2f} USDT ({pnl_pct:+.2f}%)</b>\n"
            )
            send_telegram_message(msg)
            
            # Log P/L ke CSV agar cmd_status bisa hitung total session P/L
            log_trade(sym, "SELL", sell_price, 0, "Auto Close", f"Target Hit (PNL: {pnl:+.2f} USDT)")
            
            # Record it as notified
            with open(notified_file, "a", encoding="utf-8") as f:
                f.write(trade_id + "\n")
                
    except Exception as e:
        print(f"[AUTO NOTIFICATION ERROR] {e}")

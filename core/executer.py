from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance.helpers import round_step_size
import config
from utils.telegram_notifier import send_telegram_message
from utils.trade_logger import log_trade

def open_buy_position(client: Client, symbol: str, current_price: float, reason: str):
    """
    Mengeksekusi order Market BUY di Testnet.
    Sistem akan menghitung berapa jumlah (Quantity) koin yang bisa dibeli dengan modal (TRADE_AMOUNT_USDT).
    """
    budget_usdt = config.TRADE_AMOUNT_USDT
    
    # Hitung jumlah kasaran koin yang mau dibeli
    raw_quantity = budget_usdt / current_price
    
    try:
        # Ambil Presisi (LOT_SIZE / stepSize) koin dari Binance agar tidak error
        info = client.get_symbol_info(symbol)
        
        # Cari filter ukuran kuantitas
        lot_filter = next((f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
        if lot_filter:
            step_size = float(lot_filter['stepSize'])
            quantity = round_step_size(raw_quantity, step_size)
        else:
            quantity = round(quantity, 4)
            
        # Cari filter tick ukuran harga (Untuk TP/SL)
        price_filter = next((f for f in info['filters'] if f['filterType'] == 'PRICE_FILTER'), None)
        tick_size = float(price_filter['tickSize']) if price_filter else 0.0001
        
        if quantity <= 0:
            print(f"[REJECTED] Modal terlalu kecil untuk beli {symbol}")
            return False

        print(f"\n[EXECUTION] Menyiapkan order BUY {quantity} {symbol} di harga ~{current_price} USDT")

        # Panggil API untuk membuat MARKET ORDER (Membeli aset)
        order = client.create_order(
            symbol=symbol,
            side=Client.SIDE_BUY,
            type=Client.ORDER_TYPE_MARKET,
            quantity=quantity
        )
        
        # Eksekusi OCO Order (Take Profit & Stop Loss otomatis)
        msg_oco = ""
        try:
            # Hitung harga TP dan SL secara matematis
            raw_tp = current_price * (1 + config.TAKE_PROFIT_PERCENT / 100)
            raw_sl = current_price * (1 - config.STOP_LOSS_PERCENT / 100)
            raw_sl_limit = raw_sl * 0.999
            
            # Terapkan filter presisi harga dari Binance ke OCO Order
            tp_price = round_step_size(raw_tp, tick_size)
            sl_price = round_step_size(raw_sl, tick_size)
            sl_limit_price = round_step_size(raw_sl_limit, tick_size)
            
            # Pasang OCO menggunakan endpoint terbaru Binance (orderList/oco)
            # Endpoint lama create_oco_order di python-binance sering bentrok dengan sistem param API v3 baru
            oco_params = {
                'symbol': symbol,
                'side': Client.SIDE_SELL,
                'quantity': quantity,
                'aboveType': 'LIMIT_MAKER',
                'abovePrice': tp_price,
                'belowType': 'STOP_LOSS_LIMIT',
                'belowStopPrice': sl_price,
                'belowPrice': sl_limit_price,
                'belowTimeInForce': Client.TIME_IN_FORCE_GTC
            }
            client._post('orderList/oco', True, data=oco_params)
            msg_oco = f"\n\n🎯 <b>Target Jual (TP):</b> {tp_price}\n🛡️ <b>Batas Rugi (SL):</b> {sl_price}"
        except Exception as oco_err:
            msg_oco = f"\n\n⚠️ <i>Gagal memasang otomatis TP/SL OCO: {oco_err}. (Anda harus setel manual).</i>"
        
        # Jika berhasil
        msg = f"✅ <b>Beli Berhasil</b>\n\n<b>Koin:</b> {symbol}\n<b>Harga Beli:</b> {current_price}\n<b>Modal:</b> {budget_usdt} USDT\n<b>Alasan:</b> {reason}{msg_oco}"
        send_telegram_message(msg)
        
        # Simpan ke log CSV
        log_trade(symbol, "BUY", current_price, budget_usdt, "Golden Trifecta", f"TP:{tp_price} SL:{sl_price}")
        return True
        
    except BinanceAPIException as e:
        # Gagal beli (misalnya Lot Size salah atau Server Error)
        error_msg = f"❌ <b>Gagal Beli {symbol}</b>\nError: {e.message}"
        print(f"[BINANCE ERROR] {error_msg}")
        send_telegram_message(error_msg)
        return False
    except Exception as e:
        print(f"[EXECUTION ERROR] {e}")
        return False

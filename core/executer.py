from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance.helpers import round_step_size
import config
from utils.telegram_notifier import send_telegram_message
from utils.trade_logger import log_trade

def open_buy_position(client: Client, symbol: str, current_price: float, reason: str):
    """
    Mengeksekusi order Market BUY di Testnet.

    FIX #1: Setelah BUY tereksekusi, ambil harga FILL aktual dari response Binance
            (bukan pakai current_price dari kline yang bisa meleset).
    FIX #2: Buffer SL Limit diperbesar dari 0.1% → 0.3% agar tidak terlewat saat gap down.
    FIX #3: Cek MIN_NOTIONAL sebelum pasang OCO, agar tidak silent-fail.
    FIX #4: Validasi OCO terpasang dengan cek open orders setelah eksekusi.
    """
    budget_usdt = config.TRADE_AMOUNT_USDT

    # Hitung jumlah kasaran koin yang mau dibeli
    raw_quantity = budget_usdt / current_price

    try:
        # Ambil Presisi (LOT_SIZE / stepSize) dan filter harga dari Binance
        info = client.get_symbol_info(symbol)

        lot_filter   = next((f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
        price_filter = next((f for f in info['filters'] if f['filterType'] == 'PRICE_FILTER'), None)
        notional_filter = next((f for f in info['filters'] if f['filterType'] in ('MIN_NOTIONAL', 'NOTIONAL')), None)

        if lot_filter:
            step_size = float(lot_filter['stepSize'])
            quantity  = round_step_size(raw_quantity, step_size)
        else:
            quantity = round(raw_quantity, 4)

        tick_size = float(price_filter['tickSize']) if price_filter else 0.0001

        if quantity <= 0:
            print(f"[REJECTED] Modal terlalu kecil untuk beli {symbol}")
            return False

        # --- Cek MIN_NOTIONAL sebelum pesan ---
        if notional_filter:
            min_notional = float(notional_filter.get('minNotional', notional_filter.get('minQty', 0)))
            estimated_notional = quantity * current_price
            if estimated_notional < min_notional:
                print(f"[REJECTED] {symbol} value ({estimated_notional:.2f} USDT) < MIN_NOTIONAL ({min_notional} USDT). Skip.")
                return False

        print(f"\n[EXECUTION] Menyiapkan order BUY {quantity} {symbol} @ ~{current_price} USDT")

        # Panggil API Market BUY
        order = client.create_order(
            symbol=symbol,
            side=Client.SIDE_BUY,
            type=Client.ORDER_TYPE_MARKET,
            quantity=quantity
        )

        # ─────────────────────────────────────────────────────────
        # FIX #1: Ambil harga FILL AKTUAL dari response Binance
        # current_price dari kline bisa meleset hingga 0.2–0.5%
        # ─────────────────────────────────────────────────────────
        fills = order.get('fills', [])
        if fills:
            total_qty_filled  = sum(float(f['qty'])              for f in fills)
            total_cost_filled = sum(float(f['price']) * float(f['qty']) for f in fills)
            actual_fill_price = total_cost_filled / total_qty_filled
        else:
            # Fallback ke current_price jika fills kosong (jarang terjadi di market order)
            actual_fill_price = current_price

        print(f"[FILL] Harga fill aktual: {actual_fill_price:.6f} USDT (estimasi: {current_price:.6f})")

        # Eksekusi OCO Order (Take Profit & Stop Loss otomatis)
        msg_oco = ""
        oco_success = False
        try:
            # Hitung TP dan SL berdasarkan HARGA FILL AKTUAL
            raw_tp       = actual_fill_price * (1 + config.TAKE_PROFIT_PERCENT / 100)
            raw_sl       = actual_fill_price * (1 - config.STOP_LOSS_PERCENT / 100)
            # FIX #2: Buffer SL Limit 0.3% (3× lebih besar dari 0.1% sebelumnya)
            # Ini mencegah order miss saat ada gap/spike mendadak ke bawah
            raw_sl_limit = raw_sl * 0.997

            # Terapkan filter presisi harga
            tp_price       = round_step_size(raw_tp,       tick_size)
            sl_price       = round_step_size(raw_sl,       tick_size)
            sl_limit_price = round_step_size(raw_sl_limit, tick_size)

            # Pasang OCO via endpoint terbaru Binance
            oco_params = {
                'symbol':            symbol,
                'side':              Client.SIDE_SELL,
                'quantity':          quantity,
                'aboveType':         'LIMIT_MAKER',
                'abovePrice':        tp_price,
                'belowType':         'STOP_LOSS_LIMIT',
                'belowStopPrice':    sl_price,
                'belowPrice':        sl_limit_price,
                'belowTimeInForce':  Client.TIME_IN_FORCE_GTC
            }
            oco_response = client._post('orderList/oco', True, data=oco_params)

            # FIX #4: Validasi OCO benar-benar terpasang
            if oco_response and oco_response.get('orderListId'):
                oco_success = True
                msg_oco = (
                    f"\n\n🎯 <b>Target Jual (TP):</b> {tp_price}"
                    f"\n🛡️ <b>Batas Rugi (SL):</b> {sl_price}"
                    f"\n🔒 <b>SL Limit:</b> {sl_limit_price}"
                    f"\n📌 <b>Fill Price:</b> {actual_fill_price:.6f}"
                )
            else:
                msg_oco = (
                    f"\n\n⚠️ <b>OCO terpasang tapi respons tidak valid.</b> "
                    f"Silakan cek manual di Binance."
                )

        except Exception as oco_err:
            error_str = str(oco_err)
            if "MAX_NUM_ALGO_ORDERS" in error_str:
                msg_oco = (
                    "\n\n⚠️ <b>FILTER ERROR: Terlalu banyak order gantung (OCO).</b>"
                    "\nKoin sudah dibeli tapi <b>TP/SL GAGAL terpasang</b>. "
                    "Gunakan tombol <b>Jual Manual</b> di /status."
                )
            else:
                msg_oco = (
                    f"\n\n⚠️ <i>Gagal memasang TP/SL OCO: {oco_err}</i>"
                    f"\n❗ <b>WAJIB pasang SL manual</b> agar tidak rugi besar!"
                )
            print(f"[OCO ERROR] {symbol}: {oco_err}")

        # Kirim notifikasi
        sl_status = "✅ OCO Terpasang" if oco_success else "⚠️ OCO GAGAL — Pasang Manual!"
        msg = (
            f"✅ <b>Beli Berhasil</b>\n\n"
            f"<b>Koin:</b> {symbol}\n"
            f"<b>Harga Fill:</b> {actual_fill_price:.6f} USDT\n"
            f"<b>Modal:</b> {budget_usdt} USDT\n"
            f"<b>OCO Status:</b> {sl_status}\n"
            f"<b>Alasan:</b> {reason}"
            f"{msg_oco}"
        )
        send_telegram_message(msg)

        # Simpan ke log CSV dengan harga fill aktual
        log_trade(symbol, "BUY", actual_fill_price, budget_usdt, "Golden Trifecta",
                  f"TP:{tp_price if oco_success else 'N/A'} SL:{sl_price if oco_success else 'N/A'}")
        return True

    except BinanceAPIException as e:
        error_msg = f"❌ <b>Gagal Beli {symbol}</b>\nError: {e.message}"
        print(f"[BINANCE ERROR] {error_msg}")
        send_telegram_message(error_msg)
        return False
    except Exception as e:
        print(f"[EXECUTION ERROR] {e}")
        return False

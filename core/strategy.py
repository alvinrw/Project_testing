import pandas as pd
import pandas_ta as ta

def calculate_golden_trifecta(df: pd.DataFrame, ema_len=200, rsi_len=14) -> dict:
    """
    Menghitung EMA 200, RSI, dan MACD dari DataFrame Candlestick.
    
    ⚠️ FIX: Semua keputusan trading WAJIB didasarkan pada candle yang SUDAH TUTUP
    (confirmed candle = df.iloc[-2]), bukan candle live (df.iloc[-1]) yang masih
    berubah-ubah dan bisa menyebabkan false signal.
    
    Dataframe (df) harus memiliki kolom ['open', 'high', 'low', 'close', 'volume']
    """
    # 1. Minimal data untuk EMA + sedikit buffer
    if len(df) < ema_len + 3:
        return {'signal': 'HOLD', 'reason': f'Not enough data (needs >{ema_len+3} candles)'}
        
    # Copy DataFrame untuk mencegah SettingWithCopyWarning
    df = df.copy()

    # 2. Hitung Indikator
    df.ta.ema(length=ema_len, append=True)  # EMA_200
    df.ta.rsi(length=rsi_len, append=True)  # RSI_14
    df.ta.macd(append=True)                 # MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
    
    # --- CANDLE REFERENCES ---
    # KUNCI FIX: Gunakan candle yang SUDAH TUTUP sebagai dasar keputusan
    # iloc[-1] = candle live (belum tutup, nilai berubah-ubah) → HANYA buat harga live
    # iloc[-2] = candle CONFIRMED (sudah tutup, nilai pasti) → DASAR KEPUTUSAN
    # iloc[-3] = candle sebelum confirmed → buat crossover comparison
    live    = df.iloc[-1]    # Candle live — hanya untuk ambil harga terkini
    confirm = df.iloc[-2]    # ✅ Candle terkonfirmasi (sudah tutup)
    prev    = df.iloc[-3]    # ✅ Candle sebelum terkonfirmasi
    
    # Extract column keys
    ema_key       = f"EMA_{ema_len}"
    rsi_key       = f"RSI_{rsi_len}"
    macd_line_key = "MACD_12_26_9"
    macd_sig_key  = "MACDs_12_26_9"
    
    # Pastikan data indikator sudah valid (bukan NaN)
    for val in [confirm[ema_key], confirm[rsi_key], confirm[macd_line_key],
                prev[rsi_key], prev[macd_line_key]]:
        if pd.isna(val):
            return {'signal': 'HOLD', 'reason': 'Waiting for indicators to stabilize (NaN)'}

    # Harga live terkini
    last_price = float(live['close'])

    # =========================================
    # --- ATURAN GOLDEN TRIFECTA (REVISI) ---
    # =========================================
    
    # Aturan 1: Harga live WAJIB DI ATAS EMA_200 di candle terkonfirmasi (Uptrend)
    is_uptrend = last_price > float(confirm[ema_key])
    
    # Aturan 2: RSI di candle terkonfirmasi harus di area sehat (30–68) DAN
    #           RSI harus NAIK dari candle sebelumnya (momentum bullish, bukan stagnant)
    rsi_confirmed = float(confirm[rsi_key])
    rsi_prev      = float(prev[rsi_key])
    is_rsi_healthy    = 32 < rsi_confirmed < 68
    is_rsi_rising     = rsi_confirmed > rsi_prev  # RSI sedang naik = momentum bullish
    
    # Aturan 3: MACD Crossover WAJIB terjadi di candle TERKONFIRMASI (bukan live!)
    # Crossover: candle sebelumnya Line <= Signal, candle konfirmasi Line > Signal
    macd_confirmed = float(confirm[macd_line_key])
    macd_sig_confirmed = float(confirm[macd_sig_key])
    macd_prev      = float(prev[macd_line_key])
    macd_sig_prev  = float(prev[macd_sig_key])
    is_macd_crossover = (macd_prev <= macd_sig_prev) and (macd_confirmed > macd_sig_confirmed)
    
    # Aturan 4 (Filter Tambahan): Volume spike confirmation
    # Volume candle confirmed harus lebih tinggi dari rata-rata 20 candle terakhir × 1.2
    recent_vols   = df['volume'].iloc[-22:-2]  # 20 candle sebelum confirmed
    avg_vol       = recent_vols.mean()
    confirm_vol   = float(confirm['volume'])
    is_volume_ok  = (avg_vol > 0) and (confirm_vol > avg_vol * 1.2)
    
    # KEPUTUSAN BUY: Semua 4 aturan harus terpenuhi
    if is_uptrend and is_rsi_healthy and is_rsi_rising and is_macd_crossover and is_volume_ok:
        return {
            'signal': 'BUY',
            'reason': (
                f"[CONFIRMED] Uptrend✓ RSI {rsi_confirmed:.1f}↑ "
                f"MACD Crossover✓ Vol Spike✓"
            )
        }
    
    # SELL: MACD Crossunder di candle yang sudah tutup
    is_macd_crossunder = (macd_prev >= macd_sig_prev) and (macd_confirmed < macd_sig_confirmed)
    if is_macd_crossunder:
        return {
            'signal': 'SELL',
            'reason': "[CONFIRMED] MACD Crossunder — Momentum Turun"
        }
    
    # Hold
    return {'signal': 'HOLD', 'reason': 'No confirmed setup yet'}

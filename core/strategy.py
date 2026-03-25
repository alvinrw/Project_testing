import pandas as pd
import pandas_ta as ta

def calculate_golden_trifecta(df: pd.DataFrame, ema_len=200, rsi_len=14) -> dict:
    """
    Menghitung EMA 200, RSI, dan MACD dari DataFrame Candlestick.
    Menggunakan library pandas_ta yang sangat cepat & efisien karena ditulis khusus untuk Vectorization.
    
    Dataframe (df) harus memiliki kolom ['open', 'high', 'low', 'close', 'volume']
    """
    # 1. Menghindari error jika jumlah data lilin kurang dari EMA_LENGTH
    if len(df) < ema_len:
        return {'signal': 'HOLD', 'reason': f'Not enough data (needs >{ema_len} candles)'}
        
    # Copy DataFrame untuk mencegah SettingWithCopyWarning
    df = df.copy()

    # 2. Hitung Indikator
    df.ta.ema(length=ema_len, append=True) # Adds column: EMA_200
    df.ta.rsi(length=rsi_len, append=True) # Adds column: RSI_14
    
    # MACD default = fast:12, slow:26, signal:9
    df.ta.macd(append=True) # Adds columns: MACD_12_26_9 (line), MACDh_12_26_9 (histogram), MACDs_12_26_9 (signal)
    
    # Dapatkan baris terakhir (current unfinished candle) dan baris sebelumnya (finished candle)
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Extract keys dynamically as they depend on lengths
    ema_key = f"EMA_{ema_len}"
    rsi_key = f"RSI_{rsi_len}"
    macd_line_key = "MACD_12_26_9"
    macd_sig_key = "MACDs_12_26_9"
    macd_hist_key = "MACDh_12_26_9"
    
    # Pastikan data indikator sudah selesai terhitung (bukan NaN)
    if pd.isna(latest[ema_key]) or pd.isna(latest[rsi_key]) or pd.isna(latest[macd_line_key]):
         return {'signal': 'HOLD', 'reason': 'Calculating indicators (NaN)'}

    last_price = latest['close']

    # --- ATURAN GOLDEN TRIFECTA ---
    
    # Aturan 1: Harga Saat ini WAJIB DI ATAS Garis EMA_200 (Uptrend Confirmation)
    is_uptrend = last_price > latest[ema_key]
    
    # Aturan 2: RSI sempat masuk oversold/turun, tapi sekarang sedang naik 
    # (Di sini kita sederhanakan: RSI harus stabil di area sehat atau di atas 30)
    is_rsi_healthy = latest[rsi_key] > 30 and latest[rsi_key] < 70
    
    # Aturan 3: Ada MACD Crossover ke atas (Histogram hijau segar) 
    # Crossover artinya di prev candle, Line < Signal, dan di latest candle, Line > Signal.
    is_macd_crossover = (prev[macd_line_key] <= prev[macd_sig_key]) and (latest[macd_line_key] > latest[macd_sig_key])
    
    # KEPUTUSAN (DECISION)
    if is_uptrend and is_rsi_healthy and is_macd_crossover:
        return {
            'signal': 'BUY',
            'reason': f"Perfect Setup: Uptrend, RSI {latest[rsi_key]:.2f}, MACD Crossover!"
        }
    
    # Jika sudah punya posisi dan mau mencari momen Sell/Take Profit 
    # (Contoh: Menjual jika ada MACD Crossover ke bawah)
    is_macd_crossunder = (prev[macd_line_key] >= prev[macd_sig_key]) and (latest[macd_line_key] < latest[macd_sig_key])
    if is_macd_crossunder:
        return {
            'signal': 'SELL',
            'reason': "MACD Crossunder (Momentum Turun, Waktunya Keluar)"
        }
    
    # Hold / Do nothing
    return {'signal': 'HOLD', 'reason': 'No setup yet'}

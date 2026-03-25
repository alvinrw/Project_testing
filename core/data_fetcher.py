import pandas as pd
from binance.client import Client
import config

def get_historical_klines_df(client: Client, symbol: str) -> pd.DataFrame:
    """
    Mengambil data candlestick (Klines) dari Binance lalu mengubahnya menjadi DataFrame Pandas.
    Dibutuhkan setidaknya N data (misal 250) untuk bisa menghitung EMA 200 dengan akurat.
    """
    interval = config.KLINE_INTERVAL
    limit = config.KLINE_LIMIT
    
    try:
        # Mengambil data dari REST API
        klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        
        # Kolom yang didapatkan dari Binance API (lihat dokumentasi Binance)
        columns = [
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ]
        
        df = pd.DataFrame(klines, columns=columns)
        
        # Ubah tipe data dari string menjadi float untuk kalkulasi matematika
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors='coerce')
        
        # Konversi timestamp ke Datetime object 
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        return df

    except Exception as e:
        print(f"[FETCH ERROR] Gagal mendownload data {symbol}: {e}")
        return pd.DataFrame()

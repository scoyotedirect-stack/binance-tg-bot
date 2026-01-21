import requests
import os

def get_filtered_symbols():
    try:
        volume_response = requests.get(
            "https://fapi.binance.com/fapi/v1/ticker/24hr",
            timeout=10
        )
        volume_response.raise_for_status()
        volume_data = volume_response.json()

        min_volume = int(os.environ["MIN_VOLUME"])
        max_volume = int(os.environ["MAX_VOLUME"])
        excluded_symbols = set(os.environ["EXCLUDED_SYMBOLS"].split(","))

        filtered_symbols = []
        for ticker in volume_data:
            symbol = ticker["symbol"]
            if (symbol.endswith("USDT") and symbol not in excluded_symbols):
                volume_usd = float(ticker["lastPrice"]) * float(ticker["volume"])
                if min_volume <= volume_usd <= max_volume:
                    filtered_symbols.append(symbol)
        return filtered_symbols
    except Exception:
        return []

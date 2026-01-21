import asyncio
import aiohttp
import numpy as np

# Ограничиваем параллельные запросы к Binance
CONCURRENT_REQUESTS = 5
semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

async def get_kline_data(session, symbol):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": "5m",
        "limit": 15
    }
    try:
        async with semaphore:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
    except Exception:
        return None

async def calculate_natr_14(closes, highs, lows):
    if len(closes) < 15:
        return None
    tr_list = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        tr_list.append(tr)
    atr = np.mean(tr_list[-14:])
    natr = (atr / closes[-1]) * 100
    return round(natr, 2)

async def get_natr_for_symbols(symbols):
    async with aiohttp.ClientSession() as session:
        tasks = [get_kline_data(session, symbol) for symbol in symbols]
        klines_list = await asyncio.gather(*tasks)

    natr_results = {}
    for symbol, klines in zip(symbols, klines_list):
        if klines and len(klines) >= 15:
            closes = [float(k[4]) for k in klines]
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            natr = await calculate_natr_14(closes, highs, lows)
        else:
            natr = None
        natr_results[symbol] = natr
    return natr_results

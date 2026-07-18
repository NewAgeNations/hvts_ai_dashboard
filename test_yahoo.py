import yfinance as yf

symbols = ["BTC-USD", "ETH-USD", "MATIC-USD"]

for sym in symbols:
    print(f"\n🔍 Testing {sym}...")
    try:
        ticker = yf.Ticker(sym)
        df = ticker.history(period="7d", interval="1h")
        if not df.empty:
            print(f"✅ {sym}: {len(df)} rows, latest: {df['Close'].iloc[-1]}")
        else:
            print(f"❌ {sym}: No data")
    except Exception as e:
        print(f"❌ {sym}: Error - {e}")
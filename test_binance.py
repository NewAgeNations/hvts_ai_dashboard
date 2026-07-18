from data_feed import fetch_ohlcv, test_connection

# Test connection
print("🔍 Testing Binance API connection...")
if test_connection():
    print("✅ Binance API is accessible!")
else:
    print("❌ Binance API is not accessible.")
    exit()

# Test a symbol
print("\n🔍 Fetching BTC/USDT 1h data...")
df = fetch_ohlcv("BTC/USDT", "1h", 10)
if df is not None:
    print(f"✅ Got {len(df)} rows")
    print(df.tail())
else:
    print("❌ Failed to fetch data")

# Test all symbols
print("\n🔍 Testing all symbols...")
for sym in ["BTC/USDT", "ETH/USDT", "POL/USDT"]:
    df = fetch_ohlcv(sym, "1h", 5)
    print(f"  {sym}: {'✅' if df is not None else '❌'}")
from data_feed import fetch_ohlcv, test_connection

# Test connection
print("🔍 Testing Gate.io connection...")
if test_connection():
    print("✅ Gate.io API is accessible!")
else:
    print("❌ Gate.io API is not accessible.")
    exit()

# Test a symbol
print("\n🔍 Fetching BTC/USDT 1h data...")
df = fetch_ohlcv("BTC/USDT", "1h", 10)
if df is not None:
    print(f"✅ Got {len(df)} rows")
    print(df.tail())
else:
    print("❌ Failed to fetch data")
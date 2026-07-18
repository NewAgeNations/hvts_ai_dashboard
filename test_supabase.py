from supabase import create_client

url = "https://kypymydfkeihycdiddsh.supabase.co"
key = "sb_publishable_F6aAHQyPPRqoN6YJPNh3kw_FwW7LZ0y"

supabase = create_client(url, key)
try:
    response = supabase.table('neural_signals').select('*').limit(1).execute()
    print("✅ Connected! Data:", response.data)
except Exception as e:
    print("❌ Error:", e)
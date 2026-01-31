"""
Quick diagnostic to test LLM connection
"""
import os
from anthropic import Anthropic

# Load API key
api_key = os.getenv('ANTHROPIC_API_KEY')

print("🔍 Checking LLM Setup...")
print(f"API Key present: {'Yes' if api_key else 'No'}")

if api_key:
    print(f"API Key starts with: {api_key[:15]}...")
    
    try:
        client = Anthropic(api_key=api_key)
        
        print("\n🧪 Testing API call...")
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'Hello, test successful!'"}]
        )
        
        print(f"✅ SUCCESS! Response: {response.content[0].text}")
        print("\n✓ Your API key is working correctly!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nPossible issues:")
        print("- API key might be invalid")
        print("- No credits remaining")
        print("- Network connection issue")
else:
    print("\n❌ No API key found!")
    print("Make sure your .env file has: ANTHROPIC_API_KEY=sk-ant-...")

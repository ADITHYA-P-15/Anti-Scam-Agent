"""
Verbose Test - See exactly what's happening
"""

import asyncio
import httpx
import json

API_URL = "http://localhost:8000"

async def test_single_conversation():
    """Test a single conversation with verbose output"""
    
    client = httpx.AsyncClient(timeout=30.0)
    session_id = "verbose-test-001"
    
    print("\n" + "="*80)
    print("🔍 VERBOSE TEST - Single Conversation")
    print("="*80 + "\n")
    
    # Scammer messages
    messages = [
        "Your SBI account will be blocked within 24 hours due to KYC update pending.",
        "Yes, this is from State Bank of India. Your account needs immediate verification.",
        "You must update your KYC by paying verification fee of Rs 500.",
        "You can pay via UPI. Send to verify.sbi@paytm immediately.",
        "What is taking so long? Your account will be permanently blocked!",
        "Okay, if UPI is not working, use bank transfer. Account: 1234567890123, IFSC: SBIN0001234",
    ]
    
    for i, scammer_msg in enumerate(messages, 1):
        print(f"\n{'─'*80}")
        print(f"TURN {i}")
        print(f"{'─'*80}")
        print(f"👨 SCAMMER: {scammer_msg}")
        
        # Send to API
        try:
            response = await client.post(
                f"{API_URL}/message-event",
                json={
                    "session_id": session_id,
                    "message": scammer_msg
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"🤖 AGENT: {data['agent_message']}")
                print(f"\n📊 METADATA:")
                print(f"   Phase: {data['metadata']['phase']}")
                print(f"   Persona: {data['metadata']['persona']}")
                print(f"   Turn count: {data['metadata']['turn_count']}")
                print(f"   Latency: {data['metadata']['latency_ms']}ms")
                print(f"   Scam detected: {data['detected']}")
                
                print(f"\n🔍 INTELLIGENCE EXTRACTED:")
                intel = data['intelligence']
                print(f"   UPI IDs: {intel.get('upi_ids', [])}")
                print(f"   Bank accounts: {len(intel.get('bank_accounts', []))}")
                print(f"   URLs: {intel.get('urls', [])}")
                print(f"   Phone numbers: {intel.get('phone_numbers', [])}")
                
            else:
                print(f"❌ ERROR: Status {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
        
        # Small pause
        await asyncio.sleep(0.5)
    
    print("\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80 + "\n")
    
    await client.aclose()


if __name__ == "__main__":
    asyncio.run(test_single_conversation())

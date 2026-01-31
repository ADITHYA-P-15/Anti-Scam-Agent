"""
Test Script - Simulate Scammer Conversations
Run this to test the agent's performance
"""

import asyncio
import httpx
import json
from typing import List, Dict
import time

API_URL = "http://localhost:8000"


class ScamSimulator:
    """
    Simulate scammer conversations to test the agent
    """
    
    # Sample scam scenarios - EXTENDED for longer conversations
    SCENARIOS = {
        'bank_impersonation': [
            "Your SBI account will be blocked within 24 hours due to KYC update pending.",
            "Yes, this is from State Bank of India. Your account needs immediate verification.",
            "You must update your KYC by paying verification fee of Rs 500.",
            "You can pay via UPI. Send to verify.sbi@paytm immediately.",
            "What is taking so long? Your account will be permanently blocked!",
            "Okay, if UPI is not working, use bank transfer. Account: 1234567890123, IFSC: SBIN0001234",
            "Have you sent the payment? We need confirmation number.",
            "This is urgent! Do it now or you cannot access your account anymore.",
            "You can also call this number for help: 9876543210",
            "Or you can use our alternate UPI: sbiverify@paytm as backup.",
            "Sir, this is final warning. Account will be blocked in 1 hour.",
            "Many customers already updated. Don't delay further!",
            "I'm sending you a link also: http://sbi-kyc-update.com",
            "Just complete the payment, then your account will be active immediately."
        ],
        'lottery_scam': [
            "Congratulations! You have won Rs 10 lakh in our KBC lottery draw.",
            "Yes, this is official. You are one of 10 lucky winners selected.",
            "To claim your prize, you need to pay processing fee of Rs 2000 first.",
            "Send the fee via UPI to lottery.claim@okaxis",
            "Why are you delaying? Prize will expire in 2 hours!",
            "Or send to this account if UPI not working: 9876543210987, IFSC: AXIS0001234",
            "After you pay, we will transfer full 10 lakhs to your account.",
            "Many others already claimed. Don't miss this opportunity!",
            "You can call our office: 9123456780 for verification.",
            "We also accept payment at prize.winner@paytm as alternate UPI.",
            "Sir, we need payment immediately. Prize committee is waiting.",
            "Other winners already received their money. You are delaying.",
            "This is genuine KBC lottery. Check our website: http://kbc-winners.com",
            "Just pay Rs 2000 and get Rs 10 lakhs within 24 hours!"
        ],
        'courier_scam': [
            "Your FedEx parcel from USA is pending at customs in Delhi.",
            "Parcel contains important legal documents. You must clear customs immediately.",
            "Customs clearance fee is Rs 800. Pay now or parcel will be returned.",
            "Send payment to customs.fedex@paytm for immediate release.",
            "This is last warning. Parcel will be destroyed after 24 hours!",
            "You can also call our office: 9123456789 for assistance.",
            "Or transfer to account 5678901234567, IFSC: HDFC0001234",
            "Documents are very urgent. Sender is waiting for confirmation.",
            "We have alternate payment method also: fedex.india@okaxis",
            "Parcel has been waiting for 3 days already. Please clear it.",
            "You can track your parcel here: http://fedex-tracking.com",
            "Customs office will charge penalty if you delay more.",
            "Other parcels already cleared. Yours is only one pending.",
            "Just pay Rs 800 and we will deliver tomorrow morning."
        ],
        'investment_scam': [
            "I have an exclusive investment opportunity in crypto trading.",
            "Guaranteed 50% returns in just 3 months. Government approved scheme.",
            "Minimum investment is Rs 50,000. Limited slots available.",
            "Transfer to our company account for immediate activation.",
            "Account number: 7890123456789, IFSC: ICIC0001234, or UPI: invest.pro@okicici",
            "Already 500+ investors made huge profits. Check our website.",
            "Your slot is reserved. Pay within 1 hour or we give to next person.",
            "This is legitimate business. We are registered with SEBI.",
            "You can call our advisor: 9876543219 for more details.",
            "We also accept payment at crypto.invest@paytm as backup.",
            "Sir, this opportunity won't come again. Market is perfect now.",
            "Last month investors got 60% returns. You should not miss this.",
            "Visit our website for proof: http://crypto-profits.com",
            "Just invest Rs 50,000 today and get Rs 75,000 in 3 months guaranteed!"
        ]
    }
    
    def __init__(self, api_url: str = API_URL):
        self.api_url = api_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def send_message(
        self, 
        session_id: str, 
        message: str
    ) -> Dict:
        """
        Send a message to the agent
        """
        url = f"{self.api_url}/message-event"
        
        payload = {
            "session_id": session_id,
            "message": message
        }
        
        start_time = time.time()
        
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            latency = time.time() - start_time
            data['actual_latency'] = latency
            
            return data
        
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    async def run_scenario(
        self, 
        scenario_name: str, 
        session_id: str = None
    ) -> Dict:
        """
        Run a complete scam scenario
        """
        if scenario_name not in self.SCENARIOS:
            print(f"❌ Unknown scenario: {scenario_name}")
            return None
        
        session_id = session_id or f"test-{scenario_name}-{int(time.time())}"
        messages = self.SCENARIOS[scenario_name]
        
        print(f"\n{'='*80}")
        print(f"🎭 SCENARIO: {scenario_name.upper().replace('_', ' ')}")
        print(f"📝 Session ID: {session_id}")
        print(f"{'='*80}\n")
        
        conversation = []
        intelligence_gathered = {
            'upi_ids': set(),
            'bank_accounts': set(),
            'urls': set(),
            'phone_numbers': set()
        }
        
        for i, scammer_message in enumerate(messages, 1):
            print(f"Turn {i}")
            print(f"👨 SCAMMER: {scammer_message}")
            
            # Send message to agent
            response = await self.send_message(session_id, scammer_message)
            
            if not response:
                print("❌ Failed to get response")
                break
            
            # Display agent response
            agent_message = response.get('agent_message', '')
            print(f"🤖 AGENT: {agent_message}")
            
            # Track intelligence
            intel = response.get('intelligence', {})
            intelligence_gathered['upi_ids'].update(intel.get('upi_ids', []))
            intelligence_gathered['urls'].update(intel.get('urls', []))
            intelligence_gathered['phone_numbers'].update(intel.get('phone_numbers', []))
            
            for acc in intel.get('bank_accounts', []):
                if acc.get('account_number'):
                    intelligence_gathered['bank_accounts'].add(
                        f"{acc['account_number']} ({acc.get('ifsc', 'no IFSC')})"
                    )
            
            # Display metadata
            metadata = response.get('metadata', {})
            print(f"📊 Phase: {metadata.get('phase', 'unknown')}")
            print(f"⏱️  Latency: {response.get('actual_latency', 0)*1000:.0f}ms")
            print(f"🔍 Detected: {response.get('detected', False)}")
            
            conversation.append({
                'turn': i,
                'scammer': scammer_message,
                'agent': agent_message,
                'phase': metadata.get('phase'),
                'latency_ms': response.get('actual_latency', 0) * 1000
            })
            
            print()
            
            # Pause between messages (simulate human typing)
            await asyncio.sleep(0.5)
        
        # Summary
        print(f"\n{'='*80}")
        print("📋 CONVERSATION SUMMARY")
        print(f"{'='*80}")
        print(f"Total turns: {len(conversation)}")
        print(f"Avg latency: {sum(t['latency_ms'] for t in conversation) / len(conversation):.0f}ms")
        
        print("\n🔍 INTELLIGENCE GATHERED:")
        print(f"  UPI IDs: {len(intelligence_gathered['upi_ids'])}")
        for upi in intelligence_gathered['upi_ids']:
            print(f"    ✓ {upi}")
        
        print(f"  Bank Accounts: {len(intelligence_gathered['bank_accounts'])}")
        for acc in intelligence_gathered['bank_accounts']:
            print(f"    ✓ {acc}")
        
        print(f"  URLs: {len(intelligence_gathered['urls'])}")
        for url in intelligence_gathered['urls']:
            print(f"    ✓ {url}")
        
        print(f"  Phone Numbers: {len(intelligence_gathered['phone_numbers'])}")
        for phone in intelligence_gathered['phone_numbers']:
            print(f"    ✓ {phone}")
        
        # Calculate score
        score = (
            len(intelligence_gathered['upi_ids']) * 40 +
            len(intelligence_gathered['bank_accounts']) * 40 +
            len(intelligence_gathered['urls']) * 10 +
            len(intelligence_gathered['phone_numbers']) * 5
        )
        
        print(f"\n🏆 Intelligence Score: {min(score, 100)}/100")
        print(f"{'='*80}\n")
        
        return {
            'session_id': session_id,
            'scenario': scenario_name,
            'turns': len(conversation),
            'intelligence': {
                'upi_ids': list(intelligence_gathered['upi_ids']),
                'bank_accounts': list(intelligence_gathered['bank_accounts']),
                'urls': list(intelligence_gathered['urls']),
                'phone_numbers': list(intelligence_gathered['phone_numbers'])
            },
            'score': min(score, 100),
            'conversation': conversation
        }
    
    async def run_all_scenarios(self):
        """
        Run all test scenarios
        """
        results = []
        
        for scenario_name in self.SCENARIOS.keys():
            result = await self.run_scenario(scenario_name)
            if result:
                results.append(result)
            
            # Pause between scenarios
            await asyncio.sleep(2)
        
        # Overall summary
        print("\n" + "="*80)
        print("🎯 OVERALL PERFORMANCE SUMMARY")
        print("="*80)
        
        total_turns = sum(r['turns'] for r in results)
        avg_turns = total_turns / len(results) if results else 0
        avg_score = sum(r['score'] for r in results) / len(results) if results else 0
        
        print(f"Scenarios tested: {len(results)}")
        print(f"Total turns: {total_turns}")
        print(f"Average turns per scenario: {avg_turns:.1f}")
        print(f"Average intelligence score: {avg_score:.1f}/100")
        
        print("\n📊 Scenario Breakdown:")
        for result in results:
            print(f"  {result['scenario']:<20} | Turns: {result['turns']:>2} | Score: {result['score']:>3}/100")
        
        print("="*80 + "\n")
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


async def main():
    """
    Main test function
    """
    print("\n🛡️  Anti-Scam Agent Test Suite\n")
    
    # Check if server is running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_URL}/health")
            if response.status_code == 200:
                print("✓ Server is running\n")
            else:
                print(f"⚠️  Server returned status {response.status_code}\n")
    except Exception as e:
        print(f"❌ Cannot connect to server at {API_URL}")
        print(f"   Error: {e}")
        print("\n   Please start the server first:")
        print("   uvicorn main:app --reload\n")
        return
    
    # Run tests
    simulator = ScamSimulator()
    
    try:
        # Option 1: Run single scenario
        # await simulator.run_scenario('bank_impersonation')
        
        # Option 2: Run all scenarios
        await simulator.run_all_scenarios()
    
    finally:
        await simulator.close()


if __name__ == "__main__":
    asyncio.run(main())

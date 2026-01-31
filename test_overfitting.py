"""
Overfitting Test - Completely NEW scam scenarios
These are different from the training/test data
"""

import asyncio
import httpx
import json

API_URL = "http://localhost:8000"

NEW_SCENARIOS = {
    'tax_refund_scam': [
        "Income Tax Department notification: You have a pending refund of Rs 8,450.",
        "This is from IT Department. Your PAN card shows excess tax paid last year.",
        "To process refund, we need to verify your bank account with small fee.",
        "Processing charge is Rs 299 only. Very nominal amount.",
        "Send to our official department UPI: incometax.refund@ybl",
        "Why you are not responding? Refund will expire soon.",
        "You can also transfer to Department account: 5432109876543, IFSC: UTIB0001234",
        "This is last day to claim your refund of Rs 8,450.",
        "Call our helpline: 9988776655 if you have questions.",
        "Many people already got their refunds. Don't lose yours.",
        "Alternate UPI also available: taxrefund@oksbi if first not working.",
        "Sir, please complete payment today itself. Tomorrow refund will lapse."
    ],
    
    'electricity_bill_scam': [
        "URGENT: Your electricity connection will be cut in 2 hours due to unpaid bill.",
        "This is from BESCOM. Your meter reading shows Rs 4,200 pending.",
        "Pay immediately or power will be disconnected today evening.",
        "Use quick payment on our UPI: bescom.payment@paytm to avoid disconnection.",
        "Sir, this is automated message. Your area has many pending bills.",
        "If UPI fails, use emergency payment account: 8765432109876, IFSC: HDFC0009876",
        "Disconnection team is already in your area. Pay now!",
        "For any help call: 9123498765 immediately.",
        "You can also pay at: powerbill@okicici as backup option.",
        "Don't delay, your neighbors already paid and avoided disconnection.",
        "Check payment portal: http://bescom-quickpay.com for proof.",
        "Final warning: Pay Rs 4,200 in next 30 minutes!"
    ],
    
    'job_offer_scam': [
        "Congratulations! You are selected for Software Engineer position at TCS.",
        "Your resume was shortlisted from LinkedIn. Salary is Rs 8 LPA.",
        "This is from TCS HR Department. You will join next month.",
        "For processing your offer letter, we need documentation fee.",
        "Fee is Rs 5,500 for background verification and onboarding.",
        "Please transfer to HR account for immediate offer letter release.",
        "Our company UPI for fees: tcs.recruitment@paytm",
        "Sir, we have limited positions. Others are also waiting.",
        "You can call HR head: 9876012345 for confirmation.",
        "If UPI problem, use account: 6789054321234, IFSC: SBIN0067890",
        "This is genuine TCS offer. Check website: http://tcs-careers-india.com",
        "After payment, offer letter will be emailed in 24 hours.",
        "Alternate payment: careers.tcs@okaxis for your convenience."
    ],
    
    'social_media_hack': [
        "ALERT: Someone tried to login to your Instagram from unknown device.",
        "This is Instagram Security Team. Login attempt was from Russia.",
        "Your account will be locked unless you verify it's really you.",
        "Pay verification fee Rs 199 to unlock your account immediately.",
        "Send payment to: instagram.security@paytm for instant verification.",
        "If you don't act fast, your account will be permanently deleted.",
        "All your photos and followers will be lost forever!",
        "Call our support: 9871234560 for urgent help.",
        "You can also pay to account: 3456789012345, IFSC: AXIS0003456",
        "Many users already verified and saved their accounts.",
        "Backup payment method: insta.verify@ybl if first fails.",
        "This is final warning! Account deletion starts in 1 hour.",
        "Verify here: http://instagram-account-verify.com to see login details."
    ]
}


async def test_overfitting():
    """Test agent on completely new, unseen scenarios"""
    
    client = httpx.AsyncClient(timeout=30.0)
    
    print("\n" + "="*80)
    print("🧪 OVERFITTING TEST - Brand New Scenarios")
    print("="*80)
    print("\nThese are COMPLETELY DIFFERENT from training data!")
    print("If agent performs well, it's NOT overfitting.\n")
    
    results = []
    
    for scenario_name, messages in NEW_SCENARIOS.items():
        session_id = f"overfit-test-{scenario_name}"
        
        print(f"\n{'─'*80}")
        print(f"📋 SCENARIO: {scenario_name.upper().replace('_', ' ')}")
        print(f"{'─'*80}\n")
        
        intelligence = {
            'upi_ids': set(),
            'bank_accounts': set(),
            'urls': set(),
            'phone_numbers': set()
        }
        
        turn_count = 0
        
        for i, scammer_msg in enumerate(messages, 1):
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
                    turn_count += 1
                    
                    # Track intelligence
                    intel = data['intelligence']
                    intelligence['upi_ids'].update(intel.get('upi_ids', []))
                    intelligence['urls'].update(intel.get('urls', []))
                    intelligence['phone_numbers'].update(intel.get('phone_numbers', []))
                    
                    for acc in intel.get('bank_accounts', []):
                        if acc.get('account_number'):
                            intelligence['bank_accounts'].add(acc['account_number'])
                    
                    # Print progress
                    if i % 3 == 0 or i == len(messages):
                        print(f"Turn {turn_count}: Detected={data['detected']}, Phase={data['metadata']['phase']}")
                
                await asyncio.sleep(0.3)
                
            except Exception as e:
                print(f"❌ Error on turn {i}: {e}")
                break
        
        # Calculate score
        score = (
            len(intelligence['upi_ids']) * 40 +
            len(intelligence['bank_accounts']) * 40 +
            len(intelligence['urls']) * 10 +
            len(intelligence['phone_numbers']) * 5
        )
        score = min(score, 100)
        
        results.append({
            'scenario': scenario_name,
            'turns': turn_count,
            'score': score,
            'intelligence': intelligence
        })
        
        print(f"\n✅ {scenario_name}: {turn_count} turns, Score: {score}/100")
        print(f"   UPIs: {len(intelligence['upi_ids'])}, Banks: {len(intelligence['bank_accounts'])}, "
              f"URLs: {len(intelligence['urls'])}, Phones: {len(intelligence['phone_numbers'])}")
    
    # Summary
    print("\n" + "="*80)
    print("📊 OVERFITTING TEST RESULTS")
    print("="*80)
    
    avg_turns = sum(r['turns'] for r in results) / len(results)
    avg_score = sum(r['score'] for r in results) / len(results)
    
    print(f"\nAverage turns: {avg_turns:.1f}")
    print(f"Average score: {avg_score:.1f}/100\n")
    
    print("Scenario Breakdown:")
    for r in results:
        print(f"  {r['scenario']:<25} | Turns: {r['turns']:>2} | Score: {r['score']:>3}/100")
    
    print("\n" + "="*80)
    
    # Verdict
    if avg_score >= 80 and avg_turns >= 10:
        print("✅ VERDICT: NOT OVERFITTING - Agent generalizes well!")
    elif avg_score >= 60 and avg_turns >= 8:
        print("⚠️  VERDICT: Slight overfitting - Performance dropped but still decent")
    else:
        print("❌ VERDICT: OVERFITTING DETECTED - Agent struggles with new scenarios")
    
    print("="*80 + "\n")
    
    await client.aclose()


if __name__ == "__main__":
    asyncio.run(test_overfitting())

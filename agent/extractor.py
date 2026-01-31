"""
Intelligence Extractor - Layer 3
Multi-format extraction using regex + LLM validation
"""

import re
from typing import Dict, List
import logging
from anthropic import Anthropic
import os
import json

logger = logging.getLogger(__name__)


class IntelligenceExtractor:
    """
    Extract financial/contact intelligence from scammer messages
    """
    
    # Regex patterns for different data types
    PATTERNS = {
        'upi_id': r'\b[a-zA-Z0-9._-]+@[a-zA-Z]{3,}\b',
        'phone': r'\b(?:\+91|0)?[6-9]\d{9}\b',
        'bank_account': r'\b\d{9,18}\b',
        'ifsc': r'\b[A-Z]{4}0[A-Z0-9]{6}\b',
        'url': r'https?://[^\s<>"\)]+',
        'amount': r'(?:Rs\.?|₹)\s*\d+(?:,\d+)*(?:\.\d{2})?',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    }
    
    # Bank name patterns (for enrichment)
    BANK_PATTERNS = {
        'sbi': r'\bsbi\b|\bstate bank\b',
        'hdfc': r'\bhdfc\b',
        'icici': r'\bicici\b',
        'axis': r'\baxis\b',
        'paytm': r'\bpaytm\b',
        'phonepe': r'\bphonepe\b',
        'gpay': r'\bgpay\b|google pay',
        'kotak': r'\bkotak\b'
    }
    
    def __init__(self):
        """Initialize extractor with LLM client"""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        self.client = Anthropic(api_key=api_key) if api_key else None
        
        if not self.client:
            logger.warning("No Anthropic API key - LLM extraction disabled")
    
    async def extract_intelligence(self, message: str, session: Dict) -> Dict:
        """
        Main extraction method - parallel regex + LLM
        
        Returns:
            {
                'upi_ids': List[str],
                'bank_accounts': List[Dict],
                'phone_numbers': List[str],
                'urls': List[str],
                'amounts': List[str],
                'emails': List[str]
            }
        """
        # Step 1: Fast regex extraction
        regex_data = self._extract_with_regex(message)
        
        # Step 2: LLM extraction (if available)
        llm_data = {}
        if self.client:
            try:
                llm_data = await self._extract_with_llm(message)
            except Exception as e:
                logger.error(f"LLM extraction failed: {e}")
        
        # Step 3: Merge and validate
        combined = self._merge_intelligence(regex_data, llm_data)
        validated = self._validate_intelligence(combined)
        
        logger.info(
            f"Extracted: {len(validated.get('upi_ids', []))} UPI IDs, "
            f"{len(validated.get('bank_accounts', []))} bank accounts, "
            f"{len(validated.get('urls', []))} URLs"
        )
        
        return validated
    
    def _extract_with_regex(self, message: str) -> Dict:
        """
        Fast regex-based extraction
        """
        extracted = {
            'upi_ids': [],
            'bank_accounts': [],
            'phone_numbers': [],
            'urls': [],
            'amounts': [],
            'emails': []
        }
        
        # Extract UPI IDs
        upi_matches = re.findall(self.PATTERNS['upi_id'], message)
        extracted['upi_ids'] = [upi for upi in upi_matches if '@' in upi]
        
        # Extract phone numbers
        phone_matches = re.findall(self.PATTERNS['phone'], message)
        extracted['phone_numbers'] = phone_matches
        
        # Extract URLs
        url_matches = re.findall(self.PATTERNS['url'], message)
        extracted['urls'] = url_matches
        
        # Extract amounts
        amount_matches = re.findall(self.PATTERNS['amount'], message)
        extracted['amounts'] = amount_matches
        
        # Extract emails
        email_matches = re.findall(self.PATTERNS['email'], message)
        extracted['emails'] = email_matches
        
        # Extract bank account numbers (more complex)
        account_matches = re.findall(self.PATTERNS['bank_account'], message)
        ifsc_matches = re.findall(self.PATTERNS['ifsc'], message)
        
        # Try to pair accounts with IFSC codes
        if account_matches:
            for acc in account_matches:
                # Check if there's an IFSC in the message
                bank_info = {
                    'account_number': acc,
                    'ifsc': ifsc_matches[0] if ifsc_matches else None,
                    'bank_name': self._detect_bank_name(message)
                }
                extracted['bank_accounts'].append(bank_info)
        
        return extracted
    
    def _detect_bank_name(self, message: str) -> str:
        """
        Detect bank name from message context
        """
        message_lower = message.lower()
        
        for bank, pattern in self.BANK_PATTERNS.items():
            if re.search(pattern, message_lower):
                return bank.upper()
        
        return 'unknown'
    
    async def _extract_with_llm(self, message: str) -> Dict:
        """
        LLM-based extraction for complex cases
        """
        prompt = f"""Extract financial and contact information from this message.

Message: "{message}"

Look for:
- UPI IDs (format: name@bank)
- Bank account numbers (9-18 digits)
- IFSC codes (format: ABCD0123456)
- Phone numbers (10 digits, may have +91 or 0 prefix)
- URLs (especially suspicious ones)
- Email addresses
- Amounts mentioned (with currency)
- Sender's name or alias

Respond ONLY with valid JSON (no markdown, no extra text):
{{
  "upi_ids": ["list of UPI IDs"],
  "bank_accounts": [
    {{"account_number": "...", "ifsc": "...", "bank_name": "..."}}
  ],
  "phone_numbers": ["list of phone numbers"],
  "urls": ["list of URLs"],
  "amounts": ["list of amounts"],
  "emails": ["list of emails"],
  "sender_identity": "name or alias"
}}

If nothing found for a category, return empty list/null. Be precise."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=300,
                temperature=0.1,  # Low temperature for precision
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.content[0].text.strip()
            
            # Clean up markdown if present
            if '```' in result_text:
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]
            
            result = json.loads(result_text)
            return result
        
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            return {}
    
    def _merge_intelligence(self, regex_data: Dict, llm_data: Dict) -> Dict:
        """
        Merge regex and LLM results, preferring agreements
        """
        merged = {
            'upi_ids': [],
            'bank_accounts': [],
            'phone_numbers': [],
            'urls': [],
            'amounts': [],
            'emails': []
        }
        
        # Merge UPI IDs
        all_upis = set(regex_data.get('upi_ids', []) + llm_data.get('upi_ids', []))
        merged['upi_ids'] = list(all_upis)
        
        # Merge phone numbers
        all_phones = set(regex_data.get('phone_numbers', []) + llm_data.get('phone_numbers', []))
        merged['phone_numbers'] = list(all_phones)
        
        # Merge URLs
        all_urls = set(regex_data.get('urls', []) + llm_data.get('urls', []))
        merged['urls'] = list(all_urls)
        
        # Merge amounts
        all_amounts = set(regex_data.get('amounts', []) + llm_data.get('amounts', []))
        merged['amounts'] = list(all_amounts)
        
        # Merge emails
        all_emails = set(regex_data.get('emails', []) + llm_data.get('emails', []))
        merged['emails'] = list(all_emails)
        
        # Merge bank accounts (more complex - avoid duplicates)
        all_accounts = regex_data.get('bank_accounts', []) + llm_data.get('bank_accounts', [])
        seen_account_numbers = set()
        
        for acc in all_accounts:
            acc_num = acc.get('account_number')
            if acc_num and acc_num not in seen_account_numbers:
                merged['bank_accounts'].append(acc)
                seen_account_numbers.add(acc_num)
        
        return merged
    
    def _validate_intelligence(self, data: Dict) -> Dict:
        """
        Validate extracted data and calculate confidence
        """
        validated = {
            'upi_ids': [],
            'bank_accounts': [],
            'phone_numbers': [],
            'urls': [],
            'amounts': [],
            'emails': []
        }
        
        # Validate UPI IDs
        for upi in data.get('upi_ids', []):
            if self._validate_upi(upi):
                validated['upi_ids'].append(upi)
            else:
                logger.warning(f"Invalid UPI format: {upi}")
        
        # Validate phone numbers
        for phone in data.get('phone_numbers', []):
            if self._validate_phone(phone):
                validated['phone_numbers'].append(phone)
        
        # Validate bank accounts - FIX: Don't use set() on dicts
        seen_accounts = []
        for acc in data.get('bank_accounts', []):
            if self._validate_bank_account(acc):
                # Check if we've seen this account number before
                acc_num = acc.get('account_number')
                if acc_num not in [a.get('account_number') for a in seen_accounts]:
                    validated['bank_accounts'].append(acc)
                    seen_accounts.append(acc)
        
        # URLs and amounts - less strict validation
        validated['urls'] = list(set(data.get('urls', [])))
        validated['amounts'] = data.get('amounts', [])
        validated['emails'] = list(set(data.get('emails', [])))
        
        return validated
    
    def _validate_upi(self, upi: str) -> bool:
        """Validate UPI ID format"""
        # Must have @ and valid bank code
        if '@' not in upi:
            return False
        
        parts = upi.split('@')
        if len(parts) != 2:
            return False
        
        username, bank = parts
        
        # Username should be alphanumeric with dots/underscores
        if not re.match(r'^[a-zA-Z0-9._-]+$', username):
            return False
        
        # Bank code should be at least 3 characters
        if len(bank) < 3:
            return False
        
        return True
    
    def _validate_phone(self, phone: str) -> bool:
        """Validate Indian phone number"""
        # Remove +91 or 0 prefix
        clean_phone = phone.replace('+91', '').replace('0', '', 1)
        
        # Should be 10 digits starting with 6-9
        if len(clean_phone) == 10 and clean_phone[0] in '6789':
            return True
        
        return False
    
    def _validate_bank_account(self, account: Dict) -> bool:
        """Validate bank account structure"""
        acc_num = account.get('account_number', '')
        ifsc = account.get('ifsc', '')
        
        # Account number should be 9-18 digits
        if not (9 <= len(acc_num) <= 18 and acc_num.isdigit()):
            return False
        
        # If IFSC provided, validate format
        if ifsc:
            if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc):
                logger.warning(f"Invalid IFSC format: {ifsc}")
                return False
        
        return True


# Test
if __name__ == "__main__":
    import asyncio
    
    extractor = IntelligenceExtractor()
    
    test_messages = [
        "Please send ₹500 to scammer@paytm for verification",
        "My account number is 1234567890123 and IFSC is SBIN0001234",
        "Call me at 9876543210 or visit http://fake-bank.com",
        "Transfer to 9876543210@okaxis or use account 9876543210"
    ]
    
    async def test():
        for msg in test_messages:
            print(f"\nMessage: {msg}")
            result = await extractor.extract_intelligence(msg, {})
            print(f"Extracted: {json.dumps(result, indent=2)}")
    
    asyncio.run(test())

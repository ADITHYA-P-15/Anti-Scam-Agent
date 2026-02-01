"""
Intelligence Extractor - Layer 3
Multi-format extraction with semantic analysis
Handles obfuscated UPIs, hidden bank details, etc.
Enhanced with UPI bank validation and intel scoring
"""

import re
from typing import Dict, List, Optional
import logging
import os
import json

from agent.models import ExtractedEntities, BankAccount, ValidatedUPI, validate_upi

logger = logging.getLogger(__name__)


class IntelligenceExtractor:
    """
    Extract financial/contact intelligence from scammer messages
    Uses regex + LLM for semantic extraction
    """
    
    # ==========================================================================
    # REGEX PATTERNS
    # ==========================================================================
    
    PATTERNS = {
        # UPI IDs - standard and obfuscated
        'upi_standard': r'\b[a-zA-Z0-9._-]+@[a-zA-Z]{2,}(?:axis|sbi|icici|hdfc|paytm|ybl|upi|apl|ibl|okaxis|oksbi|okicici)\b',
        'upi_general': r'\b[a-zA-Z0-9._-]+@[a-zA-Z]{3,}\b',
        
        # Phone numbers (Indian)
        'phone': r'\b(?:\+91[-\s]?|0)?[6-9]\d{9}\b',
        'phone_spaced': r'\b(?:\+91\s?)?[6-9]\d{2}[-\s]?\d{3}[-\s]?\d{4}\b',
        'phone_obfuscated': r'\b[6-9][\s\-\.]*\d[\s\-\.]*\d[\s\-\.]*\d[\s\-\.]*\d[\s\-\.]*\d[\s\-\.]*\d[\s\-\.]*\d[\s\-\.]*\d[\s\-\.]*\d\b',
        
        # Bank accounts
        'bank_account': r'\b\d{9,18}\b',
        'ifsc': r'\b[A-Z]{4}0[A-Z0-9]{6}\b',
        
        # URLs
        'url': r'https?://[^\s<>"\')\]]+',
        'short_url': r'\b(?:bit\.ly|goo\.gl|tinyurl\.com|is\.gd|t\.co)/[a-zA-Z0-9]+\b',
        
        # Amounts
        'amount_rupee': r'(?:Rs\.?|₹|INR|rupees?)\s*[\d,]+(?:\.\d{2})?',
        'amount_lakh': r'\d+(?:\.\d+)?\s*(?:lakh|lac|lakhs)',
        'amount_crore': r'\d+(?:\.\d+)?\s*(?:crore|cr)',
        
        # Email
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    }
    
    # Bank name patterns
    BANK_NAMES = {
        'SBI': r'\b(?:sbi|state\s*bank)\b',
        'HDFC': r'\bhdfc\b',
        'ICICI': r'\bicici\b',
        'AXIS': r'\baxis\b',
        'KOTAK': r'\bkotak\b',
        'PNB': r'\bpnb\b',
        'BOB': r'\bbank\s*of\s*baroda\b',
        'CANARA': r'\bcanara\b',
        'PAYTM': r'\bpaytm\b',
        'PHONEPE': r'\bphonepe\b',
        'GPAY': r'\b(?:gpay|google\s*pay)\b',
    }
    
    # Obfuscation patterns (e.g., "p-a-y-t-m" or "p a y t m")
    DEOBFUSCATION_MAP = {
        r'p[\s\-\.]*a[\s\-\.]*y[\s\-\.]*t[\s\-\.]*m': 'paytm',
        r'g[\s\-\.]*p[\s\-\.]*a[\s\-\.]*y': 'gpay',
        r'p[\s\-\.]*h[\s\-\.]*o[\s\-\.]*n[\s\-\.]*e[\s\-\.]*p[\s\-\.]*e': 'phonepe',
        r's[\s\-\.]*b[\s\-\.]*i': 'sbi',
        r'h[\s\-\.]*d[\s\-\.]*f[\s\-\.]*c': 'hdfc',
        r'i[\s\-\.]*c[\s\-\.]*i[\s\-\.]*c[\s\-\.]*i': 'icici',
    }
    
    def __init__(self):
        """Initialize extractor with LLM client"""
        self.llm_available = False
        self.genai_client = None
        
        # Try Gemini
        google_key = os.getenv('GOOGLE_API_KEY')
        if google_key:
            try:
                from google import genai
                self.genai_client = genai.Client(api_key=google_key)
                self.model = "gemini-2.0-flash"
                self.llm_available = True
                self._use_new_sdk = True
                logger.info("✓ Gemini initialized for extraction")
            except ImportError:
                try:
                    import google.generativeai as genai_old
                    genai_old.configure(api_key=google_key)
                    self.model = "gemini-1.5-flash"
                    self.llm_available = True
                    self._use_new_sdk = False
                    logger.info("✓ Gemini (legacy) initialized for extraction")
                except Exception as e:
                    logger.warning(f"Gemini legacy init failed: {e}")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")
        
        # Try Anthropic as fallback
        self.anthropic_client = None
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        if anthropic_key:
            try:
                from anthropic import Anthropic
                self.anthropic_client = Anthropic(api_key=anthropic_key)
                logger.info("✓ Anthropic initialized for extraction fallback")
            except Exception as e:
                logger.warning(f"Anthropic init failed: {e}")
        
        if not self.llm_available and not self.anthropic_client:
            logger.warning("No LLM available - using regex extraction only")
    
    def _deobfuscate(self, message: str) -> str:
        """Deobfuscate common patterns like 'p-a-y-t-m' -> 'paytm'"""
        result = message.lower()
        for pattern, replacement in self.DEOBFUSCATION_MAP.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result
    
    def _extract_phone_numbers(self, message: str) -> List[str]:
        """Extract phone numbers including obfuscated ones"""
        phones = set()
        
        # Standard patterns
        for pattern_name in ['phone', 'phone_spaced', 'phone_obfuscated']:
            matches = re.findall(self.PATTERNS[pattern_name], message)
            for match in matches:
                # Normalize: remove spaces, dashes, dots
                clean = re.sub(r'[\s\-\.]', '', match)
                # Remove +91 or leading 0
                if clean.startswith('+91'):
                    clean = clean[3:]
                elif clean.startswith('91') and len(clean) == 12:
                    clean = clean[2:]
                elif clean.startswith('0'):
                    clean = clean[1:]
                
                # Validate: 10 digits starting with 6-9
                if len(clean) == 10 and clean[0] in '6789':
                    phones.add(clean)
        
        return list(phones)
    
    def _extract_upis(self, message: str) -> List[ValidatedUPI]:
        """Extract UPI IDs with bank provider validation"""
        upis = []
        seen = set()
        
        # Deobfuscate first
        clean_message = self._deobfuscate(message)
        
        # Extract standard UPIs
        for pattern_name in ['upi_standard', 'upi_general']:
            matches = re.findall(self.PATTERNS[pattern_name], clean_message, re.IGNORECASE)
            for upi in matches:
                upi = upi.lower()
                # Validate: must have @ and not be email-like
                if '@' in upi and not upi.endswith(('.com', '.in', '.org', '.net')):
                    if upi not in seen:
                        seen.add(upi)
                        # Validate and get bank provider
                        validation = validate_upi(upi)
                        upis.append(ValidatedUPI(**validation))
        
        # Also check original message
        matches = re.findall(self.PATTERNS['upi_general'], message, re.IGNORECASE)
        for upi in matches:
            upi = upi.lower()
            if '@' in upi and not upi.endswith(('.com', '.in', '.org', '.net')):
                if upi not in seen:
                    seen.add(upi)
                    validation = validate_upi(upi)
                    upis.append(ValidatedUPI(**validation))
        
        return upis
    
    def _extract_bank_accounts(self, message: str) -> List[BankAccount]:
        """Extract bank account numbers with IFSC"""
        accounts = []
        seen_numbers = set()
        
        # Find account numbers (9-18 digits)
        acc_matches = re.findall(self.PATTERNS['bank_account'], message)
        ifsc_matches = re.findall(self.PATTERNS['ifsc'], message)
        
        # Detect bank name
        bank_name = 'unknown'
        for name, pattern in self.BANK_NAMES.items():
            if re.search(pattern, message, re.IGNORECASE):
                bank_name = name
                break
        
        for acc_num in acc_matches:
            # Filter out likely phone numbers (10 digits starting with 6-9)
            if len(acc_num) == 10 and acc_num[0] in '6789':
                continue
            
            if acc_num not in seen_numbers:
                seen_numbers.add(acc_num)
                accounts.append(BankAccount(
                    account_number=acc_num,
                    ifsc=ifsc_matches[0] if ifsc_matches else None,
                    bank_name=bank_name,
                    confidence=0.9 if ifsc_matches else 0.7
                ))
        
        return accounts
    
    def _extract_urls(self, message: str) -> List[str]:
        """Extract URLs"""
        urls = set()
        
        for pattern_name in ['url', 'short_url']:
            matches = re.findall(self.PATTERNS[pattern_name], message)
            urls.update(matches)
        
        return list(urls)
    
    def _extract_amounts(self, message: str) -> List[str]:
        """Extract monetary amounts"""
        amounts = set()
        
        for pattern_name in ['amount_rupee', 'amount_lakh', 'amount_crore']:
            matches = re.findall(self.PATTERNS[pattern_name], message, re.IGNORECASE)
            amounts.update(matches)
        
        return list(amounts)
    
    def _extract_emails(self, message: str) -> List[str]:
        """Extract email addresses"""
        emails = set()
        matches = re.findall(self.PATTERNS['email'], message)
        
        for email in matches:
            # Filter out UPI IDs
            if not any(x in email.lower() for x in ['@paytm', '@ybl', '@okaxis', '@oksbi', '@upi']):
                emails.add(email.lower())
        
        return list(emails)
    
    async def extract_intelligence(self, message: str, session: Dict) -> Dict:
        """
        Main extraction method
        Returns dict compatible with ExtractedEntities
        """
        # Step 1: Regex extraction with UPI validation
        upi_list = self._extract_upis(message)
        
        extracted = {
            'upi_ids': [upi.model_dump() for upi in upi_list],
            'bank_accounts': [acc.model_dump() for acc in self._extract_bank_accounts(message)],
            'phone_numbers': self._extract_phone_numbers(message),
            'urls': self._extract_urls(message),
            'amounts': self._extract_amounts(message),
            'emails': self._extract_emails(message),
        }
        
        # Step 2: LLM semantic extraction for complex cases
        if self.llm_available or self.anthropic_client:
            try:
                llm_extracted = await self._llm_extraction(message)
                if llm_extracted:
                    # Merge LLM results
                    for key in ['upi_ids', 'phone_numbers', 'urls', 'emails']:
                        if llm_extracted.get(key):
                            for item in llm_extracted[key]:
                                if item not in extracted[key]:
                                    extracted[key].append(item)
                    
                    # Handle bank accounts specially
                    if llm_extracted.get('bank_accounts'):
                        existing_nums = [acc.get('account_number') for acc in extracted['bank_accounts']]
                        for acc in llm_extracted['bank_accounts']:
                            if isinstance(acc, dict) and acc.get('account_number') not in existing_nums:
                                extracted['bank_accounts'].append(acc)
            except Exception as e:
                logger.error(f"LLM extraction failed: {e}")
        
        logger.info(
            f"Extracted: {len(extracted['upi_ids'])} UPIs, "
            f"{len(extracted['bank_accounts'])} accounts, "
            f"{len(extracted['phone_numbers'])} phones, "
            f"{len(extracted['urls'])} URLs"
        )
        
        return extracted
    
    async def _llm_extraction(self, message: str) -> Optional[Dict]:
        """Use LLM for semantic extraction"""
        prompt = f"""Extract financial and contact information from this message.
Look for obfuscated data like "p-a-y-t-m" = paytm, spaced phone numbers, etc.

Message: "{message}"

Return JSON only (no markdown):
{{"upi_ids": [], "bank_accounts": [{{"account_number": "", "ifsc": "", "bank_name": ""}}], "phone_numbers": [], "urls": [], "emails": []}}

If nothing found, return empty arrays."""

        # Try Gemini
        if self.llm_available:
            try:
                if self._use_new_sdk:
                    response = self.genai_client.models.generate_content(
                        model=self.model,
                        contents=prompt
                    )
                    result_text = response.text.strip()
                else:
                    import google.generativeai as genai
                    model = genai.GenerativeModel(self.model)
                    response = model.generate_content(prompt)
                    result_text = response.text.strip()
                
                # Clean markdown
                if '```' in result_text:
                    result_text = result_text.split('```')[1]
                    if result_text.startswith('json'):
                        result_text = result_text[4:]
                
                return json.loads(result_text)
            except Exception as e:
                logger.error(f"Gemini extraction failed: {e}")
        
        # Try Anthropic
        if self.anthropic_client:
            try:
                response = self.anthropic_client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=200,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                result_text = response.content[0].text.strip()
                if '```' in result_text:
                    result_text = result_text.split('```')[1]
                    if result_text.startswith('json'):
                        result_text = result_text[4:]
                return json.loads(result_text)
            except Exception as e:
                logger.error(f"Anthropic extraction failed: {e}")
        
        return None


# Standalone test
if __name__ == "__main__":
    import asyncio
    
    extractor = IntelligenceExtractor()
    
    test_messages = [
        "Send Rs 500 to scammer@paytm for verification",
        "My account number is 1234567890123 and IFSC is SBIN0001234",
        "Call me at 9 8 7 6 5 4 3 2 1 0 for help",
        "Pay to p-a-y-t-m UPI: fraud@ybl or use http://fake-bank.com",
        "Transfer to 9876543210@okaxis or account 9876543210",
    ]
    
    async def test():
        for msg in test_messages:
            print(f"\nMessage: {msg}")
            result = await extractor.extract_intelligence(msg, {})
            print(f"Extracted: {json.dumps(result, indent=2)}")
    
    asyncio.run(test())

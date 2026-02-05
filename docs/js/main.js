const CONFIG = {
    API_URL: window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://anti-scam-agent-production.up.railway.app'
};

let sessionId = `demo-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
let messageHistory = [];
let isProcessing = false;

const elements = {
    chatMessages: document.getElementById('chatMessages'),
    demoInput: document.getElementById('demoInput'),
    sendMessage: document.getElementById('sendMessage'),
    resetChat: document.getElementById('resetChat'),
    detectionStatus: document.getElementById('detectionStatus'),
    intelList: document.getElementById('intelList'),
    urgencyBar: document.getElementById('urgencyBar'),
    urgencyValue: document.getElementById('urgencyValue'),
    authorityBar: document.getElementById('authorityBar'),
    authorityValue: document.getElementById('authorityValue'),
    emotionBar: document.getElementById('emotionBar'),
    emotionValue: document.getElementById('emotionValue'),
    financialBar: document.getElementById('financialBar'),
    financialValue: document.getElementById('financialValue'),
    totalSessions: document.getElementById('totalSessions'),
    scamsDetected: document.getElementById('scamsDetected'),
    avgLatency: document.getElementById('avgLatency'),
    intelScore: document.getElementById('intelScore'),
};

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

function animateCountUp(element, target, duration = 1500) {
    const increment = target / (duration / 16);
    let current = 0;
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) { element.textContent = target; clearInterval(timer); }
        else { element.textContent = Math.floor(current); }
    }, 16);
}

function initHeroStats() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCountUp(entry.target, parseInt(entry.target.dataset.count));
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });
    document.querySelectorAll('.stat-number[data-count]').forEach(stat => observer.observe(stat));
}

function addMessage(content, type, extras = {}) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    let html = `<div class="message-content">${escapeHtml(content)}</div>`;
    if (extras.badge) html += `<span class="message-badge ${extras.badgeType || 'info'}">${extras.badge}</span>`;
    messageDiv.innerHTML = html;
    const welcome = elements.chatMessages.querySelector('.demo-welcome');
    if (welcome) welcome.remove();
    elements.chatMessages.appendChild(messageDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    return messageDiv;
}

function addIntelExtracted(type, value, provider = null) {
    const emptyState = elements.intelList.querySelector('.intel-empty');
    if (emptyState) emptyState.remove();
    const intelDiv = document.createElement('div');
    intelDiv.className = 'intel-item';
    intelDiv.innerHTML = `<span class="intel-item-type">${type}:</span><span class="intel-item-value">${escapeHtml(value)}${provider ? ` (${provider})` : ''}</span>`;
    elements.intelList.appendChild(intelDiv);
    const indicator = document.createElement('div');
    indicator.className = 'intel-extracted';
    indicator.innerHTML = `<span class="intel-icon">🎯</span><span>${type} Extracted: <strong>${escapeHtml(value)}</strong>${provider ? ` (${provider})` : ''}</span>`;
    elements.chatMessages.appendChild(indicator);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function updateDetectionStatus(isScam, scamType = null, confidence = 0) {
    const statusDiv = elements.detectionStatus;
    if (isScam) {
        statusDiv.className = 'detection-status scam';
        statusDiv.innerHTML = `<span class="status-label scam">🚨 SCAM DETECTED</span><p style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">Type: ${scamType || 'Unknown'} (${Math.round(confidence * 100)}% confidence)</p>`;
    } else {
        statusDiv.className = 'detection-status safe';
        statusDiv.innerHTML = `<span class="status-label safe">✅ Analyzing...</span>`;
    }
}

function updateTriadScores(triad) {
    const maxScores = { urgency: 3, authority: 3, emotion: 2, financial: 2 };
    Object.keys(maxScores).forEach(key => {
        const score = triad[key] || 0;
        elements[`${key}Bar`].style.width = `${Math.min((score / maxScores[key]) * 100, 100)}%`;
        elements[`${key}Value`].textContent = score.toFixed(1);
    });
}

function resetChat() {
    sessionId = `demo-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    messageHistory = [];
    elements.chatMessages.innerHTML = `<div class="demo-welcome"><p>👋 Send a scam message to see the detection in action!</p><p class="demo-hint">Try: "Your bank account will be blocked! Send Rs 500 to verify@paytm"</p></div>`;
    elements.detectionStatus.className = 'detection-status';
    elements.detectionStatus.innerHTML = '<span class="status-label">Waiting for message...</span>';
    elements.intelList.innerHTML = '<p class="intel-empty">No intelligence extracted yet</p>';
    updateTriadScores({ urgency: 0, authority: 0, emotion: 0, financial: 0 });
}

async function sendToAPI(message) {
    try {
        const response = await fetch(`${CONFIG.API_URL}/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, message: message }),
        });
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        return mockAPIResponse(message);
    }
}

function mockAPIResponse(message) {
    const lowerMsg = message.toLowerCase();
    const urgency = [/block/i, /immediate/i, /urgent/i, /24 hours/i].filter(p => p.test(lowerMsg)).length * 1.0;
    const authority = [/bank/i, /sbi/i, /kyc/i, /rbi/i, /hdfc/i].filter(p => p.test(lowerMsg)).length * 1.2;
    const emotion = [/lottery/i, /prize/i, /winner/i].filter(p => p.test(lowerMsg)).length * 1.0;
    const financial = [/@paytm/i, /@ybl/i, /rs\.?\s*\d+/i, /send/i, /pay/i, /transfer/i].filter(p => p.test(lowerMsg)).length * 0.8;
    const total = Math.min(urgency, 3) + Math.min(authority, 3) + Math.min(emotion, 2) + Math.min(financial, 2);
    const isScam = total >= 2.5;
    const upiMatch = message.match(/\b[\w.]+@(paytm|ybl|okaxis|oksbi|okicici|gpay)\b/i);
    const upiIds = upiMatch ? [{ upi_id: upiMatch[0], bank_provider: { 'paytm': 'Paytm', 'ybl': 'Yes Bank', 'okaxis': 'Axis', 'oksbi': 'SBI', 'okicici': 'ICICI', 'gpay': 'GPay' }[upiMatch[1].toLowerCase()] || 'Unknown', verified: true }] : [];
    const phoneNumbers = (message.match(/\b[6-9]\d{9}\b/) || []).slice(0, 1);
    let scamType = 'unknown';
    if (/bank|sbi|kyc|account|hdfc|icici/i.test(lowerMsg)) scamType = 'bank_impersonation';
    else if (/lottery|prize|winner|congrat/i.test(lowerMsg)) scamType = 'lottery';
    else if (/investment|returns|profit|trading/i.test(lowerMsg)) scamType = 'investment';
    else if (/job|offer|salary|work from home/i.test(lowerMsg)) scamType = 'job_offer';

    // TURN-AWARE RESPONSES - progressively advance conversation
    const turnCount = messageHistory.length;
    const responsesByPhase = {
        bank_impersonation: [
            // Turn 1: Confused/worried
            ["Oh my god! Is my account really blocked? What should I do?", "What? This is very worrying! Can you tell me more?", "Oh dear! What happened to my account?"],
            // Turn 2-3: Trust building, asking for details
            ["Wait, which bank did you say? I want to make sure this is real.", "Can you verify which account this is about?", "I need more details. What department are you from?"],
            // Turn 4+: Honey token - asking for payment details
            ["Okay, I want to fix this. What's your UPI ID so I can pay?", "I'm ready to pay. Give me your bank account number.", "Tell me where to send the money. What's the UPI?", "I'll transfer now. What's your UPI ID?"]
        ],
        lottery: [
            ["Wow! I really won? That's incredible!", "I never win anything! This is amazing!"],
            ["How do I claim my prize? I'm so excited!", "What do I need to do to get my winnings?"],
            ["I want to claim it now! What's your UPI ID?", "Where do I send the processing fee? Give me the account details."]
        ],
        investment: [
            ["20-30% returns? That sounds interesting!", "High returns? Tell me more..."],
            ["How does this investment work? Is it safe?", "I want to understand better. What's the minimum investment?"],
            ["Okay, I'm interested. What's your UPI ID for the deposit?", "Where do I transfer the investment amount?"]
        ],
        job_offer: [
            ["A job offer? I've been looking for work!", "Really? I'm very interested in this opportunity!"],
            ["What's the salary? What do I need to do?", "This sounds perfect! What are the requirements?"],
            ["I want this job! What's your UPI for the registration fee?", "I'll pay immediately! Give me the payment details."]
        ],
        unknown: [
            ["Hello? Who is this calling?", "Yes, speaking. What is this about?"],
            ["I don't understand. Can you explain more clearly?", "What exactly do you need from me?"],
            ["Okay, what do I need to do? Give me the details.", "I want to help. What information do you need?"]
        ]
    };

    // Select response based on turn count
    const phaseIndex = Math.min(Math.floor(turnCount / 2), 2); // 0, 1, or 2
    const responses = responsesByPhase[scamType] || responsesByPhase.unknown;
    const phaseResponses = responses[Math.min(phaseIndex, responses.length - 1)];
    const agentResponse = phaseResponses[Math.floor(Math.random() * phaseResponses.length)];

    return {
        session_id: sessionId, is_scam: isScam, confidence_score: Math.min(total / 10, 0.95),
        extracted_entities: { upi_ids: upiIds, phone_numbers: phoneNumbers, bank_accounts: [], urls: [], intel_completeness_score: upiIds.length * 30 + phoneNumbers.length * 15 },
        agent_response: agentResponse,
        forensics: { scam_type: scamType, persona_used: 'elderly_tech_illiterate' },
        metadata: { latency_ms: Math.floor(Math.random() * 200) + 100, typing_behavior: { typing_delay_ms: 1500 } },
        _triad: { urgency: Math.min(urgency, 3), authority: Math.min(authority, 3), emotion: Math.min(emotion, 2), financial: Math.min(financial, 2) },
    };
}

async function handleSendMessage() {
    const message = elements.demoInput.value.trim();
    if (!message || isProcessing) return;
    isProcessing = true;
    elements.sendMessage.disabled = true;
    elements.demoInput.value = '';
    addMessage(message, 'scammer');
    messageHistory.push({ role: 'scammer', message });
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message agent typing';
    typingDiv.innerHTML = '<div class="message-content">Analyzing...</div>';
    elements.chatMessages.appendChild(typingDiv);
    try {
        const response = await sendToAPI(message);
        typingDiv.remove();
        updateDetectionStatus(response.is_scam, response.forensics?.scam_type, response.confidence_score);
        if (response._triad) updateTriadScores(response._triad);
        await sleep(response.metadata?.typing_behavior?.typing_delay_ms || 1500);
        const extras = response.forensics?.persona_used ? { badge: `🎭 ${response.forensics.persona_used.replace(/_/g, ' ')}`, badgeType: 'info' } : {};
        addMessage(response.agent_response, 'agent', extras);
        const entities = response.extracted_entities || {};
        (entities.upi_ids || []).forEach(upi => addIntelExtracted('UPI', typeof upi === 'string' ? upi : upi.upi_id, upi.bank_provider));
        (entities.phone_numbers || []).forEach(phone => addIntelExtracted('Phone', phone));
        elements.totalSessions.textContent = parseInt(elements.totalSessions.textContent || 0) + 1;
        if (response.is_scam) elements.scamsDetected.textContent = parseInt(elements.scamsDetected.textContent || 0) + 1;
        elements.avgLatency.textContent = `${response.metadata?.latency_ms || 200}ms`;
        elements.intelScore.textContent = `${Math.round(entities.intel_completeness_score || 0)}%`;
    } catch (error) { typingDiv.remove(); addMessage('Error. Please try again.', 'agent'); }
    isProcessing = false;
    elements.sendMessage.disabled = false;
    elements.demoInput.focus();
}

document.addEventListener('DOMContentLoaded', () => {
    initHeroStats();
    document.querySelectorAll('a[href^="#"]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); document.querySelector(a.getAttribute('href'))?.scrollIntoView({ behavior: 'smooth' }); }));
    if (elements.sendMessage) elements.sendMessage.addEventListener('click', handleSendMessage);
    if (elements.demoInput) elements.demoInput.addEventListener('keypress', e => { if (e.key === 'Enter') handleSendMessage(); });
    if (elements.resetChat) elements.resetChat.addEventListener('click', resetChat);
    console.log('🛡️ Anti-Scam Sentinel Initialized');
});

// SmartDoc AI - Simple & Clean Chat Controller
let currentLanguage = 'en';
let currentConversationId = null;
let currentDocId = null;

document.addEventListener('DOMContentLoaded', () => {
  currentDocId = document.getElementById('currentDocId').value;
  
  const urlParams = new URLSearchParams(window.location.search);
  const convParam = urlParams.get('conversation_id');
  if (convParam) {
    currentConversationId = convParam;
  }

  loadChatHistory();
});

// Set Preferred Language
function setLanguage(lang) {
  currentLanguage = lang;
  
  ['en', 'hi', 'mr'].forEach(l => {
    const btn = document.getElementById(`lang-${l}`);
    if (btn) {
      if (l === lang) {
        btn.classList.add('active', 'btn-primary', 'text-white');
        btn.classList.remove('btn-light', 'text-secondary');
      } else {
        btn.classList.remove('active', 'btn-primary', 'text-white');
        btn.classList.add('btn-light', 'text-secondary');
      }
    }
  });
}

// Quick Prompt Click (One-click answers)
function askQuickPrompt(promptText) {
  const input = document.getElementById('questionInput');
  input.value = promptText;
  document.getElementById('chatForm').requestSubmit();
}

// Submit Question
async function handleQuestionSubmit(event) {
  event.preventDefault();
  const input = document.getElementById('questionInput');
  const question = input.value.trim();

  if (!question) return;

  const sendBtn = document.getElementById('sendBtn');
  const indicator = document.getElementById('searchingIndicator');
  const welcomeBanner = document.getElementById('welcomeChatBanner');

  // Hide welcome card on first query
  if (welcomeBanner) {
    welcomeBanner.classList.add('d-none');
  }

  // Display user question
  appendUserMessage(question);
  input.value = '';

  // Show thinking indicator
  sendBtn.disabled = true;
  indicator.classList.remove('d-none');
  scrollToBottom();

  try {
    const res = await fetch(`/api/documents/${currentDocId}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: question,
        language: currentLanguage,
        conversation_id: currentConversationId
      })
    });

    const data = await res.json();

    if (res.ok) {
      currentConversationId = data.conversation_id;
      appendAssistantMessage(data);
    } else {
      appendErrorMessage(data.detail || 'Could not retrieve answer. Please try again.');
    }
  } catch (err) {
    console.error('Chat error:', err);
    appendErrorMessage('Connection error. Please check your backend connection.');
  } finally {
    sendBtn.disabled = false;
    indicator.classList.add('d-none');
    scrollToBottom();
  }
}

// User Bubble
function appendUserMessage(text) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'chat-message-row user-row';
  div.innerHTML = `
    <div class="user-bubble">
      ${escapeHtml(text)}
    </div>
  `;
  container.appendChild(div);
}

// Assistant Bubble (Clean & Formatted)
function appendAssistantMessage(data) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  const isSupported = data.is_supported;

  div.className = 'chat-message-row assistant-row';

  // Format response text with simple bolding and clean linebreaks
  const formattedAnswer = formatSimpleMarkdown(data.answer);

  // Clean Page Badges
  let pagePills = '';
  if (data.source_pages && data.source_pages.length > 0) {
    pagePills = data.source_pages.map(p => `
      <span class="page-pill" title="Verified on Page ${p}">
        <i class="bi bi-file-earmark-check-fill text-primary"></i> Page ${p}
      </span>
    `).join(' ');
  }

  // Clean Excerpts toggle if available
  let excerptsSection = '';
  if (data.excerpts && data.excerpts.length > 0) {
    const excId = `exc-${Date.now()}`;
    const excCards = data.excerpts.map((ex, i) => `
      <div class="simple-excerpt-card">
        <div class="small fw-bold text-muted mb-1">Snippet #${i+1} (Page ${ex.page})</div>
        <div class="small text-secondary">${escapeHtml(ex.text)}</div>
      </div>
    `).join('');

    excerptsSection = `
      <div class="mt-2 pt-2 border-top">
        <a class="text-decoration-none small text-muted d-inline-flex align-items-center gap-1" data-bs-toggle="collapse" href="#${excId}" role="button">
          <i class="bi bi-card-text"></i> Show source text (${data.excerpts.length})
        </a>
        <div class="collapse mt-2" id="${excId}">
          ${excCards}
        </div>
      </div>
    `;
  }

  const copyId = `copy-${Date.now()}`;

  div.innerHTML = `
    <div class="assistant-card ${!isSupported ? 'not-found-card' : ''}">
      <div class="d-flex align-items-center justify-content-between mb-2">
        <div class="d-flex align-items-center gap-2">
          <span class="bot-badge">
            <i class="bi bi-stars"></i> SmartDoc AI
          </span>
          ${pagePills}
        </div>
        <button class="btn btn-sm btn-link text-muted p-0" id="${copyId}" title="Copy" onclick="copyAnswerText('${escapeJsString(data.answer)}')">
          <i class="bi bi-clipboard"></i>
        </button>
      </div>

      <div class="answer-content">
        ${formattedAnswer}
      </div>

      ${excerptsSection}
    </div>
  `;

  container.appendChild(div);
}

// Error Bubble
function appendErrorMessage(msg) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'chat-message-row assistant-row';
  div.innerHTML = `
    <div class="assistant-card not-found-card">
      <div class="text-danger small fw-bold mb-1"><i class="bi bi-exclamation-circle-fill"></i> Error</div>
      <div>${escapeHtml(msg)}</div>
    </div>
  `;
  container.appendChild(div);
}

// Format Simple Markdown (bolding, lists, clean spacing)
function formatSimpleMarkdown(text) {
  if (!text) return '';
  
  let formatted = escapeHtml(text);
  
  // Replace **bold** with <strong>bold</strong>
  formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  
  // Replace bullet points • with styled bullets
  formatted = formatted.replace(/•\s*(.*?)(?=\n|$)/g, '<div class="simple-bullet"><span class="bullet-dot">•</span> $1</div>');
  
  // Replace newlines with clean breaks
  formatted = formatted.replace(/\n\n/g, '<div class="my-2"></div>');
  formatted = formatted.replace(/\n/g, '<br>');
  
  return formatted;
}

// Load Previous History
async function loadChatHistory() {
  try {
    const url = currentConversationId 
      ? `/api/documents/${currentDocId}/history?conversation_id=${currentConversationId}`
      : `/api/documents/${currentDocId}/history`;

    const res = await fetch(url);
    if (!res.ok) return;

    const data = await res.json();
    const messages = data.messages || [];

    if (messages.length > 0) {
      const welcome = document.getElementById('welcomeChatBanner');
      if (welcome) welcome.classList.add('d-none');

      messages.forEach(m => {
        appendUserMessage(m.question);
        appendAssistantMessage(m);
        if (!currentConversationId) currentConversationId = m.conversation_id;
      });

      scrollToBottom();
    }
  } catch (e) {
    console.error('History load error:', e);
  }
}

// Start New Conversation
function startNewConversation() {
  currentConversationId = null;
  const container = document.getElementById('chatMessages');
  container.innerHTML = `
    <div class="welcome-card text-center my-auto py-4" id="welcomeChatBanner">
      <div class="avatar-robot mb-3">
        <i class="bi bi-robot"></i>
      </div>
      <h4 class="fw-bold text-dark mb-1">New Chat Started</h4>
      <p class="text-muted small mx-auto mb-4" style="max-width: 480px;">
        Ask anything about your document. Click any topic below or type your question:
      </p>
      <div class="row g-2 justify-content-center mx-auto" style="max-width: 620px;">
        <div class="col-sm-6 col-md-4">
          <button class="quick-prompt-btn w-100" onclick="askQuickPrompt('What is the candidate or person name in this document?')">
            <span class="prompt-icon">👤</span>
            <span class="prompt-title">Name & Profile</span>
            <span class="prompt-sub">Who is this document about?</span>
          </button>
        </div>
        <div class="col-sm-6 col-md-4">
          <button class="quick-prompt-btn w-100" onclick="askQuickPrompt('What are the key technical skills and tools?')">
            <span class="prompt-icon">🛠️</span>
            <span class="prompt-title">Technical Skills</span>
            <span class="prompt-sub">Technologies, languages & tools</span>
          </button>
        </div>
        <div class="col-sm-6 col-md-4">
          <button class="quick-prompt-btn w-100" onclick="askQuickPrompt('What is the work experience and company history?')">
            <span class="prompt-icon">💼</span>
            <span class="prompt-title">Experience</span>
            <span class="prompt-sub">Companies, roles & tenure</span>
          </button>
        </div>
        <div class="col-sm-6 col-md-4">
          <button class="quick-prompt-btn w-100" onclick="askQuickPrompt('What are the education details and degrees?')">
            <span class="prompt-icon">🎓</span>
            <span class="prompt-title">Education</span>
            <span class="prompt-sub">Degrees, college & scores</span>
          </button>
        </div>
        <div class="col-sm-6 col-md-4">
          <button class="quick-prompt-btn w-100" onclick="askQuickPrompt('What is the contact information like email and phone number?')">
            <span class="prompt-icon">📞</span>
            <span class="prompt-title">Contact Info</span>
            <span class="prompt-sub">Email, phone & location</span>
          </button>
        </div>
        <div class="col-sm-6 col-md-4">
          <button class="quick-prompt-btn w-100" onclick="askQuickPrompt('Give me a clean summary of this document.')">
            <span class="prompt-icon">📋</span>
            <span class="prompt-title">Summary</span>
            <span class="prompt-sub">Overview of key points</span>
          </button>
        </div>
      </div>
    </div>
  `;
}

// Helpers
function scrollToBottom() {
  const container = document.getElementById('chatMessages');
  setTimeout(() => {
    container.scrollTop = container.scrollHeight;
  }, 40);
}

function copyAnswerText(text) {
  navigator.clipboard.writeText(text).then(() => {
    alert('Answer copied to clipboard!');
  });
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function escapeJsString(str) {
  if (!str) return '';
  return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, '\\n');
}

// SmartDoc AI - Dashboard JavaScript
document.addEventListener('DOMContentLoaded', () => {
  initDropzone();
  loadDocuments();
  loadRecentConversations();
});

// Dropzone Initialization
function initDropzone() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');

  if (!dropzone || !fileInput) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('drag-over');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('drag-over');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleUpload(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleUpload(e.target.files[0]);
    }
  });
}

// Upload Handler
async function handleUpload(file) {
  if (!file) return;

  // Client-side extension validation
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showAlert('Please select a valid PDF file (.pdf)', 'danger');
    return;
  }

  // Client-side size validation (25MB limit)
  if (file.size > 25 * 1024 * 1024) {
    showAlert('File size exceeds the 25 MB limit.', 'danger');
    return;
  }

  const progressContainer = document.getElementById('uploadProgressContainer');
  const statusText = document.getElementById('uploadStatusText');
  progressContainer.classList.remove('d-none');
  statusText.textContent = `Uploading and indexing '${file.name}'...`;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch('/api/documents/upload', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();

    if (response.ok) {
      showAlert(`Document '${data.filename}' successfully processed with ${data.page_count} pages and ${data.total_chunks} chunks!`, 'success');
      loadDocuments();
      // Reset input
      document.getElementById('fileInput').value = '';
    } else {
      let errMessage = data.detail || 'Failed to upload document.';
      if (response.status === 422 && data.detail && data.detail.includes('scanned')) {
        showAlert(`Scanned Document Alert: ${errMessage}`, 'warning');
      } else {
        showAlert(`Upload error: ${errMessage}`, 'danger');
      }
    }
  } catch (error) {
    console.error('Upload error:', error);
    showAlert('Server connection error during upload. Please try again.', 'danger');
  } finally {
    progressContainer.classList.add('d-none');
  }
}

// Load Documents
async function loadDocuments() {
  const container = document.getElementById('documentList');
  const emptyState = document.getElementById('emptyDocsState');

  try {
    const response = await fetch('/api/documents');
    const data = await response.json();

    const docs = data.documents || [];
    updateMetrics(docs);

    if (docs.length === 0) {
      container.innerHTML = '';
      emptyState.classList.remove('d-none');
      return;
    }

    emptyState.classList.add('d-none');
    container.innerHTML = docs.map(doc => renderDocumentCard(doc)).join('');
  } catch (err) {
    console.error('Failed to load documents:', err);
    showAlert('Failed to fetch uploaded documents.', 'danger');
  }
}

// Render Document Card
function renderDocumentCard(doc) {
  const sizeMB = (doc.file_size_bytes / (1024 * 1024)).toFixed(2);
  const uploadDate = new Date(doc.created_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric'
  });

  let statusBadge = '<span class="badge-ready"><i class="bi bi-check-circle me-1"></i>Ready</span>';
  if (doc.status === 'scanned_needs_ocr') {
    statusBadge = '<span class="badge-ocr"><i class="bi bi-exclamation-triangle me-1"></i>OCR Needed</span>';
  } else if (doc.status === 'processing') {
    statusBadge = '<span class="badge-processing"><i class="bi bi-arrow-repeat me-1"></i>Processing</span>';
  } else if (doc.status === 'error') {
    statusBadge = '<span class="badge-ocr"><i class="bi bi-x-circle me-1"></i>Error</span>';
  }

  return `
    <div class="col-md-6 col-lg-4">
      <div class="doc-card">
        <div>
          <div class="d-flex align-items-start justify-content-between mb-2">
            <div class="d-flex align-items-center gap-2">
              <div class="doc-icon"><i class="bi bi-file-earmark-pdf"></i></div>
              <h6 class="doc-title mb-0" title="${escapeHtml(doc.filename)}">${escapeHtml(doc.filename)}</h6>
            </div>
            ${statusBadge}
          </div>
          
          <div class="doc-meta mb-3 mt-2">
            <span><i class="bi bi-file-text"></i> ${doc.page_count} Pages</span>
            <span><i class="bi bi-hdd"></i> ${sizeMB} MB</span>
            <span><i class="bi bi-calendar"></i> ${uploadDate}</span>
          </div>

          ${doc.error_message ? `<div class="small text-danger mb-2 p-2 bg-danger-subtle rounded">${escapeHtml(doc.error_message)}</div>` : ''}
        </div>

        <div class="d-flex align-items-center justify-content-between pt-3 border-top mt-auto">
          <button class="btn btn-sm btn-outline-secondary" onclick="openPreview('${doc.id}')">
            <i class="bi bi-eye"></i> Details
          </button>
          
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-danger" onclick="deleteDocument('${doc.id}', '${escapeHtml(doc.filename)}')" title="Delete Document">
              <i class="bi bi-trash"></i>
            </button>
            <a href="/chat/${doc.id}" class="btn btn-sm btn-primary d-flex align-items-center gap-1 ${doc.status !== 'ready' ? 'disabled' : ''}">
              <i class="bi bi-chat-dots-fill"></i> Ask AI
            </a>
          </div>
        </div>
      </div>
    </div>
  `;
}

// Update Metrics Counters (if present)
function updateMetrics(docs) {
  const docEl = document.getElementById('statDocCount');
  if (docEl) docEl.textContent = docs.length;
  const chunkEl = document.getElementById('statChunkCount');
  if (chunkEl) {
    const totalChunks = docs.reduce((acc, d) => acc + (d.total_chunks || 0), 0);
    chunkEl.textContent = totalChunks;
  }
}

// Delete Document
async function deleteDocument(docId, docName) {
  if (!confirm(`Are you sure you want to delete '${docName}'? All vector search indexes and conversations will be removed.`)) {
    return;
  }

  try {
    const res = await fetch(`/api/documents/${docId}`, { method: 'DELETE' });
    if (res.ok) {
      showAlert(`Document '${docName}' was successfully deleted.`, 'success');
      loadDocuments();
      loadRecentConversations();
    } else {
      const err = await res.json();
      showAlert(`Delete failed: ${err.detail || 'Unknown error'}`, 'danger');
    }
  } catch (error) {
    console.error('Delete error:', error);
    showAlert('Network error while deleting document.', 'danger');
  }
}

// Preview Modal Loader
async function openPreview(docId) {
  const modal = new bootstrap.Modal(document.getElementById('previewModal'));
  const body = document.getElementById('previewModalBody');
  const chatBtn = document.getElementById('previewOpenChatBtn');
  chatBtn.href = `/chat/${docId}`;

  body.innerHTML = `
    <div class="text-center py-4 text-muted">
      <div class="spinner-border spinner-border-sm text-primary me-2"></div>
      Loading document details...
    </div>
  `;
  modal.show();

  try {
    const res = await fetch(`/api/documents/${docId}`);
    if (!res.ok) throw new Error('Failed to fetch details');
    const doc = await res.json();

    let previewContent = '<div class="text-muted small">No text previews available for this file.</div>';
    if (doc.preview_pages && doc.preview_pages.length > 0) {
      previewContent = doc.preview_pages.map(p => `
        <div class="mb-3 p-3 bg-light rounded border">
          <div class="fw-bold small text-primary mb-1">Page ${p.page_number} Excerpt:</div>
          <div class="small font-monospace" style="white-space: pre-wrap; font-size: 0.8rem;">${escapeHtml(p.text_preview)}</div>
        </div>
      `).join('');
    }

    body.innerHTML = `
      <div class="mb-3">
        <h6 class="fw-bold text-dark">${escapeHtml(doc.filename)}</h6>
        <div class="row g-2 small text-muted my-2">
          <div class="col-6"><strong>Page Count:</strong> ${doc.page_count}</div>
          <div class="col-6"><strong>Indexed Chunks:</strong> ${doc.total_chunks}</div>
          <div class="col-6"><strong>Status:</strong> ${doc.status}</div>
          <div class="col-6"><strong>Scanned PDF:</strong> ${doc.is_scanned ? 'Yes (Needs OCR)' : 'No (Standard Text)'}</div>
        </div>
      </div>
      <h6 class="fw-bold mt-4 mb-2 small text-uppercase text-secondary">Document Text Sample:</h6>
      ${previewContent}
    `;
  } catch (e) {
    body.innerHTML = `<div class="alert alert-danger small">Could not load preview: ${e.message}</div>`;
  }
}

// Load Recent Conversations
async function loadRecentConversations() {
  const list = document.getElementById('recentChatsList');
  if (!list) return;
  const empty = document.getElementById('emptyChatsState');
  const statChatCount = document.getElementById('statChatCount');

  try {
    const res = await fetch('/api/conversations/recent');
    if (!res.ok) return;
    const conversations = await res.json();

    if (conversations.length === 0) {
      list.innerHTML = '';
      empty.classList.remove('d-none');
      if (statChatCount) statChatCount.textContent = '0';
      return;
    }

    empty.classList.add('d-none');
    if (statChatCount) statChatCount.textContent = conversations.length;

    list.innerHTML = conversations.map(c => `
      <a href="/chat/${c.document_id}?conversation_id=${c.conversation_id}" class="list-group-item list-group-item-action py-3 px-3">
        <div class="d-flex w-100 justify-content-between align-items-center mb-1">
          <strong class="text-truncate small text-primary" style="max-width: 200px;">
            <i class="bi bi-file-earmark-text me-1"></i> ${escapeHtml(c.document_name)}
          </strong>
          <span class="badge bg-secondary-subtle text-secondary small">${c.message_count} msgs</span>
        </div>
        <p class="mb-1 small text-dark text-truncate">${escapeHtml(c.last_question)}</p>
        <small class="text-muted" style="font-size: 0.72rem;">${new Date(c.last_activity).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</small>
      </a>
    `).join('');
  } catch (err) {
    console.error('Error loading conversations:', err);
  }
}

// Helper: Show Alert
function showAlert(message, type = 'info') {
  const alertBox = document.getElementById('alertBox');
  alertBox.className = `alert alert-${type} alert-dismissible fade show`;
  alertBox.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
  `;
  alertBox.classList.remove('d-none');

  setTimeout(() => {
    alertBox.classList.add('d-none');
  }, 7000);
}

// Helper: Escape HTML
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

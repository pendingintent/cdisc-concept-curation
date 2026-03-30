/**
 * CDISC BC Curation — main.js
 * Client-side interactivity for the BC curation platform.
 */

(function () {
  'use strict';

  /* ─────────────────────────────────────────────
     Flash message auto-dismiss (5 seconds)
  ───────────────────────────────────────────── */
  function initFlashDismiss() {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(function (el) {
      setTimeout(function () {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
        bsAlert.close();
      }, 5000);
    });
  }

  /* ─────────────────────────────────────────────
     File upload: show filename + drag-drop feedback
  ───────────────────────────────────────────── */
  function initFileUpload() {
    const fileInput = document.getElementById('file-input');
    const fileNameDisplay = document.getElementById('file-name-display');
    const uploadZone = document.getElementById('upload-zone');

    if (fileInput && fileNameDisplay) {
      fileInput.addEventListener('change', function () {
        const file = fileInput.files[0];
        if (file) {
          fileNameDisplay.textContent = file.name;
          fileNameDisplay.classList.remove('d-none');
        }
      });
    }

    if (uploadZone) {
      // Click on zone triggers file input
      uploadZone.addEventListener('click', function (e) {
        if (e.target === uploadZone || e.target.closest('.upload-zone-icon') || e.target.closest('.upload-zone-title')) {
          if (fileInput) fileInput.click();
        }
      });

      uploadZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadZone.classList.add('drag-over');
      });

      uploadZone.addEventListener('dragleave', function () {
        uploadZone.classList.remove('drag-over');
      });

      uploadZone.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadZone.classList.remove('drag-over');
        if (fileInput && e.dataTransfer.files.length > 0) {
          // Transfer files to the real input via DataTransfer
          try {
            const dt = new DataTransfer();
            dt.items.add(e.dataTransfer.files[0]);
            fileInput.files = dt.files;
            if (fileNameDisplay) {
              fileNameDisplay.textContent = e.dataTransfer.files[0].name;
              fileNameDisplay.classList.remove('d-none');
            }
          } catch (_) {
            // DataTransfer assignment not supported in all browsers — silent fallback
          }
        }
      });
    }
  }

  /* ─────────────────────────────────────────────
     NCIt lookup
     On click of #ncit-lookup-btn, fetches
     /ncit/search?term=<value of #ncit_code> and
     renders results into #ncit-results-panel.
  ───────────────────────────────────────────── */
  function initNcitLookup() {
    const lookupBtn = document.getElementById('ncit-lookup-btn');
    const ncitCodeInput = document.getElementById('ncit_code');
    const resultsPanel = document.getElementById('ncit-results-panel');
    const resultsContainer = document.getElementById('ncit-results-container');

    if (!lookupBtn || !ncitCodeInput || !resultsPanel) return;

    lookupBtn.addEventListener('click', async function () {
      const term = ncitCodeInput.value.trim();
      if (!term) {
        ncitCodeInput.focus();
        return;
      }

      lookupBtn.disabled = true;
      lookupBtn.textContent = 'Searching…';

      try {
        const url = new URL('/ncit/search', window.location.origin);
        url.searchParams.set('term', term);

        const response = await fetch(url.toString(), {
          headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) throw new Error('NCIt search failed: ' + response.status);

        const data = await response.json();
        renderNcitResults(data, resultsContainer, ncitCodeInput);
        resultsPanel.classList.remove('d-none');
      } catch (err) {
        if (resultsContainer) {
          resultsContainer.innerHTML = '<p class="text-danger small mb-0">Error fetching NCIt results. Please try again.</p>';
        }
        resultsPanel.classList.remove('d-none');
        console.error('NCIt lookup error:', err);
      } finally {
        lookupBtn.disabled = false;
        lookupBtn.textContent = 'Look up NCIt';
      }
    });
  }

  /**
   * Renders NCIt search results into the container element.
   * Expects data: Array<{ code, preferred_name, definition, synonyms }>
   */
  function renderNcitResults(data, container, ncitCodeInput) {
    if (!container) return;

    if (!data || data.length === 0) {
      container.innerHTML = '<p class="text-secondary small mb-0">No results found.</p>';
      return;
    }

    container.innerHTML = data.map(function (item) {
      const synonymList = Array.isArray(item.synonyms) ? item.synonyms.join('; ') : (item.synonyms || '');
      const safeCode = escapeHtml(item.code || '');
      const safeName = escapeHtml(item.preferred_name || '');
      const safeDef  = escapeHtml(item.definition || '');
      const safeSyn  = escapeHtml(synonymList);

      return `
        <div class="ncit-result-card" data-code="${safeCode}">
          <div class="d-flex align-items-center justify-content-between mb-1">
            <span class="ncit-code">${safeCode}</span>
            <button type="button"
                    class="btn btn-sm btn-outline-primary use-ncit-btn"
                    data-code="${safeCode}"
                    data-name="${safeName}">
              Use this concept
            </button>
          </div>
          <div class="ncit-preferred-name">${safeName}</div>
          <div class="ncit-definition">${safeDef}</div>
          ${safeSyn ? `<div class="small text-secondary"><strong>Synonyms:</strong> ${safeSyn}</div>` : ''}
        </div>
      `;
    }).join('');

    // Wire up "Use this concept" buttons
    container.querySelectorAll('.use-ncit-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        const code = btn.dataset.code;
        if (ncitCodeInput) ncitCodeInput.value = code;
        // Also fill short_name if empty
        const shortNameInput = document.getElementById('short_name');
        if (shortNameInput && !shortNameInput.value.trim()) {
          shortNameInput.value = btn.dataset.name || '';
        }
        // Hide the panel after selection
        const panel = document.getElementById('ncit-results-panel');
        if (panel) panel.classList.add('d-none');
      });
    });
  }

  /* ─────────────────────────────────────────────
     DEC table: add / delete rows dynamically
  ───────────────────────────────────────────── */
  function initDecTable() {
    const addDecBtn = document.getElementById('add-dec-btn');
    const decTableBody = document.getElementById('dec-table-body');

    if (!addDecBtn || !decTableBody) return;

    addDecBtn.addEventListener('click', function () {
      const rowIndex = decTableBody.querySelectorAll('tr').length;
      const row = buildDecRow(rowIndex);
      decTableBody.appendChild(row);
    });

    // Event delegation for delete buttons (covers dynamically added rows)
    decTableBody.addEventListener('click', function (e) {
      const deleteBtn = e.target.closest('.dec-delete-btn');
      if (deleteBtn) {
        const row = deleteBtn.closest('tr');
        if (row) row.remove();
      }
    });
  }

  /**
   * Builds a new DEC table row with editable fields.
   */
  function buildDecRow(index) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>
        <input type="text" class="form-control form-control-sm"
               name="decs[${index}][dec_label]"
               placeholder="DEC label" aria-label="DEC label">
      </td>
      <td>
        <select class="form-select form-select-sm" name="decs[${index}][data_type]" aria-label="Data type">
          <option value="">-- type --</option>
          <option value="string">string</option>
          <option value="decimal">decimal</option>
          <option value="integer">integer</option>
          <option value="boolean">boolean</option>
          <option value="date">date</option>
          <option value="datetime">datetime</option>
        </select>
      </td>
      <td>
        <input type="text" class="form-control form-control-sm"
               name="decs[${index}][example_set]"
               placeholder="Example values" aria-label="Example values">
      </td>
      <td class="text-center">
        <input type="checkbox" class="form-check-input"
               name="decs[${index}][required]" value="1"
               aria-label="Required">
      </td>
      <td>
        <button type="button" class="btn btn-sm btn-outline-danger dec-delete-btn" aria-label="Delete DEC row">
          <i class="bi bi-trash" aria-hidden="true"></i>
        </button>
      </td>
    `;
    return tr;
  }

  /* ─────────────────────────────────────────────
     Kanban: advance / reject via fetch
  ───────────────────────────────────────────── */
  function initKanban() {
    // Advance buttons
    document.querySelectorAll('.kanban-advance-btn').forEach(function (btn) {
      btn.addEventListener('click', async function (e) {
        e.stopPropagation();
        const bcId = btn.dataset.bcId;
        if (!bcId) return;

        btn.disabled = true;
        try {
          const resp = await postJson(`/governance/advance/${encodeURIComponent(bcId)}`);
          if (resp.ok) {
            const card = btn.closest('.kanban-card');
            if (card) card.remove();
            showInlineToast('BC advanced to next stage.');
          } else {
            showInlineToast('Could not advance BC — check the audit trail.', 'error');
          }
        } catch (err) {
          showInlineToast('Network error — please try again.', 'error');
          console.error('Kanban advance error:', err);
        } finally {
          btn.disabled = false;
        }
      });
    });

    // Reject buttons
    document.querySelectorAll('.kanban-reject-btn').forEach(function (btn) {
      btn.addEventListener('click', async function (e) {
        e.stopPropagation();
        const bcId = btn.dataset.bcId;
        if (!bcId) return;

        if (!confirm('Reject this BC? This action will be recorded in the audit trail.')) return;

        btn.disabled = true;
        try {
          const resp = await postJson(`/governance/reject/${encodeURIComponent(bcId)}`);
          if (resp.ok) {
            const card = btn.closest('.kanban-card');
            if (card) card.remove();
            showInlineToast('BC rejected and removed from board.');
          } else {
            showInlineToast('Could not reject BC — check the audit trail.', 'error');
          }
        } catch (err) {
          showInlineToast('Network error — please try again.', 'error');
          console.error('Kanban reject error:', err);
        } finally {
          btn.disabled = false;
        }
      });
    });
  }

  /* ─────────────────────────────────────────────
     Audit trail: toggle before/after JSON panel
  ───────────────────────────────────────────── */
  function initAuditDiff() {
    document.querySelectorAll('.audit-diff-toggle').forEach(function (btn) {
      btn.addEventListener('click', function () {
        const panel = btn.closest('tr').nextElementSibling;
        if (!panel || !panel.classList.contains('audit-diff-row')) return;
        const isHidden = panel.classList.contains('d-none');
        panel.classList.toggle('d-none', !isHidden);
        btn.setAttribute('aria-expanded', isHidden ? 'true' : 'false');
        btn.textContent = isHidden ? 'Hide diff' : 'Show diff';
      });
    });
  }

  /* ─────────────────────────────────────────────
     NCIt search page: standalone search bar
  ───────────────────────────────────────────── */
  function initNcitSearch() {
    const searchInput = document.getElementById('ncit-search-input');
    const searchBtn   = document.getElementById('ncit-search-btn');
    const resultsDiv  = document.getElementById('ncit-search-results');

    if (!searchInput || !searchBtn || !resultsDiv) return;

    async function doSearch() {
      const term = searchInput.value.trim();
      if (!term) return;

      searchBtn.disabled = true;
      searchBtn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Searching…';
      resultsDiv.innerHTML = '';

      try {
        const url = new URL('/ncit/search', window.location.origin);
        url.searchParams.set('term', term);

        const response = await fetch(url.toString(), {
          headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) throw new Error('Search failed: ' + response.status);

        const data = await response.json();
        renderNcitSearchResults(data, resultsDiv);
      } catch (err) {
        resultsDiv.innerHTML = '<div class="info-box info-red">Error performing search. Please try again.</div>';
        console.error('NCIt search error:', err);
      } finally {
        searchBtn.disabled = false;
        searchBtn.innerHTML = '<i class="bi bi-search" aria-hidden="true"></i> Search';
      }
    }

    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') doSearch();
    });
  }

  function renderNcitSearchResults(data, container) {
    if (!data || data.length === 0) {
      container.innerHTML = '<div class="info-box info-amber">No NCIt concepts matched your search.</div>';
      return;
    }

    container.innerHTML = data.map(function (item) {
      const safeCode = escapeHtml(item.code || '');
      const safeName = escapeHtml(item.preferred_name || '');
      const safeDef  = escapeHtml(item.definition || '');
      const synonymList = Array.isArray(item.synonyms) ? item.synonyms : (item.synonyms ? [item.synonyms] : []);
      const safeSyns = synonymList.map(escapeHtml);

      return `
        <div class="ncit-result-card bc-card bc-card-sm mb-3">
          <div class="d-flex align-items-center gap-2 mb-2">
            <span class="ncit-code">${safeCode}</span>
          </div>
          <div class="ncit-preferred-name">${safeName}</div>
          <p class="ncit-definition mt-1 mb-2">${safeDef}</p>
          ${safeSyns.length > 0 ? `
            <div class="mb-2 small text-secondary">
              <strong>Synonyms:</strong>
              <ul class="mb-0 ps-3 mt-1">
                ${safeSyns.map(s => `<li>${s}</li>`).join('')}
              </ul>
            </div>` : ''}
          <button type="button"
                  class="btn btn-sm btn-primary use-ncit-in-search-btn"
                  data-code="${safeCode}"
                  data-name="${safeName}">
            Use this concept
          </button>
        </div>
      `;
    }).join('');

    // "Use this concept" — navigates to a new BC pre-filled with the NCIt code
    container.querySelectorAll('.use-ncit-in-search-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        const code = encodeURIComponent(btn.dataset.code || '');
        window.location.href = `/bc/new?ncit_code=${code}`;
      });
    });
  }

  /* ─────────────────────────────────────────────
     Helpers
  ───────────────────────────────────────────── */

  /**
   * POST with JSON content-type; returns the raw Response.
   * Reads CSRF token from meta tag if present.
   */
  async function postJson(url, body) {
    const headers = { 'Content-Type': 'application/json' };
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfMeta) headers['X-CSRFToken'] = csrfMeta.getAttribute('content');

    return fetch(url, {
      method: 'POST',
      headers: headers,
      body: body ? JSON.stringify(body) : undefined
    });
  }

  /** Escape user-supplied strings before inserting into innerHTML. */
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  /** Show a short-lived Bootstrap toast at the bottom of the viewport. */
  function showInlineToast(message, type) {
    type = type || 'success';
    const colorClass = type === 'error' ? 'text-bg-danger' : 'text-bg-success';

    const container = getOrCreateToastContainer();
    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center ${colorClass} border-0`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');
    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${escapeHtml(message)}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto"
                data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    `;
    container.appendChild(toastEl);

    const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
    toast.show();

    toastEl.addEventListener('hidden.bs.toast', function () {
      toastEl.remove();
    });
  }

  function getOrCreateToastContainer() {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
      container.style.zIndex = '9999';
      document.body.appendChild(container);
    }
    return container;
  }

  /* ─────────────────────────────────────────────
     Clickable table rows with data-href
  ───────────────────────────────────────────── */
  function initClickableRows() {
    document.querySelectorAll('tr[data-href]').forEach(function (row) {
      row.addEventListener('click', function () {
        window.location.href = row.dataset.href;
      });
    });
  }

  /* ─────────────────────────────────────────────
     Init all modules on DOM ready
  ───────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    initFlashDismiss();
    initFileUpload();
    initNcitLookup();
    initDecTable();
    initKanban();
    initAuditDiff();
    initNcitSearch();
    initClickableRows();
  });

})();

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
      lookupBtn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Searching…';

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
        lookupBtn.innerHTML = '<i class="bi bi-search" aria-hidden="true"></i> Look up NCIt';
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
      btn.addEventListener('click', async function () {
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

        // Fetch full concept detail and render the NCIt metadata grid
        const metaDisplay = document.getElementById('ncit-meta-display');
        if (metaDisplay) {
          metaDisplay.innerHTML = '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span> Loading…';
          metaDisplay.classList.remove('d-none');
        }
        try {
          const url = new URL(`/ncit/concept/${encodeURIComponent(code)}`, window.location.origin);
          const response = await fetch(url.toString(), { headers: { 'Accept': 'application/json' } });
          if (response.ok) {
            const data = await response.json();
            renderNcitMetaDisplay(data);
            const metaInput = document.getElementById('ncit_metadata');
            if (metaInput) metaInput.value = JSON.stringify(data);
          } else {
            if (metaDisplay) metaDisplay.innerHTML = '<p class="text-danger small mb-0">Failed to load concept detail.</p>';
          }
        } catch (err) {
          if (metaDisplay) metaDisplay.innerHTML = '<p class="text-danger small mb-0">Error loading concept detail.</p>';
          console.error('NCIt concept detail fetch error:', err);
        }
      });
    });
  }

  /**
   * Populates #ncit-meta-display grid with fields from a selected NCIt concept.
   * Also populates parent_bc_id from the first parent code.
   */
  function renderNcitMetaDisplay(item) {
    var display = document.getElementById('ncit-meta-display');
    if (!display) return;

    var fields = [
      { key: 'preferred_name', label: 'Preferred Name' },
      { key: 'synonyms',       label: 'Synonyms' },
      { key: 'definition',     label: 'Description' },
      { key: 'parents',        label: 'Parent Concepts' },
      { key: 'children',       label: 'Children' },
      { key: 'definitions',    label: 'References' },
      { key: 'semantic_type',  label: 'Semantic Type' },
    ];

    var items = fields.filter(function (f) {
      var v = item[f.key];
      return v && (!Array.isArray(v) || v.length > 0);
    }).map(function (f) {
      var v = item[f.key];
      var text;
      if (f.key === 'definitions') {
        text = v.map(function (d) { return '[' + (d.source || '') + '] ' + (d.definition || ''); }).filter(Boolean).join('; ');
      } else if (f.key === 'parents' || f.key === 'children') {
        text = v.map(function (p) { return p.name + ' (' + p.code + ')'; }).join('; ');
      } else if (Array.isArray(v)) {
        text = v.join('; ');
      } else {
        text = String(v);
      }
      return '<div class="loinc-meta-item">' +
        '<span class="loinc-meta-label">' + escapeHtml(f.label) + '</span>' +
        '<span class="loinc-meta-value">' + escapeHtml(text) + '</span>' +
        '</div>';
    });

    // NCIt browser link
    if (item.reference) {
      items.push('<div class="loinc-meta-item">' +
        '<span class="loinc-meta-label">NCIt Link</span>' +
        '<span class="loinc-meta-value"><a href="' + escapeHtml(item.reference) + '" target="_blank" rel="noopener">View in NCIt Browser</a></span>' +
        '</div>');
    }

    display.innerHTML = items.length
      ? '<div class="loinc-meta-grid mt-2">' + items.join('') + '</div>'
      : '';
    display.classList.toggle('d-none', !items.length);

    // Populate parent_bc_id from first parent code
    var parentInput = document.getElementById('parent_bc_id');
    if (parentInput && !parentInput.value.trim() && Array.isArray(item.parents) && item.parents.length > 0) {
      parentInput.value = item.parents[0].code || '';
    }

    // Populate definition, leaving any existing curator-entered value alone
    var definitionInput = document.getElementById('definition');
    if (definitionInput && !definitionInput.value.trim() && item.definition) {
      definitionInput.value = item.definition;
    }

    // Populate synonyms (semicolon-separated, matching the field's own convention)
    var synonymsInput = document.getElementById('synonyms');
    if (synonymsInput && !synonymsInput.value.trim() && Array.isArray(item.synonyms) && item.synonyms.length > 0) {
      synonymsInput.value = item.synonyms.join('; ');
    }
  }

  /* ─────────────────────────────────────────────
     DEC table: add / delete rows dynamically
  ───────────────────────────────────────────── */
  // The DEC row most recently created via "Add DEC" — the target for the
  // DEC-scoped NCIt card below the table (see initDecNcitLookup).
  let activeDecRow = null;

  function addDecRow(decTableBody) {
    const rowIndex = decTableBody.querySelectorAll('tr').length;
    const row = buildDecRow(rowIndex);
    decTableBody.appendChild(row);
    activeDecRow = row;
    return row;
  }

  function initDecTable() {
    const addDecBtn = document.getElementById('add-dec-btn');
    const decTableBody = document.getElementById('dec-table-body');

    if (!addDecBtn || !decTableBody) return;

    addDecBtn.addEventListener('click', function () {
      addDecRow(decTableBody);
    });

    // Event delegation for delete buttons (covers dynamically added rows)
    decTableBody.addEventListener('click', function (e) {
      const deleteBtn = e.target.closest('.dec-delete-btn');
      if (deleteBtn) {
        const row = deleteBtn.closest('tr');
        if (row) {
          if (row === activeDecRow) activeDecRow = null;
          row.remove();
        }
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
        <input type="hidden" name="decs[${index}][ncit_dec_code]" value="">
        <input type="text" class="form-control form-control-sm"
               name="decs[${index}][dec_id]"
               placeholder="DEC ID" aria-label="DEC ID">
      </td>
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
     DEC-scoped NCIt card: search NCIt and apply the
     selected concept's code/preferred name to the
     DEC row most recently created via "Add DEC".
  ───────────────────────────────────────────── */
  function initDecNcitLookup() {
    const lookupBtn = document.getElementById('dec-ncit-lookup-btn');
    const ncitCodeInput = document.getElementById('dec_ncit_code');
    const resultsPanel = document.getElementById('dec-ncit-results-panel');
    const resultsContainer = document.getElementById('dec-ncit-results-container');

    if (!lookupBtn || !ncitCodeInput || !resultsPanel) return;

    lookupBtn.addEventListener('click', async function () {
      const term = ncitCodeInput.value.trim();
      if (!term) {
        ncitCodeInput.focus();
        return;
      }

      lookupBtn.disabled = true;
      lookupBtn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Searching…';

      try {
        const url = new URL('/ncit/search', window.location.origin);
        url.searchParams.set('term', term);

        const response = await fetch(url.toString(), {
          headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) throw new Error('NCIt search failed: ' + response.status);

        const data = await response.json();
        renderDecNcitResults(data, resultsContainer);
        resultsPanel.classList.remove('d-none');
      } catch (err) {
        if (resultsContainer) {
          resultsContainer.innerHTML = '<p class="text-danger small mb-0">Error fetching NCIt results. Please try again.</p>';
        }
        resultsPanel.classList.remove('d-none');
        console.error('DEC NCIt lookup error:', err);
      } finally {
        lookupBtn.disabled = false;
        lookupBtn.innerHTML = '<i class="bi bi-search" aria-hidden="true"></i> Look up NCIt';
      }
    });
  }

  /**
   * Renders NCIt search results for the DEC card. Selecting a result applies
   * its code/preferred name to the active DEC row (creating one via
   * addDecRow if none is currently tracked).
   * Expects data: Array<{ code, preferred_name, definition, synonyms }>
   */
  function renderDecNcitResults(data, container) {
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
      btn.addEventListener('click', async function () {
        const code = btn.dataset.code;
        const decTableBody = document.getElementById('dec-table-body');

        if (!activeDecRow || !document.body.contains(activeDecRow)) {
          if (decTableBody) addDecRow(decTableBody);
        }
        if (activeDecRow) {
          const decIdInput = activeDecRow.querySelector('[name$="[dec_id]"]');
          const decLabelInput = activeDecRow.querySelector('[name$="[dec_label]"]');
          const ncitDecCodeInput = activeDecRow.querySelector('[name$="[ncit_dec_code]"]');
          if (decIdInput) decIdInput.value = code;
          if (decLabelInput) decLabelInput.value = btn.dataset.name || '';
          if (ncitDecCodeInput) ncitDecCodeInput.value = code;
        }

        // Hide the panel after selection
        const panel = document.getElementById('dec-ncit-results-panel');
        if (panel) panel.classList.add('d-none');

        // Fetch full concept detail and render the NCIt metadata grid
        const metaDisplay = document.getElementById('dec-ncit-meta-display');
        if (metaDisplay) {
          metaDisplay.innerHTML = '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span> Loading…';
          metaDisplay.classList.remove('d-none');
        }
        try {
          const url = new URL(`/ncit/concept/${encodeURIComponent(code)}`, window.location.origin);
          const response = await fetch(url.toString(), { headers: { 'Accept': 'application/json' } });
          if (response.ok) {
            const data = await response.json();
            renderDecNcitMetaDisplay(data);
          } else {
            if (metaDisplay) metaDisplay.innerHTML = '<p class="text-danger small mb-0">Failed to load concept detail.</p>';
          }
        } catch (err) {
          if (metaDisplay) metaDisplay.innerHTML = '<p class="text-danger small mb-0">Error loading concept detail.</p>';
          console.error('DEC NCIt concept detail fetch error:', err);
        }
      });
    });
  }

  /**
   * Populates #dec-ncit-meta-display grid with fields from a selected NCIt concept.
   */
  function renderDecNcitMetaDisplay(item) {
    var display = document.getElementById('dec-ncit-meta-display');
    if (!display) return;

    var fields = [
      { key: 'preferred_name', label: 'Preferred Name' },
      { key: 'synonyms',       label: 'Synonyms' },
      { key: 'definition',     label: 'Description' },
      { key: 'parents',        label: 'Parent Concepts' },
      { key: 'children',       label: 'Children' },
      { key: 'definitions',    label: 'References' },
      { key: 'semantic_type',  label: 'Semantic Type' },
    ];

    var items = fields.filter(function (f) {
      var v = item[f.key];
      return v && (!Array.isArray(v) || v.length > 0);
    }).map(function (f) {
      var v = item[f.key];
      var text;
      if (f.key === 'definitions') {
        text = v.map(function (d) { return '[' + (d.source || '') + '] ' + (d.definition || ''); }).filter(Boolean).join('; ');
      } else if (f.key === 'parents' || f.key === 'children') {
        text = v.map(function (p) { return p.name + ' (' + p.code + ')'; }).join('; ');
      } else if (Array.isArray(v)) {
        text = v.join('; ');
      } else {
        text = String(v);
      }
      return '<div class="loinc-meta-item">' +
        '<span class="loinc-meta-label">' + escapeHtml(f.label) + '</span>' +
        '<span class="loinc-meta-value">' + escapeHtml(text) + '</span>' +
        '</div>';
    });

    // NCIt browser link
    if (item.reference) {
      items.push('<div class="loinc-meta-item">' +
        '<span class="loinc-meta-label">NCIt Link</span>' +
        '<span class="loinc-meta-value"><a href="' + escapeHtml(item.reference) + '" target="_blank" rel="noopener">View in NCIt Browser</a></span>' +
        '</div>');
    }

    display.innerHTML = items.length
      ? '<div class="loinc-meta-grid mt-2">' + items.join('') + '</div>'
      : '';
    display.classList.toggle('d-none', !items.length);
  }

  /* ─────────────────────────────────────────────
     Governance board: keep the active BC/Specialization
     tab in the URL hash so a post-action reload (and
     any future revisit of the link) restores it instead
     of always landing back on the first tab.
  ───────────────────────────────────────────── */
  function initGovernanceTabs() {
    const tabButtons = document.querySelectorAll('#governanceTabs button[data-bs-toggle="tab"]');
    if (!tabButtons.length) return;

    const hashTarget = location.hash && document.querySelector(`#governanceTabs button[data-bs-target="${location.hash}"]`);
    if (hashTarget && window.bootstrap) {
      new bootstrap.Tab(hashTarget).show();
    }

    tabButtons.forEach(function (btn) {
      btn.addEventListener('shown.bs.tab', function (e) {
        history.replaceState(null, '', e.target.getAttribute('data-bs-target'));
      });
    });
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
        const vlmGroupId = btn.dataset.vlmGroupId;
        if (!bcId && !vlmGroupId) return;
        const url = vlmGroupId
          ? `/governance/spec/advance/${encodeURIComponent(vlmGroupId)}`
          : `/governance/advance/${encodeURIComponent(bcId)}`;

        btn.disabled = true;
        try {
          const resp = await postJson(url);
          if (resp.ok) {
            location.reload();
          } else {
            showInlineToast('Could not advance — check the audit trail.', 'error');
            btn.disabled = false;
          }
        } catch (err) {
          showInlineToast('Network error — please try again.', 'error');
          console.error('Kanban advance error:', err);
          btn.disabled = false;
        }
      });
    });

    // Reject buttons
    document.querySelectorAll('.kanban-reject-btn').forEach(function (btn) {
      btn.addEventListener('click', async function (e) {
        e.stopPropagation();
        const bcId = btn.dataset.bcId;
        const vlmGroupId = btn.dataset.vlmGroupId;
        if (!bcId && !vlmGroupId) return;
        const url = vlmGroupId
          ? `/governance/spec/reject/${encodeURIComponent(vlmGroupId)}`
          : `/governance/reject/${encodeURIComponent(bcId)}`;

        if (!confirm('Reject this item? This action will be recorded in the audit trail.')) return;

        btn.disabled = true;
        try {
          const resp = await postJson(url);
          if (resp.ok) {
            location.reload();
          } else {
            showInlineToast('Could not reject — check the audit trail.', 'error');
            btn.disabled = false;
          }
        } catch (err) {
          showInlineToast('Network error — please try again.', 'error');
          console.error('Kanban reject error:', err);
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
                  data-name="${safeName}"
                  data-definition="${safeDef}">
            Use this concept
          </button>
        </div>
      `;
    }).join('');

    // "Use this concept" — fetches full concept detail, stores in sessionStorage, then navigates
    container.querySelectorAll('.use-ncit-in-search-btn').forEach(function (btn) {
      btn.addEventListener('click', async function () {
        const code = btn.dataset.code || '';
        const name = btn.dataset.name || '';
        const def  = btn.dataset.definition || '';

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Loading…';

        try {
          const url = new URL(`/ncit/concept/${encodeURIComponent(code)}`, window.location.origin);
          const response = await fetch(url.toString(), { headers: { 'Accept': 'application/json' } });
          if (response.ok) {
            const data = await response.json();
            sessionStorage.setItem('pendingNcitConcept', JSON.stringify(data));
          }
        } catch (err) {
          console.error('NCIt concept prefetch error:', err);
        }

        window.location.href = `/bc/new?ncit_code=${encodeURIComponent(code)}&ncit_name=${encodeURIComponent(name)}&ncit_definition=${encodeURIComponent(def)}`;
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
     LOINC lookup
     On click of #loinc-lookup-btn, fetches
     /loinc/search?term=<value of #loinc_code> and
     renders results into #loinc-results-panel.
  ───────────────────────────────────────────── */
  function initLoincLookup() {
    const lookupBtn = document.getElementById('loinc-lookup-btn');
    const codeInput = document.getElementById('loinc_code');
    const nameInput = document.getElementById('loinc_name');
    const resultsPanel = document.getElementById('loinc-results-panel');
    const resultsContainer = document.getElementById('loinc-results-container');

    if (!lookupBtn || !codeInput || !resultsPanel) return;

    async function doLoincSearch(term) {
      if (!term) return;
      lookupBtn.disabled = true;
      lookupBtn.textContent = 'Searching…';
      try {
        const url = new URL('/loinc/search', window.location.origin);
        url.searchParams.set('term', term);
        const response = await fetch(url.toString(), { headers: { 'Accept': 'application/json' } });
        if (!response.ok) throw new Error('LOINC search failed: ' + response.status);
        const data = await response.json();
        renderLoincResults(data, resultsContainer);
        resultsPanel.classList.remove('d-none');
      } catch (err) {
        if (resultsContainer) {
          resultsContainer.innerHTML = '<p class="text-danger small mb-0">Error fetching LOINC results. Please try again.</p>';
        }
        resultsPanel.classList.remove('d-none');
        console.error('LOINC lookup error:', err);
      } finally {
        lookupBtn.disabled = false;
        lookupBtn.textContent = 'Search LOINC';
      }
    }

    // Button searches using whichever field has a value (code takes priority)
    lookupBtn.addEventListener('click', function () {
      var term = codeInput.value.trim() || (nameInput && nameInput.value.trim());
      if (!term) { codeInput.focus(); return; }
      doLoincSearch(term);
    });

    // Enter key on code field triggers search
    codeInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); doLoincSearch(codeInput.value.trim()); }
    });

    // Debounced autocomplete on the Long Common Name field
    if (nameInput) {
      var nameDebounceTimer;
      nameInput.addEventListener('input', function () {
        clearTimeout(nameDebounceTimer);
        var term = nameInput.value.trim();
        if (!term) { resultsPanel.classList.add('d-none'); return; }
        nameDebounceTimer = setTimeout(function () { doLoincSearch(term); }, 400);
      });
      nameInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          clearTimeout(nameDebounceTimer);
          doLoincSearch(nameInput.value.trim());
        }
      });
    }
  }

  // LOINC field labels for display in results and saved metadata grid.
  var LOINC_FIELD_LABELS = {
    LOINC_NUM:                 'LOINC Code',
    SHORTNAME:                 'Short Name',
    LONG_COMMON_NAME:          'Long Common Name',
    COMPONENT:                 'Component',
    PROPERTY:                  'Property',
    METHOD_TYP:                'Method Type',
    units:                     'Units',
    datatype:                  'Data Type',
    CONSUMER_NAME:             'Consumer Name',
    RELATEDNAMES2:             'Related Names',
    AnswerLists:               'Answer Lists',
    isCopyrighted:             'Is Copyrighted',
    containsCopyrighted:       'Contains Copyrighted',
    EXTERNAL_COPYRIGHT_NOTICE: 'Copyright Notice',
    EXTERNAL_COPYRIGHT_LINK:   'Copyright Link',
  };

  /**
   * Renders LOINC search results into the container element.
   * Expects data: Array of objects with LOINC ef fields
   * (LOINC_NUM, SHORTNAME, LONG_COMMON_NAME, PROPERTY, …)
   */
  function renderLoincResults(data, container) {
    if (!container) return;

    if (!data || data.length === 0) {
      container.innerHTML = '<p class="text-secondary small mb-0">No results found.</p>';
      return;
    }

    if (data[0] && data[0].error) {
      container.innerHTML = `<p class="text-danger small mb-0">Error: ${escapeHtml(data[0].error)}</p>`;
      return;
    }

    container.innerHTML = data.map(function (item, idx) {
      const safeCode = escapeHtml(item.LOINC_NUM || '');
      const safeName = escapeHtml(item.LONG_COMMON_NAME || '');

      // Build metadata rows for all non-empty fields except LOINC_NUM
      // (shown in the header row; LONG_COMMON_NAME is included in the grid)
      var metaRows = Object.keys(LOINC_FIELD_LABELS)
        .filter(function (k) { return k !== 'LOINC_NUM' && item[k]; })
        .map(function (k) {
          return `<div class="loinc-meta-item">
            <span class="loinc-meta-label">${escapeHtml(LOINC_FIELD_LABELS[k])}</span>
            <span class="loinc-meta-value">${escapeHtml(String(item[k]))}</span>
          </div>`;
        }).join('');

      return `
        <div class="ncit-result-card" data-idx="${idx}">
          <div class="d-flex align-items-center justify-content-between mb-1">
            <span class="ncit-code">${safeCode}</span>
            <button type="button"
                    class="btn btn-sm btn-outline-primary use-loinc-btn"
                    data-idx="${idx}">
              Use this code
            </button>
          </div>
          <div class="ncit-preferred-name">${safeName}</div>
          ${metaRows ? `<div class="loinc-meta-grid mt-2">${metaRows}</div>` : ''}
        </div>
      `;
    }).join('');

    // Store the raw result objects on the container so the "use" handler can access them
    container._loincResults = data;

    // Wire up "Use this code" buttons
    container.querySelectorAll('.use-loinc-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var idx = parseInt(btn.dataset.idx, 10);
        var item = container._loincResults && container._loincResults[idx];
        if (!item) return;

        var codeInput = document.getElementById('loinc_code');
        var nameInput = document.getElementById('loinc_name');
        var metaInput = document.getElementById('loinc_metadata');

        if (codeInput) codeInput.value = item.LOINC_NUM || '';
        if (nameInput) nameInput.value = item.LONG_COMMON_NAME || '';
        if (metaInput) metaInput.value = JSON.stringify(item);

        renderLoincMetaDisplay(item);

        var panel = document.getElementById('loinc-results-panel');
        if (panel) panel.classList.add('d-none');
      });
    });
  }

  /**
   * Populates the #loinc-meta-display grid with fields from a selected LOINC item.
   * Called immediately after the user clicks "Use this code" so they see the
   * properties without needing to save and reload the page.
   */
  function renderLoincMetaDisplay(item) {
    var display = document.getElementById('loinc-meta-display');
    if (!display) return;

    var displayFields = [
      'LONG_COMMON_NAME', 'SHORTNAME', 'COMPONENT', 'PROPERTY', 'METHOD_TYP', 'units', 'datatype',
      'CONSUMER_NAME', 'RELATEDNAMES2', 'AnswerLists', 'isCopyrighted',
      'containsCopyrighted', 'EXTERNAL_COPYRIGHT_NOTICE', 'EXTERNAL_COPYRIGHT_LINK',
    ];

    var html = displayFields
      .filter(function (k) { return item[k]; })
      .map(function (k) {
        return `<div class="loinc-meta-item">
          <span class="loinc-meta-label">${escapeHtml(LOINC_FIELD_LABELS[k] || k)}</span>
          <span class="loinc-meta-value">${escapeHtml(String(item[k]))}</span>
        </div>`;
      }).join('');

    display.innerHTML = html;
    display.classList.toggle('d-none', !html);
  }

  /* ─────────────────────────────────────────────
     Pending NCIt concept: auto-populate on new BC
     page when navigated from the NCIt search page.
  ───────────────────────────────────────────── */
  function initPendingNcitConcept() {
    var raw = sessionStorage.getItem('pendingNcitConcept');
    if (!raw) return;

    var ncitCodeInput = document.getElementById('ncit_code');
    var metaDisplay = document.getElementById('ncit-meta-display');
    // Only consume on a page that has the NCIt metadata display (i.e. bc_detail)
    if (!metaDisplay || !ncitCodeInput) return;

    sessionStorage.removeItem('pendingNcitConcept');

    var data;
    try { data = JSON.parse(raw); } catch (e) { return; }

    renderNcitMetaDisplay(data);

    var metaInput = document.getElementById('ncit_metadata');
    if (metaInput) metaInput.value = JSON.stringify(data);
  }

  /* ─────────────────────────────────────────────
     Init all modules on DOM ready
  ───────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    initFlashDismiss();
    initFileUpload();
    initPendingNcitConcept();
    initNcitLookup();
    initLoincLookup();
    initDecTable();
    initDecNcitLookup();
    initGovernanceTabs();
    initKanban();
    initAuditDiff();
    initNcitSearch();
    initClickableRows();
  });

})();

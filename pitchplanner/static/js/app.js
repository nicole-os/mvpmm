'use strict';

// pitchplanner — AI-powered media pitch generator

class PRPitchyApp {
    constructor() {
        this.newsFiles = [];
        this.brandFiles = [];
        this.selectedTier = 2;
        this.results = null;
        this.pitchIndex = {};  // keyed by DOM id → {subject_line, body}

        // ── Two-step state ──────────────────────────────────────────
        this.sessionId = null;
        this.selectedWave1 = null;       // single pub name string or null
        this.selectedWave2 = new Set();  // set of pub name strings
        this.selectedWave3 = new Set();  // set of pub name strings
        this._inSelectionMode = false;   // true while showing target selection UI

        this._currentStep = 1;  // 1=input, 2=design, 3=deploy
        this._newsHeadline = '';
        this._analyzeData = null;       // preserved across step transitions
        this._campaignData = null;      // preserved across step transitions
        this._selectionsInitialized = false;

        this.initUploadZones();
        this.initTierButtons();
        this.loadPublications();
    }

    // ── Bottom navigator ───────────────────────────────────────────────
    _setNavStep(step) {
        this._currentStep = step;
        [1, 2, 3].forEach(n => {
            const el = document.getElementById(`bnav-step-${n}`);
            if (!el) return;
            el.classList.remove('active', 'done', 'available');
            if (n === step) el.classList.add('active');
            else if (n < step) el.classList.add('done');
            else if (n === 2 && this._analyzeData) el.classList.add('available');
            else if (n === 3 && this._campaignData) el.classList.add('available');
        });
    }

    _setNavAction(label, enabled = true) {
        const btn = document.getElementById('bnav-action-btn');
        if (btn) {
            btn.innerHTML = label;
            btn.disabled = !enabled;
        }
    }

    navAction() {
        if (this._currentStep === 1) {
            this.analyze();
        } else if (this._currentStep === 2) {
            this.buildCampaign();
        } else if (this._currentStep === 3) {
            this.navTo(2); // "← Edit Selections" goes back to plan
        }
    }

    navTo(step) {
        if (step === this._currentStep) return;
        if (step > this._currentStep) {
            // Forward — only if data already exists for that step
            if (step === 2 && this._analyzeData) this._showStep2();
            else if (step === 3 && this._campaignData) this._showStep3();
            return;
        }
        // Backward
        if (step === 1) {
            document.querySelector('.input-panel').classList.remove('collapsed');
            document.getElementById('phase-header').style.display = 'none';
            document.getElementById('results-section').style.display = 'none';
            document.getElementById('results-section').classList.remove('active');
            document.querySelectorAll('.tab-btn').forEach(b => b.style.display = '');
            this._setNavStep(1);
            this._setNavAction('Analyze &amp; Find Targets →');
            const expBtn1 = document.getElementById('bnav-export-btn');
            if (expBtn1) expBtn1.style.display = 'none';
            document.querySelector('.input-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else if (step === 2) {
            this._showStep2();
        }
    }

    _showStep2() {
        if (!this._analyzeData) return;
        this._inSelectionMode = true;
        document.querySelector('.input-panel').classList.add('collapsed');
        const phaseHeader = document.getElementById('phase-header');
        phaseHeader.style.display = 'flex';
        const section = document.getElementById('results-section');
        section.classList.add('active');
        section.style.display = 'block';
        document.getElementById('phase-title').textContent = this._newsHeadline
            ? `Campaign Design — ${this._newsHeadline}` : 'Campaign Design';
        document.querySelectorAll('.tab-btn').forEach(b => b.style.display = '');
        const targetsTabBtn2 = document.querySelector('[onclick="app.switchTab(\'targets\')"]');
        if (targetsTabBtn2) targetsTabBtn2.textContent = 'Campaign Design';
        this.renderTargetSelection({ targets: this._analyzeData.targets || [], campaign_suggestion: this._analyzeData.campaign_suggestion || {} });
        this.switchTab('targets');
        this._setNavStep(2);
        this._setNavAction('Build Campaign →', this.selectedWave2.size > 0);
        const expBtn2 = document.getElementById('bnav-export-btn');
        if (expBtn2) expBtn2.style.display = 'none';
        phaseHeader.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    _showStep3() {
        if (!this._campaignData) return;
        const data = this._campaignData;
        this._inSelectionMode = false;
        document.querySelector('.input-panel').classList.add('collapsed');
        const phaseHeader = document.getElementById('phase-header');
        phaseHeader.style.display = 'flex';
        const section = document.getElementById('results-section');
        section.classList.add('active');
        section.style.display = 'block';
        document.getElementById('phase-title').textContent = this._newsHeadline
            ? `Campaign Deployment — ${this._newsHeadline}` : 'Campaign Deployment';
        this.renderStatsBar(data);
        this.renderCampaign(data.waves, data.campaign_plan, data.press_release);
        document.getElementById('waves-tab-header').textContent = 'Campaign Waves';
        document.getElementById('waves-tab-sub').textContent = 'Three-wave campaign plan with personalized pitches. Expand any target to see the draft pitch.';
        const targetsTabBtn3 = document.querySelector('[onclick="app.switchTab(\'targets\')"]');
        if (targetsTabBtn3) targetsTabBtn3.textContent = 'Campaign Waves';
        const assessmentTab = document.querySelector('.tab-btn[onclick*="assessment"]');
        if (assessmentTab) assessmentTab.style.display = 'none';
        this._setNavStep(3);
        this._setNavAction('← Edit Selections', true);
        const expBtn3 = document.getElementById('bnav-export-btn');
        if (expBtn3) expBtn3.style.display = 'inline-flex';
        this.switchTab('targets');
        phaseHeader.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // ── File upload zones ──────────────────────────────────────────────
    initUploadZones() {
        this.initZone('news-zone', 'news-files', this.newsFiles, 'news-file-list');
        this.initZone('brand-zone', 'brand-files', this.brandFiles, 'brand-file-list');
    }

    initZone(zoneId, inputId, fileArray, listId) {
        const zone = document.getElementById(zoneId);
        const input = document.getElementById(inputId);

        zone.addEventListener('click', () => input.click());
        input.addEventListener('change', () => {
            Array.from(input.files).forEach(f => {
                if (!fileArray.find(x => x.name === f.name)) fileArray.push(f);
            });
            this.renderFileList(fileArray, listId, zoneId, inputId);
            input.value = '';
        });

        zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
        zone.addEventListener('drop', e => {
            e.preventDefault();
            zone.classList.remove('drag-over');
            Array.from(e.dataTransfer.files).forEach(f => {
                if (!fileArray.find(x => x.name === f.name)) fileArray.push(f);
            });
            this.renderFileList(fileArray, listId, zoneId, inputId);
        });
    }

    renderFileList(fileArray, listId, zoneId, inputId) {
        const list = document.getElementById(listId);
        list.innerHTML = fileArray.map((f, i) => `
            <div class="file-chip">
                <span>${f.name} <span style="color:#aaa; font-size:0.7rem;">(${this.formatBytes(f.size)})</span></span>
                <button onclick="app.removeFile('${zoneId}', '${inputId}', ${i}, '${listId}')" title="Remove">✕</button>
            </div>
        `).join('');
    }

    removeFile(zoneId, inputId, index, listId) {
        const arr = zoneId === 'news-zone' ? this.newsFiles : this.brandFiles;
        arr.splice(index, 1);
        this.renderFileList(arr, listId, zoneId, inputId);
    }

    formatBytes(bytes) {
        if (bytes < 1024) return bytes + 'B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(0) + 'KB';
        return (bytes / 1048576).toFixed(1) + 'MB';
    }

    // ── Tier selector ──────────────────────────────────────────────────
    initTierButtons() {
        document.querySelectorAll('.tier-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tier-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.selectedTier = parseInt(btn.dataset.tier);
            });
        });
    }

    // ── Tab switching ──────────────────────────────────────────────────
    switchTab(name) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        document.querySelector(`[onclick="app.switchTab('${name}')"]`).classList.add('active');
        document.getElementById(`tab-${name}`).classList.add('active');
    }

    setStatus(msg) {
        document.getElementById('status-msg').textContent = msg;
    }

    // ══════════════════════════════════════════════════════════════════
    // STEP 1 — Analyze & find targets
    // ══════════════════════════════════════════════════════════════════

    async analyze() {
        const extraContext = document.getElementById('extra-context').value.trim();

        if (this.newsFiles.length === 0 && !extraContext) {
            this.setStatus('Please upload at least one news document or add context in the text box.');
            return;
        }

        this._setNavAction('<span class="spinner"></span> Analyzing…', false);
        this.setStatus('');

        // Reset step-2 state
        this.sessionId = null;
        this.selectedWave1 = null;
        this.selectedWave2 = new Set();
        this.selectedWave3 = new Set();
        this._inSelectionMode = false;
        this._selectionsInitialized = false;

        try {
            const formData = new FormData();
            this.newsFiles.forEach(f => formData.append('news_docs', f));
            this.brandFiles.forEach(f => formData.append('brand_docs', f));
            formData.append('extra_context', extraContext);
            formData.append('tier_filter', this.selectedTier);
            const launchDateEl = document.getElementById('launch-date');
            if (launchDateEl && launchDateEl.value) {
                formData.append('launch_date', launchDateEl.value);
            }
            const cityEl = document.getElementById('company-city');
            if (cityEl && cityEl.value) formData.append('company_city', cityEl.value);
            const contactNameEl = document.getElementById('media-contact-name');
            if (contactNameEl && contactNameEl.value) formData.append('media_contact_name', contactNameEl.value);
            const contactEmailEl = document.getElementById('media-contact-email');
            if (contactEmailEl && contactEmailEl.value) formData.append('media_contact_email', contactEmailEl.value);

            const response = await fetch('/api/analyze', { method: 'POST', body: formData });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.message || response.statusText);
            }
            const data = await response.json();
            if (data.status === 'error') throw new Error(data.message);

            this.sessionId = data.session_id;
            this._inSelectionMode = true;
            this._newsHeadline = data.news_analysis?.headline || '';

            // Collapse input panel
            document.querySelector('.input-panel').classList.add('collapsed');

            // Show phase header
            const phaseHeader = document.getElementById('phase-header');
            phaseHeader.style.display = 'flex';
            document.getElementById('phase-title').textContent = this._newsHeadline
                ? `Campaign Design — ${this._newsHeadline}`
                : 'Campaign Design';

            // Show results section, restore all tabs
            const section = document.getElementById('results-section');
            section.classList.add('active');
            section.style.display = 'block';
            document.querySelectorAll('.tab-btn').forEach(b => b.style.display = '');
            const targetsTabBtnA = document.querySelector('[onclick="app.switchTab(\'targets\')"]');
            if (targetsTabBtnA) targetsTabBtnA.textContent = 'Campaign Design';

            this.renderStatsBar(data);
            this.renderAssessment(data.news_analysis);
            this.renderTargetSelection(data);

            // Store for step transitions — never cleared until next analyze
            this._analyzeData = { targets: data.targets, campaign_suggestion: data.campaign_suggestion };
            this.results = { ...(this.results || {}), targets: data.targets, campaign_suggestion: data.campaign_suggestion };

            this._setNavStep(2);
            this._setNavAction('Build Campaign →', false);

            this.switchTab('assessment');
            phaseHeader.scrollIntoView({ behavior: 'smooth', block: 'start' });
            this.setStatus('');

        } catch (e) {
            this.setStatus(`Error: ${e.message}`);
            this._setNavAction('Analyze &amp; Find Targets →');
        }
    }

    // ══════════════════════════════════════════════════════════════════
    // STEP 1 UI — Target selection
    // ══════════════════════════════════════════════════════════════════

    renderTargetSelection(data) {
        const container = document.getElementById('targets-list');
        const header = document.getElementById('waves-tab-header');
        const sub = document.getElementById('waves-tab-sub');
        const bar = null; // build bar removed

        header.textContent = 'Select Your Targets';
        sub.textContent = 'Review the ranked targets below. Select Wave 1 (exclusive), Wave 2 (launch day), and Wave 3 (follow-on) — then click "Build Campaign" to scrape their articles and draft personalized pitches.';
        // bar removed

        const targets = data.targets || [];
        const suggestion = data.campaign_suggestion || {};

        // Pre-select from LLM suggestions — only on first render, not on back-navigation
        const wave1Sug = suggestion.wave_1_suggestion || null;
        const wave2Sug = new Set(suggestion.wave_2_suggestions || []);
        const wave3Sug = new Set(suggestion.wave_3_suggestions || []);

        if (!this._selectionsInitialized) {
            if (wave1Sug) this.selectedWave1 = wave1Sug;
            wave2Sug.forEach(p => this.selectedWave2.add(p));
            wave3Sug.forEach(p => this.selectedWave3.add(p));
            this._selectionsInitialized = true;
        }

        // Build suggestion rationale banner
        let html = '';
        if (suggestion.suggestion_rationale) {
            html += `<div class="suggestion-rationale-box">
                <div class="suggestion-rationale-label">AI Campaign Suggestion</div>
                ${this._esc(suggestion.suggestion_rationale)}
            </div>`;
        }

        // Filter targets to show: score >= 5, or anything suggested
        const allSuggested = new Set([wave1Sug, ...wave2Sug, ...wave3Sug].filter(Boolean));
        const displayTargets = targets.filter(t =>
            (t.fit_score || 0) >= 5 || allSuggested.has(t.publication)
        );

        // ── Wave 1 section ──────────────────────────────────────────
        html += `<div class="target-selection-section" id="wave-section-wave1">
            <div class="selection-wave-header" onclick="app.toggleWaveSection('wave-section-wave1')">
                <button class="wave-collapse-btn" onclick="event.stopPropagation(); app.toggleWaveSection('wave-section-wave1')">−</button>
                <span class="wave-badge wave-badge-1">Wave 1</span>
                <span class="wave-title" style="font-size:0.92rem;">Exclusive / Embargo</span>
                <span class="selection-wave-instruction">Pick one outlet — or leave empty if no exclusive</span>
            </div>
            <div class="wave-section-body">
            <div class="target-select-grid" id="select-grid-wave1">`;

        // Wave 1: show top-scoring exclusive-viable targets
        const wave1Candidates = displayTargets.filter(t =>
            t.wave_suitability?.good_for_exclusive ||
            t.publication === wave1Sug ||
            (t.fit_score || 0) >= 8
        ).slice(0, 6);

        if (wave1Candidates.length === 0) {
            html += `<div class="no-wave1-notice">No outlets scored highly enough for an exclusive pitch. Proceed to Wave 2.</div>`;
        } else {
            wave1Candidates.forEach(t => {
                html += this._renderSelectCard(t, 'wave1', wave1Sug);
            });
        }
        html += `</div></div></div>`;

        // ── Wave 2 section ──────────────────────────────────────────
        html += `<div class="target-selection-section" id="wave-section-wave2">
            <div class="selection-wave-header" onclick="app.toggleWaveSection('wave-section-wave2')">
                <button class="wave-collapse-btn" onclick="event.stopPropagation(); app.toggleWaveSection('wave-section-wave2')">−</button>
                <span class="wave-badge wave-badge-2">Wave 2</span>
                <span class="wave-title" style="font-size:0.92rem;">Launch Day</span>
                <span class="selection-wave-instruction">Pick 3–5 outlets — pitched simultaneously on launch day</span>
            </div>
            <div class="wave-section-body">
            <div class="target-select-grid" id="select-grid-wave2">`;

        displayTargets.forEach(t => {
            html += this._renderSelectCard(t, 'wave2', null, wave2Sug.has(t.publication));
        });
        html += `</div></div></div>`;

        // ── Wave 3 section ──────────────────────────────────────────
        html += `<div class="target-selection-section" id="wave-section-wave3">
            <div class="selection-wave-header" onclick="app.toggleWaveSection('wave-section-wave3')">
                <button class="wave-collapse-btn" onclick="event.stopPropagation(); app.toggleWaveSection('wave-section-wave3')">−</button>
                <span class="wave-badge wave-badge-3">Wave 3</span>
                <span class="wave-title" style="font-size:0.92rem;">Follow-on</span>
                <span class="selection-wave-instruction">Pick 2–5 outlets — 1-2 weeks after launch, using Wave 2 coverage as proof</span>
            </div>
            <div class="wave-section-body">
            <div class="target-select-grid" id="select-grid-wave3">`;

        displayTargets.forEach(t => {
            html += this._renderSelectCard(t, 'wave3', null, wave3Sug.has(t.publication));
        });
        html += `</div></div></div>`;

        container.innerHTML = html;
        this._updateBuildBar();
    }

    _renderSelectCard(target, wave, wave1SugName, isPreSelected = false) {
        const pub = target.publication || '';
        const score = target.fit_score || 0;
        const scoreClass = score >= 7 ? 'score-high' : score >= 5 ? 'score-mid' : 'score-low';
        const authors = (target.known_authors || []).slice(0, 3);
        const headlines = (target.recent_headlines || []).slice(0, 3);
        const hook = target.audience_hook || '';

        // Determine initial selected state
        let isSelected = false;
        if (wave === 'wave1') isSelected = (this.selectedWave1 === pub);
        else if (wave === 'wave2') isSelected = this.selectedWave2.has(pub);
        else if (wave === 'wave3') isSelected = this.selectedWave3.has(pub);

        const isRadio = wave === 'wave1';
        const selectedClass = isSelected ? 'selected' : '';
        const radioClass = isRadio ? 'radio-style' : '';

        const tierNum = target.tier || 2;
        return `
        <div class="target-select-card ${selectedClass} ${radioClass}"
             id="selcard-${wave}-${this._slugify(pub)}"
             data-pub="${this._esc(pub)}"
             data-wave="${wave}">
            <div class="select-indicator" onclick="app.toggleSelection('${wave}', '${this._esc(pub)}')"></div>
            <div class="select-card-top" onclick="app.toggleSelection('${wave}', '${this._esc(pub)}')">
                <div class="select-card-score ${scoreClass}">${score}</div>
                <div class="select-card-name">
                    ${this._esc(pub)}
                    ${isPreSelected ? '<span class="pre-selected-badge">Suggested</span>' : ''}
                </div>
            </div>
            <div class="select-card-tier tier-${tierNum}">Tier ${tierNum}</div>
            <div style="font-size:0.74rem; color:var(--grey-medium); margin-bottom:8px;">${this._esc(target.beat || '')} · ${this._esc(target.audience || '')}</div>
            ${hook ? `<div class="audience-hook-box">
                <div class="audience-hook-label">Audience hook</div>
                ${this._esc(hook)}
            </div>` : ''}
            ${authors.length ? `<div class="select-card-authors">
                <strong>Known contributors:</strong> ${authors.map(a => this._esc(a)).join(', ')}
            </div>` : ''}
            ${headlines.length ? `<div class="select-card-headlines">
                <strong>Recent article titles:</strong>
                <ul>${headlines.map(h => {
                    const title = typeof h === 'object' ? h.title : h;
                    const url = typeof h === 'object' ? h.url : '';
                    return url
                        ? `<li><a href="${url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${this._esc(title)}</a></li>`
                        : `<li>${this._esc(title)}</li>`;
                }).join('')}</ul>
            </div>` : ''}
        </div>`;
    }

    toggleWaveSection(id) {
        const section = document.getElementById(id);
        if (!section) return;
        const isCollapsed = section.classList.toggle('collapsed');
        const btn = section.querySelector('.wave-collapse-btn');
        if (btn) btn.textContent = isCollapsed ? '+' : '−';
    }

    toggleSelection(wave, pubName) {
        // Wave exclusivity rules:
        // • Wave 1 locks the pub from W2 + W3 entirely (exclusive = no simultaneous pitching)
        // • W2 ↔ W3 auto-move: selecting in one auto-removes from the other (prevent confusion)
        // • Locked cards (Wave 1 pub in W2/W3) are unclickable via pointer-events:none — but guard here too

        if (wave === 'wave1') {
            if (this.selectedWave1 === pubName) {
                // Deselect Wave 1
                this.selectedWave1 = null;
            } else {
                // Select Wave 1 — auto-remove from W2 and W3
                const prevW1 = this.selectedWave1;
                this.selectedWave1 = pubName;
                this.selectedWave2.delete(pubName);
                this.selectedWave3.delete(pubName);
                // If we replaced a previous W1 pub, remove the lock that was on it
                // (handled by _refreshCardVisuals restoring W2/W3 cards)
            }
        } else if (wave === 'wave2') {
            // Cannot select if it's the Wave 1 exclusive pub
            if (this.selectedWave1 === pubName) return;

            if (this.selectedWave2.has(pubName)) {
                this.selectedWave2.delete(pubName);
            } else {
                // Auto-remove from Wave 3 if it was there (one-wave-at-a-time for W2/W3)
                const wasInW3 = this.selectedWave3.has(pubName);
                this.selectedWave3.delete(pubName);
                this.selectedWave2.add(pubName);
                if (wasInW3) this._showMoveNotice(pubName, 'Wave 3', 'Wave 2');
            }
        } else if (wave === 'wave3') {
            // Cannot select if it's the Wave 1 exclusive pub
            if (this.selectedWave1 === pubName) return;

            if (this.selectedWave3.has(pubName)) {
                this.selectedWave3.delete(pubName);
            } else {
                // Auto-remove from Wave 2 if it was there
                const wasInW2 = this.selectedWave2.has(pubName);
                this.selectedWave2.delete(pubName);
                this.selectedWave3.add(pubName);
                if (wasInW2) this._showMoveNotice(pubName, 'Wave 2', 'Wave 3');
            }
        }
        this._refreshCardVisuals();
        this._updateBuildBar();
    }

    _showMoveNotice(pubName, fromWave, toWave) {
        // Brief flash on the destination card
        const toWaveSlug = toWave === 'Wave 2' ? 'wave2' : 'wave3';
        const slug = this._slugify(pubName);
        const card = document.getElementById(`selcard-${toWaveSlug}-${slug}`);
        if (card) {
            card.classList.add('wave-move-flash');
            setTimeout(() => card.classList.remove('wave-move-flash'), 800);
        }
    }

    // Extract pub name from a card's onclick attribute and unescape HTML entities
    _pubNameFromCard(card, wave) {
        // Use data-pub attribute (set on card div) — more reliable than parsing onclick
        const raw = card.getAttribute('data-pub');
        if (!raw) return null;
        const txt = document.createElement('textarea');
        txt.innerHTML = raw;
        return txt.value;
    }

    _refreshCardVisuals() {
        // Derive the locked set: pubs in Wave 1 are locked from W2/W3
        const lockedByW1 = this.selectedWave1 ? new Set([this.selectedWave1]) : new Set();

        // ── Wave 1 cards ──────────────────────────────────────
        document.querySelectorAll('[id^="selcard-wave1-"]').forEach(card => {
            card.classList.remove('selected');
        });
        if (this.selectedWave1) {
            const el = document.getElementById(`selcard-wave1-${this._slugify(this.selectedWave1)}`);
            if (el) el.classList.add('selected');
        }

        // ── Wave 2 cards ──────────────────────────────────────
        document.querySelectorAll('[id^="selcard-wave2-"]').forEach(card => {
            const pubForCard = this._pubNameFromCard(card, 'wave2');

            card.classList.remove('selected', 'locked-by-wave');
            const existingLabel = card.querySelector('.locked-wave-label');
            if (existingLabel) existingLabel.remove();

            if (pubForCard && lockedByW1.has(pubForCard)) {
                card.classList.add('locked-by-wave');
                const nameEl = card.querySelector('.select-card-name');
                if (nameEl) {
                    const badge = document.createElement('span');
                    badge.className = 'locked-wave-label';
                    badge.textContent = 'In Wave 1';
                    nameEl.appendChild(badge);
                }
            } else if (pubForCard && this.selectedWave2.has(pubForCard)) {
                card.classList.add('selected');
            }
        });

        // ── Wave 3 cards ──────────────────────────────────────
        document.querySelectorAll('[id^="selcard-wave3-"]').forEach(card => {
            const pubForCard = this._pubNameFromCard(card, 'wave3');

            card.classList.remove('selected', 'locked-by-wave');
            const existingLabel = card.querySelector('.locked-wave-label');
            if (existingLabel) existingLabel.remove();

            if (pubForCard && lockedByW1.has(pubForCard)) {
                card.classList.add('locked-by-wave');
                const nameEl = card.querySelector('.select-card-name');
                if (nameEl) {
                    const badge = document.createElement('span');
                    badge.className = 'locked-wave-label';
                    badge.textContent = 'In Wave 1';
                    nameEl.appendChild(badge);
                }
            } else if (pubForCard && this.selectedWave3.has(pubForCard)) {
                card.classList.add('selected');
            }
        });
    }

    _updateBuildBar() {
        const w1 = this.selectedWave1 ? 1 : 0;
        const w2 = this.selectedWave2.size;
        const w3 = this.selectedWave3.size;
        const total = w1 + w2 + w3;

        // Status shown in bottom nav status area
        let statusText = '';
        if (total === 0) {
            statusText = 'Select at least one Wave 2 outlet to continue';
        } else {
            const parts = [];
            if (w1) parts.push(`Wave 1: 1`);
            if (w2) parts.push(`Wave 2: ${w2}`);
            if (w3) parts.push(`Wave 3: ${w3}`);
            statusText = parts.join(' · ') + ` — ${total} selected`;
        }
        const statusEl = document.getElementById('bnav-status');
        if (statusEl) statusEl.textContent = statusText;

        this._setNavAction('Build Campaign →', w2 > 0);
    }

    _slugify(str) {
        return (str || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    }

    _esc(str) {
        return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // ══════════════════════════════════════════════════════════════════
    // STEP 2 — Build campaign from selections
    // ══════════════════════════════════════════════════════════════════

    async buildCampaign() {
        if (!this.sessionId) {
            this.setStatus('Session expired — please run the analysis again.');
            return;
        }
        if (this.selectedWave2.size === 0) {
            this.setStatus('Please select at least one Wave 2 outlet.');
            return;
        }

        const bar = null; // build bar removed — bottom nav handles this
        this._setNavAction('<span class="spinner"></span> Building campaign…', false);
        this.setStatus('');

        try {
            const payload = {
                session_id: this.sessionId,
                wave_1: this.selectedWave1 || null,
                wave_2: Array.from(this.selectedWave2),
                wave_3: Array.from(this.selectedWave3),
            };

            const response = await fetch('/api/campaign', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.message || response.statusText);
            }
            const data = await response.json();
            if (data.status === 'error') throw new Error(data.message);

            this.results = data;
            this._campaignData = data;
            this.pitchIndex = {};

            this._showStep3();
            this.setStatus('');

        } catch (e) {
            this.setStatus(`Error: ${e.message}`);
            // btn removed — nav action already reset above
            this._setNavAction('Build Campaign →', this.selectedWave2.size > 0);
        }
    }

    // ══════════════════════════════════════════════════════════════════
    // Shared renderers
    // ══════════════════════════════════════════════════════════════════

    renderStatsBar(data) {
        const na = data.news_analysis || {};
        const score = na.newsworthiness_score || 0;
        const scoreColor = score >= 7 ? 'var(--success)' : score >= 5 ? '#9a7030' : 'var(--error)';
        const wc = data.wave_counts || {};

        // In selection mode, show target count instead of wave counts
        const pubCount = data.publication_count || 0;
        const articlesScanned = data.articles_scanned || 0;

        document.getElementById('stats-bar').innerHTML = `
            <div class="stat-item">
                <div class="stat-value" style="color: ${scoreColor};">${score}/10</div>
                <div class="stat-label">Newsworthiness</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${na.news_type || '—'}</div>
                <div class="stat-label">Story Type</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${wc.wave_1 !== undefined ? (wc.wave_1 || 0) : (data.targets ? data.targets.filter(t => t.fit_score >= 7).length : '—')}</div>
                <div class="stat-label">${wc.wave_1 !== undefined ? 'Wave 1 (Exclusive)' : 'High-fit Targets'}</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${wc.wave_2 !== undefined ? (wc.wave_2 || 0) : (data.targets ? data.targets.filter(t => t.fit_score >= 5).length : '—')}</div>
                <div class="stat-label">${wc.wave_2 !== undefined ? 'Wave 2 (Launch Day)' : 'Qualifying Targets'}</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${wc.wave_3 !== undefined ? (wc.wave_3 || 0) : pubCount}</div>
                <div class="stat-label">${wc.wave_3 !== undefined ? 'Wave 3 (Follow-on)' : 'Pubs Scanned'}</div>
            </div>
        `;
    }

    // ── Assessment tab ─────────────────────────────────────────────────
    renderAssessment(na) {
        if (!na) return;
        const container = document.getElementById('assessment-content');
        const score = na.newsworthiness_score || 0;
        const scoreClass = score >= 7 ? 'score-high' : score >= 5 ? 'score-mid' : 'score-low';

        const companion = na.companion_content_needed || {};
        const companionItems = [
            { key: 'press_release', label: 'Press Release' },
            { key: 'data_exclusive', label: 'Data Exclusive' },
            { key: 'byline_opportunity', label: 'Byline / Op-Ed' },
            { key: 'embargoed_briefing', label: 'Embargoed Briefing' },
        ];

        const excl = na.exclusive_viability || {};

        const anglesHtml = (na.angles || []).map(a => `
            <div class="angle-card">
                <div class="angle-name">${a.angle_name}</div>
                <div class="angle-framing">${a.framing}</div>
                <div class="angle-best-for">Best for: ${a.best_for}</div>
            </div>
        `).join('');

        const weaknessesHtml = (na.weaknesses || []).map(w => `
            <div class="weakness-item">${w}</div>
        `).join('');

        const dataAssetsHtml = (na.data_assets || []).filter(d => d).map(d => `
            <span style="background: #eaf2e6; color: #5a7a4a; padding: 3px 10px; border-radius: 10px; font-size: 0.78rem; font-weight: 500;">${d}</span>
        `).join('');

        const exclusiveHtml = excl.can_offer_exclusive ? `
            <div class="exclusive-offer-box" style="margin-bottom:16px;">
                <div class="exclusive-offer-label">Exclusive Viability</div>
                <div><strong>Can offer:</strong> ${excl.what_to_offer || '—'}</div>
                ${excl.embargo_window_suggested ? `<div style="margin-top:3px;font-size:0.8rem;opacity:0.8;">Suggested window: ${excl.embargo_window_suggested}</div>` : ''}
            </div>` : '';

        const timingHtml = na.campaign_timing_notes ? `
            <div style="margin-bottom:16px;">
                <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; font-weight: 600; margin-bottom: 6px;">Campaign Timing Notes</div>
                <div style="font-size: 0.84rem; color: var(--body-text); font-style: italic;">${na.campaign_timing_notes}</div>
            </div>` : '';

        container.innerHTML = `
            <div class="assessment-card">
                <h3>Story Assessment</h3>

                <div class="score-row">
                    <div class="score-circle ${scoreClass}">${score}</div>
                    <div>
                        <div style="font-weight: 700; font-size: 1rem; color: var(--headline); margin-bottom: 4px;">${na.headline || ''}</div>
                        <div style="font-size: 0.82rem; color: var(--grey-medium);">${na.newsworthiness_reasoning || ''}</div>
                    </div>
                </div>

                <div class="meta-grid">
                    <div class="meta-item">
                        <div class="meta-label">Story Type</div>
                        <div class="meta-value">${na.news_type || '—'}</div>
                    </div>
                    <div class="meta-item">
                        <div class="meta-label">Why Now</div>
                        <div class="meta-value">${na.why_now || 'No clear timely hook identified'}</div>
                    </div>
                    <div class="meta-item">
                        <div class="meta-label">Core Story</div>
                        <div class="meta-value">${na.core_story || '—'}</div>
                    </div>
                    <div class="meta-item">
                        <div class="meta-label">Who Cares</div>
                        <div class="meta-value">${(na.who_cares || []).join(', ') || '—'}</div>
                    </div>
                </div>

                ${dataAssetsHtml ? `
                <div style="margin-bottom: 16px;">
                    <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; font-weight: 600; margin-bottom: 6px;">Data Assets Found</div>
                    <div style="display: flex; flex-wrap: wrap; gap: 5px;">${dataAssetsHtml}</div>
                </div>` : ''}

                ${exclusiveHtml}
                ${timingHtml}

                ${anglesHtml ? `
                <div style="margin-bottom: 16px;">
                    <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; font-weight: 600; margin-bottom: 8px;">Story Angles</div>
                    <div class="angles-list">${anglesHtml}</div>
                </div>` : ''}

                <div style="margin-bottom: 16px;">
                    <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; font-weight: 600; margin-bottom: 6px;">Companion Content Recommended</div>
                    <div class="companion-tags">
                        ${companionItems.map(item => `
                            <span class="companion-tag ${companion[item.key] ? 'companion-yes' : 'companion-no'}">
                                ${companion[item.key] ? '✓' : '○'} ${item.label}
                            </span>
                        `).join('')}
                    </div>
                    ${companion.reasoning ? `<div style="font-size: 0.78rem; color: var(--grey-medium); margin-top: 8px; font-style: italic;">${companion.reasoning}</div>` : ''}
                </div>

                ${weaknessesHtml ? `
                <div>
                    <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; font-weight: 600; margin-bottom: 8px;">What Would Make This More Pitchable</div>
                    <div class="weaknesses-list">${weaknessesHtml}</div>
                </div>` : ''}
            </div>
        `;
    }

    // ── Timing schedule helper ─────────────────────────────────────────
    _renderTimingCard(waveData, waveLabel) {
        if (!waveData) return '';
        const hasDate = waveData.send_date && waveData.send_date !== 'TBD';
        if (!waveData.send_time_guidance && !waveData.follow_up_window && !hasDate) return '';
        return `<div class="timing-schedule-card">
            <div class="timing-schedule-label">Send Schedule — ${waveLabel}</div>
            ${hasDate ? `<div class="timing-row">
                <span class="timing-row-label">Send date</span>
                <span class="timing-row-value">${waveData.send_date}</span>
            </div>` : ''}
            ${waveData.send_time_guidance ? `<div class="timing-row">
                <span class="timing-row-label">Timing guidance</span>
                <span class="timing-row-value">${waveData.send_time_guidance}</span>
            </div>` : ''}
            ${waveData.follow_up_window ? `<div class="timing-row">
                <span class="timing-row-label">Follow-up window</span>
                <span class="timing-row-value">${waveData.follow_up_window}</span>
            </div>` : ''}
        </div>`;
    }

    // ── Press release / PR coordination renderer ───────────────────────
    _renderPressReleaseSection(pr) {
        if (!pr || !pr.press_release) return '';
        const prId = `pr-text-${Date.now()}`;
        const memoId = `pr-memo-${Date.now()}`;
        return `
        <div class="pr-wire-section" id="pr-wire-section">
            <div class="pr-wire-header" onclick="document.getElementById('pr-wire-section').classList.toggle('open')">
                <span class="chevron">▼</span>
                <div>
                    <div class="pr-wire-title">Press Release &amp; PR Coordination</div>
                    <div class="pr-wire-subtitle">Wire-ready press release · PR firm brief · Embargo management protocol</div>
                </div>
            </div>
            <div class="pr-wire-body">

                ${pr.wire_timing_note ? `<div class="wire-timing-note">${pr.wire_timing_note}</div>` : ''}

                <div class="pr-subsection">
                    <div class="pr-subsection-label">For the Wire (press release)</div>
                    <div class="press-release-text" id="${prId}">${this._esc(pr.press_release)}</div>
                    <button class="copy-pr-btn" onclick="app.copyText('${prId}', this)">Copy press release</button>
                </div>

                ${pr.pr_firm_brief ? `<div class="pr-subsection">
                    <div class="pr-subsection-label">Briefing your PR firm</div>
                    <div class="pr-firm-memo-box">${this._esc(pr.pr_firm_brief)}</div>
                </div>` : ''}

                ${pr.embargo_protocol ? `<div class="pr-subsection">
                    <div class="pr-subsection-label">Embargo management protocol</div>
                    <div class="embargo-protocol-box">${this._esc(pr.embargo_protocol)}</div>
                </div>` : ''}

            </div>
        </div>`;
    }

    copyText(elementId, btn) {
        const el = document.getElementById(elementId);
        if (!el) return;
        navigator.clipboard.writeText(el.textContent || el.innerText);
        if (btn) {
            btn.textContent = 'Copied!';
            btn.classList.add('copied');
            setTimeout(() => {
                btn.textContent = 'Copy press release';
                btn.classList.remove('copied');
            }, 1500);
        }
    }

    // ── Campaign Waves tab ─────────────────────────────────────────────
    renderCampaign(waves, plan, pressRelease) {
        const container = document.getElementById('targets-list');
        if (!waves && !plan) {
            container.innerHTML = '<div class="empty-state">No campaign generated. Try adding more news context.</div>';
            return;
        }
        plan = plan || {};
        waves = waves || {};

        const hasW1   = !!(waves.wave_1?.target_data);
        const w2Count = (waves.wave_2 || []).length;
        const w3Count = (waves.wave_3 || []).length;
        const defaultTab = hasW1 ? 'wave1' : 'wave2';

        let html = '';

        // Campaign summary
        if (plan.campaign_summary) {
            html += `<div class="campaign-summary-banner">
                <div class="campaign-summary-label">Campaign Strategy</div>
                <div class="campaign-summary-text">${plan.campaign_summary}</div>
            </div>`;
        }

        // Press release — collapsible drawer above tabs
        if (pressRelease) {
            html += this._renderPressReleaseSection(pressRelease);
        }

        // ── Wave tab bar ──
        html += `<div class="wave-tabs">
            <button class="wave-tab-btn wave-tab-btn-1${defaultTab === 'wave1' ? ' active' : ''}"
                    id="wtab-wave1" onclick="app.switchWaveTab('wave1')">
                <span class="wtab-badge wtab-badge-1">1</span>
                <span class="wtab-label">Exclusive</span>
                <span class="wtab-count">${hasW1 ? '1 outlet' : '—'}</span>
            </button>
            <button class="wave-tab-btn wave-tab-btn-2${defaultTab === 'wave2' ? ' active' : ''}"
                    id="wtab-wave2" onclick="app.switchWaveTab('wave2')">
                <span class="wtab-badge wtab-badge-2">2</span>
                <span class="wtab-label">Launch Day</span>
                <span class="wtab-count">${w2Count} outlet${w2Count !== 1 ? 's' : ''}</span>
            </button>
            <button class="wave-tab-btn wave-tab-btn-3${defaultTab === 'wave3' ? ' active' : ''}"
                    id="wtab-wave3" onclick="app.switchWaveTab('wave3')">
                <span class="wtab-badge wtab-badge-3">3</span>
                <span class="wtab-label">Post-Launch</span>
                <span class="wtab-count">${w3Count} outlet${w3Count !== 1 ? 's' : ''}</span>
            </button>
        </div>`;

        // ── Wave tab panels ──
        html += `<div class="wave-tab-panel${defaultTab === 'wave1' ? ' active' : ''}" id="wpanel-wave1">
            ${this._buildWave1Panel(waves, plan)}
        </div>`;
        html += `<div class="wave-tab-panel${defaultTab === 'wave2' ? ' active' : ''}" id="wpanel-wave2">
            ${this._buildWave2Panel(waves, plan)}
        </div>`;
        html += `<div class="wave-tab-panel${defaultTab === 'wave3' ? ' active' : ''}" id="wpanel-wave3">
            ${this._buildWave3Panel(waves, plan)}
        </div>`;

        container.innerHTML = html;
    }

    switchWaveTab(tabId) {
        document.querySelectorAll('.wave-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.wave-tab-panel').forEach(p => p.classList.remove('active'));
        const btn   = document.getElementById(`wtab-${tabId}`);
        const panel = document.getElementById(`wpanel-${tabId}`);
        if (btn)   btn.classList.add('active');
        if (panel) panel.classList.add('active');
    }

    _buildWave1Panel(waves, plan) {
        const w1Plan = plan.wave_1 || {};
        const w1     = waves.wave_1;
        let html = '';
        if (w1Plan.timing_label) {
            html += `<div class="wave-panel-timing-label">${w1Plan.timing_label}</div>`;
        }
        html += this._renderTimingCard(w1Plan, 'Wave 1 Exclusive');
        if (w1 && w1.target_data) {
            if (w1.exclusive_offer) {
                html += `<div class="exclusive-offer-box">
                    <div class="exclusive-offer-label">What you're offering exclusively</div>
                    ${w1.exclusive_offer}
                </div>`;
            }
            if (w1.contingency) html += this._renderContingencyBox(w1.contingency);
            html += this._renderTargetCard(w1.target_data, 'w1', 0, w1.angle_note || w1.rationale || '', null, 1);
        } else {
            html += `<div class="no-wave1-notice">No exclusive outlet selected — go back and add a Wave 1 outlet if you want an exclusive pitch.</div>`;
        }
        return html;
    }

    _buildWave2Panel(waves, plan) {
        const w2Plan    = plan.wave_2 || {};
        const wave2List = waves.wave_2 || [];
        let html = '';
        if (w2Plan.timing_label) {
            html += `<div class="wave-panel-timing-label">${w2Plan.timing_label}</div>`;
        }
        html += this._renderTimingCard(w2Plan, 'Wave 2 Launch Day');
        if (w2Plan.wave_2_note) {
            html += `<div class="wave-2-note">${w2Plan.wave_2_note}</div>`;
        }
        if (wave2List.length === 0) {
            html += `<div class="no-wave1-notice">No Wave 2 pitches generated.</div>`;
        } else {
            wave2List.forEach((entry, i) => {
                html += this._renderTargetCard(entry.target_data, 'w2', i, entry.angle_note || '', null, 2);
            });
        }
        return html;
    }

    _buildWave3Panel(waves, plan) {
        const w3Plan    = plan.wave_3 || {};
        const wave3List = waves.wave_3 || [];
        let html = '';
        if (w3Plan.timing_label) {
            html += `<div class="wave-panel-timing-label">${w3Plan.timing_label}</div>`;
        }
        html += this._renderTimingCard(w3Plan, 'Wave 3 Post-Launch');
        if (w3Plan.wave_3_strategy) {
            html += `<div class="wave-strategy-note">
                <div class="wave-strategy-note-label">Using Wave 2 coverage as social proof</div>
                ${w3Plan.wave_3_strategy}
            </div>`;
        }
        if (plan.contingency_if_wave2_thin) {
            html += `<div class="wave-strategy-note">
                <div class="wave-strategy-note-label">If Wave 2 coverage is thin</div>
                ${plan.contingency_if_wave2_thin}
            </div>`;
        }
        if (wave3List.length === 0) {
            html += `<div class="no-wave1-notice">No Wave 3 pitches generated.</div>`;
        } else {
            wave3List.forEach((entry, i) => {
                html += this._renderTargetCard(entry.target_data, 'w3', i, entry.angle_note || '', entry.format_suggestion || '', 3);
            });
        }
        return html;
    }

    _renderContingencyBox(contingency) {
        return `<div class="contingency-box">
            <div class="contingency-box-title">If the exclusive doesn't work out</div>
            ${contingency.if_rejected ? `
            <div class="contingency-row">
                <span class="contingency-trigger">If rejected:</span>
                <span class="contingency-action">${contingency.if_rejected}</span>
            </div>` : ''}
            ${contingency.if_no_response_48h ? `
            <div class="contingency-row">
                <span class="contingency-trigger">No response in 48h:</span>
                <span class="contingency-action">${contingency.if_no_response_48h}</span>
            </div>` : ''}
            ${contingency.second_choice_exclusive ? `
            <div class="contingency-row">
                <span class="contingency-trigger">Second choice exclusive:</span>
                <span class="contingency-action">${contingency.second_choice_exclusive}</span>
            </div>` : ''}
        </div>`;
    }

    _renderTargetCard(target, wavePrefix, idx, angleNote, formatSuggestion, waveNum) {
        if (!target) return '';
        const domId = `target-${wavePrefix}-${idx}`;
        const pitchId = `pitch-${wavePrefix}-${idx}`;
        const score = target.fit_score || 0;
        const scoreClass = score >= 7 ? 'score-high' : score >= 5 ? 'score-mid' : 'score-low';
        const pitch = target.pitch || {};
        const headlines = (target.recent_headlines || []).slice(0, 5);
        const authors = target.known_authors || [];
        const audienceHook = target.audience_hook || '';

        if (pitch.subject_line) {
            this.pitchIndex[pitchId] = { subject_line: pitch.subject_line, body: pitch.body || '' };
        }

        const waveBadgeColor = waveNum === 1 ? '#e8e4ef' : waveNum === 2 ? '#dde4ee' : '#f0eae9';
        const waveBadgeText = waveNum === 1 ? 'Exclusive' : waveNum === 2 ? 'Launch Day' : 'Follow-on';

        // Scrape quality badge
        const scrapeQuality = pitch.scrape_quality_used || '';
        let scrapeClass = '';
        let scrapeLabel = '';
        if (scrapeQuality === 'full')         { scrapeClass = 'scrape-quality-full';    scrapeLabel = 'Full article'; }
        else if (scrapeQuality === 'partial') { scrapeClass = 'scrape-quality-partial'; scrapeLabel = 'Partial article'; }
        else if (scrapeQuality === 'title_only') { scrapeClass = 'scrape-quality-title'; scrapeLabel = 'Title only'; }
        else if (scrapeQuality === 'failed')  { scrapeClass = 'scrape-quality-failed';  scrapeLabel = 'No article scraped'; }
        const scrapeBadge = scrapeLabel ? `<span class="scrape-quality-badge ${scrapeClass}">${scrapeLabel}</span>` : '';

        return `
        <div class="target-card" id="${domId}">
            <div class="target-header" onclick="app.toggleTarget('${domId}')">
                <span class="chevron">▼</span>
                <div class="target-score ${scoreClass}">${score}</div>
                <div class="target-meta">
                    <div class="target-name">${target.publication || '—'}</div>
                    <div class="target-sub">${target.beat || ''} · ${target.audience || ''}</div>
                </div>
                <div class="target-badges">
                    <span class="badge badge-tier${target.tier || 2}">Tier ${target.tier || 2}</span>
                    <span class="badge" style="background:${waveBadgeColor};color:var(--headline);">${waveBadgeText}</span>
                    ${score >= 7 ? '<span class="badge" style="background:#eaf2e6;color:#5a7a4a;">Strong fit</span>' : ''}
                </div>
            </div>
            <div class="target-body">

                <div class="target-section">
                    <div class="target-section-label">Why This Outlet</div>
                    <div style="font-size: 0.84rem; color: var(--body-text);">${target.fit_reasoning || ''}</div>
                </div>

                ${audienceHook ? `
                <div class="target-section">
                    <div class="target-section-label">Audience Hook</div>
                    <div class="audience-hook-box" style="margin:0;">
                        <div class="audience-hook-label">What makes their readers click</div>
                        ${audienceHook}
                    </div>
                </div>` : ''}

                ${angleNote ? `
                <div class="angle-note-box">
                    <div class="angle-note-label">Angle for this outlet</div>
                    ${angleNote}
                </div>` : `
                <div class="target-section">
                    <div class="target-section-label">Angle to Use</div>
                    <div style="font-size: 0.84rem; color: var(--body-text); background: var(--table-shade); padding: 10px 12px; border-radius: 6px; border-left: 3px solid var(--highlight-2);">${target.best_angle || ''}</div>
                </div>`}

                ${formatSuggestion ? `<span class="format-suggestion-tag">${formatSuggestion}</span>` : ''}

                <div class="target-section" style="margin-top: 12px;">
                    <div class="target-section-label">Target Journalist Type</div>
                    <div style="font-size: 0.84rem; color: var(--grey-medium); font-style: italic;">${target.suggested_journalist_type || ''}</div>
                    ${authors.length > 0 ? `
                    <div style="margin-top: 5px; font-size: 0.78rem; color: var(--highlight-2);">
                        <strong>Known contributors:</strong> ${authors.join(', ')}
                    </div>` : ''}
                </div>

                ${headlines.length > 0 ? `
                <div class="target-section">
                    <div class="target-section-label">Recent article titles</div>
                    <ul class="recent-headlines-list">
                        ${headlines.map(h => {
                            const title = typeof h === 'object' ? h.title : h;
                            const url = typeof h === 'object' ? h.url : '';
                            return url
                                ? `<li><a href="${url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${this._esc(title)}</a></li>`
                                : `<li>${this._esc(title)}</li>`;
                        }).join('')}
                    </ul>
                </div>` : ''}

                ${pitch.subject_line ? `
                <div class="target-section">
                    <div class="target-section-label">
                        Draft Pitch Email
                        ${scrapeBadge}
                    </div>
                    <div class="pitch-box">
                        <div class="pitch-subject">Subject: ${pitch.subject_line}</div>
                        <div class="pitch-body">${(pitch.body || '').replace(/\n/g, '<br>')}</div>
                        <button class="copy-pitch-btn" onclick="app.copyPitchById('${pitchId}', this)">Copy pitch</button>
                    </div>
                    ${pitch.personalization_notes ? `
                    <div style="font-size: 0.75rem; color: var(--grey-medium); margin-top: 6px; font-style: italic;">
                        <strong>Personalization rationale:</strong> ${pitch.personalization_notes}
                    </div>` : ''}
                    ${pitch.companion_content_recommended ? `
                    <div style="font-size: 0.75rem; color: var(--grey-medium); margin-top: 4px; font-style: italic;">
                        <strong>Attach / offer:</strong> ${pitch.companion_content_recommended}
                    </div>` : ''}
                    ${pitch.exclusive_offer_line ? `
                    <div style="font-size: 0.78rem; color: var(--headline); margin-top: 6px; font-weight: 600;">
                        Exclusive offer line: ${pitch.exclusive_offer_line}
                    </div>` : ''}
                    ${pitch.follow_on_hook ? `
                    <div style="font-size: 0.78rem; color: #7a5058; margin-top: 6px; font-style: italic;">
                        Follow-on hook: ${pitch.follow_on_hook}
                    </div>` : ''}
                </div>` : ''}

            </div>
        </div>`;
    }

    toggleTarget(domId) {
        const card = document.getElementById(domId);
        if (card) card.classList.toggle('open');
    }

    copyPitchById(pitchId, btn) {
        const pitch = this.pitchIndex[pitchId];
        if (!pitch) return;
        const text = `Subject: ${pitch.subject_line}\n\n${pitch.body}`;
        navigator.clipboard.writeText(text);
        if (btn) {
            btn.textContent = 'Copied!';
            btn.classList.add('copied');
            setTimeout(() => {
                btn.textContent = 'Copy pitch';
                btn.classList.remove('copied');
            }, 1500);
        }
    }

    // ── Publication library ────────────────────────────────────────────
    togglePubLibrary() {
        const body = document.getElementById('pub-library-section-body');
        const chevron = document.getElementById('pub-library-chevron');
        if (!body) return;
        const open = body.style.display !== 'none';
        body.style.display = open ? 'none' : 'block';
        if (chevron) chevron.style.transform = open ? '' : 'rotate(180deg)';
    }

    async loadPublications() {
        try {
            const res = await fetch('/api/publications');
            const data = await res.json();
            this._publications = data.publications || [];
            this._pubEditMode = false;
            this.renderPublications(this._publications);
        } catch (e) {}
    }

    renderPublications(pubs) {
        const container = document.getElementById('publications-list');
        if (!container) return;

        const editMode = this._pubEditMode || false;

        const dirty = this._pubLibraryDirty && this.sessionId;
        const toolbar = `
        <div class="pub-library-toolbar">
            <span style="font-size:0.78rem; color:var(--grey-medium);">${pubs.length} publications</span>
            <div style="display:flex; gap:8px; margin-left:auto; align-items:center;">
                ${editMode
                    ? `<button class="pub-lib-btn pub-lib-btn-export-csv" onclick="app.exportPubsCsv()">Export CSV</button>
                       <label class="pub-lib-btn pub-lib-btn-import-csv">
                           Import CSV
                           <input type="file" accept=".csv" style="display:none;" onchange="app.importPubsCsv(this)">
                       </label>
                       <button class="pub-lib-btn pub-lib-btn-save" onclick="app.savePublications()">Save changes</button>
                       <button class="pub-lib-btn pub-lib-btn-cancel" onclick="app.cancelPubEdit()">Cancel</button>
                       <button class="pub-lib-btn pub-lib-btn-reset" onclick="app.resetPublications()">Reset to defaults</button>`
                    : `<button class="pub-lib-btn pub-lib-btn-edit" onclick="app.enterPubEditMode()">Edit library</button>`
                }
            </div>
        </div>
        ${dirty ? `<div class="pub-reanalyze-banner">
            Library updated. <strong>Re-analyze to score new publications</strong> against your news and show them in Campaign Design.
            <button class="pub-lib-btn pub-lib-btn-reanalyze" onclick="app.reanalyze()">Re-analyze now →</button>
        </div>` : ''}`;

        if (editMode) {
            // Edit mode: table with inline editable fields
            const rows = pubs.map((p, i) => `
                <tr class="pub-edit-row" data-idx="${i}">
                    <td><input class="pub-edit-input" data-field="name" data-idx="${i}" value="${this._esc(p.name||'')}"></td>
                    <td><input class="pub-edit-input" data-field="domain" data-idx="${i}" value="${this._esc(p.domain||'')}"></td>
                    <td>
                        <select class="pub-edit-select" data-field="tier" data-idx="${i}">
                            <option value="1" ${p.tier==1?'selected':''}>Tier 1</option>
                            <option value="2" ${p.tier!=1?'selected':''}>Tier 2</option>
                        </select>
                    </td>
                    <td><input class="pub-edit-input" data-field="beat" data-idx="${i}" value="${this._esc(p.beat||'')}"></td>
                    <td><input class="pub-edit-input" data-field="audience" data-idx="${i}" value="${this._esc(p.audience||'')}"></td>
                    <td><input class="pub-edit-input pub-edit-input-wide" data-field="rss" data-idx="${i}" value="${this._esc(p.rss||'')}"></td>
                    <td><button class="pub-edit-delete" onclick="app.deletePub(${i})" title="Remove">✕</button></td>
                </tr>
            `).join('');

            container.innerHTML = toolbar + `
            <div class="pub-edit-table-wrap">
                <table class="pub-edit-table">
                    <thead><tr>
                        <th>Name</th><th>Domain</th><th>Tier</th><th>Beat</th><th>Audience</th><th>RSS URL</th><th></th>
                    </tr></thead>
                    <tbody id="pub-edit-tbody">${rows}</tbody>
                </table>
            </div>
            <button class="pub-lib-btn pub-lib-btn-add" onclick="app.addPub()" style="margin-top:12px;">+ Add publication</button>
            `;

            // Wire up live edits
            container.querySelectorAll('.pub-edit-input, .pub-edit-select').forEach(el => {
                el.addEventListener('change', () => {
                    const idx = parseInt(el.dataset.idx);
                    const field = el.dataset.field;
                    this._publications[idx][field] = field === 'tier' ? parseInt(el.value) : el.value;
                });
            });
        } else {
            // View mode: card grid grouped by tier
            const byTier = {};
            pubs.forEach(p => {
                const t = p.tier || 2;
                if (!byTier[t]) byTier[t] = [];
                byTier[t].push(p);
            });

            container.innerHTML = toolbar + Object.entries(byTier).sort(([a],[b]) => a-b).map(([tier, list]) => `
                <div style="margin-bottom: 20px;">
                    <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; color: var(--headline); margin-bottom: 10px;">
                        Tier ${tier} — ${tier == 1 ? 'Top-tier trade &amp; tech press' : 'Specialist &amp; enterprise press'}
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px;">
                        ${list.map(p => `
                            <div style="background: white; border: 1px solid var(--grey-light); padding: 14px 16px;">
                                <div style="font-weight: 700; font-size: 0.88rem; color: var(--headline); margin-bottom: 3px;">${this._esc(p.name)}</div>
                                <div style="font-size: 0.75rem; color: var(--grey-medium); margin-bottom: 4px;">${this._esc(p.domain||'')}</div>
                                <div style="font-size: 0.75rem; color: var(--highlight-2); margin-bottom: 4px;"><strong>Beat:</strong> ${this._esc(p.beat||'')}</div>
                                <div style="font-size: 0.75rem; color: var(--body-text);">${this._esc(p.description||'')}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `).join('');
        }
    }

    enterPubEditMode() {
        this._pubEditMode = true;
        // Deep copy so cancel can restore
        this._pubEditBackup = JSON.parse(JSON.stringify(this._publications));
        this.renderPublications(this._publications);
    }

    cancelPubEdit() {
        this._pubEditMode = false;
        this._publications = this._pubEditBackup || this._publications;
        this.renderPublications(this._publications);
    }

    addPub() {
        this._publications.push({
            name: '', domain: '', tier: 2, beat: '', audience: '', description: '', rss: ''
        });
        this.renderPublications(this._publications);
        // Focus the new name field
        const tbody = document.getElementById('pub-edit-tbody');
        if (tbody) {
            const lastRow = tbody.lastElementChild;
            if (lastRow) lastRow.querySelector('input')?.focus();
        }
    }

    deletePub(idx) {
        this._publications.splice(idx, 1);
        this.renderPublications(this._publications);
    }

    async savePublications() {
        // Collect current values from the DOM inputs before saving
        const container = document.getElementById('publications-list');
        container.querySelectorAll('.pub-edit-input, .pub-edit-select').forEach(el => {
            const idx = parseInt(el.dataset.idx);
            const field = el.dataset.field;
            if (idx >= 0 && idx < this._publications.length) {
                this._publications[idx][field] = field === 'tier' ? parseInt(el.value) : el.value;
            }
        });

        const saveBtn = container.querySelector('.pub-lib-btn-save');
        if (saveBtn) { saveBtn.textContent = 'Saving…'; saveBtn.disabled = true; }

        try {
            const res = await fetch('/api/publications', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({publications: this._publications}),
            });
            const data = await res.json();
            if (data.status === 'success') {
                this._pubEditMode = false;
                this._pubLibraryDirty = true;  // flag: needs re-analyze
                this.renderPublications(this._publications);
            } else {
                this._showStatus(`Save failed: ${data.message}`, true);
                if (saveBtn) { saveBtn.textContent = 'Save changes'; saveBtn.disabled = false; }
            }
        } catch (e) {
            this._showStatus('Save failed — network error.', true);
            if (saveBtn) { saveBtn.textContent = 'Save changes'; saveBtn.disabled = false; }
        }
    }

    async resetPublications() {
        if (!confirm('Reset to the default curated publication list? This will discard your edits.')) return;
        const res = await fetch('/api/publications/reset', {method: 'POST'});
        const data = await res.json();
        if (data.status === 'success') {
            await this.loadPublications();
            this._showStatus('Publication library reset to defaults.', false);
        }
    }

    exportPubsCsv() {
        const cols = ['name', 'domain', 'tier', 'beat', 'audience', 'description', 'rss'];
        const escape = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
        const rows = [
            cols.join(','),
            ...this._publications.map(p => cols.map(c => escape(p[c] ?? '')).join(','))
        ];
        const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'pitchplanner-publications.csv';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    }

    importPubsCsv(input) {
        const file = input.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const lines = e.target.result.split('\n').map(l => l.trim()).filter(Boolean);
                if (lines.length < 2) { alert('CSV appears empty.'); return; }

                // Parse header
                const header = this._parseCsvRow(lines[0]);
                const required = ['name'];
                for (const r of required) {
                    if (!header.includes(r)) { alert(`CSV is missing a "name" column.`); return; }
                }

                const pubs = [];
                for (let i = 1; i < lines.length; i++) {
                    const vals = this._parseCsvRow(lines[i]);
                    const pub = {};
                    header.forEach((col, idx) => { pub[col] = vals[idx] ?? ''; });
                    if (!pub.name?.trim()) continue;  // skip blank rows
                    pub.tier = parseInt(pub.tier) || 2;
                    pubs.push(pub);
                }

                if (pubs.length === 0) { alert('No valid rows found in CSV.'); return; }

                // Load into live list and switch to edit mode so user can review before saving
                this._publications = pubs;
                this._pubEditMode = true;
                this.renderPublications(this._publications);
                this._showStatus(`Imported ${pubs.length} publications. Review and click "Save changes" to apply.`, false);
            } catch (err) {
                alert('Failed to parse CSV: ' + err.message);
            }
        };
        reader.readAsText(file);
        input.value = '';  // reset so same file can be re-imported if needed
    }

    _parseCsvRow(line) {
        // Handles quoted fields with embedded commas and escaped quotes
        const result = [];
        let cur = '';
        let inQuote = false;
        for (let i = 0; i < line.length; i++) {
            const ch = line[i];
            if (inQuote) {
                if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
                else if (ch === '"') { inQuote = false; }
                else { cur += ch; }
            } else {
                if (ch === '"') { inQuote = true; }
                else if (ch === ',') { result.push(cur); cur = ''; }
                else { cur += ch; }
            }
        }
        result.push(cur);
        return result;
    }

    async reanalyze() {
        if (!this.sessionId) {
            alert('No active session — please run the analysis from Step 1 first.');
            return;
        }
        const btn = document.querySelector('.pub-lib-btn-reanalyze');
        if (btn) { btn.textContent = 'Re-analyzing…'; btn.disabled = true; }

        // Get current tier filter from the UI
        const activeTierBtn = document.querySelector('.tier-btn.active');
        const tierFilter = activeTierBtn ? parseInt(activeTierBtn.dataset.tier) : 2;

        try {
            const res = await fetch('/api/reanalyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ session_id: this.sessionId, tier_filter: tierFilter }),
            });
            const data = await res.json();
            if (data.status === 'success') {
                // Update stored analyze data
                this._analyzeData = data;
                this._selectionsInitialized = false;  // reset so suggestions re-apply
                this._pubLibraryDirty = false;
                this.renderPublications(this._publications);
                // Switch back to Campaign Design tab so user sees the new targets
                this.switchTab('targets');
                this._showStep2();
            } else {
                alert(data.message || 'Re-analyze failed.');
                if (btn) { btn.textContent = 'Re-analyze now →'; btn.disabled = false; }
            }
        } catch (e) {
            alert('Re-analyze failed — network error.');
            if (btn) { btn.textContent = 'Re-analyze now →'; btn.disabled = false; }
        }
    }

    _showStatus(msg, isError) {
        const el = document.getElementById('status-msg');
        if (!el) return;
        el.textContent = msg;
        el.style.color = isError ? '#c0392b' : '#27ae60';
        el.style.display = 'block';
        setTimeout(() => { el.style.display = 'none'; }, 5000);
    }

    async exportDocx() {
        if (!this._campaignData || !this.sessionId) {
            alert('No campaign to export yet. Complete Step 3 first.');
            return;
        }
        const btn = document.getElementById('bnav-export-btn');
        const origText = btn ? btn.textContent : '';
        if (btn) { btn.textContent = 'Exporting…'; btn.disabled = true; }

        try {
            const res = await fetch('/api/export/docx', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    session_id: this.sessionId,
                    campaign: this._campaignData,
                }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'pitchplanner-campaign.docx';
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        } catch (e) {
            alert('Export failed. Please try again.');
        } finally {
            if (btn) { btn.textContent = origText; btn.disabled = false; }
        }
    }
}

const app = new PRPitchyApp();

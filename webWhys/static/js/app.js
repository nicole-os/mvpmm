/**
 * Website Competitor Scanner - Frontend Application
 */

class WebsiteScanner {
    constructor() {
        this.form = document.getElementById('scan-form');
        this.fileInput = document.getElementById('file-input');
        this.fileDropArea = document.getElementById('file-drop-area');
        this.fileList = document.getElementById('file-list');
        this.uploadedFiles = [];

        this.inputSection = document.getElementById('input-section');
        this.loadingSection = document.getElementById('loading-section');
        this.resultsSection = document.getElementById('results-section');

        this.init();
    }

    init() {
        // Form submission
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));

        // File upload handling
        this.fileDropArea.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        // Drag and drop
        this.fileDropArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.fileDropArea.classList.add('dragover');
        });

        this.fileDropArea.addEventListener('dragleave', () => {
            this.fileDropArea.classList.remove('dragover');
        });

        this.fileDropArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.fileDropArea.classList.remove('dragover');
            this.handleFileDrop(e.dataTransfer.files);
        });

        // Tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });

        // Filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => this.filterRecommendations(btn.dataset.filter));
        });

        // Sort buttons
        document.querySelectorAll('.sort-btn').forEach(btn => {
            btn.addEventListener('click', () => this.sortRecommendations(btn.dataset.sort));
        });

        // New scan button
        document.getElementById('new-scan-btn')?.addEventListener('click', () => this.resetForm());
    }

    handleFileSelect(e) {
        this.addFiles(e.target.files);
    }

    handleFileDrop(files) {
        this.addFiles(files);
    }

    addFiles(files) {
        const allowedTypes = ['.pdf', '.docx', '.doc', '.txt', '.md', '.rtf'];

        for (const file of files) {
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (allowedTypes.includes(ext)) {
                if (!this.uploadedFiles.find(f => f.name === file.name)) {
                    this.uploadedFiles.push(file);
                }
            }
        }

        this.renderFileList();
    }

    renderFileList() {
        this.fileList.innerHTML = this.uploadedFiles.map((file, index) => `
            <div class="file-item">
                <span class="file-name">${file.name}</span>
                <button type="button" class="remove-btn" data-index="${index}">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>
        `).join('');

        this.fileList.querySelectorAll('.remove-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.uploadedFiles.splice(parseInt(btn.dataset.index), 1);
                this.renderFileList();
            });
        });
    }

    async handleSubmit(e) {
        e.preventDefault();

        const yourWebsite = document.getElementById('your-website').value.trim();
        const competitorUrls = document.getElementById('competitor-urls').value.trim();
        const focusAreas = document.getElementById('focus-areas').value.trim();

        if (!yourWebsite) {
            alert('Please enter your website URL');
            return;
        }

        // Show loading
        this.showLoading();

        try {
            // Build form data
            const formData = new FormData();
            formData.append('your_website', yourWebsite);
            formData.append('competitor_urls', competitorUrls.replace(/\n/g, ','));

            if (focusAreas) {
                formData.append('focus_areas', focusAreas);
            }

            for (const file of this.uploadedFiles) {
                formData.append('brand_docs', file);
            }

            // Minimum time per step (in ms) to ensure users can see each progress step
            const MIN_STEP_TIME = 1000;

            // Step 1: Your Site
            this.updateProgress('your-site');
            const step1Start = Date.now();

            // Make API request (happens during first step)
            const response = await fetch('/api/scan', {
                method: 'POST',
                body: formData
            });

            // Ensure minimum time for "your-site" step
            const step1Elapsed = Date.now() - step1Start;
            const step1Wait = Math.max(0, MIN_STEP_TIME - step1Elapsed);
            await this.delay(step1Wait);

            // Step 2: Competitors
            this.updateProgress('competitors');
            const step2Start = Date.now();

            if (!response.ok) {
                throw new Error(`Analysis failed: ${response.statusText}`);
            }

            // Ensure minimum time for "competitors" step
            const step2Elapsed = Date.now() - step2Start;
            const step2Wait = Math.max(0, MIN_STEP_TIME - step2Elapsed);
            await this.delay(step2Wait);

            // Step 3: Documents
            this.updateProgress('documents');
            const step3Start = Date.now();

            const results = await response.json();

            // Ensure minimum time for "documents" step
            const step3Elapsed = Date.now() - step3Start;
            const step3Wait = Math.max(0, MIN_STEP_TIME - step3Elapsed);
            await this.delay(step3Wait);

            // Step 4: Analysis
            this.updateProgress('analysis');
            const step4Start = Date.now();

            // Ensure minimum time for "analysis" step before showing results
            const step4Wait = MIN_STEP_TIME;
            await this.delay(step4Wait);

            // Display results
            this.displayResults(results);

        } catch (error) {
            console.error('Analysis error:', error);
            alert(`Error: ${error.message}`);
            this.resetForm();
        }
    }

    showLoading() {
        this.inputSection.style.display = 'none';
        this.loadingSection.classList.add('active');
        this.resultsSection.classList.remove('active');
        document.documentElement.style.overflow = 'hidden';
        document.body.style.overflow = 'hidden';
        window.scrollTo(0, 0);
    }

    hideLoading() {
        this.loadingSection.classList.remove('active');
        document.documentElement.style.overflow = 'auto';
        document.body.style.overflow = 'auto';
    }

    updateProgress(step) {
        const steps = document.querySelectorAll('.progress-step');
        let reachedCurrent = false;

        steps.forEach(s => {
            if (s.dataset.step === step) {
                s.classList.add('active');
                s.classList.remove('completed');
                reachedCurrent = true;
            } else if (!reachedCurrent) {
                s.classList.remove('active');
                s.classList.add('completed');
            } else {
                s.classList.remove('active', 'completed');
            }
        });

        const messages = {
            'your-site': 'Analyzing your website...',
            'competitors': 'Scanning competitor websites...',
            'documents': 'Processing your documents...',
            'analysis': 'Generating recommendations...'
        };

        document.getElementById('loading-message').textContent = messages[step] || 'Analyzing...';
    }

    displayResults(results) {
        this.hideLoading();
        this.resultsSection.classList.add('active');
        this.resultsSection.style.display = 'block';

        // Store results for export
        this.currentResults = results;

        // Store metric explanations for tooltips
        this.metricExplanations = results.metric_explanations || {};

        // Show which URL was analyzed
        const analyzedUrl = results.your_site_analysis?.url || 'Unknown';
        document.getElementById('analyzed-url').textContent = `Page analyzed: ${analyzedUrl}`;

        // Render priority actions
        this.renderPriorityActions(results.priority_actions);

        // Render copy suggestions
        this.renderCopySuggestions(results.your_site_analysis, results.copy_suggestions);

        // Store recommendations for sorting/filtering
        this.allRecommendations = results.recommendations || [];

        // Render all recommendations
        this.renderRecommendations(this.allRecommendations);

        // Render site analysis with explanations
        this.renderSiteAnalysis(results.your_site_analysis, results.metric_insights);

        // Render competitor comparison
        this.renderCompetitorComparison(results.your_site_analysis, results.competitor_analyses);

        // Set up export button
        document.getElementById('export-btn')?.addEventListener('click', () => this.exportReport());
    }

    renderPriorityActions(actions) {
        const container = document.getElementById('priority-grid');

        if (!actions || actions.length === 0) {
            container.innerHTML = '<p>No priority actions identified.</p>';
            return;
        }

        // Render 5 action cards with image card at position 3
        let cardsHtml = '';
        const allActions = actions.slice(0, 5);

        // Render cards 1 and 2
        for (let i = 0; i < 2; i++) {
            const action = allActions[i];
            cardsHtml += `
            <div class="priority-card">
                <div class="priority-number priority-${Math.min(i + 1, 5)}">
                    ${String(i + 1).padStart(2, '0')}
                </div>
                <div class="priority-content">
                    <div class="priority-title">${action.title}</div>
                    <div class="tags">
                        <span class="tag tag-category">${action.category}</span>
                        <span class="tag tag-${action.impact.toLowerCase()}">Value: ${action.impact}</span>
                        <span class="tag tag-${action.effort.toLowerCase()}-eff">Work: ${action.effort === 'Medium' ? 'Med' : action.effort}</span>
                    </div>
                    ${action.description ? `<p class="priority-desc">${action.description}</p>` : ''}
                    ${action.all_actions && action.all_actions.length > 0 ? `
                        <div class="action-steps">
                            <ul>
                                ${action.all_actions.map(a => `<li>${a}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
        }

        // Add image card at position 3
        cardsHtml += `
            <div class="priority-card image-card">
                <img src="/static/images/accent-photo.png" alt="Accent image">
            </div>
        `;

        // Render remaining cards (3, 4, 5)
        for (let i = 2; i < 5; i++) {
            const action = allActions[i];
            cardsHtml += `
            <div class="priority-card">
                <div class="priority-number priority-${Math.min(i + 1, 5)}">
                    ${String(i + 1).padStart(2, '0')}
                </div>
                <div class="priority-content">
                    <div class="priority-title">${action.title}</div>
                    <div class="tags">
                        <span class="tag tag-category">${action.category}</span>
                        <span class="tag tag-${action.impact.toLowerCase()}">Value: ${action.impact}</span>
                        <span class="tag tag-${action.effort.toLowerCase()}-eff">Work: ${action.effort === 'Medium' ? 'Med' : action.effort}</span>
                    </div>
                    ${action.description ? `<p class="priority-desc">${action.description}</p>` : ''}
                    ${action.all_actions && action.all_actions.length > 0 ? `
                        <div class="action-steps">
                            <ul>
                                ${action.all_actions.map(a => `<li>${a}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
        }

        container.innerHTML = cardsHtml;
    }

    renderRecommendations(recommendations) {
        const container = document.getElementById('recommendations-list');

        if (!recommendations || recommendations.length === 0) {
            container.innerHTML = '<p>No recommendations available.</p>';
            return;
        }

        container.innerHTML = recommendations.map(rec => `
            <div class="recommendation" data-category="${rec.category}">
                <div class="recommendation-header">
                    <h3 class="recommendation-title">${rec.title}</h3>
                    <div class="recommendation-badges">
                        <span class="badge badge-category">${rec.category}</span>
                        <span class="badge badge-impact-${rec.impact}">Impact: ${rec.impact}</span>
                        <span class="badge badge-effort-${rec.effort}">Effort: ${rec.effort}</span>
                    </div>
                </div>
                <p class="recommendation-description">${rec.description}</p>
                ${rec.specific_actions && rec.specific_actions.length > 0 ? `
                    <div class="recommendation-actions">
                        <h4>Action Steps:</h4>
                        <ul>
                            ${rec.specific_actions.map(action => `<li>${action}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                ${rec.expected_outcome ? `
                    <p style="margin-top: 12px; font-size: 0.875rem; color: var(--olive-green);">
                        <strong>Expected outcome:</strong> ${rec.expected_outcome}
                    </p>
                ` : ''}
            </div>
        `).join('');
    }

    renderSiteAnalysis(analysis, metricInsights) {
        const metricsContainer = document.getElementById('site-metrics');

        if (!analysis) {
            metricsContainer.innerHTML = '<p>No analysis data available.</p>';
            return;
        }

        const seo = analysis.seo_factors || {};
        const tech = analysis.technical_factors || {};
        const llm = analysis.llm_discoverability || {};
        const geo = analysis.geo_factors || {};
        const msg = analysis.page_messaging || {};
        const explanations = this.metricExplanations || {};

        // Helper to get explanation
        const getExp = (key) => explanations[key] || {};

        // Page Messaging Summary card
        const messagingHtml = `
            <div class="analysis-card" style="grid-column: 1 / -1; border-left: 4px solid var(--persimmon);">
                <h4 style="color: var(--persimmon); margin-bottom: 14px;">Page Messaging Summary</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
                    <div style="background: #fafafa; padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Primary Message</div>
                        <div style="font-size: 0.95rem; font-weight: 600; color: #222;">${msg.primary_message || '<em style="color:#aaa">Not detected</em>'}</div>
                    </div>
                    <div style="background: #fafafa; padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Value Proposition</div>
                        <div style="font-size: 0.9rem; color: #444;">${msg.value_proposition || '<em style="color:#aaa">Not detected</em>'}</div>
                    </div>
                    <div style="background: #fafafa; padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Apparent Audience</div>
                        <div style="font-size: 0.9rem; color: #444;">${msg.apparent_audience || '<em style="color:#aaa">Not explicitly stated on page</em>'}</div>
                    </div>
                    <div style="background: #fafafa; padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Page Tone</div>
                        <div style="font-size: 0.9rem; color: #444;">${msg.tone || 'Unknown'}</div>
                    </div>
                </div>
                ${msg.key_claims && msg.key_claims.length > 0 ? `
                    <div style="margin-top: 12px;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 6px;">Key Section Headlines</div>
                        <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                            ${msg.key_claims.map(c => `<span style="border: 2px solid #B38B91; background: transparent; color: #B38B91; padding: 4px 10px; border-radius: 0; font-size: 0.82rem;">${c}</span>`).join('')}
                        </div>
                    </div>
                ` : ''}
                ${msg.cta_language && msg.cta_language.length > 0 ? `
                    <div style="margin-top: 12px;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 6px;">CTA / Button Language Found</div>
                        <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                            ${msg.cta_language.map(c => `<span style="background: #B38B91; color: white; padding: 4px 10px; border-radius: 0; font-size: 0.82rem;">${c}</span>`).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;

        // Render metric insights if available
        let insightsHtml = '';
        if (metricInsights && metricInsights.length > 0) {
            insightsHtml = `
                <div class="analysis-card" style="grid-column: 1 / -1; background: linear-gradient(135deg, #fff9e6 0%, #fff 100%); border-left: 4px solid var(--persimmon);">
                    <h4 style="color: var(--persimmon); margin-bottom: 15px;">Key Insights vs Competitors</h4>
                    ${metricInsights.map(insight => `
                        <div style="margin-bottom: 15px; padding: 12px; background: white; border-radius: 0;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <strong>${getExp(insight.metric)?.name || insight.metric}</strong>
                                <span class="badge ${insight.status === 'behind' ? 'badge-impact-high' : 'badge-impact-low'}">${insight.status === 'behind' ? 'Needs Work' : 'Ahead'}</span>
                            </div>
                            <p style="font-size: 0.9rem; color: #666; margin-bottom: 8px;">
                                <strong>You:</strong> ${insight.your_value} | <strong>Competitors:</strong> ${insight.competitor_avg}
                            </p>
                            <p style="font-size: 0.85rem; color: #888; margin-bottom: 8px;"><em>Why it matters:</em> ${insight.explanation}</p>
                            <p style="font-size: 0.85rem; color: var(--olive-green);"><strong>Recommendation:</strong> ${insight.recommendation}</p>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        // Scannability scoring helpers
        const h2Count = seo.h2_tags?.length || 0;
        const h3Count = seo.h3_tags?.length || 0;
        const wordCount = seo.word_count || 0;
        const listCount = geo.lists_and_bullets || 0;
        const imgTotal = seo.images_total || 0;
        const imgBad = seo.images_without_alt || 0;
        const internalLinks = seo.internal_links || 0;
        const externalLinks = seo.external_links || 0;
        const titleLen = seo.title_length || 0;
        const metaLen = seo.meta_description_length || 0;
        const secHeaders = Object.keys(tech.security_headers || {}).length;

        // Reading time estimate (avg 200 words/min)
        const readingMins = wordCount > 0 ? Math.ceil(wordCount / 200) : 0;

        // Scannability score out of 5
        let scanScore = 0;
        if (h2Count >= 3) scanScore++;
        if (listCount >= 2) scanScore++;
        if (wordCount >= 400 && wordCount <= 2500) scanScore++;
        if (imgTotal >= 2) scanScore++;
        if (h3Count >= 2) scanScore++;
        const scanLabel = scanScore >= 4 ? ['Highly scannable', 'good'] : scanScore >= 2 ? ['Moderately scannable', 'warning'] : ['Hard to scan', 'bad'];

        // Word count context
        const wordCtx = wordCount < 300 ? ['Too short — add more content', 'bad']
            : wordCount <= 800 ? ['Good for a homepage', 'good']
            : wordCount <= 2000 ? ['Good depth for a landing page', 'good']
            : ['Very long — consider splitting', 'warning'];

        // Title length context
        const titleCtx = titleLen >= 30 && titleLen <= 60 ? ['Optimal (30–60 chars)', 'good']
            : titleLen > 60 ? ['Too long — may truncate in search', 'warning']
            : titleLen > 0 ? ['Too short — add more context', 'warning']
            : ['Missing', 'bad'];

        // Meta description context
        const metaCtx = metaLen >= 120 && metaLen <= 160 ? ['Optimal (120–160 chars)', 'good']
            : metaLen > 160 ? ['Too long — may truncate', 'warning']
            : metaLen > 0 ? ['Too short — aim for 120–160 chars', 'warning']
            : ['Missing', 'bad'];

        // Image alt coverage
        const altCoverage = imgTotal > 0 ? Math.round(((imgTotal - imgBad) / imgTotal) * 100) : 100;
        const altCtx = altCoverage === 100 ? ['100% — all images have alt text', 'good']
            : altCoverage >= 80 ? [`${altCoverage}% — a few images missing alt`, 'warning']
            : [`${altCoverage}% — many images missing alt text`, 'bad'];

        // Metrics cards
        metricsContainer.innerHTML = messagingHtml + insightsHtml + `

            <div class="analysis-card" style="grid-column: 1 / -1; border-left: 4px solid var(--highlight-2);">
                <h4 style="color: var(--highlight-2); margin-bottom: 14px;">Scannability &amp; Content Structure</h4>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 12px;">
                    <div style="background: var(--table-shade); padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Scannability</div>
                        <div style="font-size: 1.05rem; font-weight: 700;" class="${scanLabel[1]}">${scanLabel[0]}</div>
                        <div style="font-size: 0.75rem; color: #888; margin-top: 2px;">${scanScore}/5 signals present</div>
                    </div>
                    <div style="background: var(--table-shade); padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Word Count</div>
                        <div style="font-size: 1.05rem; font-weight: 700;">${wordCount.toLocaleString()}</div>
                        <div style="font-size: 0.75rem; margin-top: 2px;" class="${wordCtx[1]}">${wordCtx[0]}</div>
                    </div>
                    <div style="background: var(--table-shade); padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Est. Reading Time</div>
                        <div style="font-size: 1.05rem; font-weight: 700;">${readingMins > 0 ? readingMins + ' min' : '< 1 min'}</div>
                        <div style="font-size: 0.75rem; color: #888; margin-top: 2px;">At 200 words/min</div>
                    </div>
                    <div style="background: var(--table-shade); padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">
                            <span class="tt-wrap">
                                H2 Sections
                                <span class="tt-icon">?</span>
                                <span class="tt-box">H2 sections organize content into major topics. More sections = better scanability for humans and AI. Search engines also use these to understand page structure.</span>
                            </span>
                        </div>
                        <div style="font-size: 1.05rem; font-weight: 700;" class="${h2Count >= 3 ? 'good' : h2Count > 0 ? 'warning' : 'bad'}">${h2Count}</div>
                        <div style="font-size: 0.75rem; color: #888; margin-top: 2px;">Main content organization</div>
                    </div>
                    <div style="background: var(--table-shade); padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">
                            <span class="tt-wrap">
                                H3 Subsections
                                <span class="tt-icon">?</span>
                                <span class="tt-box">H3 subsection headings help break up content into logical chunks. More H3s = more granular content structure that AI and search engines can parse better.</span>
                            </span>
                        </div>
                        <div style="font-size: 1.05rem; font-weight: 700;">${h3Count}</div>
                        <div style="font-size: 0.75rem; color: #888; margin-top: 2px;">Granular content structure for AI parsing</div>
                    </div>
                    <div style="background: var(--table-shade); padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">
                            <span class="tt-wrap">
                                Lists / Bullets
                                <span class="tt-icon">?</span>
                                <span class="tt-box">Bulleted and numbered lists are easy for AI to parse and extract. More lists = more structured, machine-readable content. Aim for 2+ lists per page.</span>
                            </span>
                        </div>
                        <div style="font-size: 1.05rem; font-weight: 700;" class="${listCount >= 2 ? 'good' : listCount > 0 ? 'warning' : 'bad'}">${listCount}</div>
                        <div style="font-size: 0.75rem; color: #888; margin-top: 2px;">Easily parsed by AI engines</div>
                    </div>
                    <div style="background: var(--table-shade); padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Images</div>
                        <div style="font-size: 1.05rem; font-weight: 700;">${imgTotal}</div>
                        <div style="font-size: 0.75rem; margin-top: 2px;" class="${altCtx[1]}">${altCtx[0]}</div>
                    </div>
                    <div style="background: var(--table-shade); padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Internal Links</div>
                        <div style="font-size: 1.05rem; font-weight: 700;" class="${internalLinks >= 10 ? 'good' : internalLinks > 0 ? 'warning' : 'bad'}">${internalLinks}</div>
                        <div style="font-size: 0.75rem; color: #888; margin-top: 2px;">Aim for 10+ for SEO</div>
                    </div>
                    <div style="background: var(--table-shade); padding: 12px; border-radius: 0;">
                        <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">
                            <span class="tt-wrap">
                                External Links
                                <span class="tt-icon">?</span>
                                <span class="tt-box">E-E-A-T = Expertise, Experience, Authoritativeness, Trustworthiness. External links to authoritative sources signal credibility to Google and AI systems. Aim for 3+ links to trusted sources.</span>
                            </span>
                        </div>
                        <div style="font-size: 1.05rem; font-weight: 700;" class="${externalLinks >= 2 ? 'good' : externalLinks > 0 ? 'warning' : 'bad'}">${externalLinks}</div>
                        <div style="font-size: 0.75rem; color: #888; margin-top: 2px;">Trust signals for Google & AI (E-E-A-T)</div>
                    </div>
                </div>
            </div>

            <div class="analysis-card seo-card">
                <h4>SEO Factors</h4>
                <div class="metric">
                    <span class="metric-label">Title Length</span>
                    <span class="metric-value ${titleCtx[1]}" style="font-size:0.82rem;">${titleLen} chars, Optimal=30–60</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Meta Desc</span>
                    <span class="metric-value ${metaCtx[1]}" style="font-size:0.82rem;">${metaLen} chars, Optimal=120–160</span>
                </div>
                <div class="metric">
                    <span class="metric-label">H1 Tags</span>
                    <span class="metric-value ${(seo.h1_tags?.length || 0) === 1 ? 'good' : 'warning'}">${seo.h1_tags?.length || 0} <span style="font-size:0.75rem;color:#888;">(ideal: 1)</span></span>
                </div>
                <div class="metric">
                    <span class="metric-label">Structured Data</span>
                    <span class="metric-value ${analysis.content_analysis?.has_structured_data ? 'good' : 'warning'}">${analysis.content_analysis?.has_structured_data ? 'Yes' : 'No'}</span>
                </div>
            </div>

            <div class="analysis-card technical-card">
                <h4>Technical Factors</h4>
                <div class="metric">
                    <span class="metric-label">HTTPS</span>
                    <span class="metric-value ${tech.https ? 'good' : 'bad'}">${tech.https ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Sitemap</span>
                    <span class="metric-value ${tech.has_sitemap ? 'good' : 'warning'}">${tech.has_sitemap ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Robots.txt</span>
                    <span class="metric-value ${tech.has_robots_txt ? 'good' : 'warning'}">${tech.has_robots_txt ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Mobile Viewport</span>
                    <span class="metric-value ${tech.mobile_friendly_hints?.length > 0 ? 'good' : 'bad'}">${tech.mobile_friendly_hints?.length > 0 ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Security Headers</span>
                    <span class="metric-value ${secHeaders >= 3 ? 'good' : secHeaders > 0 ? 'warning' : 'bad'}">${secHeaders} / 6</span>
                </div>
            </div>

            <div class="analysis-card llm-card">
                <h4>LLM &amp; GEO Discoverability</h4>
                <div class="metric">
                    <span class="metric-label">Structured Content</span>
                    <span class="metric-value ${llm.structured_content ? 'good' : 'warning'}">${llm.structured_content ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">FAQ Schema</span>
                    <span class="metric-value ${llm.faq_schema ? 'good' : 'warning'}">${llm.faq_schema ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">How-To Schema</span>
                    <span class="metric-value ${llm.how_to_schema ? 'good' : 'warning'}">${llm.how_to_schema ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">External Citations</span>
                    <span class="metric-value ${(llm.citations_and_sources || 0) >= 3 ? 'good' : (llm.citations_and_sources || 0) > 0 ? 'warning' : 'bad'}">${llm.citations_and_sources || 0}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Statistics Present</span>
                    <span class="metric-value ${geo.statistics_present ? 'good' : 'warning'}">${geo.statistics_present ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Comparison Tables</span>
                    <span class="metric-value ${geo.comparison_tables ? 'good' : 'warning'}">${geo.comparison_tables ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">AI Citation Ready</span>
                    <span class="metric-value ${geo.citation_ready ? 'good' : 'warning'}">${geo.citation_ready ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Lists/Bullet Points</span>
                    <span class="metric-value ${(geo.lists_and_bullets || 0) >= 2 ? 'good' : (geo.lists_and_bullets || 0) > 0 ? 'warning' : 'bad'}">${geo.lists_and_bullets || 0}</span>
                </div>
            </div>

            <div class="analysis-image-container">
                <img src="/static/images/accent-photo-tab4.png" alt="Forest landscape with devices">
            </div>
        `;

    }

    renderCompetitorComparison(yourSite, competitors) {
        const container = document.getElementById('competitor-comparison');

        if (!competitors || competitors.length === 0) {
            container.innerHTML = '<p>No competitor data available.</p>';
            return;
        }

        // Show a notice for any blocked/failed competitors before the table
        const blockedComps = competitors.filter(c => c.status === 'blocked' || c.status === 'error' || c.status === 'timeout');
        const blockedNotice = blockedComps.length > 0 ? `
            <div style="background: #fff7ed; border: 1px solid #f0c070; border-radius: 0; padding: 12px 16px; margin-bottom: 16px; font-size: 0.875rem; color: #8a6200;">
                <strong>Some competitors could not be analyzed:</strong>
                <ul style="margin: 6px 0 0 18px;">
                    ${blockedComps.map(c => `<li><strong>${c.domain || c.url}</strong> — ${
                        c.status === 'blocked' ? 'Bot protection / firewall blocked access' :
                        c.status === 'timeout' ? 'Request timed out' :
                        (c.error || 'Could not retrieve page')
                    }</li>`).join('')}
                </ul>
                <p style="margin: 6px 0 0 0; color: #666;">Try a different competitor URL, or check that the site is publicly accessible.</p>
            </div>
        ` : '';

        // Show a notice for JavaScript-heavy sites with limited data
        const jsComps = competitors.filter(c => c.status === 'requires-javascript');
        const jsNotice = jsComps.length > 0 ? `
            <div style="background: #f0f9ff; border: 1px solid #7dd3fc; border-radius: 0; padding: 12px 16px; margin-bottom: 16px; font-size: 0.875rem; color: #0369a1;">
                <strong>Limited data available:</strong>
                <ul style="margin: 6px 0 0 18px;">
                    ${jsComps.map(c => `<li><strong>${c.domain || c.url}</strong> — May load content via JavaScript or display popups. Showing available HTML data only.</li>`).join('')}
                </ul>
                <p style="margin: 6px 0 0 0; color: #666;">JavaScript rendering functionality coming soon. For now, manually review the site for complete data.</p>
            </div>
        ` : '';

        container.innerHTML = blockedNotice + jsNotice;

        const yourSeo = yourSite?.seo_factors || {};
        const yourWords = yourSeo.word_count || 0;

        // Metric definitions with tooltips
        const metrics = [
            {
                label: 'Word Count',
                tooltip: 'Total words on the page. More content signals depth and expertise to search engines and AI. Homepages: aim for 500–1,000+. Landing pages: 1,500–2,500+.',
                good: (v) => v >= 500,
                warn: (v) => v > 0 && v < 500,
                your: yourSeo.word_count ?? 'N/A',
                comp: (c) => c.seo_factors?.word_count ?? 'N/A',
                context: (v) => {
                    if (!yourWords || !v || isNaN(v)) return '';
                    if (v > yourWords * 1.5) return ' ▲ more';
                    if (v < yourWords * 0.7) return ' ▼ less';
                    return ' ≈ similar';
                }
            },
            {
                label: 'H2 Sections',
                tooltip: 'Number of H2 section headings. H2s define page structure for both users and AI. Each major topic should have its own H2. More H2s = more structured, more scannable, more AI-extractable content.',
                good: (v) => v >= 4,
                warn: (v) => v > 0 && v < 4,
                your: yourSeo.h2_tags?.length ?? 0,
                comp: (c) => c.seo_factors?.h2_tags?.length ?? 0,
                context: () => ''
            },
            {
                label: 'Internal Links',
                tooltip: 'Number of internal links on the page. Internal links distribute PageRank across your site and help search engines discover and index all your pages. More is generally better, up to a natural limit.',
                good: (v) => v >= 10,
                warn: (v) => v > 0 && v < 10,
                your: yourSeo.internal_links ?? 0,
                comp: (c) => c.seo_factors?.internal_links ?? 0,
                context: () => ''
            },
            {
                label: 'External Links',
                tooltip: 'Links to other domains. Outbound links to authoritative sources are an E-E-A-T signal — they show you\'re citing credible references. AI systems also favor pages that link to evidence.',
                good: (v) => v >= 2,
                warn: (v) => v === 1,
                your: yourSeo.external_links ?? 0,
                comp: (c) => c.seo_factors?.external_links ?? 0,
                context: () => ''
            },
            {
                label: 'Images',
                tooltip: 'Total images on the page. Images improve engagement and dwell time. Check that all images have descriptive alt text for accessibility and image SEO.',
                good: (v) => v >= 3,
                warn: (v) => v > 0 && v < 3,
                your: yourSeo.images_total ?? 0,
                comp: (c) => c.seo_factors?.images_total ?? 0,
                context: () => ''
            },
            {
                label: 'Images Missing Alt',
                tooltip: 'Images without alt text are invisible to screen readers and search engines. Alt text is an easy SEO win and accessibility requirement. Should be 0.',
                good: (v) => v === 0,
                warn: (v) => v > 0 && v <= 3,
                your: yourSeo.images_without_alt ?? 0,
                comp: (c) => c.seo_factors?.images_without_alt ?? 0,
                context: () => ''
            },
            {
                label: 'Title Length',
                tooltip: 'Page title character count. Optimal is 50–60 characters — long enough to be descriptive, short enough not to be cut off in search results.',
                good: (v) => v >= 30 && v <= 60,
                warn: (v) => v > 60 || (v > 0 && v < 30),
                your: yourSeo.title_length ?? 0,
                comp: (c) => c.seo_factors?.title_length ?? 0,
                context: () => ''
            },
            {
                label: 'Structured Data',
                tooltip: 'JSON-LD / schema.org markup. Tells search engines and AI exactly what your page is about — enables rich results in Google and makes content more citable by ChatGPT and Perplexity.',
                good: (v) => v === '✓',
                warn: () => false,
                your: yourSite?.content_analysis?.has_structured_data ? '✓' : '✗',
                comp: (c) => c.content_analysis?.has_structured_data ? '✓' : '✗',
                context: () => ''
            },
            {
                label: 'FAQ Schema',
                tooltip: 'FAQ schema enables "People Also Ask" rich results in Google and lets AI assistants surface your answers directly. Low effort, high visibility impact.',
                good: (v) => v === '✓',
                warn: () => false,
                your: yourSite?.llm_discoverability?.faq_schema ? '✓' : '✗',
                comp: (c) => c.llm_discoverability?.faq_schema ? '✓' : '✗',
                context: () => ''
            },
            {
                label: 'Statistics / Data',
                tooltip: 'Specific numbers, percentages, or data points on the page. AI systems strongly prefer citing pages with concrete data. ✗ means the page relies on qualitative claims only.',
                good: (v) => v === '✓',
                warn: () => false,
                your: yourSite?.geo_factors?.statistics_present ? '✓' : '✗',
                comp: (c) => c.geo_factors?.statistics_present ? '✓' : '✗',
                context: () => ''
            },
            {
                label: 'AI Citation Ready',
                tooltip: 'Composite: does the page have statistics + expert quotes or multiple lists? Citation-ready content is what AI tools pull from when answering user questions.',
                good: (v) => v === '✓',
                warn: () => false,
                your: yourSite?.geo_factors?.citation_ready ? '✓' : '✗',
                comp: (c) => c.geo_factors?.citation_ready ? '✓' : '✗',
                context: () => ''
            },
            {
                label: 'Lists / Bullets',
                tooltip: 'Number of bulleted or numbered lists. Lists are scannable for humans and easily extractable by AI. They frequently become featured snippets. Aim for 3+.',
                good: (v) => v >= 3,
                warn: (v) => v > 0 && v < 3,
                your: yourSite?.geo_factors?.lists_and_bullets ?? 'N/A',
                comp: (c) => c.geo_factors?.lists_and_bullets ?? 'N/A',
                context: () => ''
            },
            {
                label: 'Comparison Tables',
                tooltip: 'HTML tables on the page. Highly effective for "X vs Y" and "best [product]" queries in both featured snippets and AI responses.',
                good: (v) => v === '✓',
                warn: () => false,
                your: yourSite?.geo_factors?.comparison_tables ? '✓' : '✗',
                comp: (c) => c.geo_factors?.comparison_tables ? '✓' : '✗',
                context: () => ''
            },
            {
                label: 'HTTPS',
                tooltip: 'Whether the site uses HTTPS. Required for security, trust, and is a Google ranking factor.',
                good: (v) => v === '✓',
                warn: () => false,
                your: yourSite?.technical_factors?.https ? '✓' : '✗',
                comp: (c) => c.technical_factors?.https ? '✓' : '✗',
                context: () => ''
            },
            {
                label: 'Sitemap',
                tooltip: 'A sitemap.xml file helps search engines discover and index all your pages efficiently.',
                good: (v) => v === '✓',
                warn: () => false,
                your: yourSite?.technical_factors?.has_sitemap ? '✓' : '✗',
                comp: (c) => c.technical_factors?.has_sitemap ? '✓' : '✗',
                context: () => ''
            },
            {
                label: 'Security Headers',
                tooltip: 'Number of HTTP security headers present (HSTS, CSP, X-Frame-Options, etc.). Security headers are a trust signal for enterprise buyers and some ranking systems.',
                good: (v) => v >= 3,
                warn: (v) => v > 0 && v < 3,
                your: Object.keys(yourSite?.technical_factors?.security_headers || {}).length,
                comp: (c) => Object.keys(c.technical_factors?.security_headers || {}).length,
                context: () => ''
            },
            {
                label: 'Issues Found',
                tooltip: 'Number of SEO / technical issues detected. Fewer is better. See "Your Site Analysis" tab for the full list.',
                good: (v) => !isNaN(v) && Number(v) === 0,
                warn: (v) => !isNaN(v) && Number(v) > 0 && Number(v) <= 3,
                your: yourSite?.issues?.length ?? 0,
                comp: (c) => c.issues?.length ?? 0,
                context: () => ''
            }
        ];

        const cellStyle = (val, m) => {
            const v = val;
            if (m.good(v)) return 'color: var(--success); font-weight: 600;';
            if (m.warn(v)) return 'color: var(--warning); font-weight: 600;';
            if (v === '✗') return 'color: var(--error);';
            return '';
        };

        const tableHtml = `
            <style>
                .tt-wrap { position: relative; display: inline-flex; align-items: center; gap: 5px; cursor: default; }
                .tt-icon { display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px;
                           border-radius: 50%; background: #ccc; color: white; font-size: 10px; font-weight: 700;
                           cursor: help; flex-shrink: 0; }
                .tt-box { display: none; position: absolute; left: 0; top: 100%; margin-top: 4px; z-index: 100;
                          background: #222; color: #fff; font-size: 0.78rem; line-height: 1.45; padding: 10px 12px;
                          border-radius: 0; width: 280px; box-shadow: 0 4px 16px rgba(0,0,0,0.25); pointer-events: none; }
                .tt-wrap:hover .tt-box { display: block; }
            </style>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.875rem;">
                    <thead>
                        <tr style="background: var(--grey-lightest);">
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid var(--grey-light); min-width: 180px;">Metric</th>
                            <th style="padding: 12px; text-align: center; border-bottom: 2px solid var(--grey-light); background: var(--olive-green); color: white; min-width: 100px;">Your Site</th>
                            ${competitors.map(c => `
                                <th style="padding: 12px; text-align: center; border-bottom: 2px solid var(--grey-light); min-width: 120px;">${c.domain || c.url || 'Competitor'}</th>
                            `).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${metrics.map(m => `
                            <tr>
                                <td style="padding: 12px; border-bottom: 1px solid var(--grey-light);">
                                    <span class="tt-wrap">
                                        ${m.label}
                                        <span class="tt-icon">?</span>
                                        <span class="tt-box">${m.tooltip}</span>
                                    </span>
                                </td>
                                <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light); ${cellStyle(m.your, m)}">${m.your}</td>
                                ${competitors.map(c => {
                                    const val = m.comp(c);
                                    const ctx = m.context(val);
                                    return `<td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light); ${cellStyle(val, m)}">${val}<span style="font-size:0.72rem; color:#999;">${ctx}</span></td>`;
                                }).join('')}
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;

        // Helper to render a messaging blurb card for any site
        const renderBlurb = (site, isYours = false) => {
            if (site.status !== 'success' && !isYours) return '';
            const msg = site.page_messaging || {};
            const seo = site.seo_factors || {};
            const domain = isYours ? (site.domain || site.url || 'Your Site') : (site.domain || site.url || 'Competitor');
            const borderColor = isYours ? 'var(--headline)' : 'var(--grey-light)';
            const headerColor = isYours ? 'var(--headline)' : 'var(--olive-green-dark)';
            const badge = isYours ? `<span style="font-size:0.7rem; background: var(--headline); color: white; padding: 2px 8px; border-radius: 0; margin-left: 8px; vertical-align: middle;">Your Site</span>` : '';
            return `
                <div style="background: white; border: 1px solid ${borderColor}; border-radius: 0; padding: 20px; margin-top: 16px; ${isYours ? 'border-left: 4px solid var(--headline);' : ''}">
                    <h4 style="margin: 0 0 12px 0; color: ${headerColor};">${domain}${badge}</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.875rem;">
                        <div>
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 3px;">Primary headline (H1)</div>
                            <div style="color: #333;">${msg.primary_message || seo.title || '<em style="color:#aaa">Not detected</em>'}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 3px;">Apparent audience</div>
                            <div style="color: #333;">${msg.apparent_audience || '<em style="color:#aaa">Not explicitly stated</em>'}</div>
                        </div>
                        <div style="grid-column: 1 / -1;">
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 3px;">Value prop visitor would walk away with</div>
                            <div style="color: #333;">${msg.value_proposition || '<em style="color:#aaa">Not detected — page may rely on visuals or a single headline</em>'}</div>
                        </div>
                        ${msg.tone ? `
                        <div>
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 3px;">Tone</div>
                            <div style="color: #333;">${msg.tone}</div>
                        </div>` : ''}
                        ${msg.cta_language && msg.cta_language.length > 0 ? `
                        <div>
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 3px;">CTA language</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px;">
                                ${msg.cta_language.slice(0, 5).map(ct => `<span style="background: #B38B91; color: white; padding: 2px 8px; border-radius: 0; font-size: 0.78rem;">${ct}</span>`).join('')}
                            </div>
                        </div>` : ''}
                        ${msg.keyword_targets && msg.keyword_targets.length > 0 ? `
                        <div style="grid-column: 1 / -1;">
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 5px;">Keywords they appear to be targeting</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                                ${msg.keyword_targets.map(kw => `<span style="background: var(--grey-lightest); color: var(--grey-dark); border: 1px solid var(--grey-light); padding: 2px 10px; border-radius: 0; font-size: 0.78rem; font-weight: 500;">${kw}</span>`).join('')}
                            </div>
                        </div>` : ''}
                    </div>
                </div>
            `;
        };

        const blurbsHtml = renderBlurb(yourSite, true) + competitors.map(c => renderBlurb(c, false)).join('');

        // Competitor keyword intelligence panel
        // Aggregate all competitor keywords with source labels — for strategic awareness only
        const kwByCompetitor = competitors
            .filter(c => c.status === 'success' && c.page_messaging?.keyword_targets?.length > 0)
            .map(c => ({
                domain: c.domain || c.url || 'Competitor',
                keywords: c.page_messaging.keyword_targets
            }));

        // Collect all unique keywords with a count of how many competitors use them
        const kwFreq = {};
        kwByCompetitor.forEach(({ domain, keywords }) => {
            keywords.forEach(kw => {
                const k = kw.toLowerCase();
                if (!kwFreq[k]) kwFreq[k] = { display: kw, sources: [] };
                kwFreq[k].sources.push(domain);
            });
        });
        const sortedKws = Object.values(kwFreq).sort((a, b) => b.sources.length - a.sources.length);

        // Your site's own keyword targets (for comparison)
        const yourKws = yourSite?.page_messaging?.keyword_targets || [];

        const kwIntelHtml = sortedKws.length > 0 ? `
            <div style="background: white; border: 1px solid var(--grey-light); border-radius: 0; padding: 20px; margin-top: 24px;">
                <!-- Header + Image (aligned to h4 through keyword signals box) -->
                <div style="display: flex; gap: 20px; align-items: stretch;">
                    <!-- Left column: h4, description, keyword signals -->
                    <div style="flex: 1; min-width: 0;">
                        <h4 style="margin: 0 0 12px 0; color: var(--headline);">Competitor Keyword Intelligence</h4>
                        <p style="font-size: 0.82rem; color: #888; margin: 0 0 16px 0; line-height: 1.5;">
                            Use the keywords your competitors appear to be targeting to identify active areas and differentiation opportunities.
                        </p>

                        <!-- Keyword Signals Box (always shown) -->
                        <div style="margin-bottom: 0; padding: 10px 14px; background: var(--table-shade); border-radius: 0; border-left: 3px solid var(--headline);">
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--headline); font-weight: 700; margin-bottom: 6px;">Your site's current keyword signals</div>
                            ${yourKws.length > 0 ? `
                            <div style="display: flex; flex-wrap: wrap; gap: 5px;">
                                ${yourKws.map(kw => `<span style="background: var(--headline); color: white; padding: 2px 10px; border-radius: 0; font-size: 0.78rem; font-weight: 500;">${kw}</span>`).join('')}
                            </div>` : `
                            <div style="font-size: 0.82rem; color: var(--grey-medium); font-style: italic;">No keywords detected</div>`}
                        </div>
                    </div>

                    <!-- Right column: 30% image container (stretches to match left column height) -->
                    <div style="flex: 0 0 calc(30% - 14px); border: 1px solid #E8E6E3; border-radius: 0; background: #FAF8F6; display: flex; align-items: center; justify-content: center; overflow: hidden;">
                        <img src="/static/images/accent-photo-tab5.png" alt="Competitor keyword intelligence" style="width: 100%; height: 100%; object-fit: cover; display: block;">
                    </div>
                </div>

                <!-- Competitor Keywords (full width below) -->
                <div style="margin-top: 16px; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 8px; font-weight: 600;">Competitor keywords — sorted by how many competitors use them</div>
                <div style="display: flex; flex-direction: column; gap: 6px;">
                    ${sortedKws.map(kw => {
                        const usedByAll = kw.sources.length === kwByCompetitor.length && kwByCompetitor.length > 1;
                        const isShared = kw.sources.length > 1;
                        return `
                        <div style="display: flex; align-items: center; gap: 10px; padding: 6px 10px; background: var(--table-shade); border-radius: 0; flex-wrap: wrap;">
                            <span style="font-size: 0.84rem; font-weight: 600; color: var(--body-text); min-width: 160px;">${kw.display}</span>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px; flex: 1;">
                                ${kw.sources.map(s => `<span style="font-size: 0.72rem; background: white; border: 1px solid var(--grey-light); color: #666; padding: 1px 8px; border-radius: 0;">${s}</span>`).join('')}
                            </div>
                            ${usedByAll ? `<span style="font-size: 0.7rem; background: #fdecea; color: #c0392b; padding: 1px 8px; border-radius: 0; font-weight: 600; white-space: nowrap;">All competitors</span>` :
                              isShared ? `<span style="font-size: 0.7rem; background: #fff4e0; color: #b8860b; padding: 1px 8px; border-radius: 0; font-weight: 600; white-space: nowrap;">${kw.sources.length} competitors</span>` : ''}
                        </div>`;
                    }).join('')}
                </div>
                <p style="font-size: 0.78rem; color: #aaa; margin: 12px 0 0 0; font-style: italic;">
                    Keywords used by multiple competitors signal high-competition queries. Keywords used by only one competitor may represent an opportunity to outflank them on a less-contested term.
                </p>
            </div>
        ` : '';

        container.innerHTML += tableHtml + `
            <h4 style="margin: 28px 0 4px; color: var(--olive-green-dark);">Messaging Breakdown</h4>
            <p style="font-size: 0.85rem; color: #888; margin-bottom: 0;">What each site is trying to say, who they're talking to, and the value prop a visitor would walk away with.</p>
            ${blurbsHtml}
            ${kwIntelHtml}
        `;
    }

    renderCopySuggestions(analysis, copySuggestions) {
        const container = document.getElementById('copy-suggestions-list');
        if (!container) return;

        // Format a suggestion item — detect Q:/A: pattern and render as structured QA
        const formatSuggestionItem = (item) => {
            const qMatch = item.match(/^Q:\s*(.+?)\n+A:\s*([\s\S]+)$/);
            if (qMatch) {
                return `
                    <div style="margin-bottom: 3px;">
                        <div style="font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--highlight-2); font-weight: 700; margin-bottom: 2px;">Q</div>
                        <div style="font-size: 0.84rem; font-weight: 600; color: var(--headline); margin-bottom: 6px;">${qMatch[1]}</div>
                        <div style="font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--highlight-3); font-weight: 700; margin-bottom: 2px;">A</div>
                        <div style="font-size: 0.84rem; color: var(--body-text); line-height: 1.5;">${qMatch[2]}</div>
                    </div>`;
            }
            return `<div style="font-size: 0.84rem; line-height: 1.5; color: var(--body-text);">${item}</div>`;
        };

        // If LLM returned brand-accurate copy suggestions, use those
        if (copySuggestions && copySuggestions.length > 0) {
            container.innerHTML = copySuggestions.map(s => `
                <div style="background: white; border: 1px solid var(--grey-light); border-radius: 0; padding: 14px 16px; margin-bottom: 12px;">
                    <h4 style="color: var(--headline); margin: 0 0 8px 0; font-size: 0.95rem;">${s.category}</h4>
                    ${s.current ? `
                    <div style="background: var(--table-shade); padding: 7px 10px; border-radius: 0; margin-bottom: 8px; font-size: 0.82rem;">
                        <strong>Current:</strong> <span style="color: var(--body-text);">${s.current}</span>
                    </div>` : ''}
                    ${s.why ? `
                    <p style="font-size: 0.8rem; color: var(--grey-medium); margin: 0 0 8px 0; line-height: 1.4;"><em>${s.why}</em></p>` : ''}
                    <div style="margin-top: 6px;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 5px;">Suggested wording — click to copy</div>
                        ${(s.suggestions || []).map(item => `
                            <div class="copy-item"
                                 onclick="navigator.clipboard.writeText(this.dataset.text); this.classList.add('copy-flash'); setTimeout(() => this.classList.remove('copy-flash'), 1000);"
                                 data-text="${item.replace(/"/g, '&quot;')}"
                                 style="background: var(--table-shade); padding: 8px 10px; margin-top: 5px; border-radius: 0; cursor: pointer; border-left: 3px solid var(--highlight-3);">
                                ${formatSuggestionItem(item)}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `).join('');

            // Add alt text suggestions if available
            if (analysis.alt_text_suggestions && Object.keys(analysis.alt_text_suggestions).length > 0) {
                container.innerHTML += `
                    <div style="background: white; border: 1px solid var(--grey-light); border-radius: 0; padding: 14px 16px; margin-bottom: 12px;">
                        <h4 style="color: var(--headline); margin: 0 0 8px 0; font-size: 0.95rem;">Alt Text for Images</h4>
                        <p style="font-size: 0.8rem; color: var(--grey-medium); margin: 0 0 12px 0; line-height: 1.4;">Images missing alt text hurt accessibility and SEO. Here are AI-generated suggestions based on filename and page context:</p>
                        <div style="display: flex; flex-direction: column; gap: 10px;">
                            ${Object.entries(analysis.alt_text_suggestions).map(([src, suggestion]) => `
                                <div style="padding: 10px 12px; background: var(--table-shade); border-left: 3px solid var(--highlight-2); border-radius: 0;">
                                    <div style="font-size: 0.75rem; color: #888; margin-bottom: 4px; word-break: break-all;">Image: ${src.split('/').pop()}</div>
                                    <div style="font-size: 0.85rem; color: var(--body-text); line-height: 1.4;">${suggestion}</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }
            return;
        }

        // Fallback if no LLM copy suggestions returned
        container.innerHTML = `
            <div style="background: var(--table-shade); border-radius: 0; padding: 24px; text-align: center; color: var(--grey-medium);">
                <p style="font-size: 1rem; margin-bottom: 8px;">Upload your brand/messaging documents and run the scan to get brand-accurate copy suggestions.</p>
                <p style="font-size: 0.85rem;">Copy suggestions are generated by AI using your uploaded messaging guide and sales deck — so they reflect your actual brand voice and approved positioning.</p>
            </div>
        `;
    }

    async exportReport() {
        if (!this.currentResults) {
            alert('No results to export');
            return;
        }

        const btn = document.getElementById('export-btn');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = 'Generating...';
        btn.disabled = true;

        try {
            const response = await fetch('/api/export-docx', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(this.currentResults)
            });

            if (!response.ok) {
                throw new Error('Failed to generate document');
            }

            // Get the blob from response
            const blob = await response.blob();

            // Create download link
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            // Generate filename in dd-mm-yy format
            const now = new Date();
            const day = String(now.getDate()).padStart(2, '0');
            const month = String(now.getMonth() + 1).padStart(2, '0');
            const year = String(now.getFullYear()).slice(-2);
            a.download = `webWhys-report-${day}-${month}-${year}.docx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            btn.innerHTML = 'Downloaded!';
            setTimeout(() => {
                btn.innerHTML = originalHTML;
                btn.disabled = false;
            }, 2000);

        } catch (error) {
            console.error('Export error:', error);
            alert('Error generating report. Please try again.');
            btn.innerHTML = originalHTML;
            btn.disabled = false;
        }
    }

    // Legacy text export - kept for reference
    _exportReportText() {
        const results = this.currentResults;
        const analysis = results.your_site_analysis || {};
        const seo = analysis.seo_factors || {};
        const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

        // Build report content
        let report = `WEBSITE OPTIMIZATION REPORT
Generated: ${date}
URL Analyzed: ${analysis.url || 'N/A'}

${'='.repeat(60)}

EXECUTIVE SUMMARY
${'='.repeat(60)}

This report analyzes your website for SEO, GEO (Generative Engine Optimization),
and LLM discoverability factors. Below are prioritized recommendations to improve
your visibility in both traditional search and AI-powered search engines.

${'='.repeat(60)}

TOP PRIORITY ACTIONS
${'='.repeat(60)}

`;

        // Add priority actions
        (results.priority_actions || []).forEach((action, i) => {
            report += `
${i + 1}. ${action.title}
   Category: ${action.category} | Impact: ${action.impact} | Effort: ${action.effort}

   ${action.description || ''}

   Action Steps:
${(action.all_actions || [action.first_step]).filter(Boolean).map(a => `   • ${a}`).join('\n')}

`;
        });

        report += `
${'='.repeat(60)}

SITE ANALYSIS METRICS
${'='.repeat(60)}

SEO Factors:
• Title: ${seo.title || 'Missing'}
• Title Length: ${seo.title_length || 0} characters (optimal: 50-60)
• Meta Description: ${seo.meta_description ? 'Present' : 'Missing'}
• Meta Description Length: ${seo.meta_description_length || 0} characters (optimal: 150-160)
• H1 Tags: ${seo.h1_tags?.length || 0} (optimal: 1)
• Word Count: ${seo.word_count || 0}
• Images Missing Alt Text: ${seo.images_without_alt || 0}

Technical Factors:
• HTTPS: ${analysis.technical_factors?.https ? 'Yes' : 'No'}
• Sitemap: ${analysis.technical_factors?.has_sitemap ? 'Yes' : 'No'}
• Robots.txt: ${analysis.technical_factors?.has_robots_txt ? 'Yes' : 'No'}

LLM Discoverability:
• Structured Content: ${analysis.llm_discoverability?.structured_content ? 'Yes' : 'No'}
• FAQ Schema: ${analysis.llm_discoverability?.faq_schema ? 'Yes' : 'No'}

GEO (AI Citation) Factors:
• Statistics Present: ${analysis.geo_factors?.statistics_present ? 'Yes' : 'No'}
• Citation Ready: ${analysis.geo_factors?.citation_ready ? 'Yes' : 'No'}
• Lists/Bullets: ${analysis.geo_factors?.lists_and_bullets || 0}

${'='.repeat(60)}

ALL RECOMMENDATIONS
${'='.repeat(60)}

`;

        // Add all recommendations
        (results.recommendations || []).forEach((rec, i) => {
            report += `
${i + 1}. [${rec.category}] ${rec.title}
   Impact: ${rec.impact} | Effort: ${rec.effort}

   ${rec.description}

   Action Steps:
${(rec.specific_actions || []).map(a => `   • ${a}`).join('\n')}

   Expected Outcome: ${rec.expected_outcome || 'Improved performance'}

`;
        });

        report += `
${'='.repeat(60)}

ISSUES FOUND
${'='.repeat(60)}

`;
        (analysis.issues || []).forEach(issue => {
            report += `• [${issue.severity?.toUpperCase()}] ${issue.issue} (${issue.category})\n`;
        });

        report += `

${'='.repeat(60)}

STRENGTHS
${'='.repeat(60)}

`;
        (analysis.strengths || []).forEach(strength => {
            report += `• ${strength.strength} (${strength.category})\n`;
        });

        report += `

${'='.repeat(60)}
Report generated by Website Competitor Scanner
${'='.repeat(60)}
`;

        // Download as text file
        const blob = new Blob([report], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `website-optimization-report-${new Date().toISOString().split('T')[0]}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    switchTab(tabId) {
        // Update tab buttons
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabId);
        });

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `tab-${tabId}`);
        });
    }

    filterRecommendations(category) {
        this.activeFilter = category;
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filter === category);
        });
        document.querySelectorAll('.recommendation').forEach(rec => {
            if (category === 'all' || rec.dataset.category === category) {
                rec.style.display = 'block';
            } else {
                rec.style.display = 'none';
            }
        });
    }

    sortRecommendations(sortBy) {
        // Check if same button clicked (toggle on second click)
        const isSameButton = this.activeSort === sortBy;

        // Toggle sort direction if same button clicked
        if (isSameButton) {
            this.sortReverse = !this.sortReverse;
        } else {
            this.activeSort = sortBy;
            this.sortReverse = false;
        }

        document.querySelectorAll('.sort-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.sort === sortBy);
            // Update arrow when button is active
            if (btn.dataset.sort === sortBy) {
                let arrow;
                if (btn.dataset.sort === 'impact') {
                    // Impact: ↑ for high→low (default), ↓ for low→high (reversed)
                    arrow = this.sortReverse ? '↓' : '↑';
                } else {
                    // Effort: ↓ for low→high (default), ↑ for high→low (reversed)
                    arrow = this.sortReverse ? '↑' : '↓';
                }
                btn.textContent = btn.dataset.sort === 'impact'
                    ? `Impact ${arrow}`
                    : `Effort ${arrow}`;
            }
        });

        const impactOrder = { high: 0, medium: 1, low: 2 };
        const effortOrder = { low: 0, medium: 1, high: 2 };

        let sorted = [...(this.allRecommendations || [])].sort((a, b) => {
            if (sortBy === 'impact') {
                return (impactOrder[a.impact] ?? 1) - (impactOrder[b.impact] ?? 1);
            } else if (sortBy === 'effort') {
                return (effortOrder[a.effort] ?? 1) - (effortOrder[b.effort] ?? 1);
            }
            return (a.id ?? 0) - (b.id ?? 0); // default: original order
        });

        // Reverse if toggled
        if (this.sortReverse) {
            sorted.reverse();
        }

        this.renderRecommendations(sorted);

        // Re-apply current filter
        if (this.activeFilter && this.activeFilter !== 'all') {
            this.filterRecommendations(this.activeFilter);
        }
    }

    resetForm() {
        this.form.reset();
        this.uploadedFiles = [];
        this.fileList.innerHTML = '';
        this.inputSection.style.display = 'block';
        this.resultsSection.style.display = 'none';
        this.resultsSection.classList.remove('active');

        // Reset progress
        document.querySelectorAll('.progress-step').forEach(step => {
            step.classList.remove('active', 'completed');
        });

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    new WebsiteScanner();
});

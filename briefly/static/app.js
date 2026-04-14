/**
 * briefly - Form Handler & API Integration
 */

// ────────────────────────────────────────────────────────────────
// DOM REFERENCES
// ────────────────────────────────────────────────────────────────

const form = document.getElementById('briefForm');
const generateBtn = document.getElementById('generateBtn');
const loadingOverlay = document.getElementById('loadingOverlay');
const statusSection = document.getElementById('statusSection');
const statusContent = document.getElementById('statusContent');

const blogUrlInput = document.getElementById('blogUrl');
const brandDocsInput = document.getElementById('brandDocs');
const brandDocsList = document.getElementById('brandDocsList');
const brandingJsonFile = document.getElementById('brandingJsonFile');
const logoFile = document.getElementById('logoFile');
const logoPreview = document.getElementById('logoPreview');
const companyNameInput = document.getElementById('companyName');
const companyWebsiteInput = document.getElementById('companyWebsite');

// Clear Form button (replaces the old type="reset" button)
document.getElementById('clearFormBtn')?.addEventListener('click', () => resetForm());
const manualBrandingSection = document.getElementById('manualBrandingSection');

// Color inputs
const colorInputs = {
    primary: document.getElementById('colorPrimary'),
    secondary: document.getElementById('colorSecondary'),
    accent: document.getElementById('colorAccent'),
    accent2: document.getElementById('colorAccent2'),
    accent3: document.getElementById('colorAccent3'),
    text_dark: document.getElementById('colorTextDark'),
    text_light: document.getElementById('colorTextLight'),
    border: document.getElementById('colorBorder'),
};

const hexDisplays = {
    primary: document.getElementById('hexPrimary'),
    secondary: document.getElementById('hexSecondary'),
    accent: document.getElementById('hexAccent'),
    accent2: document.getElementById('hexAccent2'),
    accent3: document.getElementById('hexAccent3'),
    text_dark: document.getElementById('hexTextDark'),
    text_light: document.getElementById('hexTextLight'),
    border: document.getElementById('hexBorder'),
};

// Font selectors
const fontSelects = {
    font_title: document.getElementById('fontTitle'),
    font_subtitle: document.getElementById('fontSubtitle'),
    font_body: document.getElementById('fontBody'),
};

// ────────────────────────────────────────────────────────────────
// STATE
// ────────────────────────────────────────────────────────────────

let currentPdfData = null;
let currentBrandingConfig = null;
let currentLogoFile = null;

// ────────────────────────────────────────────────────────────────
// COLOR PICKER LISTENERS
// ────────────────────────────────────────────────────────────────

Object.keys(colorInputs).forEach((key) => {
    colorInputs[key].addEventListener('input', (e) => {
        const hexValue = e.target.value.toUpperCase();
        hexDisplays[key].textContent = hexValue;
    });
});

// ────────────────────────────────────────────────────────────────
// BRAND DOCUMENTS
// ────────────────────────────────────────────────────────────────

brandDocsInput.addEventListener('change', (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
        const fileList = Array.from(files).map((f) => `<div>📄 ${f.name}</div>`).join('');
        brandDocsList.innerHTML = `<div style="margin-top: var(--spacing-md); padding: var(--spacing-md); background: #F2F0ED; border-radius: 2px;">${fileList}</div>`;
    } else {
        brandDocsList.innerHTML = '';
    }
});

// ────────────────────────────────────────────────────────────────
// LOGO PREVIEW
// ────────────────────────────────────────────────────────────────

logoFile.addEventListener('change', (e) => {
    const file = e.target.files?.[0];
    if (file) {
        currentLogoFile = file;
        const reader = new FileReader();
        reader.onload = (event) => {
            logoPreview.innerHTML = `<img src="${event.target.result}" alt="Logo preview">`;
        };
        reader.readAsDataURL(file);
    } else {
        currentLogoFile = null;
        logoPreview.innerHTML = '';
    }
});

// ────────────────────────────────────────────────────────────────
// PAGE PREFERENCE — toggle header style visibility
// ────────────────────────────────────────────────────────────────

function updateHeaderStyleVisibility() {
    const pageVal = document.querySelector('input[name="pagePreference"]:checked')?.value || '2';
    const is3page = pageVal === '3';

    // Header style — disabled on 3-page
    const headerStyleRow = document.querySelector('.branding-top-row .form-row-full');
    if (headerStyleRow) {
        headerStyleRow.style.opacity = is3page ? '0.35' : '';
        headerStyleRow.style.pointerEvents = is3page ? 'none' : '';
    }

    // Pull quote section — 2-page only
    const pullQuoteSection = document.getElementById('pullQuoteSection');
    if (pullQuoteSection) {
        pullQuoteSection.style.opacity = is3page ? '0.35' : '';
        pullQuoteSection.style.pointerEvents = is3page ? 'none' : '';
        const textarea = document.getElementById('pullQuote');
        const attrInput = document.getElementById('pullQuoteAttribution');
        if (is3page) {
            if (textarea) textarea.setAttribute('disabled', '');
            if (attrInput) attrInput.setAttribute('disabled', '');
        } else {
            if (textarea) textarea.removeAttribute('disabled');
            // attribution re-enable is controlled by the quote input listener
            if (attrInput && (!textarea || textarea.value.trim().length === 0)) {
                attrInput.setAttribute('disabled', '');
                attrInput.style.setProperty('opacity', '0.4');
            }
        }
    }
}

document.querySelectorAll('input[name="pagePreference"]').forEach(radio => {
    radio.addEventListener('change', updateHeaderStyleVisibility);
});

// Run once on load to set initial state
updateHeaderStyleVisibility();

// ────────────────────────────────────────────────────────────────
// PULL QUOTE CHARACTER COUNTER
// ────────────────────────────────────────────────────────────────

document.getElementById('pullQuote')?.addEventListener('input', function () {
    document.getElementById('pullQuoteCount').textContent = this.value.length;
    const attrInput = document.getElementById('pullQuoteAttribution');
    if (this.value.trim().length > 0) {
        attrInput.removeAttribute('disabled');
        attrInput.style.removeProperty('opacity');
    } else {
        attrInput.setAttribute('disabled', '');
        attrInput.value = '';
        attrInput.style.setProperty('opacity', '0.4');
        document.getElementById('pullQuoteAttrCount').textContent = '0';
    }
});

document.getElementById('pullQuoteAttribution')?.addEventListener('input', function () {
    document.getElementById('pullQuoteAttrCount').textContent = this.value.length;
});

// ────────────────────────────────────────────────────────────────
// LOGO PREVIEW BACKGROUND — mirrors the logo bg radio selection
// ────────────────────────────────────────────────────────────────

function updateLogoPreviewBg() {
    const mode = document.querySelector('input[name="logoBgMode"]:checked')?.value || 'auto';
    if (mode === 'dark') {
        logoPreview.style.background = colorInputs.primary?.value || '#4A3453';
    } else if (mode === 'light') {
        logoPreview.style.background = colorInputs.text_light?.value || '#F9F8F6';
    } else {
        logoPreview.style.background = '';  // falls back to CSS var(--bg-pale)
    }
}

document.querySelectorAll('input[name="logoBgMode"]').forEach(radio => {
    radio.addEventListener('change', updateLogoPreviewBg);
});

// Also update preview bg when primary or text_light color changes
colorInputs.primary?.addEventListener('input', updateLogoPreviewBg);
colorInputs.text_light?.addEventListener('input', updateLogoPreviewBg);

// ────────────────────────────────────────────────────────────────
// BLOG URL AUTO-DETECTION: Company Name & Logo
// ────────────────────────────────────────────────────────────────

blogUrlInput.addEventListener('blur', async (e) => {
    const blogUrl = e.target.value.trim();
    if (!blogUrl || !blogUrl.startsWith('http')) {
        return;
    }

    try {
        const formData = new FormData();
        formData.append('blog_url', blogUrl);

        // Show loading indicator
        const blogUrlLabel = document.querySelector('label[for="blogUrl"]');
        const originalLabel = blogUrlLabel?.textContent;
        if (blogUrlLabel) blogUrlLabel.textContent = '🔍 Detecting branding...';

        const response = await fetch('/api/detect-branding', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        // Restore label
        if (blogUrlLabel && originalLabel) blogUrlLabel.textContent = originalLabel;

        if (result.status === 'success') {
            // Always replace company name and website from the new URL's detected branding
            if (result.company_name) {
                companyNameInput.value = result.company_name;
            }
            if (result.company_website) {
                companyWebsiteInput.value = result.company_website;
            }
        }
    } catch (err) {
        console.error('Branding detection error:', err);
        // Silently fail - user can still enter manually
    }
});

// ────────────────────────────────────────────────────────────────
// COMPANY WEBSITE AUTO-PROTOCOL
// ────────────────────────────────────────────────────────────────

companyWebsiteInput.addEventListener('blur', (e) => {
    let url = e.target.value.trim();
    if (url && !url.startsWith('http://') && !url.startsWith('https://')) {
        e.target.value = 'https://' + url;
    }
});

// ────────────────────────────────────────────────────────────────
// BRANDING JSON UPLOAD HANDLER
// ────────────────────────────────────────────────────────────────

brandingJsonFile.addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = async (event) => {
            try {
                const brandingConfig = JSON.parse(event.target.result);

                // If config has a logo_file_path, validate it exists
                let logoValid = true;
                if (brandingConfig.logo_file_path) {
                    try {
                        const validateResponse = await fetch('/api/validate-logo-path', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ logo_path: brandingConfig.logo_file_path })
                        });
                        const validateResult = await validateResponse.json();

                        if (validateResult.valid) {
                            // Show preview from server path — user's uploaded logo (if any) still wins
                            logoPreview.innerHTML = `<img src="file://${brandingConfig.logo_file_path}" alt="Logo" style="max-width: 100%; max-height: 100%;">`;
                        } else {
                            logoValid = false;
                            showStatus('error', `✗ Logo file not found: ${brandingConfig.logo_file_path} — please re-upload the logo.`);
                            logoPreview.innerHTML = '';
                        }
                    } catch (err) {
                        console.error('Logo validation error:', err);
                        logoValid = false;
                        showStatus('error', `✗ Could not validate logo path. Please re-upload the logo.`);
                        logoPreview.innerHTML = '';
                    }
                }
                // Note: loading JSON never clears currentLogoFile — the logo file input manages its own state.

                loadBrandingConfigToForm(brandingConfig);
                manualBrandingSection.style.removeProperty('display');

                if (logoValid || !brandingConfig.logo_file_path) {
                    showStatus('success', `✓ Branding loaded: ${brandingConfig.company_name || 'custom brand'}`);
                } else {
                    showStatus('error', `⚠ Branding loaded but logo file missing. Please re-upload the logo.`);
                }
            } catch (err) {
                showStatus('error', `✗ Invalid JSON: ${err.message}`);
            }
        };
        reader.readAsText(file);
    }
});

// ────────────────────────────────────────────────────────────────
// LOAD BRANDING CONFIG INTO FORM
// ────────────────────────────────────────────────────────────────

function loadBrandingConfigToForm(config) {
    // Handle nested format
    const colors = config.colors || config;
    const fonts = config.fonts || config;

    // Load colors
    if (colors.primary) colorInputs.primary.value = colors.primary;
    if (colors.secondary) colorInputs.secondary.value = colors.secondary;
    if (colors.accent) colorInputs.accent.value = colors.accent;
    if (colors.accent2) colorInputs.accent2.value = colors.accent2;
    if (colors.accent3) colorInputs.accent3.value = colors.accent3;
    if (colors.text_dark) colorInputs.text_dark.value = colors.text_dark;
    if (colors.text_light) colorInputs.text_light.value = colors.text_light;
    if (colors.border) colorInputs.border.value = colors.border;

    // Update hex displays
    Object.keys(hexDisplays).forEach((key) => {
        hexDisplays[key].textContent = colorInputs[key].value.toUpperCase();
    });

    // Load fonts
    if (fonts.font_title) fontSelects.font_title.value = fonts.font_title;
    if (fonts.font_subtitle) fontSelects.font_subtitle.value = fonts.font_subtitle;
    if (fonts.font_body) fontSelects.font_body.value = fonts.font_body;

    // Load company info
    if (config.company_name) companyNameInput.value = config.company_name;
    if (config.company_website) companyWebsiteInput.value = config.company_website;

    // Load header style
    if (config.header_style) {
        const hs = document.querySelector(`input[name="headerStyle"][value="${config.header_style}"]`);
        if (hs) hs.checked = true;
    }

    // Load logo bg mode
    if (config.logo_bg_mode) {
        const lbg = document.querySelector(`input[name="logoBgMode"][value="${config.logo_bg_mode}"]`);
        if (lbg) lbg.checked = true;
    }

    // Sync preview background to match whichever radio is now selected
    updateLogoPreviewBg();
}

// ────────────────────────────────────────────────────────────────
// GET BRANDING CONFIG FROM FORM
// ────────────────────────────────────────────────────────────────

function getBrandingConfigFromForm() {
    // Logo background mode: 'auto' (detect) | 'dark' | 'light'
    const logoBgMode = document.querySelector('input[name="logoBgMode"]:checked')?.value || 'auto';

    const config = {
        company_name: companyNameInput.value || '',
        company_website: companyWebsiteInput.value || '',
        colors: {
            primary: colorInputs.primary.value,
            secondary: colorInputs.secondary.value,
            accent: colorInputs.accent.value,
            accent2: colorInputs.accent2.value,
            accent3: colorInputs.accent3.value,
            text_dark: colorInputs.text_dark.value,
            text_light: colorInputs.text_light.value,
            border: colorInputs.border.value,
        },
        fonts: {
            font_title: fontSelects.font_title.value,
            font_subtitle: fontSelects.font_subtitle.value,
            font_body: fontSelects.font_body.value,
        },
    };

    // Pass the logo bg mode as a signal; 'auto' means no override
    if (logoBgMode !== 'auto') {
        config.logo_bg_mode = logoBgMode;
    }

    // Header style
    const headerStyle = document.querySelector('input[name="headerStyle"]:checked')?.value || 'geometric';
    config.header_style = headerStyle;

    return config;
}

// ────────────────────────────────────────────────────────────────
// FORM SUBMISSION
// ────────────────────────────────────────────────────────────────

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const blogUrl = blogUrlInput.value.trim();
    if (!blogUrl) {
        showStatus('error', '✗ Please enter a blog URL');
        return;
    }


    // Show loading
    loadingOverlay.classList.remove('hidden');
    statusSection.classList.add('hidden');

    try {
        // Build FormData
        const formData = new FormData();
        formData.append('blog_url', blogUrl);
        const pagePreference = document.querySelector('input[name="pagePreference"]:checked')?.value || '2';
        formData.append('page_preference', pagePreference);

        // Add brand documents if selected
        const brandDocsFiles = brandDocsInput.files;
        if (brandDocsFiles && brandDocsFiles.length > 0) {
            for (let i = 0; i < brandDocsFiles.length; i++) {
                formData.append('brand_docs', brandDocsFiles[i]);
            }
        }

        // Add logo if selected
        if (currentLogoFile) {
            formData.append('logo', currentLogoFile);
        }

        // Get branding config
        const brandingConfig = getBrandingConfigFromForm();
        formData.append('brand_config_json', JSON.stringify(brandingConfig));

        // Pull quote (optional)
        formData.append('pull_quote', document.getElementById('pullQuote')?.value?.trim() || '');
        formData.append('pull_quote_attribution', document.getElementById('pullQuoteAttribution')?.value?.trim() || '');

        // API call
        const response = await fetch('/api/generate', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'API error');
        }

        const result = await response.json();

        // Store for download
        currentPdfData = result;
        currentBrandingConfig = brandingConfig;

        // Show success
        loadingOverlay.classList.add('hidden');
        showSuccess(result, pagePreference);
    } catch (err) {
        loadingOverlay.classList.add('hidden');
        showStatus('error', `✗ ${err.message}`);
    }
});

// ────────────────────────────────────────────────────────────────
// RESET BUTTON HANDLER
// ────────────────────────────────────────────────────────────────

const resetButton = form.querySelector('button[type="reset"]');
if (resetButton) {
    resetButton.addEventListener('click', (e) => {
        e.preventDefault();
        resetForm();
    });
}

// ────────────────────────────────────────────────────────────────
// RUN BOTH BUTTON — generate 2-page and 3-page in parallel
// ────────────────────────────────────────────────────────────────

let bothPdfData = null;

const runBothBtn = document.getElementById('runBothBtn');
if (runBothBtn) {
    runBothBtn.addEventListener('click', async () => {
        const blogUrl = blogUrlInput.value.trim();
        if (!blogUrl) {
            showStatus('error', '✗ Please enter a blog URL');
            return;
        }

        loadingOverlay.classList.remove('hidden');
        document.querySelector('#loadingOverlay p').textContent = 'Generating both PDFs…';
        statusSection.classList.add('hidden');

        const buildFormData = (pagePreference) => {
            const fd = new FormData();
            fd.append('blog_url', blogUrl);
            fd.append('page_preference', pagePreference);
            const brandDocsFiles = brandDocsInput.files;
            if (brandDocsFiles && brandDocsFiles.length > 0) {
                for (let i = 0; i < brandDocsFiles.length; i++) fd.append('brand_docs', brandDocsFiles[i]);
            }
            if (currentLogoFile) fd.append('logo', currentLogoFile);
            fd.append('brand_config_json', JSON.stringify(getBrandingConfigFromForm()));
            return fd;
        };

        try {
            const [res2, res3] = await Promise.all([
                fetch('/api/generate', { method: 'POST', body: buildFormData('2') }),
                fetch('/api/generate', { method: 'POST', body: buildFormData('3') }),
            ]);

            if (!res2.ok) throw new Error((await res2.json()).detail || '2-page generation failed');
            if (!res3.ok) throw new Error((await res3.json()).detail || '3-page generation failed');

            const [result2, result3] = await Promise.all([res2.json(), res3.json()]);
            bothPdfData = { two: result2, three: result3 };
            currentBrandingConfig = getBrandingConfigFromForm();

            loadingOverlay.classList.add('hidden');
            document.querySelector('#loadingOverlay p').textContent = 'Generating your PDF...';
            showBothSuccess(result2, result3);
        } catch (err) {
            loadingOverlay.classList.add('hidden');
            document.querySelector('#loadingOverlay p').textContent = 'Generating your PDF...';
            showStatus('error', `✗ ${err.message}`);
        }
    });
}

function showBothSuccess(result2, result3) {
    const html = `
        <div class="status-success">
            <h3>✓ Both PDFs Generated!</h3>
            <p style="margin: var(--spacing-lg) 0;">
                <strong>${result2.extracted.title}</strong>
            </p>
            <div style="display: flex; gap: var(--spacing-md); flex-wrap: wrap; margin-bottom: var(--spacing-sm);">
                <button class="btn btn-primary" onclick="downloadBothPdf('2')"><img src="/static/assets/history_edu.svg" class="btn-svg-icon" alt=""> Download 2-Page</button>
                <button class="btn btn-primary" onclick="downloadBothPdf('3')"><img src="/static/assets/history_edu.svg" class="btn-svg-icon" alt=""> Download 3-Page</button>
            </div>
            <div style="display: flex; gap: var(--spacing-md); flex-wrap: wrap;">
                <button class="btn btn-secondary" onclick="downloadBrandingJson()"><img src="/static/assets/save_branding.svg" class="btn-svg-icon btn-svg-icon--dark" alt=""> Save Branding</button>
                <button class="btn btn-secondary" onclick="resetForm()"><img src="/static/assets/potted_plant.svg" class="btn-svg-icon btn-svg-icon--dark" alt=""> New Brief</button>
            </div>
        </div>
    `;
    statusContent.innerHTML = html;
    statusSection.classList.remove('hidden');
}

function downloadBothPdf(which) {
    if (!bothPdfData) return;
    const data = which === '2' ? bothPdfData.two : bothPdfData.three;
    const link = document.createElement('a');
    link.href = `data:application/pdf;base64,${data.pdf_b64}`;
    link.download = data.filename;
    link.click();
}

// ────────────────────────────────────────────────────────────────
// SHOW SUCCESS
// ────────────────────────────────────────────────────────────────

function showSuccess(result, pagePreference) {
    const pageLabel = pagePreference === '3' ? '3-Page' : '2-Page';
    const html = `
        <div class="status-success">
            <h3>✓ ${pageLabel} PDF Generated Successfully!</h3>
            <p style="margin: var(--spacing-lg) 0;">
                <strong>${result.extracted.title}</strong><br>
                Pages: ${pageLabel} • Size: ${(result.pdf_b64.length / 1024 / 1024).toFixed(2)} MB
            </p>
            <div style="display: flex; gap: var(--spacing-md); flex-wrap: wrap; margin-bottom: var(--spacing-sm);">
                <button class="btn btn-primary" onclick="downloadPdf()">
                    <img src="/static/assets/history_edu.svg" class="btn-svg-icon" alt=""> Download PDF
                </button>
            </div>
            <div style="display: flex; gap: var(--spacing-md); flex-wrap: wrap;">
                <button class="btn btn-secondary" onclick="downloadBrandingJson()">
                    <img src="/static/assets/save_branding.svg" class="btn-svg-icon btn-svg-icon--dark" alt=""> Save Branding
                </button>
                <button class="btn btn-secondary" onclick="resetForm()">
                    <img src="/static/assets/potted_plant.svg" class="btn-svg-icon btn-svg-icon--dark" alt=""> New Brief
                </button>
            </div>
        </div>
    `;
    statusContent.innerHTML = html;
    statusSection.classList.remove('hidden');
}

// ────────────────────────────────────────────────────────────────
// DOWNLOAD PDF
// ────────────────────────────────────────────────────────────────

function downloadPdf() {
    if (!currentPdfData) return;

    const link = document.createElement('a');
    link.href = `data:application/pdf;base64,${currentPdfData.pdf_b64}`;
    link.download = currentPdfData.filename;
    link.click();
}

// ────────────────────────────────────────────────────────────────
// DOWNLOAD BRANDING JSON
// ────────────────────────────────────────────────────────────────

function downloadBrandingJson() {
    if (!currentBrandingConfig) return;

    const json = JSON.stringify(currentBrandingConfig, null, 2);
    const link = document.createElement('a');
    link.href = `data:application/json;base64,${btoa(json)}`;
    link.download = 'branding.json';
    link.click();
}

// ────────────────────────────────────────────────────────────────
// RESET FORM
// ────────────────────────────────────────────────────────────────

function resetForm() {
    form.reset();
    currentPdfData = null;
    currentBrandingConfig = null;
    currentLogoFile = null;
    logoPreview.innerHTML = '';
    manualBrandingSection.style.removeProperty('display');
    statusSection.classList.add('hidden');

    // Clear all file inputs and their display areas
    // form.reset() clears values but doesn't update the visible file list divs
    document.querySelectorAll('input[type="file"]').forEach(input => {
        input.value = '';
    });
    brandDocsList.innerHTML = '';

    // Reset color displays
    Object.keys(hexDisplays).forEach((key) => {
        hexDisplays[key].textContent = colorInputs[key].value.toUpperCase();
    });

    // Reset pull quote counters and attribution state
    document.getElementById('pullQuoteCount').textContent = '0';
    document.getElementById('pullQuoteAttrCount').textContent = '0';
    const attrInput = document.getElementById('pullQuoteAttribution');
    if (attrInput) {
        attrInput.setAttribute('disabled', '');
        attrInput.style.setProperty('opacity', '0.4');
    }
}

// ────────────────────────────────────────────────────────────────
// STATUS MESSAGES
// ────────────────────────────────────────────────────────────────

function showStatus(type, message) {
    const className = type === 'success' ? 'status-success' : 'status-error';
    statusContent.innerHTML = `<div class="${className}">${message}</div>`;
    statusSection.classList.remove('hidden');
    loadingOverlay.classList.add('hidden');
}

// ────────────────────────────────────────────────────────────────
// INIT
// ────────────────────────────────────────────────────────────────
updateLogoPreviewBg();

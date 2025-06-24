class ScreenTranslatorApp {
    constructor() {
        this.ws = null;
        this.isMonitoring = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.translations = new Map();
        
        this.initWebSocket();
        this.initEventListeners();
        this.loadInitialData();
    }

    initWebSocket() {
        const wsUrl = `ws://${window.location.host}/ws`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
        };

        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleWebSocketMessage(message);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.attemptReconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            setTimeout(() => this.initWebSocket(), 2000 * this.reconnectAttempts);
        }
    }

    handleWebSocketMessage(message) {
        switch (message.type) {
            case 'translation_result':
                this.addTranslationResult(message.data);
                break;
            case 'status_update':
                this.updateStatus(message.data);
                break;
            case 'error':
                this.showError(message.data.error, message.data.detail);
                break;
            case 'task_progress':
                this.updateTaskProgress(message.data);
                break;
        }
    }

    async loadInitialData() {
        try {
            // Load current status
            try {
                const statusResponse = await fetch('/api/status');
                if (!statusResponse.ok) {
                    throw new Error(`Status API returned ${statusResponse.status}: ${await statusResponse.text()}`);
                }
                const status = await statusResponse.json();
                this.updateStatus(status);
            } catch (statusError) {
                console.error('Failed to load status:', statusError);
                // Continue with other data loading even if status fails
            }

            // Load existing results
            try {
                const resultsResponse = await fetch('/api/results');
                if (!resultsResponse.ok) {
                    throw new Error(`Results API returned ${resultsResponse.status}`);
                }
                const results = await resultsResponse.json();
                if (Array.isArray(results)) {
                    results.forEach(result => this.addTranslationResult(result));
                } else {
                    console.error('Results is not an array:', results);
                }
            } catch (resultsError) {
                console.error('Failed to load results:', resultsError);
                // Show empty state if results fail to load
                this.showEmptyState();
            }

            // Load windows
            try {
                await this.loadWindows();
            } catch (windowsError) {
                console.error('Failed to load windows:', windowsError);
            }
        } catch (error) {
            this.showError('Failed to load initial data', error.message);
        }
    }

    async loadWindows() {
        try {
            const response = await fetch('/api/windows');
            const data = await response.json();
            this.populateWindowDropdown(data.windows);
        } catch (error) {
            console.error('Failed to load windows:', error);
        }
    }

    populateWindowDropdown(windows) {
        const dropdown = document.getElementById('windowDropdown');
        dropdown.innerHTML = '';

        // Add full screen option
        const fullScreenOption = document.createElement('a');
        fullScreenOption.href = '#';
        fullScreenOption.textContent = 'Full Screen';
        fullScreenOption.onclick = () => this.selectWindow(null, 'Full Screen');
        dropdown.appendChild(fullScreenOption);

        // Add separator
        const separator = document.createElement('div');
        separator.style.borderTop = '1px solid var(--border)';
        separator.style.margin = '8px 0';
        dropdown.appendChild(separator);

        // Add windows
        windows.forEach(window => {
            if (window.title.trim()) {
                const option = document.createElement('a');
                option.href = '#';
                option.textContent = window.title;
                option.onclick = () => this.selectWindow(window.hwnd, window.title);
                dropdown.appendChild(option);
            }
        });
    }

    async selectWindow(hwnd, title) {
        try {
            await fetch('/api/window/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hwnd, title })
            });
            this.closeDropdown();
        } catch (error) {
            this.showError('Failed to select window', error.message);
        }
    }

    updateStatus(status) {
        // Update status badge
        const statusBadge = document.getElementById('statusBadge');
        statusBadge.className = `status-badge status-${status.status}`;
        statusBadge.textContent = status.status.charAt(0).toUpperCase() + status.status.slice(1);

        // Update selected window
        const selectedWindow = document.getElementById('selectedWindow');
        if (status.selected_window) {
            selectedWindow.textContent = `Monitoring: ${status.selected_window.title}`;
            document.getElementById('appTitle').textContent = `Screen Translator - ${status.selected_window.title}`;
        } else {
            selectedWindow.textContent = 'No program selected';
            document.getElementById('appTitle').textContent = 'Screen Translator';
        }

        // Update translation count
        document.getElementById('translationCount').textContent = `${status.translation_count} translations`;

        // Update toggle button
        const toggleBtn = document.getElementById('toggleBtn');
        if (status.monitoring_paused) {
            toggleBtn.textContent = '▶ Start';
            toggleBtn.className = 'btn btn-success';
            this.isMonitoring = false;
        } else {
            toggleBtn.textContent = '⏸ Pause';
            toggleBtn.className = 'btn btn-secondary';
            this.isMonitoring = true;
        }

        // Update task progress
        this.updateTaskProgress(status.task_state);
    }

    updateTaskProgress(taskState) {
        const progressElement = document.getElementById('taskProgress');
        if (taskState.is_running) {
            progressElement.innerHTML = `
                <span>Processing... ${taskState.elapsed_time.toFixed(1)}s</span>
                <div class="processing-indicator"></div>
            `;
        } else {
            progressElement.innerHTML = '';
        }
    }

    addTranslationResult(result) {
        const isNew = !this.translations.has(result.id);
        this.translations.set(result.id, result);
        
        const container = document.getElementById('resultsContainer');
        
        // Remove empty state if it exists
        const emptyState = container.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        // Check if this is an update to an existing translation
        if (!isNew) {
            // Find the existing box
            const existingBox = container.querySelector(`[data-translation-id="${result.id}"]`);
            if (existingBox) {
                // Update just the content
                const contentDiv = existingBox.querySelector('.translation-content');
                contentDiv.innerHTML = this.escapeHtml(result.translation);
                
                // Update the timestamp and processing time
                const timestampDiv = existingBox.querySelector('.translation-timestamp');
                timestampDiv.innerHTML = `
                    ${new Date(result.timestamp).toLocaleTimeString()}
                    ${result.processing_time ? `(${result.processing_time.toFixed(1)}s)` : ''}
                    ${result.is_streaming ? 
                        `<span class="streaming-indicator">${result.stage === 'ocr' ? 'Running OCR...' : 'Translating...'}</span>` 
                        : ''}
                `;
                
                // Add or remove streaming class
                if (result.is_streaming) {
                    existingBox.classList.add('streaming');
                } else {
                    existingBox.classList.remove('streaming');
                }
                
                return;
            }
        }
        
        // Create new translation box for new translations
        const box = document.createElement('div');
        box.className = `translation-box ${result.is_streaming ? 'streaming' : ''}`;
        box.setAttribute('data-translation-id', result.id);
        box.innerHTML = `
            <div class="translation-header">
                <div class="translation-timestamp">
                    ${new Date(result.timestamp).toLocaleTimeString()}
                    ${result.processing_time ? `(${result.processing_time.toFixed(1)}s)` : ''}
                    ${result.is_streaming ? 
                        `<span class="streaming-indicator">${result.stage === 'ocr' ? 'Running OCR...' : 'Translating...'}</span>` 
                        : ''}
                </div>
                <div class="translation-actions">
                    <button class="btn btn-secondary btn-icon" onclick="app.copyTranslation('${result.id}')" title="Copy">
                        📋
                    </button>
                    <button class="btn btn-danger btn-icon" onclick="app.deleteTranslation('${result.id}')" title="Delete">
                        🗑️
                    </button>
                </div>
            </div>
            <div class="translation-content">${this.escapeHtml(result.translation)}</div>
        `;

        // Add to top of container
        container.insertBefore(box, container.firstChild);

        // Scroll to top
        container.scrollTop = 0;
    }

    async copyTranslation(id) {
        const result = this.translations.get(id);
        if (result) {
            try {
                await navigator.clipboard.writeText(result.translation);
                this.showSuccess('Translation copied to clipboard');
            } catch (error) {
                this.showError('Failed to copy translation', error.message);
            }
        }
    }

    async deleteTranslation(id) {
        try {
            await fetch(`/api/results/${id}`, { method: 'DELETE' });
            this.translations.delete(id);
            
            // Remove from DOM
            const boxes = document.querySelectorAll('.translation-box');
            boxes.forEach(box => {
                const deleteBtn = box.querySelector(`[onclick="app.deleteTranslation('${id}')"]`);
                if (deleteBtn) {
                    box.remove();
                }
            });

            // Show empty state if no translations left
            if (this.translations.size === 0) {
                this.showEmptyState();
            }
        } catch (error) {
            this.showError('Failed to delete translation', error.message);
        }
    }

    showEmptyState() {
        const container = document.getElementById('resultsContainer');
        container.innerHTML = `
            <div class="empty-state">
                <h3>No translations yet</h3>
                <p>Select a program and start monitoring to see translations here</p>
            </div>
        `;
    }

    async toggleMonitoring() {
        try {
            const action = this.isMonitoring ? 'pause' : 'start';
            await fetch('/api/monitor/control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action })
            });
        } catch (error) {
            this.showError('Failed to toggle monitoring', error.message);
        }
    }

    async forceTranslation() {
        try {
            await fetch('/api/translate/force', { method: 'POST' });
        } catch (error) {
            this.showError('Failed to force translation', error.message);
        }
    }

    async stopTask() {
        try {
            await fetch('/api/task/stop', { method: 'POST' });
        } catch (error) {
            this.showError('Failed to stop task', error.message);
        }
    }

    async resetCache() {
        try {
            await fetch('/api/cache/reset', { method: 'POST' });
            this.showSuccess('Cache reset successfully');
        } catch (error) {
            this.showError('Failed to reset cache', error.message);
        }
    }

    async clearResults() {
        try {
            await fetch('/api/results', { method: 'DELETE' });
            this.translations.clear();
            this.showEmptyState();
            this.showSuccess('Results cleared successfully');
        } catch (error) {
            this.showError('Failed to clear results', error.message);
        }
    }

    initEventListeners() {
        // Settings form sliders
        const sliders = ['checkInterval', 'similarityThreshold', 'timeout'];
        sliders.forEach(id => {
            const slider = document.getElementById(id);
            const valueSpan = document.getElementById(id + 'Value');
            slider.addEventListener('input', () => {
                valueSpan.textContent = slider.value;
            });
        });

        // Settings form submission
        document.getElementById('settingsForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.saveSettings();
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            const dropdown = document.getElementById('windowDropdown');
            const selectButton = document.querySelector('[onclick*="toggleWindowDropdown"]');
            if (!dropdown.contains(e.target) && !selectButton.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });
        
    }

    async loadModelOptions() {
        try {
            // Load OCR models
            const ocrResponse = await fetch('/api/models/ocr');
            const ocrData = await ocrResponse.json();
            
            const ocrSelect = document.getElementById('ocrModel');
            ocrSelect.innerHTML = '';
            
            // Check if we have a models array in the response
            const ocrModels = ocrData.models || [];
            if (Array.isArray(ocrModels)) {
                ocrModels.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = `${model.id} (${model.type})`;
                    ocrSelect.appendChild(option);
                });
            } else {
                console.error('OCR models response is not an array:', ocrModels);
                ocrSelect.innerHTML = '<option value="">No models available</option>';
            }
            
            // Load translation models
            const translationResponse = await fetch('/api/models/translation');
            const translationData = await translationResponse.json();
            
            const translationSelect = document.getElementById('translationModel');
            translationSelect.innerHTML = '';
            
            // Check if we have a models array in the response
            const translationModels = translationData.models || [];
            if (Array.isArray(translationModels)) {
                translationModels.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = `${model.id} (${model.type})`;
                    translationSelect.appendChild(option);
                });
            } else {
                console.error('Translation models response is not an array:', translationModels);
                translationSelect.innerHTML = '<option value="">No models available</option>';
            }
            
            // Load current model settings
            try {
                const settingsResponse = await fetch('/api/models/settings');
                if (!settingsResponse.ok) {
                    throw new Error(`Model settings API returned ${settingsResponse.status}`);
                }
                const modelSettings = await settingsResponse.json();
                
                if (modelSettings.ocr_model_id) {
                    document.getElementById('ocrModel').value = modelSettings.ocr_model_id;
                }
                
                if (modelSettings.translation_model_id) {
                    document.getElementById('translationModel').value = modelSettings.translation_model_id;
                }
            } catch (settingsError) {
                console.error('Failed to load model settings:', settingsError);
                // Continue without setting model values
            }
        } catch (error) {
            this.showError('Failed to load model options', error.message);
        }
    }


    async loadSettings() {
        try {
            const response = await fetch('/api/settings');
            const settings = await response.json();
            
            document.getElementById('checkInterval').value = settings.check_interval;
            document.getElementById('checkIntervalValue').textContent = settings.check_interval;
            
            document.getElementById('similarityThreshold').value = settings.similarity_threshold;
            document.getElementById('similarityThresholdValue').textContent = settings.similarity_threshold;
            
            document.getElementById('timeout').value = settings.timeout;
            document.getElementById('timeoutValue').textContent = settings.timeout;
            
            // Load model options
            await this.loadModelOptions();
        } catch (error) {
            this.showError('Failed to load settings', error.message);
        }
    }

    async saveSettings() {
        try {
            const settings = {
                check_interval: parseInt(document.getElementById('checkInterval').value),
                similarity_threshold: parseFloat(document.getElementById('similarityThreshold').value),
                timeout: parseInt(document.getElementById('timeout').value)
            };

            await fetch('/api/settings', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            
            // Save model settings separately
            const modelSettings = {
                ocr_model_id: document.getElementById('ocrModel').value,
                translation_model_id: document.getElementById('translationModel').value
            };
            
            await fetch('/api/models/settings', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(modelSettings)
            });

            closeSettings(); // Use global function instead of this.closeSettings()
            this.showSuccess('Settings saved successfully');
        } catch (error) {
            this.showError('Failed to save settings', error.message);
        }
    }

    toggleWindowDropdown(event) {
        event.stopPropagation();
        const button = event.currentTarget;
        const dropdown = document.getElementById('windowDropdown');

        // If already open, close it
        if (dropdown.style.display === 'block') {
            dropdown.style.display = 'none';
            return;
        }

        // Populate windows
        this.loadWindows();

        // Position the dropdown
        const rect = button.getBoundingClientRect();
        dropdown.style.display = 'block';
        dropdown.style.left = rect.left + 'px';
        dropdown.style.top = (rect.bottom + 4) + 'px';
        dropdown.style.minWidth = Math.max(rect.width, 250) + 'px';
        dropdown.style.position = 'fixed';

        // Close when clicking outside
        document.addEventListener('click', function handler(e) {
            if (!dropdown.contains(e.target)) {
                dropdown.style.display = 'none';
                document.removeEventListener('click', handler);
            }
        });
    }

    closeDropdown() {
        const dropdown = document.getElementById('windowDropdown');
        dropdown.style.display = 'none';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showError(message, detail = '') {
        console.error('Error:', message, detail);
        // You could implement a toast notification system here
        alert(`Error: ${message}${detail ? '\n' + detail : ''}`);
    }

    showSuccess(message) {
        console.log('Success:', message);
        // You could implement a toast notification system here
    }
}

// Global functions for onclick handlers
function openSettings() {
    app.loadSettings();
    document.getElementById('settingsModal').style.display = 'block';
}

function closeSettings() {
    document.getElementById('settingsModal').style.display = 'none';
}

function toggleWindowDropdown(event) {
    app.toggleWindowDropdown(event);
}

function toggleMonitoring() {
    app.toggleMonitoring();
}

function forceTranslation() {
    app.forceTranslation();
}

function stopTask() {
    app.stopTask();
}

function resetCache() {
    app.resetCache();
}

function clearResults() {
    app.clearResults();
}

// Initialize app
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new ScreenTranslatorApp();
});

/**
 * WhisperDesk Studio Pro — Application Engine
 * Minimalist, high-precision audio transcription & executive AI meeting minutes.
 */

document.addEventListener('DOMContentLoaded', () => {
    // =========================================================================
    // 1. STATE & REFERENCES
    // =========================================================================
    const state = {
        currentFile: null,
        uploadedFilePath: null,
        mediaUrl: null,
        isProcessing: false,
        eventSource: null,
        timerInterval: null,
        startTime: 0,
        
        // Transcription Data
        activeResult: null,
        activeSegments: [],
        activeSummary: null,
        activeWorkspaceTab: 'speakers', // 'speakers', 'plain', 'acta'
        activeMainView: 'studio',       // 'studio', 'history', 'actas', 'settings', 'help'
        activeProject: '',
        hardwareData: null,
        
        // Audio Player
        isPlaying: false,
        playbackRate: 1.0,

        // History items cache
        historyItems: []
    };

    // DOM Elements Cache
    const el = {
        // Rail Navigation
        navStudio: document.getElementById('nav-studio'),
        navHistory: document.getElementById('nav-history'),
        navActas: document.getElementById('nav-actas'),
        navSettings: document.getElementById('nav-settings'),
        navHelp: document.getElementById('nav-help'),
        
        // Main Views
        viewStudio: document.getElementById('view-studio'),
        viewHistory: document.getElementById('view-history'),
        viewActas: document.getElementById('view-actas'),
        viewSettings: document.getElementById('view-settings'),
        viewHelp: document.getElementById('view-help'),

        // Global Drag Overlay
        globalDragOverlay: document.getElementById('global-drag-overlay'),

        // Topbar
        activeSessionName: document.getElementById('active-session-name'),
        cudaStatusBadge: document.getElementById('cuda-status-badge'),
        cudaStatusText: document.getElementById('cuda-status-text'),
        ollamaStatusBadge: document.getElementById('ollama-status-badge'),
        ollamaStatusText: document.getElementById('ollama-status-text'),
        ollamaDot: document.getElementById('ollama-dot'),
        btnQuickConnectOllama: document.getElementById('btn-quick-connect-ollama'),
        projectSelector: document.getElementById('project-selector'),
        btnNewProject: document.getElementById('btn-new-project'),

        // Sidebar Controls
        tabLocal: document.getElementById('tab-local'),
        tabYoutube: document.getElementById('tab-youtube'),
        localUploadBox: document.getElementById('local-upload-box'),
        youtubeUploadBox: document.getElementById('youtube-upload-box'),
        dropZone: document.getElementById('drop-zone'),
        fileInput: document.getElementById('file-input'),
        uploadProgressCard: document.getElementById('upload-progress-card'),
        uploadStatusTitle: document.getElementById('upload-status-title'),
        uploadPercentage: document.getElementById('upload-percentage'),
        uploadBarFill: document.getElementById('upload-bar-fill'),
        uploadBytesText: document.getElementById('upload-bytes-text'),
        uploadSpeedText: document.getElementById('upload-speed-text'),
        fileLoadedCard: document.getElementById('file-loaded-card'),
        fileLoadedName: document.getElementById('file-loaded-name'),
        fileLoadedMeta: document.getElementById('file-loaded-meta'),
        btnRemoveFile: document.getElementById('btn-remove-file'),
        uploadErrorCard: document.getElementById('upload-error-card'),
        uploadErrorMsg: document.getElementById('upload-error-msg'),
        btnRetryUpload: document.getElementById('btn-retry-upload'),
        ytUrlInput: document.getElementById('yt-url-input'),
        btnFetchYt: document.getElementById('btn-fetch-yt'),
        customSessionName: document.getElementById('custom-session-name'),
        whisperModelSelect: document.getElementById('whisper-model-select'),
        languageSelect: document.getElementById('language-select'),
        progressCard: document.getElementById('progress-card'),
        progressStatusText: document.getElementById('progress-status-text'),
        progressTimeCounter: document.getElementById('progress-time-counter'),
        progressBarFill: document.getElementById('progress-bar-fill'),
        progressPercentage: document.getElementById('progress-percentage'),
        btnCancelProcess: document.getElementById('btn-cancel-process'),
        btnStartTranscription: document.getElementById('btn-start-transcription'),

        // Audio Player
        nativeAudio: document.getElementById('native-audio'),
        btnPlayPause: document.getElementById('btn-play-pause'),
        iconPlay: document.getElementById('icon-play'),
        iconPause: document.getElementById('icon-pause'),
        playerCurrentTime: document.getElementById('player-current-time'),
        playerDurationTime: document.getElementById('player-duration-time'),
        playerScrubber: document.getElementById('player-scrubber'),
        playerProgressFill: document.getElementById('player-progress-fill'),
        btnSpeedToggle: document.getElementById('btn-speed-toggle'),
        btnVolumeMute: document.getElementById('btn-volume-mute'),

        // Workspace Toolbar & Views
        btnViewSpeakers: document.getElementById('btn-view-speakers'),
        btnViewPlain: document.getElementById('btn-view-plain'),
        btnViewActa: document.getElementById('btn-view-acta'),
        ollamaModelSelect: document.getElementById('ollama-model-select'),
        btnGenerateActa: document.getElementById('btn-generate-acta'),
        btnCopyAll: document.getElementById('btn-copy-all'),
        btnExportDropdown: document.getElementById('btn-export-dropdown'),
        exportMenu: document.getElementById('export-menu'),
        
        workspaceEmpty: document.getElementById('workspace-empty'),
        viewSpeakersFeed: document.getElementById('view-speakers-feed'),
        viewPlainText: document.getElementById('view-plain-text'),
        viewActaContainer: document.getElementById('view-acta-container'),

        // Full History View
        fullHistoryGrid: document.getElementById('full-history-grid'),
        fullHistoryEmpty: document.getElementById('full-history-empty'),
        historySearchInput: document.getElementById('history-search-input'),
        btnRefreshHistory: document.getElementById('btn-refresh-history'),

        // Full Actas View
        fullActaPlaceholder: document.getElementById('full-acta-placeholder'),
        fullActaRendered: document.getElementById('full-acta-rendered'),
        btnCopyFullActa: document.getElementById('btn-copy-full-acta'),
        btnDownloadFullActa: document.getElementById('btn-download-full-acta'),

        // Settings View
        cfgGpuName: document.getElementById('cfg-gpu-name'),
        cfgVramVal: document.getElementById('cfg-vram-val'),
        cfgOllamaStatus: document.getElementById('cfg-ollama-status'),
        cfgOllamaModelsCount: document.getElementById('cfg-ollama-models-count'),
        btnCfgTestOllama: document.getElementById('btn-cfg-test-ollama'),
        btnCfgOpenOutput: document.getElementById('btn-cfg-open-output'),
        btnCfgCleanTemp: document.getElementById('btn-cfg-clean-temp'),
        cfgOutputPath: document.getElementById('cfg-output-path'),
        btnCfgChangeOutput: document.getElementById('btn-cfg-change-output'),
        btnCfgResetOutput: document.getElementById('btn-cfg-reset-output'),

        // Modal & Toast
        modalOverlay: document.getElementById('modal-overlay'),
        modalTitle: document.getElementById('modal-title'),
        modalInput: document.getElementById('modal-input'),
        modalClose: document.getElementById('modal-close'),
        modalCancel: document.getElementById('modal-cancel'),
        modalConfirm: document.getElementById('modal-confirm'),
        toastContainer: document.getElementById('toast-container')
    };

    let modalCallback = null;

    // =========================================================================
    // 2. INITIALIZATION
    // =========================================================================
    init();

    function init() {
        setupEventListeners();
        fetchAppSettings();
        fetchProjects();
        fetchHistory();
        fetchHardwareStatus();
    }

    function setupEventListeners() {
        // --- A) Left Rail Navigation Tabs (Dedicated Full Views) ---
        el.navStudio?.addEventListener('click', () => switchMainView('studio'));
        el.navHistory?.addEventListener('click', () => switchMainView('history'));
        el.navActas?.addEventListener('click', () => switchMainView('actas'));
        el.navSettings?.addEventListener('click', () => switchMainView('settings'));
        el.navHelp?.addEventListener('click', () => switchMainView('help'));

        // --- B) Source Switcher (Archivo Local / YouTube) ---
        el.tabLocal?.addEventListener('click', () => setSourceMode('local'));
        el.tabYoutube?.addEventListener('click', () => setSourceMode('youtube'));

        // --- C) Global Window & Dropzone Drag & Drop ---
        let dragCounter = 0;
        window.addEventListener('dragenter', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragCounter++;
            if (el.globalDragOverlay) {
                el.globalDragOverlay.classList.remove('hidden');
                el.globalDragOverlay.classList.add('active');
            }
        });

        window.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragCounter--;
            if (dragCounter <= 0) {
                dragCounter = 0;
                if (el.globalDragOverlay) {
                    el.globalDragOverlay.classList.add('hidden');
                    el.globalDragOverlay.classList.remove('active');
                }
            }
        });

        window.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
        });

        window.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragCounter = 0;
            if (el.globalDragOverlay) {
                el.globalDragOverlay.classList.add('hidden');
                el.globalDragOverlay.classList.remove('active');
            }
            const files = e.dataTransfer?.files;
            if (files && files.length > 0) {
                setSourceMode('local');
                switchMainView('studio');
                handleDroppedFiles(files);
            }
        });

        el.dropZone?.addEventListener('dragover', handleDragOver);
        el.dropZone?.addEventListener('dragleave', handleDragLeave);
        el.dropZone?.addEventListener('drop', handleDrop);
        el.dropZone?.addEventListener('click', openNativeFilePicker);
        el.fileInput?.addEventListener('change', handleFileSelected);
        el.btnRemoveFile?.addEventListener('click', clearLoadedFile);
        el.btnRetryUpload?.addEventListener('click', openNativeFilePicker);

        // --- D) YouTube Extractor ---
        el.btnFetchYt?.addEventListener('click', handleFetchYouTube);
        el.ytUrlInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') handleFetchYouTube();
        });

        // --- E) Transcription Start, Cancel & Format Selection ---
        document.querySelectorAll('.format-pill').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.format-pill').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const fmt = btn.getAttribute('data-fmt') || 'txt';
                const hiddenInput = document.getElementById('selected-out-format');
                if (hiddenInput) hiddenInput.value = fmt;
            });
        });
        el.btnStartTranscription?.addEventListener('click', startTranscription);
        el.btnCancelProcess?.addEventListener('click', cancelTranscription);

        // --- F) Audio Player Controls ---
        el.btnPlayPause?.addEventListener('click', toggleAudioPlay);
        el.nativeAudio?.addEventListener('timeupdate', updateAudioProgress);
        el.nativeAudio?.addEventListener('loadedmetadata', updateAudioDuration);
        el.nativeAudio?.addEventListener('ended', onAudioEnded);
        el.playerScrubber?.addEventListener('input', handleAudioSeek);
        el.btnSpeedToggle?.addEventListener('click', cyclePlaybackSpeed);
        el.btnVolumeMute?.addEventListener('click', toggleAudioMute);

        // --- G) Studio Workspace Tabs (Hablantes / Texto Limpio / Acta) ---
        el.btnViewSpeakers?.addEventListener('click', () => switchWorkspaceView('speakers'));
        el.btnViewPlain?.addEventListener('click', () => switchWorkspaceView('plain'));
        el.btnViewActa?.addEventListener('click', () => switchWorkspaceView('acta'));

        // --- H) AI Acta Generator & Ollama Connect ---
        el.btnGenerateActa?.addEventListener('click', handleGenerateActa);
        el.btnQuickConnectOllama?.addEventListener('click', startOllamaService);
        el.ollamaStatusBadge?.addEventListener('click', () => switchMainView('settings'));
        el.cudaStatusBadge?.addEventListener('click', () => switchMainView('settings'));

        // --- I) Copy & Export Dropdown ---
        el.btnCopyAll?.addEventListener('click', copyAllTranscript);
        el.btnExportDropdown?.addEventListener('click', (e) => {
            e.stopPropagation();
            el.exportMenu.classList.toggle('hidden');
        });
        document.addEventListener('click', () => el.exportMenu?.classList.add('hidden'));
        document.querySelectorAll('.export-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const fmt = e.currentTarget.getAttribute('data-fmt');
                exportDocument(fmt);
            });
        });

        // --- J) Project Selector & Modals ---
        el.projectSelector?.addEventListener('change', (e) => {
            state.activeProject = e.target.value;
            fetchHistory();
        });
        el.btnNewProject?.addEventListener('click', showNewProjectModal);
        el.modalClose?.addEventListener('click', closeModal);
        el.modalCancel?.addEventListener('click', closeModal);
        el.modalConfirm?.addEventListener('click', handleModalConfirm);

        // --- K) Settings View Actions ---
        el.btnCfgTestOllama?.addEventListener('click', () => fetchHardwareStatus(true));
        el.btnCfgOpenOutput?.addEventListener('click', () => openFolderInExplorer('output'));
        el.btnCfgCleanTemp?.addEventListener('click', handleCleanTempFiles);
        el.btnCfgChangeOutput?.addEventListener('click', handleChangeOutputFolder);
        el.btnCfgResetOutput?.addEventListener('click', handleResetOutputFolder);

        // --- L) History Search & Refresh ---
        el.historySearchInput?.addEventListener('input', filterHistoryView);
        el.btnRefreshHistory?.addEventListener('click', () => fetchHistory(true));

        // --- M) Actas View Actions ---
        el.btnCopyFullActa?.addEventListener('click', () => {
            if (state.activeSummary) {
                navigator.clipboard.writeText(state.activeSummary);
                showToast('Acta copiada al portapapeles', 'success');
            } else {
                showToast('No hay acta disponible para copiar', 'error');
            }
        });
        el.btnDownloadFullActa?.addEventListener('click', () => exportDocument('md'));
    }

    // =========================================================================
    // 3. FULL VIEW NAVIGATION (RAIL TABS)
    // =========================================================================
    function switchMainView(viewName) {
        state.activeMainView = viewName;

        // Update Rail Buttons Active State
        const railMap = {
            'studio': el.navStudio,
            'history': el.navHistory,
            'actas': el.navActas,
            'settings': el.navSettings,
            'help': el.navHelp
        };

        Object.values(railMap).forEach(btn => btn?.classList.remove('active'));
        railMap[viewName]?.classList.add('active');

        // Hide all views
        const views = [el.viewStudio, el.viewHistory, el.viewActas, el.viewSettings, el.viewHelp];
        views.forEach(v => {
            if (v) {
                v.classList.add('hidden');
                v.classList.remove('active');
            }
        });

        // Show selected view
        const viewContainerMap = {
            'studio': el.viewStudio,
            'history': el.viewHistory,
            'actas': el.viewActas,
            'settings': el.viewSettings,
            'help': el.viewHelp
        };

        const activeContainer = viewContainerMap[viewName];
        if (activeContainer) {
            activeContainer.classList.remove('hidden');
            activeContainer.classList.add('active');
        }

        // View Specific On-Open Actions
        if (viewName === 'history') {
            renderFullHistoryGrid(state.historyItems);
        } else if (viewName === 'actas') {
            renderFullActaView();
        } else if (viewName === 'settings') {
            updateSettingsView();
        }
    }

    // =========================================================================
    // 4. HARDWARE STATUS & OLLAMA
    // =========================================================================
    async function fetchHardwareStatus(showNotification = false) {
        try {
            const res = await fetch('/api/hardware');
            if (!res.ok) throw new Error('Error de conexión con hardware');
            const data = await res.json();
            state.hardwareData = data;

            // CUDA GPU Status
            if (data.cuda) {
                el.cudaStatusBadge.className = 'capsule-pill';
                el.cudaStatusBadge.querySelector('.status-dot').className = 'status-dot green';
                const gpuShort = data.gpu.replace('NVIDIA GeForce ', '');
                el.cudaStatusText.textContent = `${gpuShort} (CUDA Activo)`;
            } else {
                el.cudaStatusBadge.className = 'capsule-pill';
                el.cudaStatusBadge.querySelector('.status-dot').className = 'status-dot';
                el.cudaStatusText.textContent = 'CPU Mode';
            }

            // Ollama Status
            if (data.ollama_connected) {
                el.ollamaDot.className = 'status-dot cyan';
                el.ollamaStatusText.textContent = 'Ollama Local';
                el.btnQuickConnectOllama.classList.add('hidden');

                // Populate AI Models Dropdown
                el.ollamaModelSelect.innerHTML = '';
                const models = data.ollama_models || [];
                models.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m;
                    opt.textContent = m.replace('Ollama: ', '');
                    el.ollamaModelSelect.appendChild(opt);
                });
            } else {
                el.ollamaDot.className = 'status-dot';
                el.ollamaStatusText.textContent = 'Ollama Offline';
                el.btnQuickConnectOllama.classList.remove('hidden');

                el.ollamaModelSelect.innerHTML = '<option value="Resumen Heurístico Offline">📝 Resumen Offline</option>';
            }

            updateSettingsView();

            if (showNotification) {
                showToast(`Hardware: ${data.gpu} | Ollama: ${data.ollama_connected ? 'Conectado' : 'Desconectado'}`, 'info');
            }
        } catch (e) {
            console.error('Error fetching hardware status:', e);
        }
    }

    async function startOllamaService() {
        showToast('Iniciando servicio local de Ollama...', 'info');
        el.btnQuickConnectOllama.disabled = true;
        try {
            const res = await fetch('/api/start-ollama', { method: 'POST' });
            if (res.ok) {
                showToast('Ollama conectado exitosamente', 'success');
                setTimeout(() => fetchHardwareStatus(), 800);
            } else {
                showToast('No se pudo conectar con Ollama. Asegúrate de tenerlo instalado.', 'error');
            }
        } catch {
            showToast('Error al intentar iniciar Ollama', 'error');
        } finally {
            el.btnQuickConnectOllama.disabled = false;
        }
    }

    function updateSettingsView() {
        if (!state.hardwareData) return;
        const d = state.hardwareData;
        if (el.cfgGpuName) el.cfgGpuName.textContent = d.gpu || 'NVIDIA GeForce RTX 4070';
        if (el.cfgVramVal) el.cfgVramVal.textContent = d.vram || '12.0 GB GDDR6X';
        if (el.cfgOllamaStatus) {
            el.cfgOllamaStatus.textContent = d.ollama_connected ? 'Conectado (http://localhost:11434)' : 'Desconectado';
            el.cfgOllamaStatus.className = d.ollama_connected ? 'settings-val badge-online' : 'settings-val';
        }
        if (el.cfgOllamaModelsCount) {
            const count = (d.ollama_models || []).filter(m => !m.includes('Heurístico')).length;
            el.cfgOllamaModelsCount.textContent = `${count} modelo(s) de IA detectado(s)`;
        }
    }

    async function openFolderInExplorer(folderTarget) {
        try {
            const res = await fetch('/api/open-folder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target: folderTarget })
            });
            if (res.ok) {
                showToast(`Carpeta '${folderTarget}' abierta en el Explorador`, 'success');
            } else {
                showToast('Error al abrir la carpeta', 'error');
            }
        } catch {
            showToast('No se pudo abrir el explorador', 'error');
        }
    }

    async function handleCleanTempFiles() {
        try {
            const res = await fetch('/api/clean-temp', { method: 'POST' });
            const data = await res.json();
            if (res.ok) {
                showToast(`Archivos temporales eliminados (${data.deleted || 0})`, 'success');
            } else {
                showToast('Error al limpiar archivos temporales', 'error');
            }
        } catch {
            showToast('Error al limpiar temporales', 'error');
        }
    }

    async function fetchAppSettings() {
        try {
            const res = await fetch('/api/settings');
            if (!res.ok) return;
            const data = await res.json();
            if (el.cfgOutputPath) {
                el.cfgOutputPath.textContent = data.output_folder;
                el.cfgOutputPath.title = data.output_folder;
            }
        } catch (e) {
            console.error('Error fetching app settings:', e);
        }
    }

    async function handleChangeOutputFolder() {
        // 1. Probar puente nativo de PyWebView si está disponible
        try {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.select_folder) {
                const folderPath = await window.pywebview.api.select_folder();
                if (folderPath) {
                    await applyNewOutputFolder(folderPath);
                    return;
                }
            }
        } catch (err) {
            console.warn('Native folder picker fallback:', err);
        }

        // 2. Probar backend dialog nativo
        try {
            const res = await fetch('/api/select-folder', { method: 'POST' });
            const data = await res.json();
            if (data.success && data.path) {
                await fetchAppSettings();
                await fetchProjects();
                await fetchHistory();
                showToast(`Carpeta de guardado actualizada a '${data.path}'`, 'success');
                return;
            } else if (data.cancelled) {
                return;
            }
        } catch (e) {}

        // 3. Fallback: Diálogo modal en pantalla
        showModal('Ingresar Ruta de Guardado', el.cfgOutputPath?.textContent || '', async (newPath) => {
            if (!newPath || !newPath.trim()) return;
            await applyNewOutputFolder(newPath.trim());
        });
    }

    async function applyNewOutputFolder(newPath) {
        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ output_folder: newPath })
            });
            const data = await res.json();
            if (data.success) {
                if (el.cfgOutputPath) {
                    el.cfgOutputPath.textContent = data.output_folder;
                    el.cfgOutputPath.title = data.output_folder;
                }
                await fetchProjects();
                await fetchHistory();
                showToast(`Carpeta de guardado actualizada: ${data.output_folder}`, 'success');
            } else {
                showToast('Error al guardar la nueva ruta', 'error');
            }
        } catch (e) {
            showToast('Error actualizando la carpeta', 'error');
        }
    }

    async function handleResetOutputFolder() {
        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reset_output: true })
            });
            const data = await res.json();
            if (data.success) {
                if (el.cfgOutputPath) {
                    el.cfgOutputPath.textContent = data.output_folder;
                    el.cfgOutputPath.title = data.output_folder;
                }
                await fetchProjects();
                await fetchHistory();
                showToast(`Ruta restablecida a la predeterminada ('output')`, 'info');
            }
        } catch (e) {
            showToast('Error al restablecer ruta', 'error');
        }
    }

    // =========================================================================
    // 5. FILE UPLOAD, DIRECT PATH & DRAG-AND-DROP
    // =========================================================================
    function setSourceMode(mode) {
        if (mode === 'local') {
            el.tabLocal.classList.add('active');
            el.tabYoutube.classList.remove('active');
            el.localUploadBox.classList.remove('hidden');
            el.youtubeUploadBox.classList.add('hidden');
        } else {
            el.tabYoutube.classList.add('active');
            el.tabLocal.classList.remove('active');
            el.youtubeUploadBox.classList.remove('hidden');
            el.localUploadBox.classList.add('hidden');
            setTimeout(() => el.ytUrlInput?.focus(), 50);
        }
    }

    function handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        el.dropZone.classList.add('drag-over');
    }

    function handleDragLeave(e) {
        e.preventDefault();
        e.stopPropagation();
        el.dropZone.classList.remove('drag-over');
    }

    async function openNativeFilePicker() {
        try {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.select_file) {
                const filePath = await window.pywebview.api.select_file();
                if (filePath) {
                    processDirectFilePath(filePath);
                    return;
                }
            }
        } catch (err) {
            console.warn('Native picker fallback to input:', err);
        }
        el.fileInput?.click();
    }

    function handleDroppedFiles(files) {
        if (!files || files.length === 0) return;
        const file = files[0];
        if (file.path) {
            processDirectFilePath(file.path, file.name, file.size);
        } else {
            uploadSelectedFile(file);
        }
    }

    function handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        el.dropZone.classList.remove('drag-over');
        const files = e.dataTransfer?.files;
        if (files && files.length > 0) {
            handleDroppedFiles(files);
        }
    }

    function handleFileSelected(e) {
        const files = e.target.files;
        if (files && files.length > 0) {
            handleDroppedFiles(files);
        }
    }

    async function processDirectFilePath(filePath, optName, optSize) {
        if (!filePath) return;

        if (state.isProcessing) {
            const confirmCancel = confirm('Hay una transcripción en curso. ¿Deseas cancelarla para procesar este nuevo archivo?');
            if (!confirmCancel) return;
            cancelTranscription();
        }

        if (currentUploadXhr) {
            try { currentUploadXhr.abort(); } catch {}
            currentUploadXhr = null;
        }

        // UI State: Preparing Direct Path
        el.dropZone.classList.add('hidden');
        el.dropZone.style.display = 'none';
        el.fileLoadedCard.classList.add('hidden');
        el.fileLoadedCard.style.display = 'none';
        el.uploadErrorCard.classList.add('hidden');
        el.uploadErrorCard.style.display = 'none';

        el.uploadProgressCard.classList.remove('hidden');
        el.uploadProgressCard.style.display = 'flex';
        el.uploadBarFill.style.width = '60%';
        el.uploadPercentage.textContent = 'Enlace 0s';
        el.uploadStatusTitle.innerHTML = '<span class="spinner-icon"></span> Enlazando archivo local en disco...';
        el.uploadBytesText.textContent = optSize ? formatBytes(optSize) : 'Lectura directa de disco';
        el.uploadSpeedText.textContent = 'Ultra Rápido (0s)';
        el.btnStartTranscription.disabled = true;

        try {
            const res = await fetch('/api/load_direct', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path: filePath })
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.error || 'Error al procesar el archivo');
            }

            const data = await res.json();
            state.currentFile = null;
            state.uploadedFilePath = data.path;
            state.mediaUrl = data.media_url;

            if (!el.customSessionName.value.trim()) {
                const baseName = data.name.replace(/\.[^/.]+$/, "");
                el.customSessionName.value = baseName;
                el.activeSessionName.textContent = baseName;
            }

            // File Ready State
            el.uploadProgressCard.classList.add('hidden');
            el.uploadProgressCard.style.display = 'none';

            el.fileLoadedName.textContent = data.name;
            el.fileLoadedMeta.textContent = data.is_video
                ? `${formatBytes(data.size)} · VIDEO (AUDIO EXTRAÍDO DIRECTO)`
                : `${formatBytes(data.size)} · ${data.type.toUpperCase()} DIRECTO`;

            el.fileLoadedCard.classList.remove('hidden');
            el.fileLoadedCard.style.display = 'flex';
            el.btnStartTranscription.disabled = false;

            loadAudioPlayer(state.mediaUrl);
            showToast('Archivo enlazado instantáneamente (0s)', 'success');

        } catch (err) {
            showUploadError(err.message || 'Error cargando archivo directamente');
        }
    }

    let currentUploadXhr = null;

    function showUploadError(errorMsg) {
        if (currentUploadXhr) {
            try { currentUploadXhr.abort(); } catch {}
            currentUploadXhr = null;
        }
        state.currentFile = null;
        state.uploadedFilePath = null;
        state.mediaUrl = null;

        el.dropZone.classList.add('hidden');
        el.dropZone.style.display = 'none';
        el.uploadProgressCard.classList.add('hidden');
        el.uploadProgressCard.style.display = 'none';
        el.fileLoadedCard.classList.add('hidden');
        el.fileLoadedCard.style.display = 'none';

        el.uploadErrorCard.classList.remove('hidden');
        el.uploadErrorCard.style.display = 'flex';
        el.uploadErrorMsg.textContent = errorMsg || 'Error al procesar el archivo';

        el.btnStartTranscription.disabled = true;
        showToast(errorMsg || 'Error al procesar archivo', 'error');
    }

    function uploadSelectedFile(file) {
        if (!file) return;

        if (state.isProcessing) {
            const confirmCancel = confirm('Hay una transcripción en curso. ¿Deseas cancelarla para procesar este nuevo archivo?');
            if (!confirmCancel) return;
            cancelTranscription();
        }

        if (currentUploadXhr) {
            try { currentUploadXhr.abort(); } catch {}
            currentUploadXhr = null;
        }

        const VIDEO_EXTS = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'];
        const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();
        const isVideo = VIDEO_EXTS.includes(ext);

        el.dropZone.classList.add('hidden');
        el.dropZone.style.display = 'none';
        el.fileLoadedCard.classList.add('hidden');
        el.fileLoadedCard.style.display = 'none';
        el.uploadErrorCard.classList.add('hidden');
        el.uploadErrorCard.style.display = 'none';

        el.uploadProgressCard.classList.remove('hidden');
        el.uploadProgressCard.style.display = 'flex';
        el.uploadBarFill.style.width = '0%';
        el.uploadPercentage.textContent = '0%';
        el.uploadStatusTitle.innerHTML = '<span class="spinner-icon"></span> Subiendo archivo...';
        el.uploadBytesText.textContent = `0 B / ${formatBytes(file.size)}`;
        el.uploadSpeedText.textContent = '-- MB/s';
        el.btnStartTranscription.disabled = true;

        const startTime = Date.now();
        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();
        currentUploadXhr = xhr;
        xhr.open('POST', '/api/upload', true);

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                el.uploadBarFill.style.width = `${pct}%`;
                el.uploadPercentage.textContent = `${pct}%`;
                el.uploadBytesText.textContent = `${formatBytes(e.loaded)} / ${formatBytes(e.total)}`;

                const elapsedSec = (Date.now() - startTime) / 1000;
                if (elapsedSec > 0.2) {
                    const speed = (e.loaded / elapsedSec) / (1024 * 1024);
                    el.uploadSpeedText.textContent = `${speed.toFixed(1)} MB/s`;
                }

                if (pct >= 100) {
                    el.uploadStatusTitle.innerHTML = '<span class="spinner-icon"></span> Guardando archivo en disco...';
                    el.uploadSpeedText.textContent = 'I/O Disco';
                }
            }
        };

        xhr.upload.onload = () => {
            el.uploadBarFill.style.width = '100%';
            el.uploadPercentage.textContent = '100%';
            el.uploadStatusTitle.innerHTML = '<span class="spinner-icon"></span> Guardando archivo en disco...';
            el.uploadBytesText.textContent = 'Escribiendo y verificando en almacenamiento local...';
            el.uploadSpeedText.textContent = 'I/O Disco';
        };

        xhr.onload = async () => {
            currentUploadXhr = null;
            if (xhr.status === 200) {
                try {
                    const data = JSON.parse(xhr.responseText);
                    state.currentFile = file;

                    if (!el.customSessionName.value.trim()) {
                        const baseName = data.name.replace(/\.[^/.]+$/, "");
                        el.customSessionName.value = baseName;
                        el.activeSessionName.textContent = baseName;
                    }

                    if (isVideo) {
                        el.uploadStatusTitle.innerHTML = '<span class="spinner-icon"></span> Extrayendo audio con FFmpeg...';
                        el.uploadPercentage.textContent = 'Convirtiendo...';
                        el.uploadBarFill.style.width = '100%';
                        el.uploadBytesText.textContent = 'Extrayendo audio mono WAV 16kHz optimizado para Whisper...';
                        el.uploadSpeedText.textContent = 'FFmpeg';

                        const convRes = await fetch('/api/convert', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ file_path: data.path })
                        });

                        if (!convRes.ok) throw new Error('Error al extraer audio del video con FFmpeg');
                        const convData = await convRes.json();

                        state.uploadedFilePath = convData.audio_path;
                        state.mediaUrl = convData.media_url;
                        el.fileLoadedMeta.textContent = `${formatBytes(data.size)} · VIDEO (AUDIO EXTRAÍDO)`;
                    } else {
                        state.uploadedFilePath = data.path;
                        state.mediaUrl = data.media_url;
                        el.fileLoadedMeta.textContent = `${formatBytes(data.size)} · ${data.type.toUpperCase()}`;
                    }

                    el.uploadProgressCard.classList.add('hidden');
                    el.uploadProgressCard.style.display = 'none';

                    el.fileLoadedName.textContent = data.name;
                    el.fileLoadedCard.classList.remove('hidden');
                    el.fileLoadedCard.style.display = 'flex';
                    el.btnStartTranscription.disabled = false;

                    loadAudioPlayer(state.mediaUrl);
                    showToast('Archivo listo para transcribir', 'success');

                } catch (err) {
                    showUploadError(err.message || 'Error al procesar el archivo');
                }
            } else {
                showUploadError('Error del servidor al subir el archivo');
            }
        };

        xhr.onerror = () => {
            currentUploadXhr = null;
            showUploadError('Error de red o conexión al subir');
        };

        xhr.send(formData);
    }

    function clearLoadedFile() {
        if (currentUploadXhr) {
            try { currentUploadXhr.abort(); } catch {}
            currentUploadXhr = null;
        }
        state.currentFile = null;
        state.uploadedFilePath = null;
        state.mediaUrl = null;
        if (el.fileInput) el.fileInput.value = '';

        el.uploadErrorCard.classList.add('hidden');
        el.uploadErrorCard.style.display = 'none';
        el.uploadProgressCard.classList.add('hidden');
        el.uploadProgressCard.style.display = 'none';
        el.fileLoadedCard.classList.add('hidden');
        el.fileLoadedCard.style.display = 'none';

        el.dropZone.classList.remove('hidden');
        el.dropZone.style.display = 'block';

        el.workspaceEmpty.classList.remove('hidden');
        el.workspaceEmpty.style.display = 'flex';
        el.viewSpeakersFeed.classList.add('hidden');
        el.viewPlainText.classList.add('hidden');
        el.viewActaContainer.classList.add('hidden');

        el.btnStartTranscription.disabled = true;
        el.nativeAudio.pause();
        el.nativeAudio.src = '';
    }

    async function handleFetchYouTube() {
        const url = el.ytUrlInput.value.trim();
        if (!url) {
            showToast('Ingresa una URL de YouTube válida', 'error');
            return;
        }

        showToast('Extrayendo audio de YouTube a alta velocidad...', 'info');
        const originalBtnText = el.btnFetchYt.innerHTML;
        el.btnFetchYt.disabled = true;
        el.btnFetchYt.innerHTML = '<span class="spinner-icon"></span> Descargando audio...';

        try {
            const res = await fetch('/api/youtube', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || 'Error al descargar audio de YouTube');
            }

            state.uploadedFilePath = data.audio_path;
            state.mediaUrl = data.media_url;

            el.fileLoadedName.textContent = data.name;
            el.fileLoadedMeta.textContent = `YouTube · ${formatTime(data.duration)}`;
            el.fileLoadedCard.classList.remove('hidden');
            el.fileLoadedCard.style.display = 'flex';
            el.dropZone.classList.add('hidden');
            el.dropZone.style.display = 'none';

            el.btnStartTranscription.disabled = false;

            if (!el.customSessionName.value.trim()) {
                el.customSessionName.value = data.name;
                el.activeSessionName.textContent = data.name;
            }

            loadAudioPlayer(data.media_url);
            showToast(`Audio '${data.name}' listo para transcribir`, 'success');
        } catch (e) {
            showToast(e.message || 'Error al procesar enlace de YouTube', 'error');
        } finally {
            el.btnFetchYt.disabled = false;
            el.btnFetchYt.innerHTML = originalBtnText;
        }
    }

    // =========================================================================
    // 6. TRANSCRIPTION ENGINE (ANTI-FREEZE SSE STREAMING)
    // =========================================================================
    function startTranscription() {
        if (!state.uploadedFilePath || state.isProcessing) return;

        const model = el.whisperModelSelect.value;
        const lang = el.languageSelect.value;
        const sessionName = el.customSessionName.value.trim();
        const project = el.projectSelector.value;
        const outFormat = document.getElementById('selected-out-format')?.value || 'txt';

        state.isProcessing = true;
        el.btnStartTranscription.disabled = true;
        el.progressCard.classList.remove('hidden');
        el.progressBarFill.style.width = '0%';
        el.progressPercentage.textContent = '0%';
        el.progressStatusText.innerHTML = '<span class="spinner-icon"></span> Transcribiendo en GPU...';

        state.activeSegments = [];
        state.activeSummary = null;
        state.activeResult = null;

        // Clean workspace immediately: hide empty illustration & dead buttons
        el.workspaceEmpty.classList.add('hidden');
        el.workspaceEmpty.style.display = 'none';
        el.viewSpeakersFeed.innerHTML = '';
        el.viewPlainText.textContent = '';
        el.viewActaContainer.innerHTML = '';

        switchWorkspaceView('speakers');

        state.startTime = Date.now();
        el.progressTimeCounter.textContent = '00:00';
        clearInterval(state.timerInterval);
        state.timerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - state.startTime) / 1000);
            el.progressTimeCounter.textContent = formatTime(elapsed);
        }, 1000);

        const params = new URLSearchParams({
            file_path: state.uploadedFilePath,
            model: model,
            language: lang,
            output_format: outFormat,
            custom_name: sessionName,
            project: project
        });

        if (state.eventSource) {
            state.eventSource.close();
        }

        const source = new EventSource(`/api/transcribe?${params.toString()}`);
        state.eventSource = source;

        source.addEventListener('progress', (e) => {
            const data = JSON.parse(e.data);
            const pct = Math.round(data.progress || 0);
            el.progressBarFill.style.width = `${pct}%`;
            el.progressPercentage.textContent = `${pct}%`;

            if (data.text && data.text.trim()) {
                const seg = {
                    start: data.current - 2.0,
                    end: data.current,
                    text: data.text.trim()
                };
                state.activeSegments.push(seg);
                appendLiveSegmentToFeed(seg);
            }
        });

        source.addEventListener('complete', (e) => {
            source.close();
            state.eventSource = null;
            state.isProcessing = false;
            clearInterval(state.timerInterval);

            el.progressCard.classList.add('hidden');
            el.btnStartTranscription.disabled = false;

            const result = JSON.parse(e.data);
            state.activeResult = result;
            state.activeSegments = result.segments || state.activeSegments;

            // Render rich speaker dialogue & natural clean text
            renderDialogueFeed(result.segments);
            el.viewPlainText.textContent = result.plain_text || result.text;

            fetchHistory();
            showToast('Transcripción completada con éxito', 'success');
        });

        source.addEventListener('cancelled', () => {
            source.close();
            state.eventSource = null;
            state.isProcessing = false;
            clearInterval(state.timerInterval);
            el.progressCard.classList.add('hidden');
            el.btnStartTranscription.disabled = false;
            showToast('Transcripción cancelada', 'info');
        });

        source.addEventListener('error', (e) => {
            source.close();
            state.eventSource = null;
            state.isProcessing = false;
            clearInterval(state.timerInterval);
            el.progressCard.classList.add('hidden');
            el.btnStartTranscription.disabled = false;
            showToast('Error durante la transcripción', 'error');
        });
    }

    function cancelTranscription() {
        if (!state.isProcessing) return;
        fetch('/api/cancel', { method: 'POST' });
        if (state.eventSource) {
            state.eventSource.close();
            state.eventSource = null;
        }
        state.isProcessing = false;
        clearInterval(state.timerInterval);
        el.progressCard.classList.add('hidden');
        el.btnStartTranscription.disabled = false;
        showToast('Cancelando transcripción...', 'info');
    }

    function getSpeakerInitials(speakerLabel) {
        if (!speakerLabel) return 'H1';
        const match = speakerLabel.match(/Hablante\s*(\d+)/i);
        if (match) {
            return `H${match[1]}`;
        }
        const clean = speakerLabel.replace(/[\(\)¿\?]/g, '').trim();
        const words = clean.split(/\s+/);
        if (words.length >= 2) {
            return (words[0][0] + words[1][0]).toUpperCase();
        } else if (words.length === 1 && words[0].length > 0) {
            return words[0].substring(0, 2).toUpperCase();
        }
        return 'H1';
    }

    let currentLiveSpeaker = 'Hablante 1';
    let currentLiveBlock = null;

    function appendLiveSegmentToFeed(seg) {
        if (el.viewSpeakersFeed.classList.contains('hidden')) {
            el.viewSpeakersFeed.classList.remove('hidden');
        }

        const spk = seg.speaker || 'Hablante 1';
        const text = (seg.text || '').trim();
        if (!text) return;

        // Si ya hay un bloque del mismo hablante activo en vivo, concatenar fluidamente el texto
        if (currentLiveBlock && currentLiveSpeaker === spk) {
            const textEl = currentLiveBlock.querySelector('.dialogue-text') || currentLiveBlock.querySelector('.dialogue-body');
            if (textEl) {
                textEl.textContent += ' ' + text;
                el.viewSpeakersFeed.scrollTop = el.viewSpeakersFeed.scrollHeight;
                return;
            }
        }

        // Crear nuevo bloque de turno de diálogo
        currentLiveSpeaker = spk;
        const row = document.createElement('div');
        row.className = 'dialogue-card';
        row.innerHTML = `
            <div class="speaker-avatar-circle speaker-1">
                ${getSpeakerInitials(spk)}
            </div>
            <div class="dialogue-body">
                <div class="dialogue-header">
                    <div class="speaker-meta-left">
                        <span class="speaker-name-tag" style="color: var(--accent-indigo)">${escapeHtml(spk)}</span>
                    </div>
                    <span class="timestamp-pill">${formatTime(seg.start || 0)}</span>
                </div>
                <div class="dialogue-text">${escapeHtml(text)}</div>
            </div>
        `;
        el.viewSpeakersFeed.appendChild(row);
        currentLiveBlock = row;
        el.viewSpeakersFeed.scrollTop = el.viewSpeakersFeed.scrollHeight;
    }

    function groupSegmentsForDisplay(segments, maxGap = 8.0) {
        if (!segments || segments.length === 0) return [];
        const grouped = [];
        let currentTurn = null;

        segments.forEach(seg => {
            const spk = seg.speaker || 'Hablante 1';
            const text = (seg.text || '').trim();
            const start = typeof seg.start === 'number' ? seg.start : 0.0;
            const end = typeof seg.end === 'number' ? seg.end : start;

            if (!text) return;

            if (!currentTurn) {
                currentTurn = {
                    speaker: spk,
                    start: start,
                    end: end,
                    texts: [text],
                    tentative_name: seg.tentative_name,
                    is_tentative: seg.is_tentative
                };
            } else if (currentTurn.speaker === spk && (start - currentTurn.end <= maxGap)) {
                currentTurn.texts.push(text);
                currentTurn.end = end;
                if (!currentTurn.tentative_name && seg.tentative_name) {
                    currentTurn.tentative_name = seg.tentative_name;
                    currentTurn.is_tentative = true;
                }
            } else {
                currentTurn.text = currentTurn.texts.join(' ');
                delete currentTurn.texts;
                grouped.push(currentTurn);

                currentTurn = {
                    speaker: spk,
                    start: start,
                    end: end,
                    texts: [text],
                    tentative_name: seg.tentative_name,
                    is_tentative: seg.is_tentative
                };
            }
        });

        if (currentTurn) {
            currentTurn.text = currentTurn.texts ? currentTurn.texts.join(' ') : (currentTurn.text || '');
            delete currentTurn.texts;
            grouped.push(currentTurn);
        }

        return grouped;
    }

    function renderDialogueFeed(segments) {
        el.viewSpeakersFeed.innerHTML = '';
        currentLiveBlock = null;
        if (!segments || segments.length === 0) return;

        const turns = groupSegmentsForDisplay(segments);

        const colors = [
            { bg: 'rgba(99, 102, 241, 0.15)', text: '#818CF8', class: 'speaker-1' },
            { bg: 'rgba(16, 185, 129, 0.15)', text: '#34D399', class: 'speaker-2' },
            { bg: 'rgba(6, 182, 212, 0.15)', text: '#22D3EE', class: 'speaker-3' },
            { bg: 'rgba(245, 158, 11, 0.15)', text: '#FBBF24', class: 'speaker-4' },
            { bg: 'rgba(236, 72, 153, 0.15)', text: '#F472B6', class: 'speaker-1' }
        ];

        turns.forEach((turn) => {
            const speakerLabel = turn.speaker || 'Hablante 1';
            const speakerIdx = parseInt(speakerLabel.replace(/\D/g, '') || '1') - 1;
            const color = colors[speakerIdx % colors.length];

            const block = document.createElement('div');
            block.className = 'dialogue-card';
            block.innerHTML = `
                <div class="speaker-avatar-circle ${color.class}">
                    ${getSpeakerInitials(speakerLabel)}
                </div>
                <div class="dialogue-body">
                    <div class="dialogue-header">
                        <div class="speaker-meta-left">
                            <span class="speaker-name-tag" style="color: ${color.text}">${escapeHtml(speakerLabel)}</span>
                        </div>
                        <span class="timestamp-pill" data-start="${turn.start}" title="Hacer clic para reproducir desde aquí">⏱️ ${formatTime(turn.start)}</span>
                    </div>
                    <div class="dialogue-text">${escapeHtml(turn.text)}</div>
                </div>
            `;

            block.querySelector('.timestamp-pill').addEventListener('click', () => {
                seekAudioTo(turn.start);
            });

            el.viewSpeakersFeed.appendChild(block);
        });
    }

    // =========================================================================
    // 7. STUDIO WORKSPACE VIEWS (HABLANTES / TEXTO LIMPIO / ACTA)
    // =========================================================================
    function switchWorkspaceView(tabName) {
        state.activeWorkspaceTab = tabName;

        [el.btnViewSpeakers, el.btnViewPlain, el.btnViewActa].forEach(b => b?.classList.remove('active'));
        [el.viewSpeakersFeed, el.viewPlainText, el.viewActaContainer].forEach(v => v?.classList.add('hidden'));

        if (tabName === 'speakers') {
            el.btnViewSpeakers.classList.add('active');
            el.viewSpeakersFeed.classList.remove('hidden');
        } else if (tabName === 'plain') {
            el.btnViewPlain.classList.add('active');
            const cleanText = state.activeResult?.plain_text || state.activeResult?.text || '';
            el.viewPlainText.textContent = cleanText || 'Sin transcripción activa';
            el.viewPlainText.classList.remove('hidden');
        } else if (tabName === 'acta') {
            el.btnViewActa.classList.add('active');
            el.viewActaContainer.classList.remove('hidden');
            if (!state.activeSummary) {
                el.viewActaContainer.innerHTML = `
                    <div class="empty-illustration">
                        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                    </div>
                    <h3>Acta Oficial No Generada Aún</h3>
                    <p>Haz clic en "Generar Acta" en la barra superior para redactar el informe oficial con IA.</p>
                `;
            }
        }
    }

    // =========================================================================
    // 8. AI ACTA GENERATOR (OLLAMA & HEURÍSTICO)
    // =========================================================================
    async function handleGenerateActa() {
        const fullText = state.activeResult?.speaker_text || state.activeResult?.plain_text || state.activeResult?.text;
        if (!fullText) {
            showToast('Primero transcribe un audio para generar el acta', 'error');
            return;
        }

        const model = el.ollamaModelSelect.value;
        const title = el.customSessionName.value.trim() || 'Reunión de Trabajo';
        const durationStr = el.playerDurationTime.textContent || 'N/A';
        const sessionId = state.activeResult?.session_id || '';

        el.btnGenerateActa.disabled = true;
        el.btnGenerateActa.innerHTML = '<span class="spinner-icon"></span> Redactando...';
        showToast('Redactando Acta Oficial con IA en tiempo real...', 'info');

        switchWorkspaceView('acta');
        el.viewActaContainer.innerHTML = `
            <div class="acta-document">
                <div class="acta-streaming-header">
                    <span class="spinner-icon"></span>
                    <span>Generando Acta Oficial con ${escapeHtml(model.replace('Ollama: ', ''))}...</span>
                </div>
                <div class="acta-raw-content" id="acta-live-target"></div>
            </div>
        `;

        const targetEl = document.getElementById('acta-live-target');
        let accumulatedSummary = '';

        try {
            const response = await fetch('/api/summarize_stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: fullText,
                    title: title,
                    duration: durationStr,
                    model: model,
                    session_id: sessionId
                })
            });

            if (!response.ok) throw new Error('Error al conectar con el motor de IA');

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (trimmed.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(trimmed.slice(6));
                            if (data.error) {
                                throw new Error(data.error);
                            }
                            if (data.token) {
                                accumulatedSummary += data.token;
                                if (targetEl) {
                                    targetEl.textContent = accumulatedSummary;
                                    el.viewActaContainer.scrollTop = el.viewActaContainer.scrollHeight;
                                }
                            }
                            if (data.done) {
                                break;
                            }
                        } catch (e) {
                            if (e.message && !e.message.includes('JSON')) throw e;
                        }
                    }
                }
            }

            state.activeSummary = accumulatedSummary;
            renderActaInContainer(accumulatedSummary);
            renderFullActaView();
            showToast('Acta Oficial generada exitosamente', 'success');

        } catch (err) {
            showToast(err.message || 'Error con el motor de IA', 'error');
            el.viewActaContainer.innerHTML = `
                <div class="empty-illustration" style="color: var(--accent-rose)">
                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                </div>
                <h3>Error al redactar el acta</h3>
                <p>${escapeHtml(err.message)}</p>
                <div style="margin-top: 12px;">
                    <button id="btn-fallback-heuristic" class="btn-secondary-small">Generar con Motor Offline Inmediato (0s)</button>
                </div>
            `;
            document.getElementById('btn-fallback-heuristic')?.addEventListener('click', () => {
                el.ollamaModelSelect.value = '📝 Resumen Heurístico Offline';
                handleGenerateActa();
            });
        } finally {
            el.btnGenerateActa.disabled = false;
            el.btnGenerateActa.innerHTML = `
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3z"></path>
                </svg>
                <span>Generar Acta</span>
            `;
        }
    }

    function renderActaInContainer(summaryMarkdown) {
        el.viewActaContainer.innerHTML = `
            <div class="acta-document">
                <div class="acta-raw-content">${escapeHtml(summaryMarkdown)}</div>
            </div>
        `;
    }

    function renderFullActaView() {
        if (state.activeSummary) {
            el.fullActaPlaceholder?.classList.add('hidden');
            el.fullActaRendered?.classList.remove('hidden');
            el.fullActaRendered.textContent = state.activeSummary;
        } else {
            el.fullActaPlaceholder?.classList.remove('hidden');
            el.fullActaRendered?.classList.add('hidden');
        }
    }

    // =========================================================================
    // 9. HISTORY & SESSION ARCHIVE (SQLITE BACKED)
    // =========================================================================
    async function fetchHistory(silent = false) {
        try {
            const project = state.activeProject || '';
            const search = el.historySearchInput?.value.trim() || '';
            const res = await fetch(`/api/sessions?project=${encodeURIComponent(project)}&search=${encodeURIComponent(search)}`);
            if (!res.ok) throw new Error('Error al cargar historial');
            const data = await res.json();
            state.historyItems = data;

            if (state.activeMainView === 'history') {
                renderFullHistoryGrid(data);
            }
            if (silent) {
                showToast('Historial actualizado', 'info');
            }
        } catch (e) {
            console.error('Error fetching history:', e);
        }
    }

    function filterHistoryView() {
        const query = (el.historySearchInput?.value || '').toLowerCase().trim();
        if (!query) {
            renderFullHistoryGrid(state.historyItems);
            return;
        }
        const filtered = state.historyItems.filter(item => 
            (item.title && item.title.toLowerCase().includes(query)) ||
            (item.session_id && item.session_id.toLowerCase().includes(query))
        );
        renderFullHistoryGrid(filtered);
    }

    function renderFullHistoryGrid(items) {
        if (!el.fullHistoryGrid) return;
        el.fullHistoryGrid.innerHTML = '';

        if (!items || items.length === 0) {
            el.fullHistoryEmpty?.classList.remove('hidden');
            return;
        }

        el.fullHistoryEmpty?.classList.add('hidden');

        items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'history-card-item';
            const durationBadge = item.duration_str ? `<span class="badge-duration">⏱️ ${item.duration_str}</span>` : '';
            const hasActaBadge = item.has_summary ? `<span class="badge-acta">📜 Acta Lista</span>` : '';

            card.innerHTML = `
                <div class="history-card-header">
                    <div class="history-card-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                    </div>
                    <div class="history-card-info">
                        <div class="history-card-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div>
                        <div class="history-card-date">${item.created_str || ''} ${durationBadge} ${hasActaBadge}</div>
                    </div>
                </div>
                <div class="history-card-actions">
                    <button class="btn-card-action btn-open-history" title="Cargar en el Estudio">Abrir en Estudio</button>
                    <button class="btn-card-action btn-copy-history" title="Copiar texto">Copiar</button>
                    <button class="btn-card-delete btn-delete-history" title="Eliminar sesión">Eliminar</button>
                </div>
            `;

            card.querySelector('.btn-open-history').addEventListener('click', () => loadHistoryFileIntoStudio(item.session_id));
            card.querySelector('.btn-copy-history').addEventListener('click', () => copyHistorySessionText(item.session_id));
            card.querySelector('.btn-delete-history').addEventListener('click', () => deleteHistorySession(item.session_id));

            el.fullHistoryGrid.appendChild(card);
        });
    }

    async function loadHistoryFileIntoStudio(sessionId) {
        try {
            const res = await fetch(`/api/session/${encodeURIComponent(sessionId)}`);
            if (!res.ok) throw new Error('Error al abrir sesión');
            const data = await res.json();

            state.activeResult = data;
            state.activeSegments = data.segments || [];
            state.activeSummary = data.summary || '';

            el.customSessionName.value = data.title;
            el.activeSessionName.textContent = data.title;

            // 1. Vista Hablantes: Renderizar bloques de diálogo estructurados
            if (data.segments && data.segments.length > 0) {
                renderDialogueFeed(data.segments);
                switchWorkspaceView('speakers');
            } else {
                renderDialogueFeed([]);
                switchWorkspaceView('plain');
            }

            // 2. Vista Texto Limpio: Renderizar texto continuo SIN marcas de tiempo ni [Hablante N]
            el.viewPlainText.textContent = data.plain_text || data.text || '';

            // 3. Vista Acta Oficial: Renderizar si ya fue generada
            renderFullActaView();
            if (data.summary) {
                renderActaInContainer(data.summary);
            }

            switchMainView('studio');
            el.workspaceEmpty.classList.add('hidden');
            el.workspaceEmpty.style.display = 'none';

            // 4. Audio: Cargar y vincular reproductor
            if (data.media_url) {
                state.mediaUrl = data.media_url;
                loadAudioPlayer(data.media_url);

                el.fileLoadedName.textContent = data.audio_filename || data.title;
                el.fileLoadedMeta.textContent = `Audio sincronizado · Duración: ${data.duration_str || 'N/A'}`;

                el.dropZone.classList.add('hidden');
                el.dropZone.style.display = 'none';
                el.fileLoadedCard.classList.remove('hidden');
                el.fileLoadedCard.style.display = 'flex';

                showToast(`Sesión '${data.title}' y audio cargados en el Estudio`, 'success');
            } else {
                showToast(`Sesión '${data.title}' cargada exitosamente`, 'success');
            }

        } catch (e) {
            showToast(e.message || 'Error abriendo sesión', 'error');
        }
    }

    async function copyHistorySessionText(sessionId) {
        try {
            const res = await fetch(`/api/session/${encodeURIComponent(sessionId)}`);
            const data = await res.json();
            const textToCopy = data.plain_text || data.speaker_text || data.text || '';
            await navigator.clipboard.writeText(textToCopy);
            showToast('Texto copiado al portapapeles', 'success');
        } catch {
            showToast('Error al copiar texto', 'error');
        }
    }

    async function deleteHistorySession(sessionId) {
        if (!confirm(`¿Eliminar permanentemente esta sesión del historial?`)) return;
        try {
            const res = await fetch(`/api/session/${encodeURIComponent(sessionId)}`, {
                method: 'DELETE'
            });
            if (res.ok) {
                showToast('Sesión eliminada', 'info');
                await fetchHistory();
                await fetchProjects();
            } else {
                showToast('Error al eliminar sesión', 'error');
            }
        } catch {
            showToast('Error de conexión al eliminar', 'error');
        }
    }

    // =========================================================================
    // 10. PROJECTS & FOLDERS
    // =========================================================================
    async function fetchProjects() {
        try {
            const res = await fetch('/api/projects');
            if (!res.ok) return;
            const projects = await res.json();
            el.projectSelector.innerHTML = '';
            projects.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.path;
                opt.textContent = `${p.name} (${p.file_count})`;
                if (p.path === state.activeProject) opt.selected = true;
                el.projectSelector.appendChild(opt);
            });
        } catch (e) {
            console.error('Error fetching projects:', e);
        }
    }

    function showNewProjectModal() {
        showModal('Nuevo Proyecto / Carpeta', '', async (projectName) => {
            if (!projectName.trim()) return;
            try {
                const res = await fetch('/api/projects', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: projectName })
                });
                if (!res.ok) throw new Error('El proyecto ya existe o el nombre no es válido');
                const data = await res.json();
                state.activeProject = data.path;
                await fetchProjects();
                await fetchHistory();
                showToast(`Proyecto '${data.name}' creado`, 'success');
            } catch (err) {
                showToast(err.message, 'error');
            }
        });
    }

    // =========================================================================
    // 11. AUDIO PLAYER
    // =========================================================================
    function loadAudioPlayer(url) {
        el.nativeAudio.src = url;
        el.nativeAudio.load();
        el.playerCurrentTime.textContent = '00:00';
        el.playerDurationTime.textContent = '00:00';
        el.playerScrubber.value = 0;
        el.playerProgressFill.style.width = '0%';
        state.isPlaying = false;
        updatePlayPauseIcons();
    }

    function toggleAudioPlay() {
        if (!el.nativeAudio.src) return;
        if (state.isPlaying) {
            el.nativeAudio.pause();
            state.isPlaying = false;
        } else {
            el.nativeAudio.play();
            state.isPlaying = true;
        }
        updatePlayPauseIcons();
    }

    function updatePlayPauseIcons() {
        if (state.isPlaying) {
            el.iconPlay.classList.add('hidden');
            el.iconPause.classList.remove('hidden');
        } else {
            el.iconPlay.classList.remove('hidden');
            el.iconPause.classList.add('hidden');
        }
    }

    function updateAudioProgress() {
        const cur = el.nativeAudio.currentTime || 0;
        const dur = el.nativeAudio.duration || 1;
        el.playerCurrentTime.textContent = formatTime(cur);
        const pct = (cur / dur) * 100;
        el.playerScrubber.value = pct;
        el.playerProgressFill.style.width = `${pct}%`;
    }

    function updateAudioDuration() {
        const dur = el.nativeAudio.duration || 0;
        el.playerDurationTime.textContent = formatTime(dur);
    }

    function handleAudioSeek(e) {
        const pct = parseFloat(e.target.value);
        const dur = el.nativeAudio.duration || 0;
        el.nativeAudio.currentTime = (pct / 100) * dur;
    }

    function seekAudioTo(seconds) {
        el.nativeAudio.currentTime = seconds;
        if (!state.isPlaying) {
            el.nativeAudio.play();
            state.isPlaying = true;
            updatePlayPauseIcons();
        }
    }

    function onAudioEnded() {
        state.isPlaying = false;
        updatePlayPauseIcons();
    }

    function cyclePlaybackSpeed() {
        const speeds = [1.0, 1.25, 1.5, 2.0];
        const nextIdx = (speeds.indexOf(state.playbackRate) + 1) % speeds.length;
        state.playbackRate = speeds[nextIdx];
        el.nativeAudio.playbackRate = state.playbackRate;
        el.btnSpeedToggle.textContent = `${state.playbackRate}x`;
    }

    function toggleAudioMute() {
        el.nativeAudio.muted = !el.nativeAudio.muted;
        el.btnVolumeMute.style.opacity = el.nativeAudio.muted ? '0.4' : '1';
    }

    // =========================================================================
    // 12. EXPORT & COPY
    // =========================================================================
    async function copyAllTranscript() {
        let textToCopy = '';
        if (state.activeWorkspaceTab === 'plain') {
            textToCopy = state.activeResult?.plain_text || state.activeResult?.text || el.viewPlainText.textContent;
        } else if (state.activeWorkspaceTab === 'acta') {
            textToCopy = state.activeSummary || '';
        } else {
            textToCopy = state.activeResult?.speaker_text || state.activeSegments.map(s => `[${s.speaker || 'Hablante 1'} ${formatTime(s.start)}]: ${s.text}`).join('\n\n');
        }

        if (!textToCopy) {
            showToast('No hay contenido para copiar', 'error');
            return;
        }

        await navigator.clipboard.writeText(textToCopy);
        showToast('Texto copiado al portapapeles', 'success');
    }

    function exportDocument(format) {
        let content = '';
        let filename = (el.customSessionName.value.trim() || 'transcripcion') + `.${format}`;

        if (format === 'txt') {
            content = state.activeResult?.plain_text || state.activeResult?.text || el.viewPlainText.textContent;
        } else if (format === 'md') {
            content = state.activeSummary || `# ${filename}\n\n` + (state.activeResult?.speaker_text || '');
        } else if (format === 'srt') {
            content = generateSrtFormat(state.activeSegments);
        } else if (format === 'vtt') {
            content = 'WEBVTT\n\n' + generateSrtFormat(state.activeSegments);
        }

        if (!content) {
            showToast('No hay datos para exportar', 'error');
            return;
        }

        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        showToast(`Documento exportado como '${filename}'`, 'success');
    }

    function generateSrtFormat(segments) {
        if (!segments) return '';
        return segments.map((s, i) => {
            const start = formatTimeSRT(s.start);
            const end = formatTimeSRT(s.end);
            return `${i + 1}\n${start} --> ${end}\n${s.text}\n`;
        }).join('\n');
    }

    // =========================================================================
    // 13. MODALS, TOASTS & UTILITIES
    // =========================================================================
    function showModal(title, initialValue, callback) {
        el.modalTitle.textContent = title;
        el.modalInput.value = initialValue || '';
        el.modalOverlay.classList.remove('hidden');
        modalCallback = callback;
        setTimeout(() => el.modalInput.focus(), 50);
    }

    function closeModal() {
        el.modalOverlay.classList.add('hidden');
        modalCallback = null;
    }

    function handleModalConfirm() {
        if (modalCallback) {
            modalCallback(el.modalInput.value);
        }
        closeModal();
    }

    function showToast(msg, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = msg;
        el.toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            setTimeout(() => toast.remove(), 200);
        }, 3200);
    }

    function formatTime(seconds) {
        if (isNaN(seconds) || seconds < 0) return '00:00';
        const s = Math.floor(seconds);
        const mins = Math.floor(s / 60);
        const secs = s % 60;
        if (mins >= 60) {
            const hrs = Math.floor(mins / 60);
            const remMins = mins % 60;
            return `${hrs.toString().padStart(2, '0')}:${remMins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    function formatTimeSRT(seconds) {
        const totalMs = Math.floor((seconds || 0) * 1000);
        const hrs = Math.floor(totalMs / 3600000);
        const mins = Math.floor((totalMs % 3600000) / 60000);
        const secs = Math.floor((totalMs % 60000) / 1000);
        const ms = totalMs % 1000;
        return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`;
    }

    function formatBytes(bytes, decimals = 1) {
        if (!+bytes) return '0 B';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
});

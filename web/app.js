/**
 * Ocolyx Web Application Logic
 * Real-time on-device blink rate telemetry & eye-strain prevention
 */

(function () {
  'use strict';

  // --- Configuration & State ---
  const config = {
    bpmThreshold: 5.0,
    earThreshold: 0.21,
    consecutiveFrames: 2,
    audioAlerts: true,
    dimmingOverlay: true,
    notifications: false,
  };

  // Load persisted config from localStorage
  try {
    const saved = localStorage.getItem('ocolyx_web_config');
    if (saved) Object.assign(config, JSON.parse(saved));
  } catch (e) {
    console.warn('Could not read localStorage config', e);
  }

  const state = {
    isMonitoring: false,
    webcamStream: null,
    totalBlinks: 0,
    blinkTimestamps: [],
    closedFramesCount: 0,
    isEyeClosed: false,
    currentEAR: 0.0,
    currentBPM: 0.0,
    earHistory: new Array(120).fill(0.3),
    sessionStartTime: null,
    sessionTimerId: null,
    faceMeshInstance: null,
    cameraUtilsInstance: null,
    lowBlinkDurationSeconds: 0,
    lastDimTimestamp: 0,
    fps: 0,
    fpsCount: 0,
    lastFpsTime: performance.now(),
    audioCtx: null,
    useFallbackCV: false,
  };

  // --- DOM Elements ---
  const elements = {
    btnToggleMonitor: document.getElementById('btn-toggle-monitor'),
    btnStartExercise: document.getElementById('btn-start-exercise'),
    btnCloseExercise: document.getElementById('btn-close-exercise'),
    exerciseModal: document.getElementById('exercise-modal'),
    exerciseCountdown: document.getElementById('exercise-countdown'),
    exerciseInstruction: document.getElementById('exercise-instruction'),
    dimOverlay: document.getElementById('dim-overlay'),
    toggleDimFeature: document.getElementById('toggle-dim-feature'),
    systemStatusDot: document.getElementById('system-status-dot'),
    systemStatusText: document.getElementById('system-status-text'),
    webcamVideo: document.getElementById('webcam-video'),
    overlayCanvas: document.getElementById('overlay-canvas'),
    cyberEyeCore: document.getElementById('cyber-eye-core'),
    radarStatusTitle: document.getElementById('radar-status-title'),
    radarStatusDesc: document.getElementById('radar-status-desc'),
    waveformCanvas: document.getElementById('waveform-canvas'),
    metricBpm: document.getElementById('metric-bpm'),
    metricBpmBadge: document.getElementById('metric-bpm-badge'),
    metricEar: document.getElementById('metric-ear'),
    metricEarBadge: document.getElementById('metric-ear-badge'),
    metricBlinks: document.getElementById('metric-blinks'),
    metricTimer: document.getElementById('metric-timer'),
    metricSessionBadge: document.getElementById('metric-session-badge'),
    metricRisk: document.getElementById('metric-risk'),
    metricRiskBadge: document.getElementById('metric-risk-badge'),
    hudFps: document.getElementById('hud-fps'),
    hudStatus: document.getElementById('hud-status'),
    hudEar: document.getElementById('hud-ear'),
    navButtons: document.querySelectorAll('.nav-item'),
    viewSections: document.querySelectorAll('.view-section'),
    cfgBpm: document.getElementById('cfg-bpm'),
    cfgBpmVal: document.getElementById('cfg-bpm-val'),
    cfgEar: document.getElementById('cfg-ear'),
    cfgEarVal: document.getElementById('cfg-ear-val'),
    cfgAudio: document.getElementById('cfg-audio'),
    cfgDim: document.getElementById('cfg-dim'),
    btnSaveSettings: document.getElementById('btn-save-settings'),
    btnRequestNotifications: document.getElementById('btn-request-notifications'),
    logTableBody: document.getElementById('log-table-body'),
    btnClearLogs: document.getElementById('btn-clear-logs'),
  };

  // --- Web Audio Synthesizer (Zero-dependency Chime) ---
  function playAlertChime() {
    if (!config.audioAlerts) return;
    try {
      if (!state.audioCtx) {
        state.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (state.audioCtx.state === 'suspended') {
        state.audioCtx.resume();
      }

      const ctx = state.audioCtx;
      const now = ctx.currentTime;

      // Soft harmonic chord (C5, G5)
      const freqs = [523.25, 783.99];
      freqs.forEach((freq, idx) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, now + idx * 0.08);

        gain.gain.setValueAtTime(0.001, now + idx * 0.08);
        gain.gain.exponentialRampToValueAtTime(0.12, now + idx * 0.08 + 0.04);
        gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.08 + 0.6);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(now + idx * 0.08);
        osc.stop(now + idx * 0.08 + 0.65);
      });
    } catch (e) {
      console.warn('Audio playback error', e);
    }
  }

  // --- Geometry: Eye Aspect Ratio (EAR) ---
  // MediaPipe FaceMesh Eye landmark indices
  // Left eye: [33, 160, 158, 133, 153, 144]
  // Right eye: [362, 385, 387, 263, 373, 380]
  function computeEAR(landmarks, indices) {
    const p1 = landmarks[indices[0]];
    const p2 = landmarks[indices[1]];
    const p3 = landmarks[indices[2]];
    const p4 = landmarks[indices[3]];
    const p5 = landmarks[indices[4]];
    const p6 = landmarks[indices[5]];

    const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

    const verticalA = dist(p2, p6);
    const verticalB = dist(p3, p5);
    const horizontal = dist(p1, p4);

    if (horizontal < 1e-6) return 0.25;
    return (verticalA + verticalB) / (2.0 * horizontal);
  }

  // --- Blink Registration & Rolling BPM ---
  function registerBlink() {
    state.totalBlinks++;
    const now = Date.now();
    state.blinkTimestamps.push(now);

    // Keep timestamps from the last 60 seconds
    const cutoff = now - 60000;
    state.blinkTimestamps = state.blinkTimestamps.filter((ts) => ts >= cutoff);

    // Calculate rolling BPM
    const elapsedSeconds = state.sessionStartTime
      ? Math.max(1, (now - state.sessionStartTime) / 1000)
      : 1;

    if (elapsedSeconds < 60) {
      // Extrapolate in first minute with gentle dampening
      state.currentBPM = Number(((state.blinkTimestamps.length / elapsedSeconds) * 60).toFixed(1));
    } else {
      state.currentBPM = Number(state.blinkTimestamps.length.toFixed(1));
    }

    elements.metricBlinks.textContent = state.totalBlinks;
    updateBpmBadge();

    // Visual ocular pulse on privacy radar
    if (elements.cyberEyeCore) {
      elements.cyberEyeCore.classList.add('blinking');
      setTimeout(() => elements.cyberEyeCore.classList.remove('blinking'), 180);
    }
  }

  function updateBpmBadge() {
    const bpm = state.currentBPM;
    elements.metricBpm.textContent = bpm.toFixed(1);

    const badge = elements.metricBpmBadge;
    const riskBadge = elements.metricRiskBadge;
    const riskText = elements.metricRisk;

    if (bpm >= 12.0) {
      badge.className = 'status-badge badge-healthy';
      badge.textContent = 'Optimal (Healthy)';
      riskBadge.className = 'status-badge badge-healthy';
      riskBadge.textContent = 'Normal';
      riskText.textContent = 'Low';
      hideDimOverlay();
      state.lowBlinkDurationSeconds = 0;
    } else if (bpm >= 6.0) {
      badge.className = 'status-badge badge-neutral';
      badge.textContent = 'Moderate';
      riskBadge.className = 'status-badge badge-neutral';
      riskBadge.textContent = 'Fair';
      riskText.textContent = 'Moderate';
      hideDimOverlay();
    } else if (bpm >= 3.0) {
      badge.className = 'status-badge badge-warning';
      badge.textContent = 'Low Blink Rate';
      riskBadge.className = 'status-badge badge-warning';
      riskBadge.textContent = 'Notice';
      riskText.textContent = 'Elevated';
    } else {
      badge.className = 'status-badge badge-critical';
      badge.textContent = 'Critical Strain';
      riskBadge.className = 'status-badge badge-critical';
      riskBadge.textContent = 'Alert';
      riskText.textContent = 'High';
    }
  }

  // --- Intervention Engine ---
  function evaluateStrainHealth() {
    if (!state.isMonitoring) return;

    if (state.currentBPM < config.bpmThreshold && state.currentBPM > 0) {
      state.lowBlinkDurationSeconds += 1;

      // Notice alert after 15 seconds of sustained low blink
      if (state.lowBlinkDurationSeconds === 15) {
        logSessionEvent('Low Blink Notice', `${state.currentBPM} bpm`, 'Warning', 'Audio Chime');
        playAlertChime();
        if (config.notifications && 'Notification' in window && Notification.permission === 'granted') {
          new Notification('Ocolyx Eye-Strain Alert', {
            body: `Your blink rate is ${state.currentBPM} bpm. Remember to blink softly.`,
            icon: 'favicon.ico',
          });
        }
      }

      // Screen Dim intervention after 30 seconds
      if (state.lowBlinkDurationSeconds >= 30 && config.dimmingOverlay && elements.toggleDimFeature.checked) {
        const now = Date.now();
        if (now - state.lastDimTimestamp > 60000) {
          triggerDimOverlay();
          state.lastDimTimestamp = now;
          logSessionEvent('Screen Dim Triggered', `${state.currentBPM} bpm`, 'Critical', 'Ambient Dim Overlay');
        }
      }
    } else {
      state.lowBlinkDurationSeconds = 0;
    }
  }

  function triggerDimOverlay() {
    elements.dimOverlay.classList.add('active');
    setTimeout(() => {
      elements.dimOverlay.classList.remove('active');
    }, 4500);
  }

  function hideDimOverlay() {
    elements.dimOverlay.classList.remove('active');
  }

  // --- Session Event Logger ---
  function logSessionEvent(type, bpm, status, intervention) {
    const timestamp = new Date().toLocaleTimeString();
    const row = document.createElement('tr');

    const badgeClass =
      status === 'Healthy'
        ? 'badge-healthy'
        : status === 'Warning'
        ? 'badge-warning'
        : 'badge-critical';

    row.innerHTML = `
      <td>${timestamp}</td>
      <td><strong>${type}</strong></td>
      <td>${bpm}</td>
      <td><span class="status-badge ${badgeClass}">${status}</span></td>
      <td>${intervention}</td>
    `;

    // Remove empty notice if present
    const firstRow = elements.logTableBody.querySelector('td[colspan]');
    if (firstRow) elements.logTableBody.innerHTML = '';

    elements.logTableBody.prepend(row);
  }

  // --- Telemetry Waveform Visualizer ---
  function renderWaveform() {
    const canvas = elements.waveformCanvas;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Draw Grid Lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 1;
    for (let y = 0; y < height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Draw Threshold Line
    const threshY = height - (config.earThreshold / 0.45) * height;
    ctx.strokeStyle = '#f59e0b';
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.moveTo(0, threshY);
    ctx.lineTo(width, threshY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw Waveform Curve
    const data = state.earHistory;
    const step = width / (data.length - 1);

    ctx.beginPath();
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = '#00f0ff';

    // Area Gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, 'rgba(0, 240, 255, 0.35)');
    gradient.addColorStop(1, 'rgba(0, 240, 255, 0.0)');

    for (let i = 0; i < data.length; i++) {
      const val = Math.min(Math.max(data[i], 0.0), 0.45);
      const x = i * step;
      const y = height - (val / 0.45) * height;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    // Fill area below waveform
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw glowing current point cursor
    const latestY = height - (Math.min(Math.max(data[data.length - 1], 0.0), 0.45) / 0.45) * height;
    ctx.beginPath();
    ctx.arc(width - 2, latestY, 5, 0, 2 * Math.PI);
    ctx.fillStyle = '#00f0ff';
    ctx.shadowColor = '#00f0ff';
    ctx.shadowBlur = 12;
    ctx.fill();
    ctx.shadowBlur = 0;
  }

  // --- MediaPipe FaceMesh Frame Callback ---
  function onFaceMeshResults(results) {
    // Measure FPS
    state.fpsCount++;
    const now = performance.now();
    if (now - state.lastFpsTime >= 1000) {
      state.fps = state.fpsCount;
      state.fpsCount = 0;
      state.lastFpsTime = now;
      elements.hudFps.textContent = `${state.fps} FPS`;
    }

    const overlay = elements.overlayCanvas;
    const octx = overlay.getContext('2d');
    octx.clearRect(0, 0, overlay.width, overlay.height);

    if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
      const landmarks = results.multiFaceLandmarks[0];

      // Calculate Left and Right EAR
      const leftEAR = computeEAR(landmarks, [33, 160, 158, 133, 153, 144]);
      const rightEAR = computeEAR(landmarks, [362, 385, 387, 263, 373, 380]);
      const ear = (leftEAR + rightEAR) / 2.0;

      state.currentEAR = Number(ear.toFixed(3));
      elements.metricEar.textContent = state.currentEAR.toFixed(2);
      elements.hudEar.textContent = `EAR: ${state.currentEAR.toFixed(2)}`;

      // Push to waveform buffer
      state.earHistory.push(state.currentEAR);
      if (state.earHistory.length > 120) state.earHistory.shift();

      // Draw subtle eye contours on HUD canvas
      octx.strokeStyle = ear < config.earThreshold ? '#f59e0b' : '#00f0ff';
      octx.lineWidth = 1.5;

      const drawEye = (indices) => {
        octx.beginPath();
        indices.forEach((idx, i) => {
          const pt = landmarks[idx];
          const x = pt.x * overlay.width;
          const y = pt.y * overlay.height;
          if (i === 0) octx.moveTo(x, y);
          else octx.lineTo(x, y);
        });
        octx.closePath();
        octx.stroke();
      };

      drawEye([33, 160, 158, 133, 153, 144]);
      drawEye([362, 385, 387, 263, 373, 380]);

      // Blink State Machine
      if (ear < config.earThreshold) {
        state.closedFramesCount++;
        if (state.closedFramesCount >= config.consecutiveFrames) {
          state.isEyeClosed = true;
          elements.hudStatus.textContent = 'EYES CLOSED';
          elements.hudStatus.style.color = '#f59e0b';
        }
      } else {
        if (state.isEyeClosed) {
          registerBlink();
          state.isEyeClosed = false;
        }
        state.closedFramesCount = 0;
        elements.hudStatus.textContent = 'TRACKING';
        elements.hudStatus.style.color = '#10b981';
      }
    } else {
      elements.hudStatus.textContent = 'SEARCHING FACE';
      elements.hudStatus.style.color = '#94a3b8';
    }

    renderWaveform();
  }

  // --- Fallback Computer Vision (Canvas Frame Difference) ---
  let lastImageData = null;
  function processFallbackCVFrame() {
    if (!state.isMonitoring) return;

    const video = elements.webcamVideo;
    if (video.readyState < 2) {
      requestAnimationFrame(processFallbackCVFrame);
      return;
    }

    const overlay = elements.overlayCanvas;
    const ctx = overlay.getContext('2d');

    // Draw video frame to small buffer
    ctx.drawImage(video, 0, 0, overlay.width, overlay.height);
    const frame = ctx.getImageData(0, 0, overlay.width, overlay.height);
    const data = frame.data;

    // Check optical frame difference in upper-center region (eye band)
    if (lastImageData) {
      let diff = 0;
      const startY = Math.floor(overlay.height * 0.25);
      const endY = Math.floor(overlay.height * 0.55);

      for (let y = startY; y < endY; y += 4) {
        for (let x = 0; x < overlay.width; x += 4) {
          const idx = (y * overlay.width + x) * 4;
          const delta = Math.abs(data[idx] - lastImageData.data[idx]);
          diff += delta;
        }
      }

      const normalizedDiff = diff / 150000;
      const syntheticEAR = Math.max(0.12, Math.min(0.38, 0.32 - normalizedDiff));
      state.currentEAR = Number(syntheticEAR.toFixed(2));
      elements.metricEar.textContent = state.currentEAR.toFixed(2);
      elements.hudEar.textContent = `EAR: ${state.currentEAR.toFixed(2)}`;

      state.earHistory.push(state.currentEAR);
      if (state.earHistory.length > 120) state.earHistory.shift();

      if (syntheticEAR < config.earThreshold) {
        state.closedFramesCount++;
        if (state.closedFramesCount >= config.consecutiveFrames) {
          state.isEyeClosed = true;
          elements.hudStatus.textContent = 'BLINKING';
        }
      } else {
        if (state.isEyeClosed) {
          registerBlink();
          state.isEyeClosed = false;
        }
        state.closedFramesCount = 0;
        elements.hudStatus.textContent = 'OPTICAL TRACK';
      }
      renderWaveform();
    }

    lastImageData = frame;
    requestAnimationFrame(processFallbackCVFrame);
  }

  // --- Webcam Lifecycle ---
  async function startMonitoring() {
    try {
      elements.btnToggleMonitor.disabled = true;
      elements.systemStatusText.textContent = 'Starting Camera...';

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
        audio: false,
      });

      state.webcamStream = stream;
      elements.webcamVideo.srcObject = stream;
      await elements.webcamVideo.play();

      if (elements.radarStatusTitle) {
        elements.radarStatusTitle.textContent = 'Active Eye Tracking';
        elements.radarStatusDesc.textContent = 'Camera is actively monitoring blinks in memory. Video is hidden from screen.';
      }

      // Resize overlay canvas to match video
      elements.overlayCanvas.width = elements.webcamVideo.videoWidth || 640;
      elements.overlayCanvas.height = elements.webcamVideo.videoHeight || 480;

      // Match waveform canvas dimensions
      elements.waveformCanvas.width = elements.waveformCanvas.clientWidth || 400;
      elements.waveformCanvas.height = elements.waveformCanvas.clientHeight || 220;

      // Initialize FaceMesh if loaded from CDN
      if (window.FaceMesh && !state.faceMeshInstance) {
        state.faceMeshInstance = new window.FaceMesh({
          locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`,
        });
        state.faceMeshInstance.setOptions({
          maxNumFaces: 1,
          refineLandmarks: true,
          minDetectionConfidence: 0.5,
          minTrackingConfidence: 0.5,
        });
        state.faceMeshInstance.onResults(onFaceMeshResults);

        if (window.Camera) {
          state.cameraUtilsInstance = new window.Camera(elements.webcamVideo, {
            onFrame: async () => {
              if (state.isMonitoring && state.faceMeshInstance) {
                await state.faceMeshInstance.send({ image: elements.webcamVideo });
              }
            },
            width: 640,
            height: 480,
          });
          state.cameraUtilsInstance.start();
        }
      } else {
        // Fallback to in-browser optical CV
        state.useFallbackCV = true;
        requestAnimationFrame(processFallbackCVFrame);
      }

      state.isMonitoring = true;
      state.sessionStartTime = Date.now();
      state.sessionTimerId = setInterval(updateSessionTimer, 1000);
      setInterval(evaluateStrainHealth, 1000);

      elements.btnToggleMonitor.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
        <span>Stop Monitoring</span>
      `;
      elements.btnToggleMonitor.className = 'btn btn-danger';
      elements.btnToggleMonitor.disabled = false;

      elements.systemStatusDot.className = 'status-dot active';
      elements.systemStatusText.textContent = 'Vision Active';
      elements.metricSessionBadge.className = 'status-badge badge-healthy';
      elements.metricSessionBadge.textContent = 'Live Session';

      logSessionEvent('Session Started', '--', 'Healthy', 'Webcam Initialized');
    } catch (err) {
      console.error('Webcam initialization failed', err);
      alert('Could not access webcam. Please verify camera permissions in your browser.');
      elements.btnToggleMonitor.disabled = false;
      elements.systemStatusText.textContent = 'Camera Blocked';
    }
  }

  function stopMonitoring() {
    state.isMonitoring = false;

    if (state.webcamStream) {
      state.webcamStream.getTracks().forEach((track) => track.stop());
      state.webcamStream = null;
    }
    if (state.cameraUtilsInstance) {
      try {
        state.cameraUtilsInstance.stop();
      } catch (e) {}
    }

    clearInterval(state.sessionTimerId);
    if (elements.radarStatusTitle) {
      elements.radarStatusTitle.textContent = 'System Standby';
      elements.radarStatusDesc.textContent = 'Camera tracks blinks in local memory. Video is hidden from screen.';
    }

    elements.btnToggleMonitor.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
      <span>Start Monitoring</span>
    `;
    elements.btnToggleMonitor.className = 'btn btn-primary';
    elements.systemStatusDot.className = 'status-dot';
    elements.systemStatusText.textContent = 'System Idle';
    elements.metricSessionBadge.className = 'status-badge badge-neutral';
    elements.metricSessionBadge.textContent = 'Stopped';
    elements.hudStatus.textContent = 'OFFLINE';

    hideDimOverlay();
    logSessionEvent('Session Ended', `${state.currentBPM} bpm`, 'Healthy', 'User Stopped');
  }

  // --- Session Duration Timer ---
  function updateSessionTimer() {
    if (!state.sessionStartTime) return;
    const elapsedMs = Date.now() - state.sessionStartTime;
    const hours = Math.floor(elapsedMs / 3600000);
    const mins = Math.floor((elapsedMs % 3600000) / 60000);
    const secs = Math.floor((elapsedMs % 60000) / 1000);

    const pad = (n) => String(n).padStart(2, '0');
    elements.metricTimer.textContent = `${pad(hours)}:${pad(mins)}:${pad(secs)}`;
  }

  // --- 20-20-20 Micro-Exercise Modal ---
  let exerciseInterval = null;
  function startExercise() {
    let secondsRemaining = 20;
    elements.exerciseCountdown.textContent = secondsRemaining;
    elements.exerciseModal.classList.add('active');

    const steps = [
      'Inhale slowly and look at an object 20 feet away...',
      'Blink gently and relax your eye muscles...',
      'Breathe out smoothly, keeping your gaze soft...',
      'Take two deep natural blinks...',
      'Excellent. Your tear film is refreshed.',
    ];

    exerciseInterval = setInterval(() => {
      secondsRemaining--;
      elements.exerciseCountdown.textContent = secondsRemaining;

      const stepIndex = Math.min(
        steps.length - 1,
        Math.floor(((20 - secondsRemaining) / 20) * steps.length)
      );
      elements.exerciseInstruction.textContent = steps[stepIndex];

      if (secondsRemaining <= 0) {
        clearInterval(exerciseInterval);
        playAlertChime();
        setTimeout(closeExercise, 1200);
      }
    }, 1000);
  }

  function closeExercise() {
    clearInterval(exerciseInterval);
    elements.exerciseModal.classList.remove('active');
  }

  // --- View Switcher ---
  function switchView(viewName) {
    elements.navButtons.forEach((btn) => {
      if (btn.dataset.view === viewName) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    elements.viewSections.forEach((section) => {
      if (section.id === `view-${viewName}`) {
        section.classList.add('active');
      } else {
        section.classList.remove('active');
      }
    });
  }

  // --- Event Listeners ---
  function bindEvents() {
    // Monitor Toggle
    elements.btnToggleMonitor.addEventListener('click', () => {
      if (state.isMonitoring) stopMonitoring();
      else startMonitoring();
    });

    // Guided Exercise
    elements.btnStartExercise.addEventListener('click', startExercise);
    elements.btnCloseExercise.addEventListener('click', closeExercise);

    // Nav Buttons
    elements.navButtons.forEach((btn) => {
      btn.addEventListener('click', () => switchView(btn.dataset.view));
    });

    // Settings Sliders
    elements.cfgBpm.addEventListener('input', (e) => {
      config.bpmThreshold = Number(e.target.value);
      elements.cfgBpmVal.textContent = `${e.target.value} bpm`;
    });

    elements.cfgEar.addEventListener('input', (e) => {
      config.earThreshold = Number(e.target.value);
      elements.cfgEarVal.textContent = Number(e.target.value).toFixed(2);
      elements.metricEarBadge.textContent = `Threshold: ${Number(e.target.value).toFixed(2)}`;
    });

    elements.cfgAudio.addEventListener('change', (e) => {
      config.audioAlerts = e.target.checked;
    });

    elements.cfgDim.addEventListener('change', (e) => {
      config.dimmingOverlay = e.target.checked;
    });

    elements.btnSaveSettings.addEventListener('click', () => {
      try {
        localStorage.setItem('ocolyx_web_config', JSON.stringify(config));
        alert('Settings saved successfully!');
        switchView('dashboard');
      } catch (e) {
        alert('Could not save settings to localStorage.');
      }
    });

    // Request Notification Permissions
    elements.btnRequestNotifications.addEventListener('click', async () => {
      if ('Notification' in window) {
        const perm = await Notification.requestPermission();
        if (perm === 'granted') {
          config.notifications = true;
          elements.btnRequestNotifications.textContent = 'Notifications Enabled ✓';
          elements.btnRequestNotifications.disabled = true;
        } else {
          alert('Notification permission was denied.');
        }
      }
    });

    // Clear Logs
    elements.btnClearLogs.addEventListener('click', () => {
      elements.logTableBody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; color: var(--text-dim); padding: 30px;">
            Log cleared.
          </td>
        </tr>
      `;
    });

    // Window Resize -> Adjust Waveform Canvas
    window.addEventListener('resize', () => {
      elements.waveformCanvas.width = elements.waveformCanvas.clientWidth || 400;
      elements.waveformCanvas.height = elements.waveformCanvas.clientHeight || 220;
      renderWaveform();
    });
  }

  // --- Initialization ---
  function init() {
    bindEvents();
    elements.cfgBpm.value = config.bpmThreshold;
    elements.cfgBpmVal.textContent = `${config.bpmThreshold} bpm`;
    elements.cfgEar.value = config.earThreshold;
    elements.cfgEarVal.textContent = config.earThreshold.toFixed(2);
    elements.cfgAudio.checked = config.audioAlerts;
    elements.cfgDim.checked = config.dimmingOverlay;

    // Canvas sizes
    elements.waveformCanvas.width = elements.waveformCanvas.clientWidth || 400;
    elements.waveformCanvas.height = elements.waveformCanvas.clientHeight || 220;
    renderWaveform();
  }

  document.addEventListener('DOMContentLoaded', init);
})();

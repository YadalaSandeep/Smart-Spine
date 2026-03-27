/**
 * posture.js
 * Client-Side MediaPipe Pose Detection with direct getUserMedia camera access
 */

// UI Elements
const webcamVideo = document.getElementById('webcamVideo');
const outputCanvas = document.getElementById('outputCanvas');
const canvasCtx = outputCanvas.getContext('2d');
const idlePrompt = document.getElementById('idleVideoPrompt');
const btnStart = document.getElementById('btnStartDetect');
const btnStop = document.getElementById('btnStopDetect');
const btnAntiGravity = document.getElementById('btnAntiGravity');
const badgeStatus = document.getElementById('monitorStatus');

const dsStatus = document.getElementById('curPostureStatus');
const dsGood = document.getElementById('curGoodTime');
const dsBad = document.getElementById('curBadTime');

let _pose = null;
let _stream = null;
let _isDetecting = false;
let _antiGravityMode = false;
let _flashState = false;
let _badPostureStartTime = null;
let _lastSyncTime = 0;
let _analysisLoopId = null;

// Firebase Initialization
let db = null;
if (typeof firebase !== 'undefined') {
    const firebaseConfig = { projectId: "smart-spine-b553a" };
    if (!firebase.apps.length) {
        firebase.initializeApp(firebaseConfig);
    }
    db = firebase.firestore();
} else {
    console.warn("[Firebase] SDK not found. Cloud syncing disabled.");
}

// Session Stats
let _stats = {
    goodSec: 0,
    badSec: 0,
    startTime: null,
    lastUpdate: null,
    history: []
};

// Thresholds (Refined to 10 degrees)
const NECK_THRESHOLD = 10;
const SPINE_THRESHOLD = 10;
const SHOULDER_THRESHOLD = 5;

function resetUI() {
    dsStatus.textContent = 'AI Detection Running...';
    dsStatus.className = 'value text-cyan';
    dsGood.textContent = '0s';
    dsBad.textContent = '0s';
    document.getElementById('toastAlert').style.display = 'none';
    _badPostureStartTime = null;
}

function initMediaPipe() {
    _pose = new Pose({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose@0.5.1675469404/${file}`
    });

    _pose.setOptions({
        modelComplexity: 1,
        smoothLandmarks: true,
        minDetectionConfidence: 0.6,
        minTrackingConfidence: 0.6
    });

    _pose.onResults(onResults);
}

function drawLine(p1, p2, color, thickness = 4) {
    canvasCtx.beginPath();
    canvasCtx.moveTo(p1.x * outputCanvas.width, p1.y * outputCanvas.height);
    canvasCtx.lineTo(p2.x * outputCanvas.width, p2.y * outputCanvas.height);
    canvasCtx.strokeStyle = color;
    canvasCtx.lineWidth = thickness;
    canvasCtx.lineCap = 'round';
    canvasCtx.stroke();
}

function onResults(results) {
    if (!_isDetecting) return;

    canvasCtx.save();
    canvasCtx.clearRect(0, 0, outputCanvas.width, outputCanvas.height);
    
    // Draw the camera feed onto the canvas
    canvasCtx.drawImage(webcamVideo, 0, 0, outputCanvas.width, outputCanvas.height);

    if (results.poseLandmarks) {
        analyzePosture(results.poseLandmarks);
    }
    
    canvasCtx.restore();
}

function analyzePosture(landmarks) {
    const leftEar = landmarks[7];
    const rightEar = landmarks[8];
    const leftShoulder = landmarks[11];
    const rightShoulder = landmarks[12];
    const leftHip = landmarks[23];
    const rightHip = landmarks[24];

    // Midpoints for skeleton logic
    const midEar = { x: (leftEar.x + rightEar.x) / 2, y: (leftEar.y + rightEar.y) / 2 };
    const midShoulder = { x: (leftShoulder.x + rightShoulder.x) / 2, y: (leftShoulder.y + rightShoulder.y) / 2 };
    const midHip = { x: (leftHip.x + rightHip.x) / 2, y: (leftHip.y + rightHip.y) / 2 };

    // Angles
    const neckTilt = calculateAngle(midEar, midShoulder);
    const spineLean = calculateAngle(midShoulder, midHip);
    const shoulderDiff = Math.abs(leftShoulder.y - rightShoulder.y) * 100;

    const isBad = neckTilt > NECK_THRESHOLD || spineLean > SPINE_THRESHOLD || shoulderDiff > SHOULDER_THRESHOLD;
    
    // Choose Line Color
    let lineColor = '#22C55E'; // Green
    if (isBad) {
        lineColor = (neckTilt > 25 || spineLean > 20) ? '#EF4444' : '#F59E0B'; // Red or Yellow
        if (_antiGravityMode && _flashState) lineColor = 'transparent'; // Flash effect
    }

    // DRAW SKELETON ALIGNMENT LINES
    drawLine(midEar, midShoulder, lineColor);
    drawLine(midShoulder, leftShoulder, lineColor);
    drawLine(midShoulder, rightShoulder, lineColor);
    drawLine(midShoulder, midHip, lineColor);
    drawLine(midHip, leftHip, lineColor);
    drawLine(midHip, rightHip, lineColor);
    drawLine(leftShoulder, rightShoulder, lineColor, 2);

    updateLiveStats(neckTilt, spineLean, shoulderDiff, isBad);
    
    if (window.spineVisualizer) {
        window.spineVisualizer.updatePosture(neckTilt, spineLean, shoulderDiff);
    }
}

function calculateAngle(p1, p2) {
    const dx = p2.x - p1.x;
    const dy = p2.y - p1.y;
    const angle = Math.atan2(Math.abs(dx), Math.abs(dy)) * (180 / Math.PI);
    return angle;
}

function updateLiveStats(neck, spine, shad, isBad) {
    const now = Date.now();
    const delta = _stats.lastUpdate ? (now - _stats.lastUpdate) / 1000 : 0;
    _stats.lastUpdate = now;

    const totalTime = _stats.goodSec + _stats.badSec;
    const sessionScore = totalTime > 0 ? (_stats.goodSec / totalTime) * 100 : 100;

    if (isBad) {
        _stats.badSec += delta;
        if (!dsStatus.textContent.includes('Bad Posture')) {
            savePostureData('Bad', totalTime);
        }
        dsStatus.textContent = '⚠ Bad Posture Detected';
        dsStatus.className = 'value text-red font-bold';
        if (!_badPostureStartTime) _badPostureStartTime = now;

        // Always show bad posture alert
        showToast('Bad Posture Detected – Please straighten your back.');
    } else {
        _stats.goodSec += delta;
        if (!dsStatus.textContent.includes('Good Posture') && dsStatus.textContent !== 'AI Detection Running...') {
            savePostureData('Good', totalTime);
        }
        dsStatus.textContent = '✅ Good Posture';
        dsStatus.className = 'value text-green font-bold';
        _badPostureStartTime = null;
        hideToast();
    }

    dsGood.textContent = `${Math.round(_stats.goodSec)}s`;
    dsBad.textContent = `${Math.round(_stats.badSec)}s`;

    // Anti-Gravity Mode: enhanced feedback
    if (_antiGravityMode) {
        _flashState = Math.floor(now / 500) % 2 === 0;

        if (isBad && _badPostureStartTime && (now - _badPostureStartTime) > 10000) {
            showToast('Posture correction urgently recommended!', true);
        }
    }

    // Graph Update Logic
    if (!_stats.lastGraphUpdate || (now - _stats.lastGraphUpdate) > 3000) {
        _stats.history.push({ time: new Date().toLocaleTimeString(), score: sessionScore });
        if (_stats.history.length > 30) _stats.history.shift();
        _stats.lastGraphUpdate = now;
        if (window.updateLiveGraph) window.updateLiveGraph(_stats.history);
    }

    // Firebase Periodic Sync (Every 5 seconds)
    if (now - _lastSyncTime > 5000) {
        savePostureData(isBad ? 'Bad' : 'Good', totalTime);
        _lastSyncTime = now;
    }
}

async function savePostureData(currentStatus, sessionTime) {
    if (!db) return;
    try {
        const data = {
            user: "Sandeep",
            posture: currentStatus,
            sessionTime: Math.round(sessionTime),
            goodPostureTime: Math.round(_stats.goodSec),
            badPostureTime: Math.round(_stats.badSec),
            timestamp: firebase.firestore.FieldValue.serverTimestamp()
        };
        await db.collection("posture_data").add(data);
        console.log("[Firebase] Posture data saved successfully:", data);
    } catch (error) {
        console.error("[Firebase] Error saving posture data:", error);
    }
}

function showToast(msg, persistent = false) {
    const toast = document.getElementById('toastAlert');
    toast.innerHTML = `⚠️ ${msg}`;
    toast.style.display = 'block';
    if (persistent) {
        toast.style.backgroundColor = 'var(--danger)';
        toast.style.border = '2px solid black';
    } else {
        toast.style.backgroundColor = 'var(--danger)';
        toast.style.border = 'none';
    }
}

function hideToast() {
    document.getElementById('toastAlert').style.display = 'none';
}

/**
 * Continuous analysis loop: sends webcam frames to MediaPipe Pose
 * at ~30fps using requestAnimationFrame for smooth, non-blocking analysis.
 */
function analysisLoop() {
    if (!_isDetecting || !_pose || !webcamVideo) return;

    // Only send when video has data
    if (webcamVideo.readyState >= 2) {
        _pose.send({ image: webcamVideo }).then(() => {
            if (_isDetecting) {
                _analysisLoopId = requestAnimationFrame(analysisLoop);
            }
        }).catch(err => {
            console.warn("[Posture] Frame send error:", err);
            if (_isDetecting) {
                _analysisLoopId = requestAnimationFrame(analysisLoop);
            }
        });
    } else {
        // Video not ready yet, retry next frame
        _analysisLoopId = requestAnimationFrame(analysisLoop);
    }
}

/**
 * Start detection using navigator.mediaDevices.getUserMedia directly.
 * Shows clear error message if camera access fails.
 */
async function startDetection() {
    if (_isDetecting) return;

    // Request camera permission via getUserMedia
    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw new Error("Secure context required");
        _stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: 'user' }
        });

        // Attach the stream to the video element
        webcamVideo.srcObject = _stream;
        await webcamVideo.play();

        _isDetecting = true;
        _stats = { goodSec: 0, badSec: 0, startTime: Date.now(), lastUpdate: Date.now(), history: [] };
        resetUI();
        
        idlePrompt.style.display = 'none';
        outputCanvas.style.display = 'block';
        document.getElementById('serverVideoFeed').style.display = 'none';
        btnStart.style.display = 'none';
        btnStop.style.display = 'inline-block';
        badgeStatus.textContent = 'Running';
        badgeStatus.className = 'status-badge live';

        if (!_pose) initMediaPipe();

        // Start continuous analysis loop
        console.log("[Posture] ✅ Camera active, starting continuous analysis...");
        _analysisLoopId = requestAnimationFrame(analysisLoop);
    } catch (err) {
        console.warn("[Camera] Client access failed, falling back to server backend...", err);
        startServerDetection();
    }
}

async function startServerDetection() {
    try {
        await fetch('/api/camera/start', { method: 'POST' });
        
        const canvas = document.getElementById('outputCanvas');
        if (canvas) canvas.style.display = 'none';

        let serverImg = document.getElementById('serverVideoFeed');
        if (!serverImg) {
            serverImg = document.createElement('img');
            serverImg.id = 'serverVideoFeed';
            serverImg.style.width = '100%';
            serverImg.style.height = 'auto';
            serverImg.style.borderRadius = 'var(--radius)';
            document.querySelector('.video-container').insertBefore(serverImg, document.getElementById('idleVideoPrompt'));
        }
        serverImg.src = '/video_feed?' + new Date().getTime();
        serverImg.style.display = 'block';

        _isDetecting = true;
        _stats = { goodSec: 0, badSec: 0, startTime: Date.now(), lastUpdate: Date.now(), history: [] };
        resetUI();

        const ip = document.getElementById('idleVideoPrompt');
        if (ip) ip.style.display = 'none';
        
        const bs = document.getElementById('btnStartDetect');
        if (bs) bs.style.display = 'none';

        const bsp = document.getElementById('btnStopDetect');
        if (bsp) bsp.style.display = 'inline-block';

        const bst = document.getElementById('monitorStatus');
        if (bst) {
            bst.textContent = 'Running (Server)';
            bst.className = 'status-badge live';
        }

        _analysisLoopId = setInterval(pollServerStats, 1000);
    } catch (err) {
        console.error("[Camera] Server fallback failed:", err);
        const errorMsg = document.getElementById('idleVideoPrompt');
        if (errorMsg) {
            errorMsg.innerHTML = '<p style="color: #EF4444; font-weight: bold;">⚠️ Camera access completely failed.</p><p style="color: #94A3B8; margin-top: 8px;">Please allow camera permissions or check python backend.</p>';
            errorMsg.style.display = 'flex';
        }
    }
}

async function pollServerStats() {
    if (!_isDetecting) return;
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        const totalTime = data.good_duration + data.bad_duration;
        const sessionScore = totalTime > 0 ? (data.good_duration / totalTime) * 100 : 100;
        
        _stats.goodSec = data.good_duration;
        _stats.badSec = data.bad_duration;
        dsGood.textContent = Math.round(_stats.goodSec) + 's';
        dsBad.textContent = Math.round(_stats.badSec) + 's';
        
        const now = Date.now();
        if (!_stats.lastGraphUpdate || (now - _stats.lastGraphUpdate) > 3000) {
            _stats.history.push({ time: new Date().toLocaleTimeString(), score: sessionScore });
            if (_stats.history.length > 30) _stats.history.shift();
            _stats.lastGraphUpdate = now;
            if (window.updateLiveGraph) window.updateLiveGraph(_stats.history);
        }

        if (data.current_posture === 'Bad') {
            dsStatus.textContent = '⚠ Bad Posture Detected';
            dsStatus.className = 'value text-red font-bold';
            
            // We use standard showToast instead of referring to implicit ones
            const toast = document.getElementById('toastAlert');
            if (toast) {
                toast.innerHTML = '⚠️ Bad Posture Detected – Please straighten your back.';
                toast.style.display = 'block';
                toast.style.backgroundColor = 'var(--danger)';
            }
            if (window.spineVisualizer) window.spineVisualizer.setHighlight(true);
        } else {
            dsStatus.textContent = '✅ Good Posture';
            dsStatus.className = 'value text-green font-bold';
            const toast = document.getElementById('toastAlert');
            if (toast) toast.style.display = 'none';
            if (window.spineVisualizer) window.spineVisualizer.setHighlight(false);
        }
    } catch (e) { }
}

function stopDetection() {
    _isDetecting = false;

    const serverImg = document.getElementById('serverVideoFeed');
    if (serverImg && serverImg.style.display !== 'none') {
        serverImg.style.display = 'none';
        serverImg.src = '';
        fetch('/api/camera/stop', { method: 'POST' });
        clearInterval(_analysisLoopId);
    } else {
        if (_analysisLoopId) cancelAnimationFrame(_analysisLoopId);
        if (_stream) {
            _stream.getTracks().forEach(track => track.stop());
            _stream = null;
        }
        webcamVideo.srcObject = null;
    }
    _analysisLoopId = null;
    
    idlePrompt.style.display = 'flex';
    outputCanvas.style.display = 'none';
    btnStart.style.display = 'inline-block';
    btnStop.style.display = 'none';
    badgeStatus.textContent = 'Stopped';
    badgeStatus.className = 'status-badge offline';
    
    saveSessionLocally();
    setTimeout(() => { window.location.hash = 'analytics'; }, 1000);
}

async function saveSessionLocally() {
    const totalTime = _stats.goodSec + _stats.badSec;
    const scoreVal = totalTime > 0 ? Math.round((_stats.goodSec / totalTime) * 100) : 0;
    const session = {
        date: new Date().toLocaleDateString('en-CA'), // YYYY-MM-DD
        time: new Date().toLocaleTimeString('it-IT'), // HH:MM:SS
        posture_score: scoreVal,
        good_posture_time: Math.round(_stats.goodSec),
        bad_posture_time: Math.round(_stats.badSec),
        session_duration: Math.round((Date.now() - _stats.startTime) / 1000),
        bad_streak_count: 0
    };

    // 1. Save to LocalStorage (as backup/offline speed)
    let localData = JSON.parse(localStorage.getItem('spine_sessions') || '[]');
    localData.push(session);
    localStorage.setItem('spine_sessions', JSON.stringify(localData));

    // 2. Sync to Firebase via Backend
    try {
        console.log("[Firebase] Syncing session to cloud...");
        const resp = await fetch('/api/save_session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(session)
        });
        const result = await resp.json();
        console.log("[Firebase] Sync result:", result);
    } catch (err) {
        console.error("[Firebase] Sync failed:", err);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log("[Posture] Initializing event listeners...");
    
    const elements = {
        btnStart: document.getElementById('btnStartDetect'),
        btnStop: document.getElementById('btnStopDetect'),
        btnAntiGravity: document.getElementById('btnAntiGravity')
    };

    if (elements.btnStart) {
        elements.btnStart.addEventListener('click', startDetection);
    }
    if (elements.btnStop) {
        elements.btnStop.addEventListener('click', stopDetection);
    }
    if (elements.btnAntiGravity) {
        elements.btnAntiGravity.addEventListener('click', () => {
            _antiGravityMode = !_antiGravityMode;
            elements.btnAntiGravity.textContent = _antiGravityMode ? '🚀 Deactivate Anti-Gravity' : '🚀 Activate Anti-Gravity Mode';
            elements.btnAntiGravity.classList.toggle('btn-primary');
        });
    }
    
    // Global aliases for legacy support
    window.btnStart = elements.btnStart;
    window.btnStop = elements.btnStop;

    console.log("[Posture] 🔍 Detection buttons ready.");
});

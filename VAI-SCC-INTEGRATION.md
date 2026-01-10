# VAI-SCC Integration Guide

## Bidirectional Patient Context Sync via postMessage

This document describes how **VAI (Voice AI / PlaudAI Uploader)** and **SCC (Surgical Command Center)** communicate when VAI is embedded as an iframe in SCC.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SURGICAL COMMAND CENTER (SCC)                        │
│                    http://localhost:3001                                 │
│                                                                         │
│  ┌───────────────────┐                    ┌──────────────────────────┐  │
│  │ Patient Sidebar   │                    │ VAI iframe               │  │
│  │                   │                    │ src=100.75.237.36:8001   │  │
│  │ ┌───────────────┐ │   PATIENT_CONTEXT  │                          │  │
│  │ │ Pringle, J    │─┼───────────────────►│  Receives & loads        │  │
│  │ │ MRN: 35072287 │ │                    │  patient by MRN          │  │
│  │ └───────────────┘ │                    │                          │  │
│  │ ┌───────────────┐ │                    │                          │  │
│  │ │ Allen, D      │ │◄───────────────────┼─ PATIENT_SELECTED        │  │
│  │ └───────────────┘ │                    │  (user clicked in VAI)   │  │
│  └───────────────────┘                    └──────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Message Protocol

### SCC → VAI Messages

| Message Type | Trigger | Payload |
|--------------|---------|---------|
| `PATIENT_CONTEXT_LOADED` | User selects patient in SCC sidebar | `{ type, mrn, patientName }` |
| `SELECT_PATIENT` | Direct command to load a patient | `{ type, mrn }` |

### VAI → SCC Messages

| Message Type | Trigger | Payload |
|--------------|---------|---------|
| `VAI_READY` | VAI iframe finished loading | `{ type, source: 'vai-clinical' }` |
| `PATIENT_SELECTED` | User clicks patient in VAI | `{ type, mrn, patientName, source }` |

---

## VAI Implementation

The integration code is located in `frontend/index.html` (lines 1284-1403).

### SCC_INTEGRATION Object

```javascript
const SCC_INTEGRATION = {
    isEmbedded: window.parent !== window,  // Detect iframe context
    currentMrn: null,
    currentPatientName: null,

    // Notify parent SCC when patient selected
    notifyPatientSelected(mrn, patientName) {
        if (!this.isEmbedded) return;
        window.parent.postMessage({
            type: 'PATIENT_SELECTED',
            mrn: mrn,
            patientName: patientName,
            source: 'vai-clinical'
        }, '*');
    },

    // Load patient by MRN
    loadPatientByMRN(mrn) {
        document.getElementById('emrMrnSearch').value = mrn;
        switchTab('emr');
        loadPatientRecords();
    },

    // Parse MRN from URL (supports ?mrn=XXX and #emr?mrn=XXX)
    getMRNFromURL() {
        let params = new URLSearchParams(window.location.search);
        if (params.get('mrn')) return params.get('mrn');

        const hash = window.location.hash;
        if (hash.includes('?')) {
            params = new URLSearchParams(hash.split('?')[1]);
            if (params.get('mrn')) return params.get('mrn');
        }
        return null;
    },

    init() {
        // Listen for SCC messages
        window.addEventListener('message', (event) => {
            if (event.data?.type === 'PATIENT_CONTEXT_LOADED' && event.data.mrn) {
                this.loadPatientByMRN(event.data.mrn);
            }
            if (event.data?.type === 'SELECT_PATIENT' && event.data.mrn) {
                this.loadPatientByMRN(event.data.mrn);
            }
        });

        // Check URL for MRN on load
        const urlMrn = this.getMRNFromURL();
        if (urlMrn) {
            setTimeout(() => this.loadPatientByMRN(urlMrn), 100);
        }

        // Notify parent that VAI is ready
        if (this.isEmbedded) {
            window.parent.postMessage({
                type: 'VAI_READY',
                source: 'vai-clinical'
            }, '*');
        }
    }
};
```

---

## SCC Implementation Requirements

SCC needs to implement these features:

### 1. Update iframe URL when patient changes

```javascript
// In patient-context.js or equivalent
function updateVAIFrames(mrn) {
    const frames = [
        document.getElementById('vai-query-frame'),
        document.getElementById('vai-emr-frame')
    ];

    frames.forEach(frame => {
        if (frame) {
            const baseUrl = frame.src.split('?')[0];
            frame.src = `${baseUrl}?mrn=${mrn}`;
            console.log(`[PatientContext] Updated ${frame.id} with MRN: ${mrn}`);
        }
    });
}
```

### 2. Send postMessage for immediate context

```javascript
function sendPatientContextToVAI(mrn, patientName) {
    const frames = document.querySelectorAll('iframe[id*="vai"]');

    frames.forEach(frame => {
        frame.contentWindow.postMessage({
            type: 'PATIENT_CONTEXT_LOADED',
            mrn: mrn,
            patientName: patientName
        }, '*');
        console.log(`[PatientContext] Posted context to ${frame.id}`);
    });
}
```

### 3. Listen for VAI patient selection

```javascript
window.addEventListener('message', (event) => {
    if (event.data?.type === 'PATIENT_SELECTED' && event.data.source === 'vai-clinical') {
        console.log('[SCC] Received patient selection from VAI:', event.data.mrn);

        // Update SCC's patient context
        selectPatientByMRN(event.data.mrn);
    }

    if (event.data?.type === 'VAI_READY') {
        console.log('[SCC] VAI iframe ready, sending current patient context');
        // Send current patient to newly loaded iframe
        if (currentPatientMrn) {
            event.source.postMessage({
                type: 'PATIENT_CONTEXT_LOADED',
                mrn: currentPatientMrn
            }, '*');
        }
    }
});
```

---

## URL Parameter Support

VAI supports loading a patient directly via URL:

| Format | Example |
|--------|---------|
| Query string | `http://100.75.237.36:8001/index.html?mrn=35072287` |
| Hash-based | `http://100.75.237.36:8001/index.html#emr?mrn=35072287` |

This allows SCC to update iframe `src` attribute instead of using postMessage.

---

## Testing

### Browser Console Tests

**In SCC (parent window):**
```javascript
// Send patient context to VAI
document.getElementById('vai-query-frame').contentWindow.postMessage({
    type: 'PATIENT_CONTEXT_LOADED',
    mrn: '35072287'
}, '*');
```

**In VAI (iframe or standalone):**
```javascript
// Check integration status
console.log('Embedded:', SCC_INTEGRATION.isEmbedded);
console.log('Current MRN:', SCC_INTEGRATION.currentMrn);

// Manually load a patient
SCC_INTEGRATION.loadPatientByMRN('35072287');
```

### Expected Console Output

**SCC side:**
```
[PatientContext] Updating vai-query-frame URL with MRN: 35072287
[PatientContext] Posted patient context to vai-query-frame
[SCC] Received patient selection from VAI: 18889107
```

**VAI side:**
```
[VAI-SCC] Initializing integration. Embedded: true
[VAI-SCC] Received patient context from SCC: 35072287
[VAI-SCC] Loading patient by MRN: 35072287
[VAI-SCC] Notifying parent of patient selection: 35072287
```

---

## Telemetry

Patient context sync events are sent to Observer:

| Stage | Event | Data |
|-------|-------|------|
| `vai_sync` | `CONTEXT_RECEIVED` | `{ mrn, source }` |
| `vai_sync` | `CONTEXT_SENT` | `{ mrn, target_frame }` |
| `vai_sync` | `PATIENT_LOADED` | `{ mrn, success, duration_ms }` |

---

## Security Notes

- postMessage uses `'*'` for origin (development mode)
- For production, restrict to specific origins:
  ```javascript
  window.parent.postMessage(data, 'http://localhost:3001');  // SCC origin
  frame.contentWindow.postMessage(data, 'http://100.75.237.36:8001');  // VAI origin
  ```
- No PHI is transmitted via postMessage (only MRN)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Jan 2026 | Initial VAI-SCC postMessage integration |

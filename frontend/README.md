# AI CCTV Fire & Smoke Monitoring Platform - Frontend Architecture & Decoupling Strategy

## Overview

This repository uses a **Strictly Frontend-Independent Architecture**. In Phase 1, no frontend application is created. The backend serves purely as a headless, API-first service exposing standardized interfaces.

---

## Frontend Independence Principles

The backend communicates strictly via protocol specifications:

1. **REST API (JSON over HTTP/HTTPS)**
   - All data exchanges (camera management, alert queries, configuration) use standard JSON request and response models defined via OpenAPI / Pydantic schemas.

2. **Real-time Event WebSockets (`ws://` / `wss://`)**
   - WebSockets are used **exclusively for real-time alert notifications** (e.g., instant push of Fire/Smoke detection events).
   - Video frame streaming is **decoupled** from WebSockets to avoid standard browser payload overhead.

3. **Browser-Compatible Video Streaming Architecture**
   - In subsequent phases, video streaming will utilize HTTP MJPEG, HLS (HTTP Live Streaming), or WebRTC standards compatible with standard HTML5 elements (`<video>`, `<img>`, HLS.js, Video.js, or native video components across platforms).

---

## Supported Client Technologies

Because the backend is 100% decoupled, any API-compatible client can be integrated in future phases without altering backend business logic:

- **Web Frameworks**: React, Vue.js, Angular, Svelte, Next.js, Nuxt.js
- **Mobile Applications**: Flutter, React Native, Native Android (Kotlin/Java), Native iOS (Swift)
- **Desktop Applications**: Electron, Tauri, Qt / PySide, C# .NET WPF
- **Enterprise Integrations**: Third-party NVR/DVR management systems, SIEM dashboards, webhook receivers.

---

## Integrating a New Client (Guidelines for Phase 2+)

1. Consume OpenAPI Specification: Obtain schema definitions from `http://<backend-host>:8000/openapi.json` or Swagger UI at `/docs`.
2. Include Correlation Headers: Send `X-Request-ID` in HTTP headers to enable end-to-end request tracing.
3. Handle Standard Error Responses: Handle unified error envelopes:
   ```json
   {
     "success": false,
     "error": {
       "code": "ERROR_CODE",
       "message": "Human readable message",
       "details": null
     },
     "request_id": "uuid"
   }
   ```

# SafeZone

**A high-performance, WhatsApp-first disaster triage system engineered for Karachi.**  
*Winner at CODE//CONNECT'26 · UBIT, University of Karachi*

> SafeZone revolutionizes crisis response by cutting through the chaos of thousands of emergency messages, instantly extracting critical data, and delivering prioritized intelligence to emergency coordinators and field teams where it matters most.

---

## The Breakthrough Solution

During severe monsoon flooding, emergency channels face a massive **information overload crisis**. The bottleneck isn't a shortage of resources or community volunteers; it is the inability to quickly sort through hundreds of incoming messages to identify critical, life-threatening situations in real time.

SafeZone acts as an automated intelligence layer that intercepts chaotic, multi-lingual messages, structures them, and runs an instant prioritization matrix so that high-risk cases rise to the top of the action queue immediately.

## Core Capabilities

Citizens interact with a single, dedicated WhatsApp number using any natural phrasing — **English, Urdu, Roman Urdu, or mixed text**. Without downloading any apps, creating accounts, or filling out forms, SafeZone executes a robust pipeline within seconds:

* **Instant Fail-Safe Guidance:** The system immediately replies with localized safety protocols and official emergency hotlines. This response fires instantly before any AI processing, entirely removing human or network delays from the first response.
* **Geolocated Volunteer Coordination:** Utilizing precise spatial coordinates, the system automatically alerts the nearest on-duty community volunteers with a concise, privacy-safe, one-line incident brief.
* **Intelligent Scoring & De-duplication:** Incoming distress signals are scored using an objective urgency and vulnerability index. To optimize resources, duplicate reports originating from the same street are automatically merged into a single actionable incident thread.
* **Centralized Live Control Room:** Incidents stream directly onto a secure, real-time dashboard. High-level coordinators review automated triage scores alongside clear, plain-language reasoning to confirm and authorize formal rescue dispatches.
* **Closed-Loop Verification:** Once an incident is marked resolved, the system automatically checks back with the original reporter via WhatsApp. If help failed to arrive, the ticket is instantly escalated back to the top of the queue.

**Extensive Regional Footprint:** Fully localized and configured to cover **78 distinct areas across all seven districts** of Karachi Division.

---

## Elite System Architecture

SafeZone is built from the ground up for maximum runtime resilience, reliability, and predictability under crisis conditions:

* **Isolated AI Fail-Safes:** The AI LLM is completely isolated from the runtime critical path. It operates exclusively to convert free text into structured JSON fields. If external AI API providers go offline, the core system continues accepting, ranking, calculating coordinates, and routing tickets without missing a beat.
* **Centralized Security Gateway:** Outbound traffic routes through a single core function executing robust kill-switch protocols, dynamic rate-limiting, explicit domain allowlisting, and strict 24-hour delivery compliance checks.
* **Immutable Event Sourcing:** Every architectural state change is logged as a discrete event, allowing developers to replay precise historical system timelines directly from the data logs.
* **Rigorous Production Testing:** Shipped with **463 comprehensive unit and integration tests** passing with a 100% success rate, completely runnable offline without network dependencies or active API keys.

### The Tech Stack
* **Backend:** Python 3.11+, FastAPI, Supabase (PostgreSQL), WhatsApp Cloud API.
* **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, Server-Sent Events (SSE).

---

## Quickstart Guide

### Environment Setup
Create a `.env` file at the repository root based on `.env.example` to securely configure your local secrets, WhatsApp credentials, and Supabase database endpoints.

### 1. Backend Engine
Launch the high-performance FastAPI server directly from the `Backend/` directory:
```bash
cd Backend
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
*Note: On initialization, the backend automatically audits your configuration and prints out any potential integration anomalies.*

### 2. Frontend Interface
Initialize the reactive dashboard user interface:
```bash
cd Frontend
npm install
npm run dev
```
* The development server fires up on port `5173` and automatically reverse-proxies `/api` requests directly to the backend engine on port `8000`.

### 3. Automated Test Suite
Execute the offline test suite to verify system integrity:
```bash
cd Backend
python -m pytest -q
```

### 4. Utilities & Optimization
Generate secure cryptographic components for control room session authentication:
```bash
python -m scripts.hash_password
```
Compile and bootstrap localized OpenStreetMap spatial data files to enable runtime-free geocoding matches across Karachi:
```bash
python -m scripts.build_localities
```

---

## Engineering Team

**Team Nova Strike** — Department of Computer Science (UBIT), University of Karachi

* **Muhammad Salman** — [@SalmanZulfiqarShaikh](https://github.com)
* **Hussain Abbas** — [@hussainabbas6706](https://github.com)
* **Abdul Rehman** — [@mabdulrehmankhan666](https://github.com)
* **Usaim** — [@usaim35](https://github.com)

For the community, by the community.

---

## Data & Asset Attribution
* **Spatial Data:** Locality parameters and boundary datasets provided by OpenStreetMap contributors under the Open Database License (ODbL).
* **Specifications:** Detailed protocol mappings, non-negotiable architectural boundaries, and code ownership distribution can be found inside the comprehensive `AGENTS.md` file.

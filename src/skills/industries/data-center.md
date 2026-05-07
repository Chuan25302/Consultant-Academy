# Data Center — Skill Card

## Thai context
- Major operators: Equinix (BK1), STT GDC, AIS (Saraburi), True IDC, GULF
- Pace: hyperscaler builds (Microsoft, Google, AWS) ramping in EEC + Bangkok periphery
- Tier I → IV per Uptime Institute classification

## Energy profile (typical Tier III, ~5 MW IT load)
- **IT load**: 50–60% of total (servers, storage, network)
- **Cooling**: 30–40% (CRAC/CRAH, chiller plant, cooling tower)
- **UPS losses**: 5–8% (depends on topology)
- **Lighting + admin**: 2–3%
- **PUE** (Power Usage Effectiveness) = total / IT — target 1.3–1.5 for new builds

## High-impact opportunities
- **Hot/cold aisle containment** (10–25% cooling reduction)
- **Raised setpoint** — ASHRAE TC 9.9 allows up to 27°C inlet (vs 22°C historical)
- **Free cooling** in cooler months (Thailand: limited but possible at night)
- **Variable-speed CRAC fans + EC plug fans**
- **Liquid cooling** (direct-to-chip / immersion) for high-density (>15 kW/rack) — emerging
- **Chiller plant optimization** (variable primary flow + setpoint reset)
- Server consolidation + virtualization (fewer servers = less cooling)

## Standards
- **Uptime Institute Tier I-IV** — availability classification (Tier III = 99.982%)
- **ASHRAE TC 9.9** — thermal guidelines (recommended: 18–27°C, 60% RH max)
- **TIA-942** — telecom infrastructure standard
- **ISO 50600** — data center facility energy management
- **LEED** + **EDGE** for green DC certification
- อาคารควบคุมตาม พ.ร.บ. 2535 (ขนาดเข้าเกณฑ์)

## Talking to this customer
- Facility Engineer + DC Operations + Customer SLA Manager
- Uptime is religion — any retrofit must have proven, reversible procedure
- PUE is the headline KPI — every 0.05 reduction is news-worthy
- Customer co-location pricing tied to density + PUE — efficiency matters commercially

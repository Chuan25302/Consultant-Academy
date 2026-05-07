# BESS (Battery Energy Storage System) — Skill Card

## Key concepts
- **Round-trip efficiency** (RTE) = energy out ÷ energy in (LFP: 88–92%, NMC: 90–94%)
- **C-rate** — charge/discharge speed (1C = full discharge in 1 hour)
- **DoD** (Depth of Discharge) — cycling deeper = shorter life
- **Cycle life** — typical LFP 4,000–6,000 cycles to 80% capacity
- Chemistries: **LFP** (most common for stationary, safer), NMC (higher density), flow batteries (long-duration)

## Use cases in Thailand industry
- **Peak shaving** — reduce demand charge (กิโลวัตต์-สูงสุด) on TOU/TOD tariff
- **Solar self-consumption** — store midday solar for evening peak (4 บาท+/kWh)
- **Backup power** — replace/supplement diesel gen (cleaner + cheaper)
- **VSPP/SPP frequency response** — sell ancillary service to grid
- **Off-grid** — remote site combined with solar PV

## Economics rule of thumb
- Capex: ~10,000–20,000 บาท/kWh (2024) for utility-scale LFP including BoS
- Demand charge in TH: ~140–290 บาท/kW/month → peak shaving payback 4–8 yrs
- Combined solar + BESS: payback shorter when solar > 30% self-consumed
- Scope 2 reduction depends on RE source feeding the BESS

## Sizing approach
- Analyze 15-min interval data for 1 month
- Identify peak window (usually 14–22h in Thailand TOU)
- Size BESS to shave peak by X kW for Y hours
- Don't oversize — cycle life decay + capex doubles for marginal benefit

## Common pitfalls
- Spec'd in MWh without considering kW (peak shaving is power-limited, not energy)
- HVAC for battery room often missed (~3–5% parasitic)
- Warranty terms: cycle count vs throughput vs calendar — compare carefully
- Permitting + grid interconnect approval (PEA/MEA) takes 3–6 months

## Standards
- **IEC 62619 / 62933** — battery system safety + performance
- **NFPA 855** — fire safety in stationary BESS
- **IEEE 1547** — distributed resource interconnection
- **ERC** licensing for >1 MW or grid export

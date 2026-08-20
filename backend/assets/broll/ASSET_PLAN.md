# Visual asset plan

What to seed `assets/broll/library/` with, and why these and not others.

The retriever ranks on metadata, not pixels, so an asset earns its place by
being *describable* in the words a notice actually uses. A beautiful photo with
thin metadata will never be retrieved; a plain one tagged with the vocabulary
of the schemes we cover will be retrieved constantly.

## How assets are stored

```
assets/broll/library/<FACT_CATEGORY>/<name>.<ext>
assets/broll/library/<FACT_CATEGORY>/<name>.source.json
```

`<FACT_CATEGORY>` is one of `AUTHORITY`, `SCHEME_NAME`, `AMOUNT`, `DEADLINE`,
`ACTION_REQUIRED`, `ELIGIBILITY`, `BENEFICIARY`. The sidecar:

```json
{
  "category": "ELIGIBILITY",
  "title": "Smallholder farmers harvesting paddy",
  "description": "Two farmers cutting paddy by hand in a small field",
  "tags": ["farmer", "smallholder", "paddy", "harvest", "agriculture", "rural"],
  "domains": ["agriculture", "rural_livelihood"],
  "licence": "CC BY-SA 4.0",
  "artist": "...",
  "source_page": "https://commons.wikimedia.org/wiki/File:...",
  "width": 2048, "height": 1365
}
```

`domains` and `description` are new and optional; older sidecars without them
still load. Both feed `embedding_text()`, so filling them in materially
improves retrieval — `description` especially, because it is the only field
written in the same register as the narration.

**Tagging rule of thumb:** write the tags a *notice* would use, not the ones a
photographer would. `beneficiary`, `disbursement`, `verification`, `deadline`,
`installment` retrieve well. `golden hour`, `bokeh`, `wide angle` never will.

## Domains

Twelve domains cover the overwhelming majority of Indian government notices.
Each maps to the fact categories it most often serves.

| # | Domain | Serves | Why it matters |
|---|--------|--------|----------------|
| 1 | `agriculture` | ELIGIBILITY, BENEFICIARY, SCHEME_NAME | PM-KISAN, crop insurance, MSP — the single most common notice type |
| 2 | `banking_dbt` | AMOUNT, ACTION_REQUIRED | Almost every benefit scheme ends in a bank transfer |
| 3 | `identity_kyc` | ACTION_REQUIRED, DEADLINE | Aadhaar, e-KYC, ration card seeding — the most common *action* demanded |
| 4 | `rural_development` | ELIGIBILITY, BENEFICIARY | MGNREGA, PMAY-G, rural roads and water |
| 5 | `health` | SCHEME_NAME, BENEFICIARY | Ayushman Bharat, immunisation, PHC services |
| 6 | `education` | SCHEME_NAME, ELIGIBILITY | Scholarships, mid-day meal, admissions |
| 7 | `women_child` | BENEFICIARY, ELIGIBILITY | Anganwadi, maternity benefit, girl-child schemes |
| 8 | `energy_utilities` | SCHEME_NAME, AMOUNT | Ujjwala LPG, electrification, rooftop solar |
| 9 | `employment_skills` | ELIGIBILITY, ACTION_REQUIRED | Skill India, employment exchange, apprenticeships |
| 10 | `governance` | AUTHORITY | Ministry buildings, secretariats, official seals |
| 11 | `compliance_deadline` | DEADLINE | Calendars, clocks, queues, forms, service counters |
| 12 | `infrastructure` | SCHEME_NAME | Roads, water supply, electrification, connectivity |

## Assets to seed

Target **6–10 per domain**, roughly 3:1 stills to b-roll. Stills are cheap,
Ken Burns makes them move, and they carry the load. B-roll is expensive to
source and store, so spend it where motion actually says something — a hand
counting notes, a queue moving, a crop being cut.

Commons search terms in brackets are starting points for
`scripts/build_image_library.py`.

### 1. agriculture — ELIGIBILITY, BENEFICIARY
- **Stills:** smallholder farmer in field [`Category:Agriculture in India`]; paddy/wheat harvest by hand; tractor ploughing; farmer with produce at a mandi; irrigation channel in a small field; soil-health card / farm paperwork
- **B-roll:** wheat or paddy swaying in wind (loops beautifully); hand cutting crop; grain pouring through hands
- **Tags:** `farmer, smallholder, marginal, agriculture, crop, harvest, kisan, rural, land, paddy, wheat, irrigation`

### 2. banking_dbt — AMOUNT, ACTION_REQUIRED
- **Stills:** rural bank branch exterior; passbook being updated; ATM in a small town; bank counter with customers; rupee notes counted; UPI/QR payment at a small shop
- **B-roll:** notes being counted; passbook printer running; card inserted into ATM
- **Tags:** `bank, account, transfer, dbt, disbursement, rupee, payment, passbook, atm, upi, deposit, installment`

### 3. identity_kyc — ACTION_REQUIRED, DEADLINE
- **Stills:** biometric fingerprint scanner; Aadhaar enrolment centre; CSC / common service centre; person at a document counter; ration card / document close-up; form being filled
- **B-roll:** fingerprint scan glowing; queue advancing at a counter; stamp pressed onto a form
- **Tags:** `aadhaar, ekyc, verification, biometric, identity, enrolment, document, seeding, csc, authentication`

### 4. rural_development — ELIGIBILITY, BENEFICIARY
- **Stills:** village housing cluster; newly built rural road; handpump / village water point; MGNREGA worksite; village panchayat building; rural household exterior
- **B-roll:** water pumping from a handpump; road construction; village street life
- **Tags:** `village, rural, household, panchayat, housing, awas, road, water, mgnrega, gram`

### 5. health — SCHEME_NAME, BENEFICIARY
- **Stills:** primary health centre exterior; nurse with patient; vaccination in progress; health card / hospital paperwork; ASHA worker in a village; district hospital ward
- **B-roll:** vaccination being administered; PHC waiting area
- **Tags:** `health, hospital, clinic, phc, vaccination, treatment, ayushman, patient, asha, medical`

### 6. education — SCHEME_NAME, ELIGIBILITY
- **Stills:** government school building; students in classroom; girl student with books; scholarship / exam paperwork; school library; mid-day meal being served
- **B-roll:** students entering school; writing in a notebook
- **Tags:** `school, student, education, scholarship, classroom, exam, admission, literacy, books`

### 7. women_child — BENEFICIARY, ELIGIBILITY
- **Stills:** anganwadi centre; self-help group meeting; mother and infant at a health centre; women at a bank counter; women's cooperative at work
- **B-roll:** SHG meeting in progress; anganwadi activity
- **Tags:** `women, mother, child, anganwadi, maternity, shg, girl, family, welfare`
- **Care:** avoid identifiable children's faces. This project has already had to prune one such image after review — check at full resolution, not from a thumbnail.

### 8. energy_utilities — SCHEME_NAME, AMOUNT
- **Stills:** LPG cylinder delivered to a rural home; woman cooking on a gas stove; rural electrification poles; rooftop solar panels; electricity meter close-up
- **B-roll:** gas flame igniting; solar panels under moving cloud shadow
- **Tags:** `lpg, ujjwala, cylinder, cooking, electricity, power, solar, energy, connection, meter`

### 9. employment_skills — ELIGIBILITY, ACTION_REQUIRED
- **Stills:** vocational training workshop; ITI classroom; young people at a job fair; tailoring / craft training; employment exchange counter
- **B-roll:** hands at a sewing machine; welding sparks; training session
- **Tags:** `employment, skill, training, iti, apprentice, job, vocational, workshop, livelihood`

### 10. governance — AUTHORITY
- **Stills:** ministry building exterior; state secretariat; Parliament / North Block; district collectorate; official notice board; government seal or emblem *(not the State Emblem itself — its use is restricted)*
- **B-roll:** flag on a government building; office corridor
- **Tags:** `ministry, government, secretariat, official, authority, department, administration, collectorate, notice`

### 11. compliance_deadline — DEADLINE
- **Stills:** wall calendar; clock face; queue at a service counter; stack of forms; token/appointment slip; deadline stamped on a document
- **B-roll:** clock hands moving; queue advancing; calendar pages turning
- **Tags:** `deadline, cutoff, date, calendar, clock, last, urgent, expiry, queue, compliance, submit`

### 12. infrastructure — SCHEME_NAME
- **Stills:** rural road; water pipeline laying; transmission lines; bridge; mobile tower in a rural area
- **B-roll:** traffic on a new road; pipeline work; construction
- **Tags:** `road, bridge, pipeline, water, connectivity, construction, infrastructure, network`

## Licensing

Only these licences (already enforced in `scripts/build_image_library.py`):
Public Domain / CC0 / PDM, CC BY, CC BY-SA, GODL-India.

Never seed: anything NC or ND licensed, press-agency photographs, stills of
identifiable named officials, or images whose subject is an identifiable
private individual — most of all children.

Every asset keeps `licence`, `artist` and `source_page` in its sidecar. The
library directory is gitignored: these are other people's photographs and this
repo should not redistribute them.

## Building the index

```bash
cd backend
../.venv/Scripts/python.exe scripts/build_visual_index.py            # embed + store
../.venv/Scripts/python.exe scripts/query_visual_index.py "eligible farmer families" --compare
```

`--compare` shows the vector and fuzzy rankings side by side. If they agree on
every query, the vector index is not yet earning its keep — which usually
means the sidecars need richer `description` and `domains` fields rather than
more assets.

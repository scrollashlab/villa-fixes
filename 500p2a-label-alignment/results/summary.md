# 500p2a label alignment: results

Prereg sha256 `3910d3f3278ac0f93aa609ff939666e3b2ebc2c9a43636dc720e43305b74a1c5` (sealed 2026-10-08 20:30:27 HST). Scored once. Source of every number: `metrics.json` (sha256 `7922c7502c88c37e5f62a4b034f24d23976320b1aa8e2ffd9d0a12d8622a8072`).

**Verdict (P1): ALIGNED-UNREAD.** P2, P3 and P4 each reach the same verdict (3/3). None of their T* lies within 8 px of T*1 in the same orientation.

Grid G 13120 × 8091 (8.64 µm). The scored region R has 8,704,170 px, of which 3,055,075 are ink. The median column is 4482. Half B gives 4,354,257 pixels in 1,266 blocks of 64 × 64.

| Pred | T* (orientation, dy, dx) | AUC_B(T*) | AUC_B(identity) | Δ | 95% CI (block bootstrap, B=2000) |
|---|---|---|---|---|---|
| P1 canonical fwd | identity, −256, −177 | 0.4497 | 0.4072 | +0.0424 | [+0.0078, +0.0772] |
| P2 ps48 fwd | flip-UD, +91, −172 | 0.4909 | 0.4739 | +0.0170 | [−0.0282, +0.0598] |
| P3 ps512 fwd | rot180, −208, +256 | 0.5170 | 0.4968 | +0.0202 | [−0.0237, +0.0643] |
| P4 ps512 rev | identity, −256, +158 | 0.5019 | 0.5100 | −0.0081 | [−0.0481, +0.0337] |

Why P1 is not MISREGISTERED: T*1 is a shift of (−256, −177), far from identity, but Δ1 = 0.042 < 0.10 and AUC_B(T*1) = 0.450 < 0.65. Why it is not ALIGNED-READ: AUC_B(identity) = 0.407 < 0.65.

Observations (not pre-registered; reported, not tested):
- 3 of the 4 T* sit on the edge of the ±256 search range (P1, P3, P4). P2 is the exception. Together with the small Δ, this reads as no clear correlation peak anywhere in the family, rather than a found offset.
- At zero shift, the half-A separation (mean pred on ink − non-ink) is negative for all 4 predictions in all 4 orientations. P1's identity AUC_B of 0.407 is below chance.

Exploratory (pre-declared, not part of the verdict): the AUC of (255 − IR luminance) over all of R is **0.9897** at identity and 0.4585 at T*1. The labels follow the shipped IR photo closely on the shared canvas.

Limitations: the organizer models' training data is not documented. Rigid transforms only (4 orientations, ±256 px shifts); non-rigid or larger misregistration is not tested. Whether the IR photo itself is registered to the CT render is not tested here: the IR AUC shows that the labels agree with the IR, not that the IR agrees with the CT.

AI-assisted.

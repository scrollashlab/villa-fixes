# #1648 held-out matrix: results

Pre-registration sha256 `157a375acfff539253ac75cdf6dbe752d2eb0b83003c26fca3633d5febb32ec6`. Verdict: **CONFIRM** (3/3 segments confirm, 0 contradict).

| case | seed | dir | AUC L2 | AUC L0 | delta (L2-L0) | 95% CI | operative |
|---|---|---|---|---|---|---|---|
| pherc0139-w016 | seed42 | forward | 0.8829 | 0.5676 | +0.3153 | [+0.2571, +0.3719] | yes |
| pherc0139-w016 | seed42 | reverse | 0.5960 | 0.5546 | +0.0414 | [-0.1280, +0.1994] |  |
| pherc0139-w016 | seed43 | forward | 0.9143 | 0.6027 | +0.3116 | [+0.2445, +0.3864] | yes |
| pherc0139-w016 | seed43 | reverse | 0.5298 | 0.5705 | -0.0407 | [-0.1681, +0.0739] |  |
| pherc0814-46527 | seed42 | forward | 0.8861 | 0.6388 | +0.2473 | [+0.1765, +0.3066] | yes |
| pherc0814-46527 | seed42 | reverse | 0.5437 | 0.5297 | +0.0139 | [-0.1135, +0.1341] |  |
| pherc0814-46527 | seed43 | forward | 0.8568 | 0.6701 | +0.1867 | [+0.1139, +0.2556] | yes |
| pherc0814-46527 | seed43 | reverse | 0.5364 | 0.4836 | +0.0528 | [-0.0396, +0.1405] |  |
| pherc1667-w029 | seed42 | forward | 0.9007 | 0.5361 | +0.3646 | [+0.3147, +0.4145] | yes |
| pherc1667-w029 | seed42 | reverse | 0.6034 | 0.4665 | +0.1369 | [+0.0505, +0.2276] |  |
| pherc1667-w029 | seed43 | forward | 0.8980 | 0.5435 | +0.3545 | [+0.2967, +0.4107] | yes |
| pherc1667-w029 | seed43 | reverse | 0.6336 | 0.5333 | +0.1003 | [+0.0145, +0.1929] |  |

| case | operative direction | mean AUC fwd / rev | outcome |
|---|---|---|---|
| pherc0139-w016 | forward | 0.7419 / 0.5627 | confirms |
| pherc0814-46527 | forward | 0.7630 / 0.5233 | confirms |
| pherc1667-w029 | forward | 0.7196 / 0.5592 | confirms |

Sensitivity (L0 requantized to floor(sum/16)): pherc0139-w016: confirms, pherc0814-46527: confirms, pherc1667-w029: confirms

Average precision per run is in metrics.json (descriptive only).

# Evaluation, Metrics & Leakage Diagnostics

## 1. Reproducible Baseline Metrics

Evaluation performed using a stratified train/test split (80% train, 20% holdout) with 3-fold cross validation:

| Split | Metric | Value |
|---|---|---|
| **Holdout Test** | Accuracy | **100.0%** (399 / 399 correct) |
| **Holdout Test** | Macro F1 | **1.0000** |
| **Holdout Test** | ROC-AUC | **1.0000** |
| **Holdout Test** | Average Precision | **1.0000** |
| **Train CV (3-Fold)** | Accuracy | **99.62% ± 0.27%** |
| **Train CV (3-Fold)** | Macro F1 | **99.62% ± 0.27%** |
| **Train CV (3-Fold)** | ROC-AUC | **99.99% ± 0.006%** |

## 2. Confusion Matrix

```text
                  Predicted REAL    Predicted FAKE    Recall
Actual REAL            199                0           100.0%
Actual FAKE              0              200           100.0%
```

## 3. Source Confounding Diagnostic

* **Confounding Score:** 1.000 (100% confounded)
* In the reference dataset (`data/True.csv` and `data/Fake.csv`), 99.8% of real news articles are sourced from Reuters wire copy, while fake news articles originate from independent blogs with clickbait footers.
* The diagnostic reports that an out-of-source split is infeasible on this specific dataset because classes map 1:1 with source labels.
* Training with `--strip-source-artifacts` removes wire tags; accuracy shifts to **99.5%**.

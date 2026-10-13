# Machine Learning Pipeline & Checksum Security

## 1. Pipeline Architecture

The baseline classifier uses a scikit-learn pipeline persisted with joblib:

```text
Raw Text Input
      ↓
TextCleaner (Lowercasing, regex normalization, whitespace stripping)
      ↓
TfidfVectorizer (Word n-grams 1-2, sublinear TF scaling, min_df=2)
      ↓
LogisticRegression (L2 regularization, C=1.0, solver='lbfgs')
      ↓
Fake Probability [0.0 - 1.0]
      ↓
Uncertainty Band & Decision Rule
```

## 2. Model Integrity & Checksum Sidecar

Serialized Python objects (`.joblib` / `.pickle`) present security vulnerabilities if loaded from unverified sources. TrustSignal implements cryptographic sidecar checksums:

* Model Artifact: `outputs/pipeline.joblib`
* Sidecar Hash: `outputs/pipeline.joblib.sha256`

Before loading any model, `model_compat.load_pipeline()` recomputes the SHA-256 digest and verifies it against the sidecar. If a file swap or tampering occurs, execution halts immediately with a `ValueError`.

## 3. Sklearn Compatibility Repair

Cross-version compatibility patches ensure that models trained in older scikit-learn environments run reliably in modern Python 3.13 environments without deserialization crashes.

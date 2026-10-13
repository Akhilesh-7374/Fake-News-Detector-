# Contributing to TrustSignal

We welcome contributions to the TrustSignal Misinformation Intelligence Platform!

## Development Guidelines

1. **Keep Baseline Models Measurable:** Never remove the baseline TF-IDF + Logistic Regression model or bypass checksum verification.
2. **Responsible ML First:** Never claim the system knows absolute truth. Keep uncertainty bands and honest diagnostics.
3. **No Fabricated Data:** If external evidence or an OCR/audio provider is unavailable, report provider-unavailable explicitly.
4. **Run Tests:** Ensure all tests pass before submitting changes:
   ```bash
   python -m pytest tests/
   ```

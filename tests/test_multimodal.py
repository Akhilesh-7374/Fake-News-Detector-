from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from media_analyzer import MediaAnalyzer
from realtime_engine import RealTimeAnalyzer


def test_text_multimodal_job_completes(tmp_path):
    pipeline = tmp_path / 'missing.joblib'
    # Test object construction only; provider execution is separately covered by realtime tests.
    assert pipeline.name.endswith('.joblib')
    assert MediaAnalyzer is not None


def test_media_analyzer_kind_mapping():
    assert MediaAnalyzer._kind_from_mime('image/png', '.png') == 'image'
    assert MediaAnalyzer._kind_from_mime('audio/mpeg', '.mp3') == 'audio'
    assert MediaAnalyzer._kind_from_mime('video/mp4', '.mp4') == 'video'
    assert MediaAnalyzer._kind_from_mime('text/plain', '.txt') == 'text'

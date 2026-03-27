import pytest
import time
from utils import ScoreCalculator, SessionStats, ExerciseRecommender

def test_score_calculator_posture_score():
    assert ScoreCalculator.posture_score(10, 0) == 100.0
    assert ScoreCalculator.posture_score(0, 10) == 0.0
    assert ScoreCalculator.posture_score(5, 5) == 50.0
    assert ScoreCalculator.posture_score(0, 0) == 100.0

def test_score_calculator_bone_health_index():
    # Good posture, no streaks
    assert ScoreCalculator.bone_health_index(60, 0, 0) == 70.0  # 100 * 0.7 - 0 - 0
    # Bad posture, many streaks
    bhi = ScoreCalculator.bone_health_index(0, 60, 10)
    assert bhi < 70.0

def test_session_stats_initialization():
    stats = SessionStats()
    assert stats.good_duration == 0.0
    assert stats.bad_duration == 0.0
    assert stats.bad_streak_count == 0
    assert stats.last_posture == "Unknown"

def test_session_stats_update_good():
    stats = SessionStats()
    # Mock delta time by manually setting last_update_time
    stats.last_update_time = time.time() - 1.0 
    stats.update("Good Posture", {}, True)
    assert stats.good_duration >= 1.0
    assert stats.bad_duration == 0.0
    assert stats.last_posture == "Good Posture"

def test_session_stats_update_bad():
    stats = SessionStats()
    stats.last_update_time = time.time() - 1.0
    stats.update("Bad Posture", {}, True)
    assert stats.bad_duration >= 1.0
    assert stats.bad_streak_count == 1
    assert stats.last_posture == "Bad Posture"

def test_exercise_recommender():
    recs = ExerciseRecommender.recommend(0)
    assert len(recs) == 2
    recs = ExerciseRecommender.recommend(3)
    assert len(recs) == 4
    recs = ExerciseRecommender.recommend(6)
    assert len(recs) > 4

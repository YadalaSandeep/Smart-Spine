import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index_page(client):
    rv = client.get('/')
    assert rv.status_code == 200
    assert b"Smart Spine" in rv.data

def test_api_stats(client):
    rv = client.get('/api/stats')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'posture_score' in data
    assert 'bone_health_index' in data

def test_api_exercises(client):
    rv = client.get('/api/exercises')
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)
    assert len(data) > 0

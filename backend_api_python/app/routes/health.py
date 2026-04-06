"""
Health check routing
"""
from flask import Blueprint, jsonify
from datetime import datetime

health_bp = Blueprint('health', __name__)


@health_bp.route('/', methods=['GET'])
def index():
    """API Home Page"""
    return jsonify({
        'name': 'QuantDinger Python API',
        'version': '2.0.0',
        'status': 'running',
        'timestamp': datetime.now().isoformat()
    })


@health_bp.route('/health', methods=['GET'])
def health_check():
    """health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


@health_bp.route('/api/health', methods=['GET'])
def api_health_check():
    """Compatible path: used for container health check/anti-generation probe and other scenarios."""
    return health_check()

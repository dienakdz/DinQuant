"""
Community APIs - indicator community interface

REST API that provides indicator markets, buying, commenting, and more.
"""

from flask import Blueprint, jsonify, request, g

from app.utils.auth import login_required
from app.utils.logger import get_logger
from app.services.community_service import get_community_service

logger = get_logger(__name__)

community_bp = Blueprint("community", __name__)


# ==========================================
# indicator market
# ==========================================

@community_bp.route("/indicators", methods=["GET"])
@login_required
def get_market_indicators():
    """
    Get a list of market indicators
    
    Query params:
        page: page number (default 1)
        page_size: Number of pages per page (default 12)
        keyword: search keyword
        pricing_type: 'free' / 'paid' / empty (all)
        sort_by: 'newest' / 'hot' / 'price_asc' / 'price_desc' / 'rating'
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 12))
        keyword = request.args.get('keyword', '').strip()
        pricing_type = request.args.get('pricing_type', '').strip() or None
        sort_by = request.args.get('sort_by', 'newest').strip()
        
        # Limit the number of pages per page
        page_size = min(max(page_size, 1), 50)
        
        service = get_community_service()
        result = service.get_market_indicators(
            page=page,
            page_size=page_size,
            keyword=keyword if keyword else None,
            pricing_type=pricing_type,
            sort_by=sort_by,
            user_id=g.user_id
        )
        
        return jsonify({'code': 1, 'msg': 'success', 'data': result})
        
    except Exception as e:
        logger.error(f"get_market_indicators failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@community_bp.route("/indicators/<int:indicator_id>", methods=["GET"])
@login_required
def get_indicator_detail(indicator_id: int):
    """Get indicator details"""
    try:
        service = get_community_service()
        result = service.get_indicator_detail(indicator_id, user_id=g.user_id)
        
        if not result:
            return jsonify({'code': 0, 'msg': 'indicator_not_found', 'data': None}), 404
        
        return jsonify({'code': 1, 'msg': 'success', 'data': result})
        
    except Exception as e:
        logger.error(f"get_indicator_detail failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


# ==========================================
# Purchase function
# ==========================================

@community_bp.route("/indicators/<int:indicator_id>/purchase", methods=["POST"])
@login_required
def purchase_indicator(indicator_id: int):
    """
    buy indicator
    
    will automatically:
    1. Check whether the points are sufficient
    2. Deduct buyer points and increase seller points
    3. Create purchase records
    4. Copy the indicator to the buyer’s account
    """
    try:
        service = get_community_service()
        success, message, data = service.purchase_indicator(
            buyer_id=g.user_id,
            indicator_id=indicator_id
        )
        
        if success:
            return jsonify({'code': 1, 'msg': message, 'data': data})
        else:
            return jsonify({'code': 0, 'msg': message, 'data': data}), 400
            
    except Exception as e:
        logger.error(f"purchase_indicator failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@community_bp.route("/my-purchases", methods=["GET"])
@login_required
def get_my_purchases():
    """Get a list of indicators I purchased"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        page_size = min(max(page_size, 1), 50)
        
        service = get_community_service()
        result = service.get_my_purchases(
            user_id=g.user_id,
            page=page,
            page_size=page_size
        )
        
        return jsonify({'code': 1, 'msg': 'success', 'data': result})
        
    except Exception as e:
        logger.error(f"get_my_purchases failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


# ==========================================
# Comment function
# ==========================================

@community_bp.route("/indicators/<int:indicator_id>/comments", methods=["GET"])
@login_required
def get_comments(indicator_id: int):
    """Get a list of indicator comments"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        page_size = min(max(page_size, 1), 50)
        
        service = get_community_service()
        result = service.get_comments(
            indicator_id=indicator_id,
            page=page,
            page_size=page_size
        )
        
        return jsonify({'code': 1, 'msg': 'success', 'data': result})
        
    except Exception as e:
        logger.error(f"get_comments failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@community_bp.route("/indicators/<int:indicator_id>/comments", methods=["POST"])
@login_required
def add_comment(indicator_id: int):
    """
    Add comment
    
    Request body:
        rating: 1-5 star rating
        content: Comment content (optional, up to 500 words)
    
    Note: Only users who have purchased can comment, and they can only comment once
    """
    try:
        data = request.get_json() or {}
        rating = int(data.get('rating', 5))
        content = (data.get('content') or '').strip()
        
        service = get_community_service()
        success, message, result = service.add_comment(
            user_id=g.user_id,
            indicator_id=indicator_id,
            rating=rating,
            content=content
        )
        
        if success:
            return jsonify({'code': 1, 'msg': message, 'data': result})
        else:
            return jsonify({'code': 0, 'msg': message, 'data': result}), 400
            
    except Exception as e:
        logger.error(f"add_comment failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@community_bp.route("/indicators/<int:indicator_id>/comments/<int:comment_id>", methods=["PUT"])
@login_required
def update_comment(indicator_id: int, comment_id: int):
    """
    Update comments (you can only modify your own comments)
    
    Request body:
        rating: 1-5 star rating
        content: Comment content (up to 500 words)
    """
    try:
        data = request.get_json() or {}
        rating = int(data.get('rating', 5))
        content = (data.get('content') or '').strip()
        
        service = get_community_service()
        success, message, result = service.update_comment(
            user_id=g.user_id,
            comment_id=comment_id,
            indicator_id=indicator_id,
            rating=rating,
            content=content
        )
        
        if success:
            return jsonify({'code': 1, 'msg': message, 'data': result})
        else:
            return jsonify({'code': 0, 'msg': message, 'data': result}), 400
            
    except Exception as e:
        logger.error(f"update_comment failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@community_bp.route("/indicators/<int:indicator_id>/my-comment", methods=["GET"])
@login_required
def get_my_comment(indicator_id: int):
    """Get the current user's comments on the specified indicator (for editing)"""
    try:
        service = get_community_service()
        result = service.get_user_comment(
            user_id=g.user_id,
            indicator_id=indicator_id
        )
        
        return jsonify({'code': 1, 'msg': 'success', 'data': result})
        
    except Exception as e:
        logger.error(f"get_my_comment failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


# ==========================================
# Real offer performance
# ==========================================

@community_bp.route("/indicators/<int:indicator_id>/performance", methods=["GET"])
@login_required
def get_indicator_performance(indicator_id: int):
    """Get real performance statistics of indicators"""
    try:
        service = get_community_service()
        result = service.get_indicator_performance(indicator_id)
        
        return jsonify({'code': 1, 'msg': 'success', 'data': result})
        
    except Exception as e:
        logger.error(f"get_indicator_performance failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


# ==========================================
# Administrator review function
# ==========================================

def _is_admin():
    """Check if the current user is an administrator"""
    role = getattr(g, 'user_role', None)
    return role == 'admin'


@community_bp.route("/admin/pending-indicators", methods=["GET"])
@login_required
def get_pending_indicators():
    """
    Get the list of indicators to be reviewed (for administrators only)
    
    Query params:
        page: page number (default 1)
        page_size: Number of pages per page (default 20)
        review_status: 'pending' / 'approved' / 'rejected' / 'all'
    """
    try:
        if not _is_admin():
            return jsonify({'code': 0, 'msg': 'admin_required', 'data': None}), 403
        
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        review_status = request.args.get('review_status', 'pending').strip() or 'pending'
        page_size = min(max(page_size, 1), 100)
        
        service = get_community_service()
        result = service.get_pending_indicators(
            page=page,
            page_size=page_size,
            review_status=review_status
        )
        
        return jsonify({'code': 1, 'msg': 'success', 'data': result})
        
    except Exception as e:
        logger.error(f"get_pending_indicators failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@community_bp.route("/admin/review-stats", methods=["GET"])
@login_required
def get_review_stats():
    """Get audit statistics (for administrators only)"""
    try:
        if not _is_admin():
            return jsonify({'code': 0, 'msg': 'admin_required', 'data': None}), 403
        
        service = get_community_service()
        result = service.get_review_stats()
        
        return jsonify({'code': 1, 'msg': 'success', 'data': result})
        
    except Exception as e:
        logger.error(f"get_review_stats failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@community_bp.route("/admin/indicators/<int:indicator_id>/review", methods=["POST"])
@login_required
def review_indicator(indicator_id: int):
    """
    Audit indicators (for administrators only)
    
    Request body:
        action: 'approve' / 'reject'
        note: review notes (optional)
    """
    try:
        if not _is_admin():
            return jsonify({'code': 0, 'msg': 'admin_required', 'data': None}), 403
        
        data = request.get_json() or {}
        action = data.get('action', '').strip()
        note = data.get('note', '').strip()
        
        if action not in ('approve', 'reject'):
            return jsonify({'code': 0, 'msg': 'invalid_action', 'data': None}), 400
        
        service = get_community_service()
        success, message = service.review_indicator(
            admin_id=g.user_id,
            indicator_id=indicator_id,
            action=action,
            note=note
        )
        
        if success:
            return jsonify({'code': 1, 'msg': message, 'data': None})
        else:
            return jsonify({'code': 0, 'msg': message, 'data': None}), 400
            
    except Exception as e:
        logger.error(f"review_indicator failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@community_bp.route("/admin/indicators/<int:indicator_id>/unpublish", methods=["POST"])
@login_required
def unpublish_indicator(indicator_id: int):
    """
    Delisting indicator (for administrators only)
    
    Request body:
        note: Reason for delisting (optional)
    """
    try:
        if not _is_admin():
            return jsonify({'code': 0, 'msg': 'admin_required', 'data': None}), 403
        
        data = request.get_json() or {}
        note = data.get('note', '').strip()
        
        service = get_community_service()
        success, message = service.unpublish_indicator(
            admin_id=g.user_id,
            indicator_id=indicator_id,
            note=note
        )
        
        if success:
            return jsonify({'code': 1, 'msg': message, 'data': None})
        else:
            return jsonify({'code': 0, 'msg': message, 'data': None}), 400
            
    except Exception as e:
        logger.error(f"unpublish_indicator failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@community_bp.route("/admin/indicators/<int:indicator_id>", methods=["DELETE"])
@login_required
def admin_delete_indicator(indicator_id: int):
    """Delete indicator (only for administrators)"""
    try:
        if not _is_admin():
            return jsonify({'code': 0, 'msg': 'admin_required', 'data': None}), 403
        
        service = get_community_service()
        success, message = service.admin_delete_indicator(
            admin_id=g.user_id,
            indicator_id=indicator_id
        )
        
        if success:
            return jsonify({'code': 1, 'msg': message, 'data': None})
        else:
            return jsonify({'code': 0, 'msg': message, 'data': None}), 400
            
    except Exception as e:
        logger.error(f"admin_delete_indicator failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500

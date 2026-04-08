"""
Community Service - indicator community service

Handles functions such as indicator markets, purchases, and comments.
"""
import json
import time
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

from app.utils.db import get_db_connection
from app.utils.logger import get_logger
from app.services.billing_service import get_billing_service

logger = get_logger(__name__)


class CommunityService:
    """Indicator Community Service Category"""
    
    def __init__(self):
        self.billing = get_billing_service()
        # Best-effort: ensure vip_free column exists (for old databases)
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute("ALTER TABLE qd_indicator_codes ADD COLUMN IF NOT EXISTS vip_free BOOLEAN DEFAULT FALSE")
                db.commit()
                cur.close()
        except Exception:
            pass
    
    # ==========================================
    # indicator market
    # ==========================================
    
    def get_market_indicators(
        self,
        page: int = 1,
        page_size: int = 12,
        keyword: str = None,
        pricing_type: str = None,  # 'free' / 'paid' / None(all)
        sort_by: str = 'newest',   # 'newest' / 'hot' / 'price_asc' / 'price_desc' / 'rating'
        user_id: int = None        # Current user ID, used to determine whether purchase has been made
    ) -> Dict[str, Any]:
        """Get a list of published indicators on the market"""
        offset = (page - 1) * page_size
        
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                
                # Build query conditions - only display published and approved indicators
                where_clauses = ["i.publish_to_community = 1", "(i.review_status = 'approved' OR i.review_status IS NULL)"]
                params = []
                
                if keyword and keyword.strip():
                    where_clauses.append("(i.name ILIKE ? OR i.description ILIKE ?)")
                    search_term = f"%{keyword.strip()}%"
                    params.extend([search_term, search_term])
                
                if pricing_type == 'free':
                    where_clauses.append("(i.pricing_type = 'free' OR i.price <= 0)")
                elif pricing_type == 'paid':
                    where_clauses.append("(i.pricing_type != 'free' AND i.price > 0)")
                
                where_sql = " AND ".join(where_clauses)
                
                # sort
                order_map = {
                    'newest': 'i.created_at DESC',
                    'hot': 'i.purchase_count DESC, i.view_count DESC',
                    'price_asc': 'i.price ASC, i.created_at DESC',
                    'price_desc': 'i.price DESC, i.created_at DESC',
                    'rating': 'i.avg_rating DESC, i.rating_count DESC'
                }
                order_sql = order_map.get(sort_by, 'i.created_at DESC')
                
                # Get total
                count_sql = f"""
                    SELECT COUNT(*) as count 
                    FROM qd_indicator_codes i 
                    WHERE {where_sql}
                """
                cur.execute(count_sql, tuple(params))
                total = cur.fetchone()['count']
                
                # Get the list (join the table to query author information)
                query_sql = f"""
                    SELECT 
                        i.id, i.name, i.description, i.pricing_type, i.price, COALESCE(i.vip_free, FALSE) as vip_free,
                        i.preview_image, i.purchase_count, i.avg_rating, i.rating_count,
                        i.view_count, i.created_at, i.updated_at,
                        u.id as author_id, u.username as author_username, 
                        u.nickname as author_nickname, u.avatar as author_avatar
                    FROM qd_indicator_codes i
                    LEFT JOIN qd_users u ON i.user_id = u.id
                    WHERE {where_sql}
                    ORDER BY {order_sql}
                    LIMIT ? OFFSET ?
                """
                cur.execute(query_sql, tuple(params + [page_size, offset]))
                rows = cur.fetchall() or []
                
                # If there is a current user, query the purchased indicators
                purchased_ids = set()
                if user_id:
                    indicator_ids = [r['id'] for r in rows]
                    if indicator_ids:
                        placeholders = ','.join(['?'] * len(indicator_ids))
                        cur.execute(
                            f"SELECT indicator_id FROM qd_indicator_purchases WHERE buyer_id = ? AND indicator_id IN ({placeholders})",
                            tuple([user_id] + indicator_ids)
                        )
                        purchased_ids = {r['indicator_id'] for r in (cur.fetchall() or [])}
                
                cur.close()
                
                #Format return data
                items = []
                for row in rows:
                    items.append({
                        'id': row['id'],
                        'name': row['name'],
                        'description': row['description'][:200] if row['description'] else '',
                        'pricing_type': row['pricing_type'] or 'free',
                        'price': float(row['price'] or 0),
                        'vip_free': bool(row.get('vip_free') or False),
                        'preview_image': row['preview_image'] or '',
                        'purchase_count': row['purchase_count'] or 0,
                        'avg_rating': float(row['avg_rating'] or 0),
                        'rating_count': row['rating_count'] or 0,
                        'view_count': row['view_count'] or 0,
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                        'author': {
                            'id': row['author_id'],
                            'username': row['author_username'],
                            'nickname': row['author_nickname'] or row['author_username'],
                            'avatar': row['author_avatar'] or '/avatar2.jpg'
                        },
                        'is_purchased': row['id'] in purchased_ids,
                        'is_own': row['author_id'] == user_id
                    })
                
                return {
                    'items': items,
                    'total': total,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total + page_size - 1) // page_size if total > 0 else 0
                }
                
        except Exception as e:
            logger.error(f"get_market_indicators failed: {e}")
            return {'items': [], 'total': 0, 'page': 1, 'page_size': page_size, 'total_pages': 0}
    
    def get_indicator_detail(self, indicator_id: int, user_id: int = None) -> Optional[Dict[str, Any]]:
        """Get indicator details."""
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                
                # Get indicator information
                cur.execute("""
                    SELECT 
                        i.id, i.name, i.description, i.pricing_type, i.price, COALESCE(i.vip_free, FALSE) as vip_free,
                        i.preview_image, i.purchase_count, i.avg_rating, i.rating_count,
                        i.view_count, i.publish_to_community, i.created_at, i.updated_at,
                        i.user_id,
                        u.id as author_id, u.username as author_username, 
                        u.nickname as author_nickname, u.avatar as author_avatar
                    FROM qd_indicator_codes i
                    LEFT JOIN qd_users u ON i.user_id = u.id
                    WHERE i.id = ?
                """, (indicator_id,))
                row = cur.fetchone()
                
                if not row:
                    cur.close()
                    return None
                
                # Check if it has been published to the community (or its own indicator)
                if not row['publish_to_community'] and row['user_id'] != user_id:
                    cur.close()
                    return None
                
                # Check if purchased
                is_purchased = False
                if user_id:
                    cur.execute(
                        "SELECT id FROM qd_indicator_purchases WHERE indicator_id = ? AND buyer_id = ?",
                        (indicator_id, user_id)
                    )
                    is_purchased = cur.fetchone() is not None
                
                # Increase the number of views
                cur.execute(
                    "UPDATE qd_indicator_codes SET view_count = COALESCE(view_count, 0) + 1 WHERE id = ?",
                    (indicator_id,)
                )
                db.commit()
                cur.close()
                
                return {
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'] or '',
                    'pricing_type': row['pricing_type'] or 'free',
                    'price': float(row['price'] or 0),
                    'vip_free': bool(row.get('vip_free') or False),
                    'preview_image': row['preview_image'] or '',
                    'purchase_count': row['purchase_count'] or 0,
                    'avg_rating': float(row['avg_rating'] or 0),
                    'rating_count': row['rating_count'] or 0,
                    'view_count': (row['view_count'] or 0) + 1,
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
                    'author': {
                        'id': row['author_id'],
                        'username': row['author_username'],
                        'nickname': row['author_nickname'] or row['author_username'],
                        'avatar': row['author_avatar'] or '/avatar2.jpg'
                    },
                    'is_purchased': is_purchased,
                    'is_own': row['user_id'] == user_id
                }
                
        except Exception as e:
            logger.error(f"get_indicator_detail failed: {e}")
            return None
    
    # ==========================================
    # Purchase function
    # ==========================================
    
    def purchase_indicator(self, buyer_id: int, indicator_id: int) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Purchase an indicator.

        Returns:
            (success, message, data)
        """
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                
                # 1. Get indicator information
                cur.execute("""
                    SELECT id, user_id, name, code, description, pricing_type, price, COALESCE(vip_free, FALSE) as vip_free,
                           preview_image, is_encrypted
                    FROM qd_indicator_codes
                    WHERE id = ? AND publish_to_community = 1
                """, (indicator_id,))
                indicator = cur.fetchone()
                
                if not indicator:
                    cur.close()
                    return False, 'indicator_not_found', {}
                
                seller_id = indicator['user_id']
                price = float(indicator['price'] or 0)
                pricing_type = indicator['pricing_type'] or 'free'
                vip_free = bool(indicator.get('vip_free') or False)
                is_vip, _ = self.billing.get_user_vip_status(buyer_id)

                # VIP-free indicator: VIP users can get it without credits charge
                effective_price = 0.0 if (vip_free and is_vip) else price
                
                # 2. Check whether to buy your own indicator
                if seller_id == buyer_id:
                    cur.close()
                    return False, 'cannot_buy_own', {}
                
                # 3. Check if purchased
                cur.execute(
                    "SELECT id FROM qd_indicator_purchases WHERE indicator_id = ? AND buyer_id = ?",
                    (indicator_id, buyer_id)
                )
                if cur.fetchone():
                    cur.close()
                    return False, 'already_purchased', {}
                
                # 4. If it is a paid indicator, check and deduct points
                if pricing_type != 'free' and effective_price > 0:
                    buyer_credits = self.billing.get_user_credits(buyer_id)
                    if buyer_credits < effective_price:
                        cur.close()
                        return False, 'insufficient_credits', {
                            'required': effective_price,
                            'current': float(buyer_credits)
                        }
                    
                    # Deduct buyer points
                    new_buyer_balance = buyer_credits - Decimal(str(effective_price))
                    cur.execute(
                        "UPDATE qd_users SET credits = ?, updated_at = NOW() WHERE id = ?",
                        (float(new_buyer_balance), buyer_id)
                    )
                    
                    # Record buyer points log
                    cur.execute("""
                        INSERT INTO qd_credits_log 
                        (user_id, action, amount, balance_after, feature, reference_id, remark, created_at)
                        VALUES (?, 'indicator_purchase', ?, ?, 'indicator_purchase', ?, ?, NOW())
                    """, (buyer_id, -effective_price, float(new_buyer_balance), str(indicator_id), 
                          f"Buy indicator: {indicator['name']}"))
                    
                    # Increase points for sellers (the commission ratio can be configured, here 100% is given to sellers first)
                    seller_credits = self.billing.get_user_credits(seller_id)
                    new_seller_balance = seller_credits + Decimal(str(effective_price))
                    cur.execute(
                        "UPDATE qd_users SET credits = ?, updated_at = NOW() WHERE id = ?",
                        (float(new_seller_balance), seller_id)
                    )
                    
                    # Record seller points log
                    cur.execute("""
                        INSERT INTO qd_credits_log 
                        (user_id, action, amount, balance_after, feature, reference_id, remark, created_at)
                        VALUES (?, 'indicator_sale', ?, ?, 'indicator_sale', ?, ?, NOW())
                    """, (seller_id, effective_price, float(new_seller_balance), str(indicator_id),
                          f"Sell indicator: {indicator['name']}"))
                
                # 5. Create purchase record
                cur.execute("""
                    INSERT INTO qd_indicator_purchases 
                    (indicator_id, buyer_id, seller_id, price, created_at)
                    VALUES (?, ?, ?, ?, NOW())
                """, (indicator_id, buyer_id, seller_id, effective_price))
                
                # 6. Copy the indicator to the buyer’s account
                now_ts = int(time.time())
                # Get vip_free as boolean from indicator
                vip_free_value = bool(indicator.get('vip_free') or False)
                cur.execute("""
                    INSERT INTO qd_indicator_codes
                    (user_id, is_buy, end_time, name, code, description,
                     publish_to_community, pricing_type, price, is_encrypted, preview_image, vip_free,
                     createtime, updatetime, created_at, updated_at)
                    VALUES (?, 1, 0, ?, ?, ?, 0, 'free', 0, ?, ?, ?, ?, ?, NOW(), NOW())
                """, (
                    buyer_id,
                    indicator['name'],
                    indicator['code'],
                    indicator['description'],
                    indicator['is_encrypted'] or 0,
                    indicator['preview_image'],
                    vip_free_value,  # Use boolean value instead of integer 0
                    now_ts, now_ts
                ))
                
                # 7. Update indicator purchase times
                cur.execute("""
                    UPDATE qd_indicator_codes 
                    SET purchase_count = COALESCE(purchase_count, 0) + 1 
                    WHERE id = ?
                """, (indicator_id,))
                
                db.commit()
                cur.close()
                
                logger.info(f"User {buyer_id} purchased indicator {indicator_id} for {effective_price} credits (vip_free={vip_free}, is_vip={is_vip})")
                return True, 'success', {'indicator_name': indicator['name'], 'price': price, 'charged': effective_price, 'vip_free': vip_free}
                
        except Exception as e:
            logger.error(f"purchase_indicator failed: {e}")
            return False, f'error: {str(e)}', {}
    
    def get_my_purchases(self, user_id: int, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get the list of indicators purchased by the user."""
        offset = (page - 1) * page_size
        
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                
                # Get total
                cur.execute(
                    "SELECT COUNT(*) as count FROM qd_indicator_purchases WHERE buyer_id = ?",
                    (user_id,)
                )
                total = cur.fetchone()['count']
                
                # Get list
                cur.execute("""
                    SELECT 
                        p.id as purchase_id, p.price as purchase_price, p.created_at as purchase_time,
                        i.id, i.name, i.description, i.preview_image, i.avg_rating,
                        u.nickname as seller_nickname, u.avatar as seller_avatar
                    FROM qd_indicator_purchases p
                    LEFT JOIN qd_indicator_codes i ON p.indicator_id = i.id
                    LEFT JOIN qd_users u ON p.seller_id = u.id
                    WHERE p.buyer_id = ?
                    ORDER BY p.created_at DESC
                    LIMIT ? OFFSET ?
                """, (user_id, page_size, offset))
                rows = cur.fetchall() or []
                cur.close()
                
                items = []
                for row in rows:
                    items.append({
                        'purchase_id': row['purchase_id'],
                        'purchase_price': float(row['purchase_price'] or 0),
                        'purchase_time': row['purchase_time'].isoformat() if row['purchase_time'] else None,
                        'indicator': {
                            'id': row['id'],
                            'name': row['name'],
                            'description': row['description'][:100] if row['description'] else '',
                            'preview_image': row['preview_image'] or '',
                            'avg_rating': float(row['avg_rating'] or 0)
                        },
                        'seller': {
                            'nickname': row['seller_nickname'],
                            'avatar': row['seller_avatar'] or '/avatar2.jpg'
                        }
                    })
                
                return {
                    'items': items,
                    'total': total,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total + page_size - 1) // page_size if total > 0 else 0
                }
                
        except Exception as e:
            logger.error(f"get_my_purchases failed: {e}")
            return {'items': [], 'total': 0, 'page': 1, 'page_size': page_size, 'total_pages': 0}
    
    # ==========================================
    # Comment function
    # ==========================================
    
    def get_comments(self, indicator_id: int, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get the list of indicator comments."""
        offset = (page - 1) * page_size
        
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                
                # Get the total number (only first-level comments are counted)
                cur.execute("""
                    SELECT COUNT(*) as count FROM qd_indicator_comments 
                    WHERE indicator_id = ? AND parent_id IS NULL AND is_deleted = 0
                """, (indicator_id,))
                total = cur.fetchone()['count']
                
                # Get the list of comments
                cur.execute("""
                    SELECT 
                        c.id, c.rating, c.content, c.created_at,
                        u.id as user_id, u.nickname, u.avatar
                    FROM qd_indicator_comments c
                    LEFT JOIN qd_users u ON c.user_id = u.id
                    WHERE c.indicator_id = ? AND c.parent_id IS NULL AND c.is_deleted = 0
                    ORDER BY c.created_at DESC
                    LIMIT ? OFFSET ?
                """, (indicator_id, page_size, offset))
                rows = cur.fetchall() or []
                cur.close()
                
                items = []
                for row in rows:
                    items.append({
                        'id': row['id'],
                        'rating': row['rating'],
                        'content': row['content'],
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                        'user': {
                            'id': row['user_id'],
                            'nickname': row['nickname'],
                            'avatar': row['avatar'] or '/avatar2.jpg'
                        }
                    })
                
                return {
                    'items': items,
                    'total': total,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total + page_size - 1) // page_size if total > 0 else 0
                }
                
        except Exception as e:
            logger.error(f"get_comments failed: {e}")
            return {'items': [], 'total': 0, 'page': 1, 'page_size': page_size, 'total_pages': 0}
    
    def add_comment(
        self, 
        user_id: int, 
        indicator_id: int, 
        rating: int, 
        content: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Add a comment.

        Only users who purchased the indicator can comment, and only once.
        """
        try:
            # Verify score range
            rating = max(1, min(5, int(rating)))
            content = (content or '').strip()[:500] # Limit 500 words
            
            with get_db_connection() as db:
                cur = db.cursor()
                
                # Check if the indicator exists
                cur.execute(
                    "SELECT id, user_id FROM qd_indicator_codes WHERE id = ? AND publish_to_community = 1",
                    (indicator_id,)
                )
                indicator = cur.fetchone()
                if not indicator:
                    cur.close()
                    return False, 'indicator_not_found', {}
                
                # Cannot comment on own indicators
                if indicator['user_id'] == user_id:
                    cur.close()
                    return False, 'cannot_comment_own', {}
                
                # Check if it has been purchased (free indicators also need to be "acquired" to comment)
                cur.execute(
                    "SELECT id FROM qd_indicator_purchases WHERE indicator_id = ? AND buyer_id = ?",
                    (indicator_id, user_id)
                )
                if not cur.fetchone():
                    cur.close()
                    return False, 'not_purchased', {}
                
                # Check if comments have been made
                cur.execute(
                    "SELECT id FROM qd_indicator_comments WHERE indicator_id = ? AND user_id = ? AND parent_id IS NULL",
                    (indicator_id, user_id)
                )
                if cur.fetchone():
                    cur.close()
                    return False, 'already_commented', {}
                
                #Add comment
                cur.execute("""
                    INSERT INTO qd_indicator_comments 
                    (indicator_id, user_id, rating, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?, NOW(), NOW())
                """, (indicator_id, user_id, rating, content))
                comment_id = cur.lastrowid
                
                # Update the scoring statistics of the indicator
                cur.execute("""
                    UPDATE qd_indicator_codes 
                    SET 
                        rating_count = COALESCE(rating_count, 0) + 1,
                        avg_rating = (
                            SELECT AVG(rating) FROM qd_indicator_comments 
                            WHERE indicator_id = ? AND parent_id IS NULL AND is_deleted = 0
                        )
                    WHERE id = ?
                """, (indicator_id, indicator_id))
                
                db.commit()
                cur.close()
                
                logger.info(f"User {user_id} commented on indicator {indicator_id} with rating {rating}")
                return True, 'success', {'comment_id': comment_id}
                
        except Exception as e:
            logger.error(f"add_comment failed: {e}")
            return False, f'error: {str(e)}', {}
    
    def update_comment(
        self,
        user_id: int,
        comment_id: int,
        indicator_id: int,
        rating: int,
        content: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Update a comment.

        Users can only edit their own comments.
        """
        try:
            rating = max(1, min(5, int(rating)))
            content = (content or '').strip()[:500]
            
            with get_db_connection() as db:
                cur = db.cursor()
                
                # Check if the comment exists and belongs to the current user
                cur.execute("""
                    SELECT id, rating as old_rating FROM qd_indicator_comments 
                    WHERE id = ? AND user_id = ? AND indicator_id = ? AND is_deleted = 0
                """, (comment_id, user_id, indicator_id))
                comment = cur.fetchone()
                
                if not comment:
                    cur.close()
                    return False, 'comment_not_found', {}
                
                old_rating = comment['old_rating']
                
                # Update comment
                cur.execute("""
                    UPDATE qd_indicator_comments 
                    SET rating = ?, content = ?, updated_at = NOW()
                    WHERE id = ?
                """, (rating, content, comment_id))
                
                # If the rating changes, update the average rating of the metric
                if old_rating != rating:
                    cur.execute("""
                        UPDATE qd_indicator_codes 
                        SET avg_rating = (
                            SELECT AVG(rating) FROM qd_indicator_comments 
                            WHERE indicator_id = ? AND parent_id IS NULL AND is_deleted = 0
                        )
                        WHERE id = ?
                    """, (indicator_id, indicator_id))
                
                db.commit()
                cur.close()
                
                logger.info(f"User {user_id} updated comment {comment_id}")
                return True, 'success', {'comment_id': comment_id}
                
        except Exception as e:
            logger.error(f"update_comment failed: {e}")
            return False, f'error: {str(e)}', {}
    
    def get_user_comment(self, user_id: int, indicator_id: int) -> Optional[Dict[str, Any]]:
        """Get the user's comment for a specific indicator."""
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute("""
                    SELECT id, rating, content, created_at, updated_at
                    FROM qd_indicator_comments
                    WHERE user_id = ? AND indicator_id = ? AND parent_id IS NULL AND is_deleted = 0
                """, (user_id, indicator_id))
                row = cur.fetchone()
                cur.close()
                
                if not row:
                    return None
                
                return {
                    'id': row['id'],
                    'rating': row['rating'],
                    'content': row['content'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                }
                
        except Exception as e:
            logger.error(f"get_user_comment failed: {e}")
            return None
    
    # ==========================================
    # Administrator review function
    # ==========================================
    
    def get_pending_indicators(
        self,
        page: int = 1,
        page_size: int = 20,
        review_status: str = 'pending'  # 'pending' / 'approved' / 'rejected' / 'all'
    ) -> Dict[str, Any]:
        """Get the list of indicators pending review for admins."""
        offset = (page - 1) * page_size
        
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                
                # Build query conditions
                where_clauses = ["i.publish_to_community = 1"]
                params = []
                
                if review_status and review_status != 'all':
                    where_clauses.append("i.review_status = ?")
                    params.append(review_status)
                
                where_sql = " AND ".join(where_clauses)
                
                # Get total
                count_sql = f"""
                    SELECT COUNT(*) as count 
                    FROM qd_indicator_codes i 
                    WHERE {where_sql}
                """
                cur.execute(count_sql, tuple(params))
                total = cur.fetchone()['count']
                
                # Get the list
                query_sql = f"""
                    SELECT 
                        i.id, i.name, i.description, i.pricing_type, i.price,
                        i.preview_image, i.code, i.review_status, i.review_note, 
                        i.reviewed_at, i.reviewed_by, i.created_at,
                        u.id as author_id, u.username as author_username, 
                        u.nickname as author_nickname, u.avatar as author_avatar,
                        r.username as reviewer_username
                    FROM qd_indicator_codes i
                    LEFT JOIN qd_users u ON i.user_id = u.id
                    LEFT JOIN qd_users r ON i.reviewed_by = r.id
                    WHERE {where_sql}
                    ORDER BY i.created_at DESC
                    LIMIT ? OFFSET ?
                """
                cur.execute(query_sql, tuple(params + [page_size, offset]))
                rows = cur.fetchall() or []
                cur.close()
                
                items = []
                for row in rows:
                    items.append({
                        'id': row['id'],
                        'name': row['name'],
                        'description': row['description'][:300] if row['description'] else '',
                        'pricing_type': row['pricing_type'] or 'free',
                        'price': float(row['price'] or 0),
                        'preview_image': row['preview_image'] or '',
                        'code': row['code'] or '', # Administrators can view the code
                        'review_status': row['review_status'] or 'pending',
                        'review_note': row['review_note'] or '',
                        'reviewed_at': row['reviewed_at'].isoformat() if row['reviewed_at'] else None,
                        'reviewer_username': row['reviewer_username'],
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                        'author': {
                            'id': row['author_id'],
                            'username': row['author_username'],
                            'nickname': row['author_nickname'] or row['author_username'],
                            'avatar': row['author_avatar'] or '/avatar2.jpg'
                        }
                    })
                
                return {
                    'items': items,
                    'total': total,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total + page_size - 1) // page_size if total > 0 else 0
                }
                
        except Exception as e:
            logger.error(f"get_pending_indicators failed: {e}")
            return {'items': [], 'total': 0, 'page': 1, 'page_size': page_size, 'total_pages': 0}
    
    def review_indicator(
        self,
        admin_id: int,
        indicator_id: int,
        action: str,  # 'approve' / 'reject'
        note: str = ''
    ) -> Tuple[bool, str]:
        """Review an indicator."""
        try:
            new_status = 'approved' if action == 'approve' else 'rejected'
            note = (note or '').strip()[:500]
            
            with get_db_connection() as db:
                cur = db.cursor()
                
                # Check if the indicator exists and has been published to the community
                cur.execute("""
                    SELECT id, name, user_id FROM qd_indicator_codes 
                    WHERE id = ? AND publish_to_community = 1
                """, (indicator_id,))
                indicator = cur.fetchone()
                
                if not indicator:
                    cur.close()
                    return False, 'indicator_not_found'
                
                # Update review status
                cur.execute("""
                    UPDATE qd_indicator_codes 
                    SET review_status = ?, review_note = ?, reviewed_at = NOW(), reviewed_by = ?
                    WHERE id = ?
                """, (new_status, note, admin_id, indicator_id))
                
                db.commit()
                cur.close()
                
                logger.info(f"Admin {admin_id} {action}d indicator {indicator_id}")
                return True, 'success'
                
        except Exception as e:
            logger.error(f"review_indicator failed: {e}")
            return False, f'error: {str(e)}'
    
    def unpublish_indicator(self, admin_id: int, indicator_id: int, note: str = '') -> Tuple[bool, str]:
        """Unpublish an indicator."""
        try:
            note = (note or '').strip()[:500]
            
            with get_db_connection() as db:
                cur = db.cursor()
                
                # Check if the indicator exists
                cur.execute("""
                    SELECT id, name FROM qd_indicator_codes WHERE id = ?
                """, (indicator_id,))
                indicator = cur.fetchone()
                
                if not indicator:
                    cur.close()
                    return False, 'indicator_not_found'
                
                # Remove from shelves (cancel publication)
                cur.execute("""
                    UPDATE qd_indicator_codes 
                    SET publish_to_community = 0, review_status = 'rejected', 
                        review_note = ?, reviewed_at = NOW(), reviewed_by = ?
                    WHERE id = ?
                """, (f"Removal: {note}" if note else "Removal by administrator", admin_id, indicator_id))
                
                db.commit()
                cur.close()
                
                logger.info(f"Admin {admin_id} unpublished indicator {indicator_id}")
                return True, 'success'
                
        except Exception as e:
            logger.error(f"unpublish_indicator failed: {e}")
            return False, f'error: {str(e)}'
    
    def admin_delete_indicator(self, admin_id: int, indicator_id: int) -> Tuple[bool, str]:
        """Delete an indicator as an admin."""
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                
                # Check if the indicator exists
                cur.execute("SELECT id, name FROM qd_indicator_codes WHERE id = ?", (indicator_id,))
                indicator = cur.fetchone()
                
                if not indicator:
                    cur.close()
                    return False, 'indicator_not_found'
                
                # Delete associated comments
                cur.execute("DELETE FROM qd_indicator_comments WHERE indicator_id = ?", (indicator_id,))
                
                # Delete associated purchase history
                cur.execute("DELETE FROM qd_indicator_purchases WHERE indicator_id = ?", (indicator_id,))
                
                # Delete indicator
                cur.execute("DELETE FROM qd_indicator_codes WHERE id = ?", (indicator_id,))
                
                db.commit()
                cur.close()
                
                logger.info(f"Admin {admin_id} deleted indicator {indicator_id}")
                return True, 'success'
                
        except Exception as e:
            logger.error(f"admin_delete_indicator failed: {e}")
            return False, f'error: {str(e)}'
    
    def get_review_stats(self) -> Dict[str, int]:
        """Get audit statistics"""
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute("""
                    SELECT 
                        COUNT(*) FILTER (WHERE review_status = 'pending' OR review_status IS NULL) as pending_count,
                        COUNT(*) FILTER (WHERE review_status = 'approved') as approved_count,
                        COUNT(*) FILTER (WHERE review_status = 'rejected') as rejected_count
                    FROM qd_indicator_codes
                    WHERE publish_to_community = 1
                """)
                row = cur.fetchone()
                cur.close()
                
                return {
                    'pending': row['pending_count'] or 0,
                    'approved': row['approved_count'] or 0,
                    'rejected': row['rejected_count'] or 0
                }
        except Exception as e:
            logger.error(f"get_review_stats failed: {e}")
            return {'pending': 0, 'approved': 0, 'rejected': 0}
    
    # ==========================================
    # Real performance (aggregated backtest + real transaction data)
    # ==========================================

    def get_indicator_performance(self, indicator_id: int) -> Dict[str, Any]:
        """
        Get live performance statistics for an indicator.

        Data sources:
        1. qd_backtest_runs - Backtest records (result_json contains totalReturn, winRate, etc.)
        2. qd_strategy_trades + qd_strategies_trading - Real live trading records
        """
        default_result = {
            'strategy_count': 0,
            'trade_count': 0,
            'win_rate': 0,
            'total_profit': 0,
            'avg_return': 0,
            'max_drawdown': 0
        }

        try:
            with get_db_connection() as db:
                cur = db.cursor()

                # ---------- Part 1: Backtest data (parsed from result_json) ----------
                bt_returns = []
                bt_win_rates = []
                bt_drawdowns = []
                bt_trade_counts = []

                try:
                    cur.execute("""
                        SELECT result_json
                        FROM qd_backtest_runs
                        WHERE indicator_id = %s AND status = 'success'
                              AND result_json IS NOT NULL AND result_json != ''
                    """, (indicator_id,))
                    rows = cur.fetchall()

                    for row in rows:
                        try:
                            rj = json.loads(row['result_json']) if isinstance(row['result_json'], str) else {}
                            tr = float(rj.get('totalReturn', 0) or 0)
                            wr = float(rj.get('winRate', 0) or 0)
                            md = float(rj.get('maxDrawdown', 0) or 0)
                            tc = int(rj.get('totalTrades', 0) or 0)
                            bt_returns.append(tr)
                            bt_win_rates.append(wr)
                            bt_drawdowns.append(md)
                            bt_trade_counts.append(tc)
                        except (json.JSONDecodeError, TypeError, ValueError):
                            continue
                except Exception:
                    logger.debug("Backtest runs query skipped or failed", exc_info=True)

                bt_run_count = len(bt_returns)

                # ---------- Part 2: Real transaction data ----------
                live_strategy_count = 0
                live_trade_count = 0
                live_win_rate = 0.0
                live_total_profit = 0.0

                try:
                    # Find the strategy that uses this indicator (matches indicator_id in indicator_config JSON)
                    cur.execute("""
                        SELECT id FROM qd_strategies_trading
                        WHERE indicator_config::text LIKE %s
                    """, (f'%"indicator_id": {indicator_id}%',))
                    strategy_rows = cur.fetchall()

                    # Also try to match formats without spaces
                    if not strategy_rows:
                        cur.execute("""
                            SELECT id FROM qd_strategies_trading
                            WHERE indicator_config::text LIKE %s
                        """, (f'%"indicator_id":{indicator_id}%',))
                        strategy_rows = cur.fetchall()

                    if strategy_rows:
                        strategy_ids = [r['id'] for r in strategy_rows]
                        live_strategy_count = len(strategy_ids)

                        placeholders = ','.join(['%s'] * len(strategy_ids))
                        cur.execute(f"""
                            SELECT 
                                COUNT(*) as trade_count,
                                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as win_count,
                                SUM(profit) as total_profit
                            FROM qd_strategy_trades
                            WHERE strategy_id IN ({placeholders})
                              AND profit != 0
                        """, tuple(strategy_ids))
                        trade_row = cur.fetchone()

                        if trade_row and (trade_row['trade_count'] or 0) > 0:
                            live_trade_count = int(trade_row['trade_count'] or 0)
                            win_count = int(trade_row['win_count'] or 0)
                            live_win_rate = round(win_count / live_trade_count * 100, 2) if live_trade_count > 0 else 0.0
                            live_total_profit = round(float(trade_row['total_profit'] or 0), 2)
                except Exception:
                    logger.debug("Live trading query skipped or failed", exc_info=True)

                cur.close()

                # ---------- Combine results ----------
                total_strategy_count = bt_run_count + live_strategy_count
                total_trade_count = sum(bt_trade_counts) + live_trade_count

                # Comprehensive winning rate: Prioritize real offer > Backtest average
                if live_trade_count > 0:
                    combined_win_rate = live_win_rate
                elif bt_win_rates:
                    combined_win_rate = round(sum(bt_win_rates) / len(bt_win_rates), 2)
                else:
                    combined_win_rate = 0.0

                # Average return (backtest totalReturn %)
                avg_return = round(sum(bt_returns) / len(bt_returns), 2) if bt_returns else 0.0

                #Total profit: priority is given to the absolute profit of the real offer. If there is no real offer, the average return rate of the backtest will be displayed.
                combined_profit = live_total_profit if live_trade_count > 0 else avg_return

                # The maximum drawdown is the worst in the backtest (maxDrawdown is a negative number, the smallest is the worst)
                avg_drawdown = round(min(bt_drawdowns), 2) if bt_drawdowns else 0.0

                if total_strategy_count == 0 and total_trade_count == 0:
                    return default_result

                return {
                    'strategy_count': total_strategy_count,
                    'trade_count': total_trade_count,
                    'win_rate': combined_win_rate,
                    'total_profit': round(combined_profit, 2),
                    'avg_return': avg_return,
                    'max_drawdown': avg_drawdown
                }

        except Exception as e:
            logger.error(f"get_indicator_performance failed: {e}")
            return default_result


# Global singleton
_community_service = None


def get_community_service() -> CommunityService:
    """Get the community service singleton."""
    global _community_service
    if _community_service is None:
        _community_service = CommunityService()
    return _community_service

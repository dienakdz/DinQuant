"""
Polymarket background tasks
Update market data every 30 minutes and analyze market opportunities in batches
"""

import os
import threading
import time
from typing import Dict, Optional

from app.data_sources.polymarket import PolymarketDataSource
from app.services.polymarket_batch_analyzer import PolymarketBatchAnalyzer
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PolymarketWorker:
    """Polymarket data update and analysis background tasks"""

    def __init__(self, update_interval_minutes: int = 30, analysis_cache_minutes: int = 1440):  # 24 hours cache
        """
        Initialize background tasks

        Args:
            update_interval_minutes: market data update interval (minutes)
            analysis_cache_minutes: AI analysis result cache time (minutes)
        """
        self.update_interval_minutes = update_interval_minutes
        self.analysis_cache_minutes = analysis_cache_minutes
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.polymarket_source = PolymarketDataSource()
        self.batch_analyzer = PolymarketBatchAnalyzer()
        self._last_update_ts = 0.0

    def start(self) -> bool:
        """Start background task"""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, name="PolymarketWorker", daemon=True)
            self._thread.start()
            logger.info(
                f"PolymarketWorker started (update_interval={self.update_interval_minutes}min, cache={self.analysis_cache_minutes}min)"
            )
            return True

    def stop(self, timeout_sec: float = 5.0) -> None:
        """Stop background tasks"""
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return
            self._stop_event.set()
            self._thread.join(timeout=timeout_sec)
            if self._thread.is_alive():
                logger.warning("PolymarketWorker thread did not stop within timeout")
            else:
                logger.info("PolymarketWorker stopped")

    def _run_loop(self) -> None:
        """main loop"""
        logger.info("PolymarketWorker loop started")

        # Execute once immediately on startup
        self._update_markets_and_analyze()

        while not self._stop_event.is_set():
            try:
                # Wait for specified time interval
                wait_seconds = self.update_interval_minutes * 60
                if self._stop_event.wait(wait_seconds):
                    break  # If a stop signal is received, exit the loop

                # Perform updates and analysis
                self._update_markets_and_analyze()

            except Exception as e:
                logger.error(f"PolymarketWorker loop error: {e}", exc_info=True)
                # After an error, wait 1 minute and try again
                self._stop_event.wait(60)

        logger.info("PolymarketWorker loop stopped")

    def _update_markets_and_analyze(self) -> None:
        """Update market data and analyze"""
        try:
            logger.info("Starting Polymarket data update and analysis...")
            start_time = time.time()

            # Gamma API /events has no category param — fetch ALL once, categorize locally.
            all_markets = self.polymarket_source.get_trending_markets(category="all", limit=500)
            logger.info(f"Fetched {len(all_markets)} markets from Gamma API (single request)")

            unique_markets = {}
            cat_counts: Dict[str, int] = {}
            for market in all_markets:
                market_id = market.get("market_id")
                if market_id:
                    unique_markets[market_id] = market
                    cat = market.get("category", "other")
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1

            logger.info(f"Total unique markets: {len(unique_markets)}, by category: {cat_counts}")

            # 2. Analyze the market in batches (analyze all markets at once, and use AI to screen opportunities)
            markets_list = list(unique_markets.values())
            logger.info(f"Starting batch analysis for {len(markets_list)} markets...")

            # Optimization strategy: first use rules to filter and only call LLM on high-value opportunities
            # This can greatly reduce the number of LLM calls and save tokens.

            # 1. First use rules to filter out the most valuable opportunities (without calling LLM)
            rule_based_opportunities = []
            for market in markets_list:
                prob = market.get("current_probability", 50.0)
                volume = market.get("volume_24h", 0)
                divergence = abs(prob - 50.0)

                # Rule screening: high trading volume + obvious probability deviation
                if volume > 5000 and divergence > 8:
                    rule_based_opportunities.append(market)

            # 2. Only call LLM for opportunities filtered out by rules (up to 30, saving tokens)
            if rule_based_opportunities:
                logger.info(
                    f"Rule-based filtering: {len(rule_based_opportunities)} opportunities, analyzing top 30 with LLM"
                )
                # Sort by transaction volume and probability deviation, take the top 30
                rule_based_opportunities.sort(
                    key=lambda x: x.get("volume_24h", 0) * abs(x.get("current_probability", 50) - 50), reverse=True
                )
                top_opportunities = rule_based_opportunities[:30]

                analyzed_markets = self.batch_analyzer.batch_analyze_markets(
                    top_opportunities,
                    max_opportunities=30,  # Analyze only the 30 most valuable opportunities
                )
            else:
                logger.info("No rule-based opportunities found, skipping LLM analysis")
                analyzed_markets = []

            # 3. Save the analysis results to the database
            if analyzed_markets:
                self.batch_analyzer.save_batch_analysis(analyzed_markets)
                analyzed_count = len(analyzed_markets)
            else:
                analyzed_count = 0

            elapsed = time.time() - start_time
            logger.info(
                f"Polymarket update completed: {len(unique_markets)} markets updated, {analyzed_count} opportunities identified in {elapsed:.1f}s"
            )
            self._last_update_ts = time.time()

        except Exception as e:
            logger.error(f"Failed to update markets and analyze: {e}", exc_info=True)

    def force_update(self) -> None:
        """Force immediate update (for manual triggering)"""
        logger.info("Force update triggered")
        self._update_markets_and_analyze()


# Global singleton
_polymarket_worker: Optional[PolymarketWorker] = None
_worker_lock = threading.Lock()


def get_polymarket_worker() -> PolymarketWorker:
    """Get PolymarketWorker singleton"""
    global _polymarket_worker
    with _worker_lock:
        if _polymarket_worker is None:
            update_interval = int(os.getenv("POLYMARKET_UPDATE_INTERVAL_MIN", "30"))
            cache_minutes = int(os.getenv("POLYMARKET_ANALYSIS_CACHE_MIN", "30"))
            _polymarket_worker = PolymarketWorker(
                update_interval_minutes=update_interval, analysis_cache_minutes=cache_minutes
            )
        return _polymarket_worker

"""
Cryptocurrency data source
Get data using CCXT (Coinbase)
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import ccxt

from app.data_sources.base import BaseDataSource, TIMEFRAME_SECONDS
from app.utils.logger import get_logger
from app.config import CCXTConfig, APIKeys

logger = get_logger(__name__)


class CryptoDataSource(BaseDataSource):
    """Cryptocurrency data source"""
    
    name = "Crypto/CCXT"
    
    # time period mapping
    TIMEFRAME_MAP = CCXTConfig.TIMEFRAME_MAP
    
    # List of common quote currencies (sorted by priority)
    COMMON_QUOTES = ['USDT', 'USD', 'BTC', 'ETH', 'BUSD', 'USDC', 'BNB', 'EUR', 'GBP']
    
    def __init__(self):
        config = {
            'timeout': CCXTConfig.TIMEOUT,
            'enableRateLimit': CCXTConfig.ENABLE_RATE_LIMIT
        }
        
        # If a proxy is configured
        if CCXTConfig.PROXY:
            config['proxies'] = {
                'http': CCXTConfig.PROXY,
                'https': CCXTConfig.PROXY
            }
        
        exchange_id = CCXTConfig.DEFAULT_EXCHANGE
        
        # Dynamically loading exchange classes
        if not hasattr(ccxt, exchange_id):
            logger.warning(f"CCXT exchange '{exchange_id}' not found, falling back to 'coinbase'")
            exchange_id = 'coinbase'
            
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class(config)
        
        # Lazy loading of markets (loaded on first use)
        self._markets_loaded = False
        self._markets_cache = None
    
    def _ensure_markets_loaded(self) -> bool:
        """Make sure markets are loaded (for symbol verification)"""
        if self._markets_loaded and self._markets_cache is not None:
            return True
        
        try:
            # Some exchanges require explicit loading of markets
            if hasattr(self.exchange, 'load_markets'):
                self.exchange.load_markets(reload=False)
            self._markets_cache = getattr(self.exchange, 'markets', {})
            self._markets_loaded = True
            return True
        except Exception as e:
            logger.debug(f"Failed to load markets for {self.exchange.id}: {e}")
            return False
    
    def _normalize_symbol(self, symbol: str) -> Tuple[str, str]:
        """
        Normalized symbol format, returns (normalized_symbol, base_currency)
        
        Handles various input formats:
        - BTC/USDT -> BTC/USDT
        - BTCUSDT -> BTC/USDT
        - BTC/USDT:USDT -> BTC/USDT
        - BTC -> BTC/USDT (default)
        - PI, TRX -> PI/USDT, TRX/USDT
        """
        if not symbol:
            return '', ''
        
        sym = symbol.strip()
        
        # Remove swap/futures suffix
        if ':' in sym:
            sym = sym.split(':', 1)[0]
        
        sym = sym.upper()
        
        # If there is already a separator, parse it directly
        if '/' in sym:
            parts = sym.split('/', 1)
            base = parts[0].strip()
            quote = parts[1].strip() if len(parts) > 1 else ''
            if base and quote:
                return f"{base}/{quote}", base
        
        # Try to identify from common quote currencies
        for quote in self.COMMON_QUOTES:
            if sym.endswith(quote) and len(sym) > len(quote):
                base = sym[:-len(quote)]
                if base:
                    return f"{base}/{quote}", base
        
        # If not recognized, USDT will be used by default.
        return f"{sym}/USDT", sym
    
    def _find_valid_symbol(self, base: str, preferred_quote: str = 'USDT') -> Optional[str]:
        """
        Find valid symbols in the exchange's markets
        
        Args:
            base: base currency (e.g. 'PI', 'TRX')
            preferred_quote: preferred quote currency
            
        Returns:
            A valid symbol found, or None if not found
        """
        if not self._ensure_markets_loaded():
            return None
        
        markets = self._markets_cache or {}
        if not markets:
            return None
        
        # Try different quote currencies by priority
        quotes_to_try = [preferred_quote] + [q for q in self.COMMON_QUOTES if q != preferred_quote]
        
        for quote in quotes_to_try:
            candidate = f"{base}/{quote}"
            if candidate in markets:
                market = markets[candidate]
                # Check if the market is active
                if market.get('active', True):
                    return candidate
        
        return None
    
    def _normalize_symbol_for_exchange(self, symbol: str) -> str:
        """
        Standardize symbols based on exchange characteristics
        
        Symbol format requirements for different exchanges:
        - Binance: BTC/USDT (standard format)
        - OKX: BTC/USDT (standard format, but some currencies may not be supported)
        - Coinbase: BTC/USD (usually use USD instead of USDT)
        - Kraken: XBT/USD (BTC is mapped to XBT)
        - Bitfinex: tBTCUST (special format)
        """
        normalized, base = self._normalize_symbol(symbol)
        
        if not normalized or not base:
            return symbol
        
        exchange_id = getattr(self.exchange, 'id', '').lower()
        
        # Special handling: symbol mapping for certain exchanges
        if exchange_id == 'coinbase':
            # Coinbase usually uses USD instead of USDT
            if normalized.endswith('/USDT'):
                usd_version = normalized.replace('/USDT', '/USD')
                if self._ensure_markets_loaded():
                    markets = self._markets_cache or {}
                    if usd_version in markets:
                        return usd_version
        
        # Try to find a valid symbol on the exchange
        if self._ensure_markets_loaded():
            valid_symbol = self._find_valid_symbol(base, normalized.split('/')[1] if '/' in normalized else 'USDT')
            if valid_symbol:
                return valid_symbol
        
        return normalized

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get latest ticker for a crypto symbol via CCXT.

        Accepts common formats:
        - BTC/USDT, BTCUSDT, BTC/USDT:USDT
        - PI, TRX (will be normalized and searched across exchanges)
        - Automatically adapt to the symbol format requirements of different exchanges
        """
        if not symbol or not symbol.strip():
            return {'last': 0, 'symbol': symbol}
        
        # normalized notation
        normalized = self._normalize_symbol_for_exchange(symbol)
        
        if not normalized:
            logger.warning(f"Failed to normalize symbol: {symbol}")
            return {'last': 0, 'symbol': symbol}
        
        # Try to get ticker
        try:
            ticker = self.exchange.fetch_ticker(normalized)
            if ticker and isinstance(ticker, dict):
                return ticker
        except Exception as e:
            error_msg = str(e).lower()
            is_symbol_error = any(keyword in error_msg for keyword in [
                'does not have market symbol',
                'symbol not found',
                'invalid symbol',
                'market does not exist',
                'trading pair not found'
            ])
            
            if is_symbol_error:
                # Try to find alternative symbols
                base = normalized.split('/')[0] if '/' in normalized else normalized
                if self._ensure_markets_loaded():
                    valid_symbol = self._find_valid_symbol(base)
                    if valid_symbol and valid_symbol != normalized:
                        try:
                            logger.debug(f"Trying alternative symbol: {valid_symbol} (original: {symbol}, first attempt: {normalized})")
                            ticker = self.exchange.fetch_ticker(valid_symbol)
                            if ticker and isinstance(ticker, dict):
                                return ticker
                        except Exception as e2:
                            logger.debug(f"Alternative symbol {valid_symbol} also failed: {e2}")
            
            # If all attempts fail, log a warning and return a default value
            logger.warning(
                f"Symbol '{symbol}' (normalized: {normalized}) not found on {self.exchange.id}. "
                f"Error: {str(e)[:100]}"
            )
        
        return {'last': 0, 'symbol': symbol}
    
    def get_kline(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get cryptocurrency K-line data"""
        klines = []
        
        try:
            ccxt_timeframe = self.TIMEFRAME_MAP.get(timeframe, '1d')
            
            # Use a unified symbol normalization method
            symbol_pair = self._normalize_symbol_for_exchange(symbol)
            
            if not symbol_pair:
                logger.warning(f"Failed to normalize symbol for K-line: {symbol}")
                return []
            
            # logger.info(f"Get cryptocurrency K-line: {symbol_pair}, period: {ccxt_timeframe}, number of bars: {limit}")
            
            ohlcv = self._fetch_ohlcv(symbol_pair, ccxt_timeframe, limit, before_time, timeframe)
            
            if not ohlcv:
                logger.warning(f"CCXT returned no K-lines: {symbol_pair}")
                return []
            
            # Convert data format
            for candle in ohlcv:
                if len(candle) < 6:
                    continue
                klines.append(self.format_kline(
                    timestamp=int(candle[0] / 1000),  # Milliseconds to seconds
                    open_price=candle[1],
                    high=candle[2],
                    low=candle[3],
                    close=candle[4],
                    volume=candle[5]
                ))
            
            # Filter and restrict
            klines = self.filter_and_limit(klines, limit, before_time)
            
            # Record results
            self.log_result(symbol, klines, timeframe)
            
        except Exception as e:
            logger.error(f"Failed to fetch crypto K-lines {symbol}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return klines
    
    def _fetch_ohlcv(
        self,
        symbol_pair: str,
        ccxt_timeframe: str,
        limit: int,
        before_time: Optional[int],
        timeframe: str
    ) -> List:
        """Obtain OHLCV data (supports paging to obtain complete data)"""
        try:
            if before_time:
                # Calculation time range
                total_seconds = self.calculate_time_range(timeframe, limit)
                end_time = datetime.fromtimestamp(before_time)
                start_time = end_time - timedelta(seconds=total_seconds)
                since = int(start_time.timestamp() * 1000)
                end_ms = before_time * 1000
                
                # logger.info(f"Historical data request: since={since//1000}, end={before_time}, time span={total_seconds/86400:.1f} days")
                
                # Fetch data in pages until the complete time range is covered
                all_ohlcv = []
                batch_limit = 300  # Coinbase limit is often 300, safer than 1000
                current_since = since
                
                while current_since < end_ms:
                    batch = self.exchange.fetch_ohlcv(
                        symbol_pair, 
                        ccxt_timeframe, 
                        since=current_since, 
                        limit=batch_limit
                    )
                    
                    if not batch:
                        break
                    
                    all_ohlcv.extend(batch)
                    
                    # The time when the last piece of data is obtained is used as the starting time of the next request
                    last_timestamp = batch[-1][0]
                    
                    # If the time of the last data exceeds the end time, or the returned data is less than the requested amount, it means that the acquisition has been completed.
                    # if last_timestamp >= end_ms or len(batch) < batch_limit:
                    if last_timestamp >= end_ms:
                        break
                    
                    # Next time, start from the next time point of the last item
                    timeframe_ms = TIMEFRAME_SECONDS.get(timeframe, 86400) * 1000
                    current_since = last_timestamp + timeframe_ms
                    
                    # logger.info(f"Getting in paging: {len(all_ohlcv)} items have been obtained, continue from {datetime.fromtimestamp(current_since/1000)}")
                
                ohlcv = all_ohlcv
            else:
                ohlcv = self.exchange.fetch_ohlcv(symbol_pair, ccxt_timeframe, limit=limit)
            
            # logger.info(f"CCXT returns {len(ohlcv) if ohlcv else 0} pieces of data")
            return ohlcv
            
        except Exception as e:
            logger.warning(f"CCXT fetch_ohlcv failed: {str(e)}; trying fallback")
            return self._fetch_ohlcv_fallback(symbol_pair, ccxt_timeframe, limit, before_time, timeframe)
    
    def _fetch_ohlcv_fallback(
        self,
        symbol_pair: str,
        ccxt_timeframe: str,
        limit: int,
        before_time: Optional[int],
        timeframe: str
    ) -> List:
        """Alternate acquisition method"""
        try:
            total_seconds = self.calculate_time_range(timeframe, limit)
            
            if before_time:
                end_time = datetime.fromtimestamp(before_time)
                start_time = end_time - timedelta(seconds=total_seconds)
                since = int(start_time.timestamp() * 1000)
            else:
                since = int((datetime.now() - timedelta(seconds=total_seconds)).timestamp() * 1000)
            
            ohlcv = self.exchange.fetch_ohlcv(symbol_pair, ccxt_timeframe, since=since, limit=limit)
            # logger.info(f"CCXT alternative method returns {len(ohlcv) if ohlcv else 0} pieces of data")
            return ohlcv
        except Exception as e:
            logger.error(f"CCXT fallback method also failed: {str(e)}")
            return []


"""
data source factory
Return the corresponding data source according to the market type
"""
from typing import Dict, List, Any, Optional

from app.data_sources.base import BaseDataSource
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DataSourceFactory:
    """data source factory"""
    
    _sources: Dict[str, BaseDataSource] = {}
    
    @classmethod
    def get_source(cls, market: str) -> BaseDataSource:
        """
        Get the data source for the specified market
        
        Args:
            market: market type (Crypto, USStock, Forex, Futures)
            
        Returns:
            Data source instance
        """
        if market not in cls._sources:
            cls._sources[market] = cls._create_source(market)
        return cls._sources[market]

    @classmethod
    def get_data_source(cls, name: str) -> BaseDataSource:
        """
        Backward compatible alias used by older code paths.

        Some modules historically called `get_data_source("binance")` to fetch a crypto data source.
        In the localized Python backend we primarily use `get_source("Crypto")`.
        """
        key = (name or "").strip().lower()
        if key in ("crypto", "binance", "okx", "bybit", "bitget", "kucoin", "gate", "mexc", "kraken", "coinbase"):
            return cls.get_source("Crypto")
        if key in ("futures",):
            return cls.get_source("Futures")
        # Default to Crypto for safety (most callers want a ticker for crypto pairs).
        return cls.get_source("Crypto")
    
    @classmethod
    def _create_source(cls, market: str) -> BaseDataSource:
        """Create data source instance"""
        if market == 'Crypto':
            from app.data_sources.crypto import CryptoDataSource
            return CryptoDataSource()
        elif market == 'USStock':
            from app.data_sources.us_stock import USStockDataSource
            return USStockDataSource()
        elif market == 'Forex':
            from app.data_sources.forex import ForexDataSource
            return ForexDataSource()
        elif market == 'Futures':
            from app.data_sources.futures import FuturesDataSource
            return FuturesDataSource()
        else:
            raise ValueError(f"Unsupported market type: {market}")
    
    @classmethod
    def get_kline(
        cls,
        market: str,
        symbol: str,
        timeframe: str,
        limit: int,
        before_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        A convenient way to obtain K-line data
        
        Args:
            market: market type
            symbol: trading pair/stock code
            timeframe: time period
            limit: number of data items
            before_time: Get data before this time
            
        Returns:
            K-line data list
        """
        try:
            source = cls.get_source(market)
            klines = source.get_kline(symbol, timeframe, limit, before_time)
            
            # Make sure the data is sorted by time
            klines.sort(key=lambda x: x['time'])
            
            return klines
        except Exception as e:
            logger.error(f"Failed to fetch K-lines {market}:{symbol} - {str(e)}")
            return []
    
    @classmethod
    def get_ticker(cls, market: str, symbol: str) -> Dict[str, Any]:
        """
        The convenient way to get realtime quotes
        
        Args:
            market: market type
            symbol: trading pair/stock code
            
        Returns:
            Real-time quotation data: {
                'last': latest price,
                'change': change amount,
                'changePercent': increase or decrease,
                ...
            }
        """
        try:
            source = cls.get_source(market)
            return source.get_ticker(symbol)
        except NotImplementedError:
            logger.warning(f"get_ticker not implemented for market: {market}")
            return {'last': 0, 'symbol': symbol}
        except Exception as e:
            logger.error(f"Failed to fetch ticker {market}:{symbol} - {str(e)}")
            return {'last': 0, 'symbol': symbol}


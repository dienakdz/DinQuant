"""
Indicator Parameters Parser and Helper Functions

Supports two core functions:
1. External transfer of indicator parameters - parse the @param statement in the indicator code
2. Indicators call other indicators - provide call_indicator() function

Parameter declaration format:
# @param param_name type default_value description
# @param ma_fast int 5 short-term moving average period
# @param ma_slow int 20 long-term moving average period
# @param threshold float 0.5 threshold

Supported types: int, float, bool, str
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from app.utils.logger import get_logger
from app.utils.db import get_db_connection

logger = get_logger(__name__)


class IndicatorParamsParser:
    """Parsing parameter declarations in indicator code"""
    
    # Parameter declaration rules: # @param name type default description
    PARAM_PATTERN = re.compile(
        r'#\s*@param\s+(\w+)\s+(int|float|bool|str|string)\s+(\S+)\s*(.*)',
        re.IGNORECASE
    )
    
    @classmethod
    def parse_params(cls, indicator_code: str) -> List[Dict[str, Any]]:
        """
        Parsing parameter declarations in indicator code
        
        Returns:
            List of param definitions:
            [
                {
                    "name": "ma_fast",
                    "type": "int",
                    "default": 5,
                    "description": "Short-term moving average cycle"
                },
                ...
            ]
        """
        params = []
        if not indicator_code:
            return params
        
        for line in indicator_code.split('\n'):
            line = line.strip()
            match = cls.PARAM_PATTERN.match(line)
            if match:
                name = match.group(1)
                param_type = match.group(2).lower()
                default_str = match.group(3)
                description = match.group(4).strip() if match.group(4) else ''
                
                # Convert default value type
                default = cls._convert_value(default_str, param_type)
                
                # Canonical type name
                if param_type == 'string':
                    param_type = 'str'
                
                params.append({
                    "name": name,
                    "type": param_type,
                    "default": default,
                    "description": description
                })
        
        return params
    
    @classmethod
    def _convert_value(cls, value_str: str, param_type: str) -> Any:
        """Convert string value to corresponding type"""
        try:
            param_type = param_type.lower()
            if param_type == 'int':
                return int(value_str)
            elif param_type == 'float':
                return float(value_str)
            elif param_type == 'bool':
                return value_str.lower() in ('true', '1', 'yes', 'on')
            else:  # str/string
                return value_str
        except (ValueError, TypeError):
            return value_str
    
    @classmethod
    def merge_params(cls, declared_params: List[Dict], user_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge declared parameters with user-supplied parameters
        
        Args:
            declared_params: parameter declarations parsed from code
            user_params: user-provided parameter values
            
        Returns:
            Merged parameter dictionary (using user values ​​or default values)
        """
        result = {}
        for param in declared_params:
            name = param['name']
            param_type = param['type']
            default = param['default']
            
            if name in user_params:
                # User supplied value, converted to correct type
                result[name] = cls._convert_value(str(user_params[name]), param_type)
            else:
                # Use default value
                result[name] = default
        
        return result


class IndicatorCaller:
    """
    Indicator caller - allows one indicator to call another indicator
    
    Usage (in indicator code):
        # Call by ID
        rsi_df = call_indicator(5, df)
        
        # Call by name (own indicator)
        macd_df = call_indicator('My MACD', df)
    """
    
    # Maximum call depth to prevent circular dependencies
    MAX_CALL_DEPTH = 5
    
    def __init__(self, user_id: int, current_indicator_id: int = None):
        self.user_id = user_id
        self.current_indicator_id = current_indicator_id
        self._call_stack = []  # Call stack for detecting circular dependencies
    
    def call_indicator(
        self, 
        indicator_ref: Any,  # int (ID) or str (name)
        df: 'pd.DataFrame',
        params: Dict[str, Any] = None,
        _depth: int = 0
    ) -> Optional['pd.DataFrame']:
        """
        Call another indicator and return the result
        
        Args:
            indicator_ref: indicator ID or name
            df: input K-line data
            params: parameters passed to the called indicator
            _depth: used internally to track call depth
            
        Returns:
            DataFrame after execution, containing columns calculated by the called indicator
        """
        import pandas as pd
        import numpy as np
        
        # Check call depth
        if _depth >= self.MAX_CALL_DEPTH:
            logger.error(f"Indicator call depth exceeded {self.MAX_CALL_DEPTH}")
            return df.copy()
        
        # Get indicator code
        indicator_code, indicator_id = self._get_indicator_code(indicator_ref)
        if not indicator_code:
            logger.warning(f"Indicator not found: {indicator_ref}")
            return df.copy()
        
        # Check for circular dependencies
        if indicator_id in self._call_stack:
            logger.error(f"Circular dependency detected: {self._call_stack} -> {indicator_id}")
            return df.copy()
        
        self._call_stack.append(indicator_id)
        
        try:
            # Parse and merge parameters
            declared_params = IndicatorParamsParser.parse_params(indicator_code)
            merged_params = IndicatorParamsParser.merge_params(declared_params, params or {})
            
            # Prepare execution environment
            df_copy = df.copy()
            local_vars = {
                'df': df_copy,
                'open': df_copy['open'].astype('float64') if 'open' in df_copy.columns else pd.Series(dtype='float64'),
                'high': df_copy['high'].astype('float64') if 'high' in df_copy.columns else pd.Series(dtype='float64'),
                'low': df_copy['low'].astype('float64') if 'low' in df_copy.columns else pd.Series(dtype='float64'),
                'close': df_copy['close'].astype('float64') if 'close' in df_copy.columns else pd.Series(dtype='float64'),
                'volume': df_copy['volume'].astype('float64') if 'volume' in df_copy.columns else pd.Series(dtype='float64'),
                'signals': pd.Series(0, index=df_copy.index, dtype='float64'),
                'np': np,
                'pd': pd,
                'params': merged_params,
                # Recursive call support
                'call_indicator': lambda ref, d, p=None: self.call_indicator(ref, d, p, _depth + 1)
            }
            
            # Safe execution
            import builtins
            def safe_import(name, *args, **kwargs):
                allowed_modules = ['numpy', 'pandas', 'math', 'json', 'time']
                if name in allowed_modules or name.split('.')[0] in allowed_modules:
                    return builtins.__import__(name, *args, **kwargs)
                raise ImportError(f"Module not allowed: {name}")
            
            safe_builtins = {k: getattr(builtins, k) for k in dir(builtins) 
                           if not k.startswith('_') and k not in [
                               'eval', 'exec', 'compile', 'open', 'input',
                               'help', 'exit', 'quit', '__import__',
                               'copyright', 'credits', 'license'
                           ]}
            safe_builtins['__import__'] = safe_import
            
            exec_env = local_vars.copy()
            exec_env['__builtins__'] = safe_builtins
            
            pre_import = "import numpy as np\nimport pandas as pd\n"
            exec(pre_import, exec_env)
            exec(indicator_code, exec_env)
            
            return exec_env.get('df', df_copy)
            
        except Exception as e:
            logger.error(f"Error calling indicator {indicator_ref}: {e}")
            return df.copy()
        finally:
            self._call_stack.pop()
    
    def _get_indicator_code(self, indicator_ref: Any) -> Tuple[Optional[str], Optional[int]]:
        """Get indicator code"""
        try:
            with get_db_connection() as db:
                cursor = db.cursor()
                
                if isinstance(indicator_ref, int):
                    # Query by ID
                    cursor.execute("""
                        SELECT id, code FROM qd_indicator_codes 
                        WHERE id = %s AND (user_id = %s OR publish_to_community = 1)
                    """, (indicator_ref, self.user_id))
                else:
                    # Query by name (priority to own indicators)
                    cursor.execute("""
                        SELECT id, code FROM qd_indicator_codes 
                        WHERE name = %s AND user_id = %s
                        UNION
                        SELECT id, code FROM qd_indicator_codes 
                        WHERE name = %s AND publish_to_community = 1
                        LIMIT 1
                    """, (str(indicator_ref), self.user_id, str(indicator_ref)))
                
                row = cursor.fetchone()
                cursor.close()
                
                if row:
                    return row['code'], row['id']
                return None, None
                
        except Exception as e:
            logger.error(f"Error fetching indicator code: {e}")
            return None, None


def get_indicator_params(indicator_id: int) -> List[Dict[str, Any]]:
    """
    Get the indicator parameter declarations for API usage
    
    Args:
        indicator_id: Indicator ID
        
    Returns:
        A list of parameter declarations
    """
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            cursor.execute("SELECT code FROM qd_indicator_codes WHERE id = %s", (indicator_id,))
            row = cursor.fetchone()
            cursor.close()
            
            if row and row['code']:
                return IndicatorParamsParser.parse_params(row['code'])
            return []
    except Exception as e:
        logger.error(f"Error getting indicator params: {e}")
        return []

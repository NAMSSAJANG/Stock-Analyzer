"""Cache identity includes the actual stock and benchmark observations."""
import hashlib

import pandas as pd

from calibration_engine import CALIBRATION_LOGIC_VERSION


def data_signature(*frames):
    digest = hashlib.sha256()
    for frame in frames:
        if frame is None:
            digest.update(b"<none>")
            continue
        digest.update(str((frame.shape, list(frame.columns), list(map(str, frame.dtypes)))).encode())
        digest.update(pd.util.hash_pandas_object(frame, index=True).values.tobytes())
    return digest.hexdigest()


def calibration_key(symbol, threshold, frame, benchmark=None):
    return f"calibration_result_{CALIBRATION_LOGIC_VERSION}_{symbol}_{threshold}_{data_signature(frame, benchmark)}"

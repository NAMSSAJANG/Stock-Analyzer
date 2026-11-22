"""Cache identity includes the actual stock and benchmark observations."""

import hashlib
from typing import cast

import numpy as np
import pandas as pd

from goldnam_engine.validation.calibration_engine import CALIBRATION_LOGIC_VERSION


def data_signature(*frames: pd.DataFrame | None) -> str:
    digest = hashlib.sha256()
    for frame in frames:
        if frame is None:
            digest.update(b"<none>")
            continue
        digest.update(
            str((frame.shape, list(frame.columns), list(map(str, frame.dtypes)))).encode()
        )
        digest.update(
            cast(np.ndarray, pd.util.hash_pandas_object(frame, index=True).values).tobytes()
        )
    return digest.hexdigest()


def calibration_key(
    symbol: str, threshold: float, frame: pd.DataFrame, benchmark: pd.DataFrame | None = None
) -> str:
    return f"calibration_result_{CALIBRATION_LOGIC_VERSION}_{symbol}_{threshold}_{data_signature(frame, benchmark)}"

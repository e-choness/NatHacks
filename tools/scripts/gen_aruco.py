#!/usr/bin/env python3
"""
Generate printable ArUco markers for IDs used by the tool guidance.
Usage:
  python scripts/gen_aruco.py --ids 23 42 --size 500 --dict DICT_5X5_250 --out out_dir
"""
import argparse
import importlib
from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', type=int, nargs='+', default=[23, 42])
    ap.add_argument('--size', type=int, default=500)
    ap.add_argument('--dict', dest='dict_name', type=str, default='DICT_5X5_250')
    ap.add_argument('--out', type=str, default='markers')
    args = ap.parse_args()

    aruco = importlib.import_module('cv2.aruco')
    dictionary = getattr(aruco, args.dict_name, getattr(aruco, 'DICT_5X5_250'))
    dictionary = aruco.getPredefinedDictionary(dictionary)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for mid in args.ids:
        img = np.zeros((args.size, args.size), dtype=np.uint8)
        img = aruco.drawMarker(dictionary, int(mid), args.size)
        out_path = out_dir / f'aruco_{mid}.png'
        cv2.imwrite(str(out_path), img)
        print(f'Wrote {out_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

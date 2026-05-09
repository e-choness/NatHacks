#!/usr/bin/env python3
"""
Chessboard-based camera calibration for generating config/camera_intrinsics.yml
Usage:
  python scripts/calibrate_cam.py --rows 6 --cols 9 --square 0.024 --out config/camera_intrinsics.yml
Press space to capture a frame; q to finish when you have >=10 captures.
"""
import argparse
import cv2
import numpy as np
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--rows', type=int, default=6)
    ap.add_argument('--cols', type=int, default=9)
    ap.add_argument('--square', type=float, default=0.024, help='square size in meters')
    ap.add_argument('--device', type=int, default=0)
    ap.add_argument('--out', type=str, default='config/camera_intrinsics.yml')
    args = ap.parse_args()

    board = (args.rows, args.cols)
    objp = np.zeros((board[0]*board[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:board[0], 0:board[1]].T.reshape(-1, 2)
    objp *= args.square

    objpoints = []
    imgpoints = []

    cap = cv2.VideoCapture(args.device)
    if not cap.isOpened():
        print('Failed to open camera')
        return 1

    print('Press space to capture frames with visible chessboard; q to finish')
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ret_c, corners = cv2.findChessboardCorners(gray, board, None)
        vis = frame.copy()
        if ret_c:
            cv2.drawChessboardCorners(vis, board, corners, ret_c)
        cv2.imshow('calibrate', vis)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            if ret_c:
                objpoints.append(objp)
                corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1),
                                             (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
                imgpoints.append(corners2)
                print(f'Captured {len(objpoints)} frames')
            else:
                print('Chessboard not found; try again')
        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    if len(objpoints) < 10:
        print('Need at least 10 valid captures')
        return 1

    img_size = (gray.shape[1], gray.shape[0])
    K_init = None  # let OpenCV allocate
    dist_init = None
    ret, K, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, img_size, K_init, dist_init)
    print(f'Reprojection error: {ret:.4f}')

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fs = cv2.FileStorage(str(out_path), cv2.FILE_STORAGE_WRITE)
    fs.write("K", K)
    fs.write("dist", dist)
    fs.release()
    print(f'Wrote {out_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

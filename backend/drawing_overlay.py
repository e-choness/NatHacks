"""
Face & landmark detection on sample image
Overlay drawings to represent task directions
"""

from cloud_vision import CloudVisionClient
import os
import cv2
import numpy as np

# setup credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "backend/eminent-will-477604-h6-d9d50a6b65d4.json"
os.environ["GOOGLE_CLOUD_PROJECT"] = "vision-api-nathacks25"


### VISION WORKFLOW
"""
# get sample image
with open("backend/sample_human_face.jpeg", "rb") as f:
    image_bytes = f.read()

# detect faces
client = CloudVisionClient(timeout_s=5)
result = client.detect_faces(image_bytes)

# output results
if result and result["ok"]:
    for landmark_type, (x, y) in result["landmarks"].items():
        print(f"{landmark_type}: x={x:.3f}, y={y:.3f}")
    print("Confidence:", result["confidence"])
else:
    print(f"\033[31m{result}\033[0m")
    print("No landmarks detected")
"""

### WORKFLOW WITH EYEBROW
# get image, prep for vision api
img = cv2.imread("backend/sample_human_face.jpeg")
_, buffer = cv2.imencode(".jpeg", img)
image_bytes = buffer.tobytes()

# detect faces & landmarks in img
client = CloudVisionClient(timeout_s=5)
result = client.detect_faces(image_bytes)

# get coords of landmarks detected
# if result and result["ok"]:
#     for landmark_type, (x, y) in result["landmarks"].items():
#         print(f"{landmark_type}: x={x:.3f}, y={y:.3f}")
#     print("Confidence:", result["confidence"])
# else:
#     print(f"\033[31m{result}\033[0m")
#     print("No landmarks detected")

# prepare for overlay
height, width, _ = img.shape

# un-normalize back to pixel coords
landmarks_px = {
    landmark_type: (int(x * width), int(y * height)) 
    for landmark_type, (x, y) in result["landmarks"].items()
}
"""
print(landmarks_px)

output:

{'mouth_center': (1542, 1155), 'mouth_left': (1406, 1160), 'mouth_right': (1673, 1153), 'cheek_left': (1314, 1022), 'cheek_right': (1737, 1014), 'left_of_left_eyebrow': (1259, 718), 'right_of_left_eyebrow': (1466, 721), 'left_of_right_eyebrow': (1630, 724), 'right_of_right_eyebrow': (1784, 723)}
"""
left_eyebrow_coords = [landmarks_px["right_of_left_eyebrow"], landmarks_px["left_of_left_eyebrow"]]

right_eyebrow_coords = [landmarks_px["left_of_right_eyebrow"], landmarks_px["right_of_right_eyebrow"]]

print(left_eyebrow_coords)
print(right_eyebrow_coords)


# calc dimensions for resizing eyebrow img onto right eyebrow
right_eyebrow_length = abs(right_eyebrow_coords[0][0] - right_eyebrow_coords[1][0])
right_eyebrow_height = abs(right_eyebrow_coords[0][1] - right_eyebrow_coords[1][1])

left_eyebrow_length = abs(left_eyebrow_coords[0][0] - left_eyebrow_coords[1][0])
left_eyebrow_height = abs(left_eyebrow_coords[0][1] - left_eyebrow_coords[1][1])

# calc dimensions for resisizing eyebrow img onto left eyebrow (need to reflect original img)

# place eyebrow over base img (no rotating?)

# animate / apply effects as mask?





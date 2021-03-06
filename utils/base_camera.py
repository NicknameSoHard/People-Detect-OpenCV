from cv2 import VideoCapture

from multiprocessing import Lock
from threading import Thread


class Camera(Thread):
    def __init__(self, cam_string=0):
        self.cam = VideoCapture(cam_string)
        if not self.cam.isOpened():
            raise ValueError('Error VideoCapture')

        self.lock = Lock()
        self.current_frame = None
        super().__init__()
        self.start()

    def get_camera_settings(self):
        return {"frame_width": self.cam.get(3),
                'frame_height': self.cam.get(4)}

    def run(self):
        while self.cam.isOpened():
            res, frame = self.cam.read()
            with self.lock:
                if frame is not None:
                    self.current_frame = frame.copy()

    def get_frame(self):
        with self.lock:
            frame = self.current_frame.copy() if self.current_frame is not None else None
        return frame

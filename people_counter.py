import datetime

import cv2
import numpy
import os

from utils.base_camera import Camera
from utils.person import Person
from utils.settings_dict import SettingsDict


class PeopleCounter:
    def __init__(self):
        self.cnt_up = 0
        self.cnt_down = 0

        cam_string = os.getenv('CAMERA_ADDRESS', 0)
        # Catch video
        self.cap = Camera(cam_string)
        # Load settings
        self.setting = SettingsDict()

        # take frame width and height
        self.cam_characteristic = self.cap.get_camera_settings()
        self.res = self.cam_characteristic['frame_height'] * self.cam_characteristic['frame_width']
        # Calculate the min and max size of the object
        self.min_areaTH = self.res / 40
        self.max_areaTH = self.res / 3

        cv2.namedWindow("Panel")

        cv2.createTrackbar("THRSH_MIN", "Panel", self.setting['THRSH_MIN'], 255, self.do_nothing)
        cv2.createTrackbar("MIN_OBJ", "Panel", self.setting['MIN_OBJ'], 255, self.do_nothing)
        cv2.createTrackbar("MAX_OBJ", "Panel", self.setting['MAX_OBJ'], 255, self.do_nothing)
        cv2.createTrackbar("DWN_LINE", "Panel", self.setting['DWN_LINE'],
                           self.cam_characteristic['frame_height'], self.do_nothing)
        cv2.createTrackbar("TOP_LINE", "Panel", self.setting['TOP_LINE'],
                           self.cam_characteristic['frame_height'], self.do_nothing)

        # Create morphological filters
        self.kernelOp = numpy.ones((3, 3), numpy.uint8)
        self.kernelCl = numpy.ones((11, 11), numpy.uint8)

        # create fonts type
        self.font = cv2.FONT_HERSHEY_SIMPLEX

        # Makes array for detector
        self.persons = []

    def save_log(self, direction):
        """
        Write log for 1C.
        """
        try:
            direction_mark = "2" if direction == "up" else "1"

            now = datetime.datetime.now()
            with open(now.strftime("%d%m%y%H") + ".txt", "a") as log_file:
                log_file.write(f"{now.strftime('%d.%m.%Y')}|{now.microsecond}"
                               f"|1|{direction_mark[1]}|PCCapture|0|")
            return True
        except Exception:
            return False

    def do_nothing(x):
        """
         Trackpad function. nothing to do
        """
        pass

    def run(self):
        iteration_counter = 0

        # Create panel and trackpads
        panel = numpy.zeros([1, 256], numpy.uint8)

        # Get mask
        mask_frame = self.cap.get_frame()
        settings_change = True
        while True:
            # Get frame
            frame = self.cap.get_frame()
            # Calculates the absolute difference between mask and frame frames(arrays).
            frame_ABS = cv2.absdiff(frame, mask_frame)
            #            cv2.imshow('ADS',frame_ABS)
            # Converts an image to gray color space.
            gray_frame = cv2.cvtColor(frame_ABS, cv2.COLOR_BGR2GRAY)

            cv2.imshow("Panel", panel)

            # if position trackbars not equal settings
            for key in self.setting.get_settings_names():
                trackbar_position = cv2.getTrackbarPos(key, "Panel")
                if self.setting[key] != trackbar_position:
                    self.setting[key] = trackbar_position
                    settings_change = True

            if settings_change:
                # Recalculate setting
                self.min_areaTH = self.res / (255 - self.setting['MIN_OBJ'] + 1)
                self.max_areaTH = self.res / (255 - self.setting['MAX_OBJ'] + 1)

                # If setting line position change, recalculate and her
                line_down = int(self.setting[3])
                pt1, pt2 = [0, line_down], [self.cam_characteristic['frame_width'], line_down]
                pts_L1 = numpy.array([pt1, pt2], numpy.int32)
                pts_L1 = pts_L1.reshape((-1, 1, 2))

                line_up = int(self.setting[4])
                pt3, pt4 = [0, line_up], [self.cam_characteristic['frame_width'], line_up]
                pts_L2 = numpy.array([pt3, pt4], numpy.int32)
                pts_L2 = pts_L2.reshape((-1, 1, 2))

                self.setting.write_file()
            settings_change = False

            try:
                # Threshold the difference frame (Change color space to black and white)
                ret, imBin = cv2.threshold(gray_frame, self.setting[0], 255, cv2.THRESH_BINARY)
                # Morphology transformation (open and close). Just filter the noise in the image.
                morphology_mask = cv2.morphologyEx(imBin, cv2.MORPH_OPEN, self.kernelOp)
                morphology_mask = cv2.morphologyEx(morphology_mask, cv2.MORPH_CLOSE, self.kernelCl)
            #                cv2.imshow('morphologyEx', morphology_mask)
            except Exception:
                # All exceptions end the program.
                print('Error threshold or morphology. End of programm.')
                print(f"UP:{self.cnt_up}")
                print(f"DOWN:{self.cnt_down}")
                break

                # Find contours on image
            ___, contours0, ___ = cv2.findContours(morphology_mask,
                                                   cv2.RETR_EXTERNAL,
                                                   cv2.CHAIN_APPROX_SIMPLE
                                                   )

            # For all contours
            for cnt in contours0:
                # Calculate size of contours
                area = cv2.contourArea(cnt)
                # check cameras on noise
                detected_area = self.cam_characteristic['frame_width'] \
                                * self.cam_characteristic['frame_height'] * 0.90
                if area > detected_area:
                    iteration_counter = 1000

                if self.min_areaTH < area < self.max_areaTH:
                    M = cv2.moments(cnt)
                    # Get coordinates of the edges
                    cx = int(M['m10'] / M['m00'])
                    cy = int(M['m01'] / M['m00'])
                    # Get the coordinates of the scope
                    x, y, w, h = cv2.boundingRect(cnt)
                    # Check for a new object
                    new = True
                    for i in self.persons:
                        # If the object is close to already detected
                        if abs(cx - i.getX()) <= w and abs(cy - i.get_y()) <= h:
                            new = False
                            # Update coordinates for better tracking
                            i.update_coords(cx, cy)

                            date_now = datetime.datetime.now()
                            # Check cross the line
                            if i.going_up(line_up):
                                self.cnt_up += 1
                                # Write log to console and file
                                self.save_log("up")
                                break

                            elif i.going_down(line_down):
                                self.cnt_down += 1
                                self.save_log("down")
                                break
                        else:
                            print("New obj")
                        # delete object if work done
                        if i.timed_out():
                            index = self.persons.index(i)
                            self.persons.pop(index)
                            del i

                    # Create new object
                    if new:
                        p = Person(cx, cy)
                        self.persons.append(p)

                    # Draw red dot in a middle object, and make scope.
                    cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    iteration_counter = 0
                else:
                    # Count frames without tracking objects
                    iteration_counter += 1
                    # If we had a lot of frames without tracking object,
                    # we update mask and tracking array
                    if iteration_counter > 1000:
                        ret, mask_frame = self.cap.get_frame()
                        iteration_counter = 0
                        self.persons = []

            # Draw lines and text on frames
            str_up = f"UP: {self.cnt_up}"
            str_down = f"DOWN:{self.cnt_down}"
            frame = cv2.polylines(frame, [pts_L1], False, (255, 0, 0), thickness=2)
            frame = cv2.polylines(frame, [pts_L2], False, (255, 0, 0), thickness=2)

            cv2.putText(frame, str_up, (10, 40), self.font, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, str_up, (10, 40), self.font, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, str_down, (10, 90), self.font, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, str_down, (10, 90), self.font, 0.5, (255, 0, 0), 1, cv2.LINE_AA)

            # Show final frame
            cv2.imshow('Frame', frame)

            # Checking the key press
            k = cv2.waitKey(30) & 0xff
            # if ESC - end program
            if k == 27:
                break
            # If SPACE, we update mask and reset exit counters
            elif k == 32:
                ret, mask_frame = self.cap.get_frame()
                self.cnt_up = 0
                self.cnt_down = 0

        # Close camera and all windows
        cv2.destroyAllWindows()


if __name__ == '__main__':
    pc = PeopleCounter()
    pc.run()

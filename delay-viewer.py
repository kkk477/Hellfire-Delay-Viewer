import sys
import cv2
import numpy as np
import threading
import time
import pyautogui
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QListWidget, QPushButton, QVBoxLayout, QHBoxLayout, QWidget # type: ignore
from PyQt5.QtCore import QTimer, QThread, pyqtSignal # type: ignore
import os
import datetime

class RecognitionThread(QThread):
    recognized = pyqtSignal(str)

    def __init__(self, template_durations, mp_template_path):  # mp_template_path 추가
        super().__init__()
        self.template_durations = template_durations
        self.mp_template = cv2.imread(mp_template_path, 0)  # MP 템플릿 로드
        self.running = True
        self.mp_detected = False  # MP 템플릿이 감지되었는지 여부를 추적

    def run(self):
        templates = {name: cv2.imread(name, 0) for name in self.template_durations.keys()}
        while self.running:
            screenshot = pyautogui.screenshot()
            frame = np.array(screenshot)
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 먼저 MP 템플릿 감지 확인
            mp_res = cv2.matchTemplate(gray_frame, self.mp_template, cv2.TM_CCOEFF_NORMED)
            mp_min_val, mp_max_val, mp_min_loc, mp_max_loc = cv2.minMaxLoc(mp_res)
            self.mp_detected = mp_max_val > 0.8

            for template_name, template in templates.items():
                if template is None:
                    continue

                res = cv2.matchTemplate(gray_frame, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

                if max_val > 0.8 and self.mp_detected:
                    # 헬파이어 또는 삼매진화 템플릿과 MP 템플릿이 모두 감지되었을 때
                    self.recognized.emit(template_name)

            time.sleep(0.05)

    def stop(self):
        self.running = False
        self.quit()
        self.wait()

class ImageRecognitionTimerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('헬파이어 딜레이 표시기')
        self.setGeometry(100, 100, 300, 200)
        self.setFixedSize(300, 400)

        # Main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Top layout for timer list
        self.top_layout = QHBoxLayout()
        self.main_layout.addLayout(self.top_layout, stretch=2)

        # Timer list
        timer_layout = QVBoxLayout()
        timer_label = QLabel('타이머')
        timer_label.setStyleSheet("font-size: 15px;")  # Set font size to 15
        timer_layout.addWidget(timer_label)
        self.timer_list = QListWidget()
        self.timer_list.setStyleSheet("font-size: 20px;")  # Set font size to 20
        timer_layout.addWidget(self.timer_list)
        self.top_layout.addLayout(timer_layout)

        # Control buttons
        self.control_layout = QHBoxLayout()
        self.main_layout.addLayout(self.control_layout, stretch=1)
        
        self.start_button = QPushButton('시 작')
        self.start_button.setFixedHeight(30)
        self.start_button.setStyleSheet("font-size: 15px;")
        self.start_button.setEnabled(True)
        self.start_button.clicked.connect(self.start_recognition)
        self.control_layout.addWidget(self.start_button)

        self.stop_button = QPushButton('정 지')
        self.stop_button.setFixedHeight(30)
        self.stop_button.setStyleSheet("font-size: 15px;")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_recognition)
        self.control_layout.addWidget(self.stop_button)

        # Timer and recognition control
        self.recognition_thread = None
        self.template_durations = {
            './images/hellfire.png': {'duration': 9, 'name': '헬파이어'},  # 9초 타이머
            './images/crosshellfire.png': {'duration': 60, 'name': '삼매진화'},  # 60초 타이머
        }
        self.timers = {}
        self.timer_objects = {}

        # Ensure logs directory exists
        if not os.path.exists('logs'):
            os.makedirs('logs')

    def log(self, message):
        print(message)  # 콘솔에 로그 출력

    def start_recognition(self):
        if not self.recognition_thread:
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.log('Image recognition started.')
            self.recognition_thread = RecognitionThread(self.template_durations, './images/mp_zero.png')
            self.recognition_thread.recognized.connect(self.add_timer)
            self.recognition_thread.start()

    def stop_recognition(self):
        if self.recognition_thread:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.recognition_thread.stop()
            self.recognition_thread = None
            self.log('Image recognition stopped.')
            self.save_log_to_file()

    def add_timer(self, template_name):
        if template_name in self.timers and self.timers[template_name]['active']:
            return

        template_info = self.template_durations[template_name]
        duration = template_info['duration']
        timer_label = f"{template_info['name']}: {duration:02}.0"
        self.timer_list.addItem(timer_label)

        self.timers[template_name] = {'duration': duration, 'active': True}
        timer = QTimer(self)
        timer.setInterval(100)
        timer.timeout.connect(lambda: self.update_timer(template_name, timer))
        timer.start()
        self.timer_objects[template_name] = timer

    def update_timer(self, template_name, timer):
        if template_name not in self.timers or not self.timers[template_name]['active']:
            return

        timer_info = self.timers[template_name]
        elapsed_time = (timer.interval() / 1000)
        timer_info['duration'] -= elapsed_time

        if timer_info['duration'] <= 0:
            timer.stop()  # 타이머만 멈추고, 프로그램 종료는 없음
            self.remove_timer(template_name)
            return

        minutes, seconds = divmod(int(timer_info['duration']), 60)
        milliseconds = int((timer_info['duration'] - int(timer_info['duration'])) * 10)
        updated_label = f"{self.template_durations[template_name]['name']}: {minutes:02}:{seconds:02}.{milliseconds}"
        for i in range(self.timer_list.count()):
            if self.timer_list.item(i).text().startswith(self.template_durations[template_name]['name']):
                self.timer_list.item(i).setText(updated_label)

    def remove_timer(self, template_name):
        for i in range(self.timer_list.count()):
            if self.timer_list.item(i).text().startswith(self.template_durations[template_name]['name']):
                self.timer_list.takeItem(i)
                break

        if template_name in self.timers:
            self.log(f"{self.template_durations[template_name]['name']} timer finished and removed.")
            self.timers[template_name]['active'] = False

    def save_log_to_file(self):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f'log_{timestamp}.txt'
        with open(f'logs/{filename}', 'w') as log_file:
            log_file.write('Logs saved to file.')

    def closeEvent(self, event):
        if self.recognition_thread:
            self.recognition_thread.stop()
        self.save_log_to_file()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ImageRecognitionTimerApp()
    window.show()
    sys.exit(app.exec_())

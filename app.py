import string
import random
import cv2
import camera
import pyaudio
import csv
import os

from flask import Flask, Response, render_template, request, redirect
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app)
camera.load_all_cameras()
camera.start_refreshing()
a = False
audio1 = pyaudio.PyAudio()
data = {}
userName = ''
streamerList = list()
fileName='streamers.csv'
urlList = list()
for i in range(30):
    urlList.append(''.join(random.SystemRandom().choice(string.ascii_lowercase + string.digits) for _ in range(5)))
class Audio:
    """
    Audio processing
    Generate header of stream audio
    """
    def __init__(self,sampleRate,bitsPerSample,channels):
        self.sampleRate = sampleRate
        self.bitsPerSample = bitsPerSample
        self.channels = channels

    def genHeader(self, ):
        datasize = 10240000
        header = bytes("RIFF", 'ascii')  # (4byte) Marks file as RIFF
        header += (datasize + 36).to_bytes(4, 'little')  # (4byte) File size in bytes excluding this and RIFF marker
        header += bytes("WAVE", 'ascii')  # (4byte) File type
        header += bytes("fmt ", 'ascii')  # (4byte) Format Chunk Marker
        header += (16).to_bytes(4, 'little')  # (4byte) Length of above format data
        header += (1).to_bytes(2, 'little')  # (2byte) Format type (1 - PCM)
        header += (self.channels).to_bytes(2, 'little')  # (2byte)
        header += (self.sampleRate).to_bytes(4, 'little')  # (4byte)
        header += (self.sampleRate * self.channels *self.bitsPerSample // 8).to_bytes(4, 'little')  # (4byte)
        header += (self.channels * self.bitsPerSample// 8).to_bytes(2, 'little')  # (2byte)
        header += (self.bitsPerSample).to_bytes(2, 'little')  # (2byte)
        header += bytes("data", 'ascii')  # (4byte) Data Chunk Marker
        header += (datasize).to_bytes(4, 'little')  # (4byte) Data size in bytes
        return header


class Video:
    """
    Video processing
    Generate stream of .jpg images from camera
    """
    def __init__(self):
        self.camera = cv2.VideoCapture(0)  # get camera with index 0

    def gen(self):
        out = cv2.VideoWriter('output.avi', -1, 20.0, (640, 480))
        while True:
            ret, img = self.camera.read()
            if ret:
                frame = cv2.imencode('.jpg', img)[1].tobytes() # get converted images from camera
                yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                break

    def showStream(self, url):
        self.camera.release()
        cap = cv2.VideoCapture(url)
        while (True):
            ret, frame = cap.read()

            if ret:
                cv2.imshow('output', frame)
                if cv2.waitKey(1) == ord('q'):
                    break
            else:
                break
        return True


    def save_video(self):
        cap = cv2.VideoCapture(0)
        out = cv2.VideoWriter('output.avi', -1, 20.0, (640, 480))
        i = 1
        while (cap.isOpened()):
            ret, frame = cap.read()
            i = i + 1
            print(i)
            if ret == True:
                frame = cv2.flip(frame, 0)
                # write the flipped frame
                out.write(frame)
                cv2.imshow('frame', frame)
                if (cv2.waitKey(1) & 0xFF == ord('q') or i > 100):
                    break
            else:
                break
        cap.release()
        out.release()
        cv2.destroyAllWindows()


@app.route('/video_feed')
def video_feed():
    video = Video()
    return Response(video.gen(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/start', methods=["GET", "POST"])
def button():
    return app.send_static_file('start_menu.html')


def main():
    socketio.run(app)


@app.route('/'+urlList[0], methods=["GET", "POST"])
def stream():
    e = fileName
    try:
        with open(fileName) as csvfile:
            csvv = csv.reader(csvfile, delimiter=',', quotechar='"')
            for row in csvv:
                if ((row[0] == request.remote_addr) &(row[1]==urlList[0])):
                    urlList.pop(0)
                    dat = data
                    return render_template('stream.html', data=data)
            video = Video()
            video.showStream(url=urlList[0])
            urlList.pop(0)
            input().close()
            return render_template('stream.html', data=data, src2='/' + urlList[0])
    except Exception:
        print('stream: {0}'.format(Exception))


@app.route('/stream', methods=["GET", "POST"])
def generateStream(): # generate stream
    try:
        if request.method=='POST':
            userName=request.form.get('userName')
            print(len(userName))
            if (len(userName) != 0 and ' ' not in userName):
                global urlList
                global streamerList
                streamerList.append(request.remote_addr)
                fields = [streamerList[-1], urlList[0]]
                with open(fileName, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(fields)
                url = urlList[0]
                global data
                data = {'userName':userName}
                return redirect('/' + url)
            else:
                return redirect('/start')
    except Exception:
        print('generateStream: {0}'.format(Exception))


def messageReceived(methods=['GET', 'POST']):
    print('message was received!!!')


@socketio.on('my event')
def handle_my_custom_event(json, methods=['GET', 'POST']):
    print('received my event: ' + str(json))
    socketio.emit('my response', json, callback=messageReceived)


def endStream():
    try:
        input = open(fileName, 'rb')
        output = open('intermediate.csv', 'wb')
        writer = csv.writer(output)
        for row in csv.reader(input):
            if row[0] != request.remote_addr:
                writer.writerow(row)
            input.close()
            output.close()
        os.rename('intermediate.csv', fileName)
    except Exception:
        print('endStream: {0}'.format(Exception))


@app.route('/audio')
def audio():
    """
    Start recording
    Read and playing audio
    """
    def sound():
        CHUNK = 1024 # passage size
        FORMAT = pyaudio.paInt16
        RATE = 44100
        bitsPerSample = 16 # sound depth
        channels = 1 # number of channels
        audio = Audio(RATE, bitsPerSample, channels)
        wav_header = audio.genHeader()

        stream = audio1.open(format=FORMAT, channels=channels,
                        rate=RATE, input=True,input_device_index=1,
                        frames_per_buffer=CHUNK)
        print("recording...")
        frames = []
        first_run = True
        data = wav_header
        data += stream.read(CHUNK)
        yield(data)
        while True:
            global a
            if (a == True):
                break
            data = stream.read(CHUNK)
            yield(data)
    return Response(sound())


@app.route('/press_button', methods=['POST'])
def press_button():
    try:
        if request.method == "POST":
            global a
            a = True
    except Exception:
        print(Exception)

if __name__ == '__main__':
    main()
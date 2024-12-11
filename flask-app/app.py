from collections import defaultdict
from flask import Flask, render_template, url_for, request
from flask_socketio import SocketIO, emit
import os
import operator
from threading import Lock
import time
import redis
import json



# Taken from https://web.archive.org/web/20190420170234/http://flask.pocoo.org/snippets/35/
class ReverseProxied(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


app = Flask(__name__)
app.config['SECRET_KEY'] = '0101010101010'
app.wsgi_app = ReverseProxied(app.wsgi_app)

REDIS_URL = "redis://redis:6379/0"

redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)

socketio = SocketIO(app, message_queue=REDIS_URL, )


users = 0

button_pressed = False
button_clicks = 0

strokes = defaultdict(list)
strokes_lock = Lock()

# Taken from https://stackoverflow.com/questions/32132648/python-flask-and-jinja2-passing-parameters-to-url-for
@app.context_processor
def override_url_for():
    if app.debug:
        return dict(url_for=dated_url_for)
    return dict(url_for=url_for)


def dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(app.root_path,
                                     endpoint, filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)


@app.route('/')
def index():
    return render_template('index.html')


def get_all_strokes():
    """
    Retrieve from strokes list strokes in sorted order.
    :return: list of strokes in sorted by time, ascending
    """
    stroke_keys = redis_client.keys('stroke:*')  # Redis keys with pattern 'stroke:*'
    all_strokes = []

    for key in stroke_keys:
        stroke_data = redis_client.get(key)
        if stroke_data:
            all_strokes.append(json.loads(stroke_data))

    # Sort strokes by time
    # all_strokes.sort(key=operator.itemgetter('time'))
    return all_strokes


@socketio.on('connect')
def socket_connect():
    global users, button_clicks
    users += 1
    emit('users', users, broadcast=True)
    emit('update-click-count', button_clicks)
    emit('draw-strokes', get_all_strokes())
    if button_pressed:
        emit('btn-click')


@socketio.on('disconnect')
def socket_disconnect():
    global users
    users -= 1
    emit('users', users, broadcast=True)

# Button handling
@socketio.on('btn-click')
def button_click():
    global button_pressed, button_clicks

    if button_pressed:
        return

    button_clicks += 1
    button_pressed = True

    emit('update-click-count', button_clicks, broadcast=True)
    emit('btn-click', broadcast=True)


@socketio.on('btn-release')
def button_release():
    global button_pressed

    if not button_pressed:
        return

    button_pressed = False
    emit('btn-release', broadcast=True)

# Whiteboard handling
@socketio.on('stroke-start')
def stroke_start(data):
    global strokes

    with strokes_lock:
        data['time'] = time.time()

        # Store stroke in Redis
        stroke_id = f"stroke:{request.sid}:{data['time']}"  # Unique stroke identifier
        redis_client.set(stroke_id, json.dumps(data))

        strokes[request.sid].append(data)
        


@socketio.on('stroke-update')
def stroke_update(data):
    global strokes
    
    
    data['time'] = time.time()
    with strokes_lock:
        # Original stroke will still update
        # because stroke holds reference to most recent stroke
        stroke = strokes[request.sid][-1]
        stroke['points'].append(data)
        stroke_id = f"stroke:{request.sid}:{data['time']}" 
        update_stroke = {'thickness': stroke['thickness'],
                         'color': stroke['color'],
                         'points': stroke['points'][-2:]}
        
        redis_client.set(stroke_id, json.dumps(update_stroke))
    emit('draw-new-stroke', update_stroke, broadcast=True, include_self=False)


@socketio.on('stroke-delete')
def stroke_delete():
    global strokes

    with strokes_lock:
        strokes[request.sid].pop()

    emit('clear-board', broadcast=True)
    emit('draw-strokes', get_all_strokes(), broadcast=True)


@socketio.on('clear-board')
def clear_board():
    global strokes

    with strokes_lock:
        strokes.clear()

    stroke_keys = redis_client.keys('stroke:*')
    for key in stroke_keys:
        redis_client.delete(key)    
    emit('clear-board', broadcast=True, include_self=False)


@socketio.on('save-drawing')
def save_drawing(data):
    pass


if __name__ == '__main__':
    print("Server running with Redis backend.")
    socketio.run(app, host='0.0.0.0', debug=True)
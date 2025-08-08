from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route('/ping')
def ping():
    return "Pong!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

def start_web_server_thread():
    thread = threading.Thread(target=run_web_server)
    thread.daemon = True
    thread.start()

if __name__ == '__main__':
    run_web_server()

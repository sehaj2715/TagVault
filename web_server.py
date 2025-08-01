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
    # Start the Flask app in a separate thread
    # This allows the main bot script to continue running
    thread = threading.Thread(target=run_web_server)
    thread.daemon = True  # Daemonize thread so it exits when the main program exits
    thread.start()

if __name__ == '__main__':
    # This block is for testing the web server independently
    run_web_server()

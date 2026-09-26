from led_web_v7 import create_app


app, socketio = create_app()


if __name__ == "__main__":
    socketio.run(
        app,
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=False,
        allow_unsafe_werkzeug=True,
    )

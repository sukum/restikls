from restikls import create_app

# create_app function is defined in app/__init__.py
app = create_app()

if __name__ == '__main__':
    # You can specify host, port, debug mode here
    # For development, you often run with FLASK_APP and flask run
    # but this is useful for direct execution or Gunicorn/Waitress setup
    app.run(debug=False)

from AppOpener import open, close

def open_application(app_name):
    try:
        open(app_name, match_closest=True)
    except Exception as e:
        print(f"failed to open {app_name}: {e}")

def close_application(app_name):
    try:
        close(app_name, match_closest=True)
    except Exception as e:
        print(f"Failed to close {app_name}: {e}")


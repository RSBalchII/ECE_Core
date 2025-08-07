"""
This module provides GUI automation functionalities using the pyautogui library.
"""
import pyautogui
import os

def get_screen_resolution() -> dict:
    """
    Gets and returns the screen resolution.

    Returns:
        A dictionary with 'status' and 'result' keys.
    """
    try:
        width, height = pyautogui.size()
        return {'status': 'success', 'result': f"Screen resolution is {width}x{height}."}
    except Exception as e:
        return {'status': 'error', 'result': str(e)}

def move_mouse_to(x: int, y: int, duration: float = 0.5) -> dict:
    """
    Moves the mouse cursor to the specified X and Y coordinates.

    Args:
        x: The x-coordinate.
        y: The y-coordinate.
        duration: The duration of the mouse movement in seconds.

    Returns:
        A dictionary with 'status' and 'result' keys.
    """
    try:
        pyautogui.moveTo(x, y, duration=duration)
        return {'status': 'success', 'result': f"Mouse moved to ({x}, {y})."}
    except Exception as e:
        return {'status': 'error', 'result': str(e)}

def mouse_click(button: str = 'left') -> dict:
    """
    Performs a mouse click with the specified button.

    Args:
        button: The mouse button to click ('left', 'right', 'middle').

    Returns:
        A dictionary with 'status' and 'result' keys.
    """
    try:
        pyautogui.click(button=button)
        return {'status': 'success', 'result': f"{button.capitalize()} mouse button clicked."}
    except Exception as e:
        return {'status': 'error', 'result': str(e)}

def type_text(text: str, interval: float = 0.1) -> dict:
    """
    Types out the given string of text.

    Args:
        text: The text to type.
        interval: The interval between each keystroke.

    Returns:
        A dictionary with 'status' and 'result' keys.
    """
    try:
        pyautogui.write(text, interval=interval)
        return {'status': 'success', 'result': "Typed the specified text."}
    except Exception as e:
        return {'status': 'error', 'result': str(e)}

def take_screenshot(filepath: str) -> dict:
    """
    Takes a screenshot of the entire screen and saves it to the specified filepath.

    Args:
        filepath: The path to save the screenshot.

    Returns:
        A dictionary with 'status' and 'result' keys.
    """
    try:
        # Ensure the directory exists
        directory = os.path.dirname(filepath)
        if not os.path.exists(directory):
            os.makedirs(directory)

        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)
        return {'status': 'success', 'result': f"Screenshot saved to {filepath}"}
    except Exception as e:
        return {'status': 'error', 'result': str(e)}

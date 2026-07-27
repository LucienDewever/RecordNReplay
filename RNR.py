# Python package imports
from pynput import mouse, keyboard
import time
import datetime
from json import dump, load
import argparse

# Custom file imports
from targetWindow import pick_window, activate_window, engage_cursor_capture
from gamemouse import RawMouseRecorder
import relmouseTest


events = []
start_time = None
replay_type = "OS"
raw_recorder = None  # only instantiated for GAME-mode recording

# Parser for commandline, public to reduce parameters passed to functions later, but this can be changed
parser = argparse.ArgumentParser(
        description="cmd line arg parser for RecordNReplay."
    )

####################
# Config Functions #
####################

def print_help_and_exit():
    parser.print_help()
    exit()

# Process possible conflicts and oddities between args
# Im sure there is a way to do this natively with argparse, but I dont want to read the docs right now
def process_args(args):
    if args.operation == "record" and args.source:
        print("\t\n\033[33m*** Cannot specify a source file for recording, only a destination ***\033[0m -- exiting\n")
        print_help_and_exit()

    elif args.operation == "replay" and args.destination:
        print("\t\n\033[33m*** Cannot specify a destination file for replay, only a source ***\033[0m -- exiting\n")
        print_help_and_exit()

########## END CONFIG FUNCTIONS ##########

###########################
# Event Record Functions #
###########################

def on_move(x, y):
    # OS mode only. Absolute cursor position is ok here since we're
    # not driving a relative camera. Absolute coordinates are fine.
    events.append({'type': 'move', 'x': x, 'y': y, 'time': time.time() - start_time})


def on_raw_delta(dx, dy):
    # GAME mode. These deltas come straight from (WM_INPUT), not the OS cursor position, so they aren't clamped
    # at screen edges and represent relative motion
    events.append({'type': 'move_relative', 'dx': dx, 'dy': dy, 'time': time.time() - start_time})


def on_click(x, y, button, pressed):
    events.append({'type': 'click', 'x': x, 'y': y, 'button': str(button), 'pressed': pressed, 'time': time.time() - start_time})


def on_press(key):
    # Stop recording if ESC is pressed, before logging event to file
    if key == keyboard.Key.esc:
        return False

    events.append({'type': 'press', 'key': str(key), 'time': time.time() - start_time})


def on_release(key):
    events.append({'type': 'release', 'key': str(key), 'time': time.time() - start_time})


########## END RECORD FUNCTIONS ##########


##########################
# Event Replay Functions #
##########################

def replay_move(mouse_controller, event):
    mouse_controller.position = (event['x'], event['y'])


def replay_move_relative(event):
    # Recorded events are the relative deltas captured from WM_INPUT
    relmouseTest.moveRel(event['dx'], event['dy'])


def replay_click(mouse_controller, event):
    button = mouse.Button[event['button'].split('.')[1]]
    if event['pressed']:
        mouse_controller.press(button)

    else:
        mouse_controller.release(button)


def replay_press(keyboard_controller, event):
    try:
        if('.' in event['key']):
            key = keyboard.Key[event['key'].split('.')[1]]

        else:
            key = event['key'].replace("'", "")

    except KeyError:
        key = event['key'].replace("'", "")

    print(f"Pressing key: {key}")
    keyboard_controller.press(key)


def replay_release(keyboard_controller, event):
    try:
        if('.' in event['key']):
            key = keyboard.Key[event['key'].split('.')[1]]

        else:
            key = event['key'].replace("'", "")

    except KeyError:
        key = event['key'].replace("'", "")

    print(f"Releasing key: {key}")
    keyboard_controller.release(key)
    
########## END REPLAY FUNCTIONS ##########


############################
# Main Operation Functions #
############################

def record(filename):
    global raw_recorder

    # In GAME mode, mouse motion is captured via RawMouseRecorder instead
    # so no need to register on_move with the mouse listener
    mouse_listener_kwargs = {'on_click': on_click}
    if replay_type == "OS":
        mouse_listener_kwargs['on_move'] = on_move

    mouse_listener = mouse.Listener(**mouse_listener_kwargs)
    keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)

    mouse_listener.start()

    if replay_type == "GAME":
        raw_recorder = RawMouseRecorder(on_delta=on_raw_delta)
        raw_recorder.start()

    keyboard_listener.start()

    print("Recording started. Press ESC to stop...")
    keyboard_listener.join()

    mouse_listener.stop()
    if raw_recorder is not None:
        raw_recorder.stop()

    # Save recorded events to a file
    with open(filename, 'w') as f:
        dump(events, f)
    print(f"Recording saved to {filename}")


def replay(filename):
    try:
        with open(filename, 'r') as f:
            loaded_events = load(f)
    except FileNotFoundError:
        print(f"File {filename} not found.")
        return

    mouse_controller = mouse.Controller()
    keyboard_controller = keyboard.Controller()

    for event in loaded_events:
        # Wait for the exact time the event occurred
        while time.time() - start_time < event['time']:
            time.sleep(0.01)

        print(f"Replaying event: {event}")

        if event['type'] == 'move':
            replay_move(mouse_controller, event)

        elif event['type'] == 'move_relative':
            replay_move_relative(event)

        elif event['type'] == 'click':
            replay_click(mouse_controller, event)

        elif event['type'] == 'press':
            replay_press(keyboard_controller, event)

        elif event['type'] == 'release':
            replay_release(keyboard_controller, event)


if __name__ == "__main__":

## Add arguments to parser ##
    parser.add_argument(
            "operation", 
            type=str, 
            choices=["record", "replay"], 
            help="Script Operation to perform [record|replay]"
        )

    parser.add_argument(
            "type", 
            type=str, 
            choices=["OS", "GAME"], 
            help="Platform of operation [OS|GAME]"
        )

    parser.add_argument(
        "-w", "--window", 
        action="store_true",
        help="allows user to choose a target window in OS mode, this is typically not necessary"
    )

    parser.add_argument(
        "-d", "--destination", 
        type=str, 
        help="destination file to record to"
    )

    parser.add_argument(
        "-s", "--source", 
        type=str,  
        help="source file to replay from"
    )

    # Get value for arguments from commandline
    args = parser.parse_args()

    # Process arguments for conflicts etc
    process_args(args)

    # Do record operations
    if args.operation == "record":
        print(f"Recording Type: |{args.type}|")
        start_time = time.time()

        if args.destination:
            record(args.destination + ".json")

        else:
            name = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            record(name + ".json")

    # Do replay operations
    elif args.operation == "replay":
        print(f"Replaying Type: |{args.type}|")
        if args.source:
            name = args.source
        else:
            name = "macro.json"

        # Replay is by far more complex, so lets be safe and wrap in a dedicated try/except
        try:
            if args.window or args.type == "GAME":
                hwnd = pick_window() # Pick target window

                if hwnd:
                    activate_window(hwnd)
                    time.sleep(.5) # Sleep helps OS achieve focus on the desired window before starting replay

                    if args.type == "GAME":
                        # Only games/raw-input targets need a click-in, in order to lock focus;
                        engage_cursor_capture(hwnd)
                        time.sleep(.5) # Sleep helps ensure click is registered before starting replay

        except Exception as e:
            print(f"Error: {e}")

        # Record current time to keep replay events in step with recording
        start_time = time.time()
        replay(name)

    else:
        # Blanket catch, even through argparse should catch this. Still good practice to cap with an else
        print("Usage: python RNR.py [record|replay]")
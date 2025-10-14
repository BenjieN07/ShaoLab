# File: opticool_server.py
# This script must be run on the Windows PC connected to the OptiCool instrument.
#
# Pre-requisites:
# 1. MultiPyVu module and its dependencies (pywin32, pandas, pillow, pyyaml) must be installed 
#    in the Python environment (Python >= 3.8).

import MultiPyVu as mpv
import sys
import logging
import argparse
import time # <-- Standard Python 'time' module imported here

# Configure logging to see server activity
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Default hostname/IP is '0.0.0.0' (listens on all interfaces) and default port is 5000.
HOST = '0.0.0.0'
PORT = 5001 
PLATFORM = 'opticool' # Used only for the '--scaffold' flag

def run_server(scaffolding=False):
    """Initializes and runs the MultiPyVu Server for the OptiCool platform."""
    
    server_flags = []
    if scaffolding:
        # Set flags to enable Scaffolding Mode and specify the platform for the simulator
        # This is where the platform name is correctly passed when simulating.
        server_flags = ['-s', PLATFORM]
        logging.info("--- RUNNING IN SCAFFOLDING (SIMULATION) MODE ---")
        logging.info("This mode does NOT require MultiVu or OptiCool hardware.")
    else:
        logging.info(f"Starting MultiPyVu Server for platform: {PLATFORM} (Requires MultiVu)")

    logging.info(f"Listening on {HOST}:{PORT}.")

    try:
        # We now correctly initialize the server using the fixed arguments
        with mpv.Server(host=HOST, port=PORT, flags=server_flags) as server:
            # The server runs indefinitely until manually stopped (Ctrl+C)
            logging.info("Server is now running. Press Ctrl+C to stop.")
            while True:
                # Use standard 'time.sleep'
                time.sleep(1)

    except mpv.MultiPyVuError as e:
        logging.error(f"MultiPyVu Initialization Error: {e}")
        if not scaffolding:
            # Enhanced error message for when the server fails to connect to MultiVu (the "not connected" scenario)
            logging.error("-" * 50)
            logging.error("FATAL: Could not connect to the MultiVu software.")
            logging.error("ACTION REQUIRED: Ensure MultiVu is running on this PC.")
            logging.error(f"If you are testing without hardware, run this script with: python {sys.argv[0]} --scaffold")
            logging.error("-" * 50)
        else:
            logging.error("Check environment and MultiPyVu installation.")
        sys.exit(1) # Exit immediately on critical error
    except KeyboardInterrupt:
        logging.info("Server stopped by user (Ctrl+C).")
    except Exception as e:
        # Catch any other unexpected exceptions and log them
        logging.critical(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Start the MultiPyVu Server for OptiCool.")
    parser.add_argument('--scaffold', action='store_true', 
                        help='Run the server in simulation (scaffolding) mode for testing.')
    args = parser.parse_args()
    
    run_server(scaffolding=args.scaffold)

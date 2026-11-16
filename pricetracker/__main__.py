import argparse
import uvicorn


def main():
    ap = argparse.ArgumentParser(description="Prices Tracker – live price search")
    ap.add_argument("--host", default="127.0.0.1", help="bind address (default: local only)")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    print(f"\n  Prices Tracker → http://{a.host}:{a.port}\n")
    uvicorn.run("pricetracker.server:app", host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()

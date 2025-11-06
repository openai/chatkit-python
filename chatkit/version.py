import importlib.metadata

try:
    __version__ = importlib.metadata.version("openai-chatkit")
except importlib.metadata.PackageNotFoundError:
    # Fallback if running from source without being installed
    __version__ = "0.0.0"
